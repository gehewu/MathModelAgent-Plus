"""视觉模型服务，供代码解释器对生成的图片做质量评估反馈。

核心作用：Coder 画完图后，把图片 base64 发给视觉模型，返回「内容描述 +
质量问题 + 改进建议」的结构化反馈，再回传给 CoderAgent 迭代重绘——
解决"代码手看不到自己画的图"这一结构性问题。

配置：.env.dev 中设置 VISION_ENABLED=true 及 VISION_API_KEY/MODEL/BASE_URL 后生效；
未配置时自动降级，解释器保持"图片已生成，未展示"的原有行为。
"""

import asyncio
import re

from openai import AsyncOpenAI

from app.config.setting import settings
from app.utils.log_util import logger

# 视觉模型调用超时（秒）：避免视觉 API 慢/挂起拖住整条任务
_VISION_CALL_TIMEOUT = 30

# 重绘评分阈值：反馈中评分 < 该值则触发重绘
_VISION_RETRY_SCORE = 7

_VISION_PROMPT = """你是一名科研图表质量审查专家。分析这张图，按[内容][评分][问题][建议]四段输出：
[内容] 坐标轴含义、数据趋势、关键特征（2-3句）
[评分] 按维度打分，格式"评分：7/10"（0-10整数）：
   - 坐标轴：标签清晰含单位、刻度合理不重叠
   - 图例：清晰、无遮挡、位置合理
   - 数据可读性：数据点/柱条/线条可分辨、标签可读
   - 配色：统一美观、对比度足、避免刺眼红绿灯配色
   - 清晰度：不模糊、分辨率足、文字不重叠
   - 整体：无残图（缺轴/缺标签/图案不完整）、无文字遮挡、留白得当
[问题] 指出上述维度的具体缺陷；无则写"无"
[建议] 2-3条可执行改进（如"x轴标签重叠，加长figsize"）；合格写"可接受"
注意：轻微瑕疵不影响阅读给7分以上并标"可接受"，不过度要求重绘；明显残图或不可读给6分以下。"""

# 一致性核对段：仅在拿到代码手自述（图片元数据卡）时追加。
# 目的：让视觉模型把「代码手声称这张图画了什么」与「图中实际呈现」对照，
# 抓出画质合格但内容说错/串图的问题（纯质量审查抓不到）。
_CONSISTENCY_PROMPT = """
额外要求——增加第5段[一致性]，对照下方「代码手自述」逐条核对：
{expected}
核对：
  - 图表类型是否一致（自述"散点图+回归线"，实为柱状图 → 不一致）
  - 数据来源/变量是否与坐标轴、图例吻合（自述 x 轴为月份，实为类别名 → 不一致）
  - 核心结论是否被图支持（自述"逐年上升"，曲线下降 → 不一致）
[一致性] 输出"一致" / "不一致：<冲突点>" / "无法核对"（自述缺失或图中信息不足）。
**硬性要求：判定"不一致"时[评分]不得超过 5/10**——内容与自述矛盾比画质瑕疵更严重。"""


class VisionService:
    """基于 OpenAI 兼容接口的图片质量评估服务。"""

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    @property
    def enabled(self) -> bool:
        """是否启用：需同时开启 VISION_ENABLED 且配置了 key 与模型。"""
        return bool(
            settings.VISION_ENABLED
            and settings.VISION_API_KEY
            and settings.VISION_MODEL
        )

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.VISION_API_KEY,
                base_url=settings.VISION_BASE_URL or "https://api.siliconflow.cn/v1",
            )
        return self._client

    async def analyze_image(
        self,
        base64_data: str,
        mime: str = "image/png",
        context: str = "",
        expected: str = "",
    ) -> str:
        """评估一张图片，返回结构化反馈文本。

        Args:
            base64_data: 图片的 base64 编码字符串。
            mime: 图片 MIME 类型（image/png / image/jpeg）。
            context: 可选的绘图代码片段/子任务名，帮助模型理解图。
            expected: 代码手对该图的自述（图片元数据卡关键字段）。非空时
                额外要求视觉模型核对「自述 vs 图中实际」是否一致并输出[一致性]段。

        Returns:
            视觉模型的评估文本。

        Raises:
            RuntimeError: 视觉模型未启用时抛出。
        """
        if not self.enabled:
            raise RuntimeError("视觉模型未启用：请配置 VISION_ENABLED=true 及 VISION_*")
        # 类型窄化：enabled 已保证 VISION_MODEL 非空
        model = settings.VISION_MODEL
        assert model is not None, "VISION_MODEL 未配置"

        # 去掉可能已带的前缀
        if "," in base64_data and base64_data.split(",")[0].startswith("data:"):
            base64_data = base64_data.split(",", 1)[1]

        prompt = _VISION_PROMPT
        # 有自述才追加一致性核对（无自述时退化为纯质量审查，不误判）
        if expected:
            prompt += _CONSISTENCY_PROMPT.format(expected=expected[:400])
        if context:
            prompt += f"\n生成该图的上下文（子任务/代码片段）：{context[:500]}"

        try:
            response = await asyncio.wait_for(
                self._get_client().chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{base64_data}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=settings.VISION_MAX_TOKENS or 600,
                ),
                timeout=_VISION_CALL_TIMEOUT,
            )
            content = response.choices[0].message.content or ""
            logger.info(f"视觉模型评估完成，反馈 {len(content)} 字")
            return content
        except Exception as e:
            logger.error(f"视觉模型调用失败: {e}")
            raise RuntimeError(f"视觉模型调用失败: {e}") from e

    @staticmethod
    def _parse_score(feedback: str) -> int | None:
        """从反馈中解析"X/10"格式的评分。

        Args:
            feedback: 视觉模型返回的评估文本。

        Returns:
            0-10 的整数评分；解析失败返回 None。
        """
        m = re.search(r"(\d{1,2})\s*/\s*10", feedback)
        if m:
            score = int(m.group(1))
            if 0 <= score <= 10:
                return score
        return None

    @staticmethod
    def should_retry(feedback: str) -> bool:
        """根据视觉反馈判断是否需要重绘。

        判定优先级：
        1. 反馈判定「不一致」（图与代码手自述矛盾）-> 直接重绘，不看清分；
        2. 反馈中含"X/10"评分 -> 低于阈值 _VISION_RETRY_SCORE 即重绘；
        3. 无评分或解析失败 -> 回退到关键词判断（"可接受"短路 + 残图关键词）。
        """
        if not feedback:
            return False

        # 1. 一致性硬门控：图与自述矛盾比画质瑕疵更严重，不受评分影响。
        #    注意"不一致"包含"一致"，故必须先判"不一致"；"无法核对"不算失败。
        if "不一致" in feedback:
            return True

        # 2. 优先用评分门控
        score = VisionService._parse_score(feedback)
        if score is not None:
            return score < _VISION_RETRY_SCORE

        # 3. 关键词兜底
        if "可接受" in feedback:
            return False
        markers = [
            "残图",
            "无刻度",
            "缺轴",
            "被截断",
            "重叠",
            "无法阅读",
            "不可读",
            "遮挡",
            "模糊",
            "分辨率不足",
            "无图例",
        ]
        return any(m in feedback for m in markers)
