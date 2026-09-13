"""代码解释器抽象基类模块。"""

import abc
import base64
import hashlib
import os
import re
from app.tools.notebook_serializer import NotebookSerializer
from app.tools.vision_service import VisionService
from app.services.redis_manager import redis_manager
from app.utils.log_util import logger
from app.schemas.response import (
    OutputItem,
    InterpreterMessage,
)

# 图片元数据卡：代码手 savefig 后按 CODER_PROMPT 要求 print 的【图片元数据】块。
# 解析出关键字段后作为"代码手自述"交给视觉模型核对图与描述是否一致。
_CARD_BLOCK_RE = re.compile(r"【图片元数据】(.*?)(?=【|\Z)", re.DOTALL)
_CARD_FIELD_RE = re.compile(r"(文件名|图表类型|数据来源|核心结论)\s*[:：]\s*([^\n]+)")
# 可被图片核实的关键字段；「文件名」用于匹配、「适用章节」图里看不出来，均不送审。
_CARD_CHECK_FIELDS = ("图表类型", "数据来源", "核心结论")


class BaseCodeInterpreter(abc.ABC):
    """代码解释器抽象基类，定义代码执行、输出管理和资源清理的接口。"""

    def __init__(
        self,
        task_id: str,
        work_dir: str,
        notebook_serializer: NotebookSerializer,
    ):
        self.task_id = task_id
        self.work_dir = work_dir
        self.notebook_serializer = notebook_serializer
        self.section_output: dict[str, dict[str, list[str]]] = {}
        self.last_created_images = set()
        # 视觉模型服务：画图后质量评估反馈（未配置时自动降级）
        self.vision = VisionService()

    @abc.abstractmethod
    async def initialize(self):
        """初始化解释器，必要时上传文件、启动内核等"""
        ...

    @abc.abstractmethod
    async def _pre_execute_code(self):
        """执行初始化代码"""
        ...

    @abc.abstractmethod
    async def execute_code(self, code: str) -> tuple[str, bool, str]:
        """执行一段代码，返回 (输出文本, 是否出错, 错误信息)"""
        ...

    @abc.abstractmethod
    async def cleanup(self):
        """清理资源，比如关闭沙箱或内核"""
        ...

    @abc.abstractmethod
    async def get_created_images(self, section: str) -> list[str]:
        """获取当前 section 创建的图片列表"""
        ...

    async def _push_to_websocket(self, content_to_display: list[OutputItem] | None):
        logger.info("执行结果已推送到WebSocket")

        agent_msg = InterpreterMessage(
            output=content_to_display,
        )
        logger.debug(f"发送消息: {agent_msg.model_dump_json()}")
        await redis_manager.publish_message(
            self.task_id,
            agent_msg,
        )

    def add_section(self, section_name: str) -> None:
        """确保添加的section结构正确"""

        if section_name not in self.section_output:
            self.section_output[section_name] = {"content": [], "images": []}

    def add_content(self, section: str, text: str) -> None:
        """向指定section添加文本内容"""
        self.add_section(section)
        self.section_output[section]["content"].append(text)

    def get_code_output(self, section: str) -> str:
        """获取指定section的代码输出"""
        return "\n".join(self.section_output[section]["content"])

    def delete_color_control_char(self, string):
        ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")
        return ansi_escape.sub("", string)

    def _truncate_text(self, text: str, max_length: int = 1000) -> str:
        """截断文本，保留开头和结尾的重要信息"""
        if len(text) <= max_length:
            return text

        half_length = max_length // 2
        return text[:half_length] + "\n... (内容已截断) ...\n" + text[-half_length:]

    def _append_vision_feedback(
        self, text_to_gpt: list[str], label: str, feedback: str
    ) -> None:
        """把视觉评估反馈追加进给主 LLM 的文本；判定需重绘时附加 REDRAW 标记。

        该标记由 CoderAgent 识别，用于触发强制重绘（而不只是依赖主 LLM 自觉）。
        """
        marker = "[REDRAW_REQUIRED] " if VisionService.should_retry(feedback) else ""
        text_to_gpt.append(f"[{label} 图片已生成，{marker}视觉模型评估：{feedback}]")

    def _list_images(self) -> list[str]:
        """递归扫描工作目录下所有图片文件，返回相对路径列表（含子目录）。

        大模型可能自建子目录（如 ``figures/``、``cleaned_data/``）存放图片，
        仅用 ``os.listdir`` 扫根目录会漏掉子目录里的图，导致视觉评估与图片登记
        双双失效。递归 ``os.walk`` 覆盖所有子目录；键为相对路径（如
        ``figures/xxx.png``），写作手按此相对路径引用图片。

        Returns:
            图片相对路径列表（``xxx.png`` 或 ``figures/xxx.png``）。
        """
        images: list[str] = []
        try:
            for root, _dirs, files in os.walk(self.work_dir):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                        rel = os.path.relpath(os.path.join(root, f), self.work_dir)
                        images.append(rel.replace(os.sep, "/"))
        except OSError as e:
            logger.warning(f"图片扫描失败: {e}")
        return images

    def _snapshot_image_hashes(self) -> dict[str, str]:
        """递归扫描工作目录图片文件，返回 {相对路径: md5}。

        用于检测一次代码执行后新增/内容变化的图片——figure_guide 引导的
        ``plt.savefig + plt.close`` 不会产生 iopub 图片输出，视觉评估（依赖
        display_data）在此场景下无法触发，需从文件层面兜底覆盖。递归子目录以
        覆盖大模型自建 ``figures/`` 等目录存放的图片。
        """
        snaps: dict[str, str] = {}
        for rel in self._list_images():
            fp = os.path.join(self.work_dir, rel)
            try:
                with open(fp, "rb") as fh:
                    snaps[rel] = hashlib.md5(fh.read()).hexdigest()
            except OSError as e:
                logger.warning(f"图片快照失败 {rel}: {e}")
        return snaps

    @staticmethod
    def _extract_image_cards(texts: list[str]) -> dict[str, str]:
        """解析代码手输出的【图片元数据】卡，返回 {图片文件名小写: 关键字段自述}。

        仅保留可被图片核实的关键字段（图表类型/数据来源/核心结论），供视觉模型
        核对「自述 vs 图中实际」。文件名用于与扫描到的图片文件匹配；未写卡片或
        字段缺失时该图为空字符串，视觉审查退化为纯质量评估。

        Args:
            texts: 待解析的文本片段（应传未截断的原始 stdout）。

        Returns:
            图片文件名（小写 basename）到自述文本的映射。
        """
        cards: dict[str, str] = {}
        blob = "\n".join(texts)
        for block in _CARD_BLOCK_RE.findall(blob):
            fields = {k: v.strip() for k, v in _CARD_FIELD_RE.findall(block)}
            fname = fields.get("文件名", "")
            if not fname:
                continue
            parts = [
                f"{k}：{fields[k]}"
                for k in _CARD_CHECK_FIELDS
                if fields.get(k)
            ]
            if parts:
                key = os.path.basename(fname).strip().lower()
                cards[key] = "；".join(parts)
        return cards

    async def _assess_new_images(
        self,
        before: dict[str, str],
        text_to_gpt: list[str],
        raw_texts: list[str] | None = None,
    ) -> None:
        """对执行前后新增/内容变化的图片文件做视觉质量评估，反馈追加进 text_to_gpt。

        Args:
            before: 执行前 ``_snapshot_image_hashes`` 的快照。
            text_to_gpt: 回传给主 LLM 的输出文本列表（就地追加反馈）。
            raw_texts: 未截断的原始 stdout（用于解析图片元数据卡）；为 None 时
                回退用 text_to_gpt（e2b 分支本就未截断，可直接复用）。
        """
        if not self.vision.enabled:
            return
        cards = self._extract_image_cards(
            raw_texts if raw_texts is not None else text_to_gpt
        )
        after = self._snapshot_image_hashes()
        for rel, digest in after.items():
            if before.get(rel) != digest:
                fp = os.path.join(self.work_dir, rel)
                try:
                    with open(fp, "rb") as fh:
                        b64 = base64.b64encode(fh.read()).decode("ascii")
                    mime = (
                        "image/png" if rel.lower().endswith(".png") else "image/jpeg"
                    )
                    # 按文件名匹配代码手自述，交给视觉模型做一致性核对
                    expected = cards.get(os.path.basename(rel).lower(), "")
                    feedback = await self.vision.analyze_image(
                        b64, mime=mime, context=rel, expected=expected
                    )
                    if feedback:
                        self._append_vision_feedback(text_to_gpt, rel, feedback)
                except Exception as e:
                    logger.warning(f"图片文件视觉评估失败 {rel}: {e}")
