"""建模手 Agent 模块，负责分析问题并制定建模方案。"""

import asyncio
from app.core.agents.agent import Agent
from app.core.llm.llm import LLM
from app.core.prompts import MODELER_PROMPT, get_json_error_feedback
from app.schemas.A2A import CoordinatorToModeler, ModelerToCoder
from app.schemas.response import ModelerMessage
from app.services.redis_manager import redis_manager
from app.utils.log_util import logger
import json
import re
from icecream import ic  # type: ignore[import-unresolved]

MAX_JSON_RETRIES = 3


def repair_json(json_str: str) -> dict | None:
    """尝试修复 LLM 输出的格式错误的 JSON。

    常见问题：value 内含裸换行、未转义引号、末尾多逗号。
    修复策略：预处理裸换行 → 直接 parse → 修复引号 → 正则兜底提取。

    Args:
        json_str: 可能包含格式错误的 JSON 字符串。

    Returns:
        修复后的字典，无法修复时返回 None。
    """
    json_str = json_str.replace("```json", "").replace("```", "").strip()

    # 预处理：把 value 内的裸换行转成 \n（保留结构换行）。
    # 策略：匹配 ": "..." 区间，把其中的真实换行替换为 \n。
    def escape_newlines_in_values(match):
        value = match.group(1)
        # 把 value 内的真实换行转义
        value = value.replace("\n", "\\n").replace("\r", "")
        return f'"{match.group(0).split(":")[0]}": "{value}"'

    # 匹配 "key": "value"（value 可能跨多行）
    json_str = re.sub(
        r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*?)"(?=\s*[,}])',
        lambda m: f'"{m.group(1)}": "{m.group(2).replace(chr(10), "\\n").replace(chr(13), "")}"',
        json_str,
        flags=re.DOTALL,
    )

    # Try direct parse first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Fix unescaped quotes inside string values (原有逻辑保留)
    try:
        fixed = re.sub(
            r'(?<=: ")(.*?)(?=",\s*\n\s*"|"\s*\n\s*})',
            lambda m: m.group(0).replace('"', '\\"'),
            json_str,
            flags=re.DOTALL,
        )
        return json.loads(fixed)
    except (json.JSONDecodeError, re.error):
        pass

    # Extract key-value pairs with regex as last resort（现在能处理跨行 value）
    try:
        # 改进正则：匹配 value 内任意内容（已预处理换行为 \n）
        pattern = r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*?)"'
        matches = re.findall(pattern, json_str, re.DOTALL)
        if matches:
            return {k: v.replace('\\"', '"').replace("\\n", "\n") for k, v in matches}
    except re.error:
        pass

    return None


class ModelerAgent(Agent):
    """建模手 Agent，分析问题类型并制定建模方案、求解方法和可视化策略。"""

    def __init__(
        self,
        task_id: str,
        model: LLM,
        context_window: int = 128000,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        super().__init__(task_id, model, context_window, cancel_event=cancel_event)
        self.system_prompt = MODELER_PROMPT

    async def run(self, coordinator_to_modeler: CoordinatorToModeler) -> ModelerToCoder:  # type: ignore[reportIncompatibleMethodOverride]
        """根据协调者拆解的问题生成建模方案。

        Args:
            coordinator_to_modeler: 协调者传递的结构化问题信息。

        Returns:
            ModelerToCoder 对象，包含各问题的建模解决方案。
        """
        await self.append_chat_history(
            {"role": "system", "content": self.system_prompt}
        )
        await self.append_chat_history(
            {
                "role": "user",
                "content": json.dumps(coordinator_to_modeler.questions),
            }
        )

        attempt = 0
        while attempt < MAX_JSON_RETRIES:
            response = await self._chat(
                history=self.chat_history,
                agent_name=self.__class__.__name__,
            )

            json_str = response.content
            if not json_str:
                raise ValueError("返回的 JSON 字符串为空，请检查输入内容。")

            questions_solution = repair_json(json_str)
            if questions_solution:
                ic(questions_solution)
                # 前端「建模手册」用严格 JSON.parse 解析原样 content；弱模型输出的 JSON value
                # 可能含未转义换行/引号导致前端解析失败。这里把 repair 后的规范化 JSON 补发给前端，
                # 前端 latestModelerMessage 取最后一条即拿到合法 JSON（后端下游用的也是这份修复结果）。
                normalized = json.dumps(questions_solution, ensure_ascii=False)
                logger.info(
                    f"[ModelerAgent] 补发规范化建模手册 JSON，长度={len(normalized)} 字符"
                )
                await redis_manager.publish_message(
                    self.task_id,
                    ModelerMessage(content=normalized),
                )
                return ModelerToCoder(questions_solution=questions_solution)

            attempt += 1
            logger.warning(
                f"JSON 解析失败 (第{attempt}/{MAX_JSON_RETRIES}次)，请求模型重新生成"
            )
            # 获取具体解析错误位置（若有），用于针对性反馈
            cleaned = json_str.replace("```json", "").replace("```", "").strip()
            parse_err: json.JSONDecodeError | None = None
            try:
                json.loads(cleaned)
            except json.JSONDecodeError as e:
                parse_err = e
            retry_msg: dict = {"role": "assistant", "content": json_str}
            if response.reasoning_content:
                retry_msg["reasoning_content"] = response.reasoning_content
            await self.append_chat_history(retry_msg)
            await self.append_chat_history(
                {
                    "role": "user",
                    "content": get_json_error_feedback(cleaned, parse_err),
                }
            )

        raise ValueError("ModelerAgent JSON 解析重试次数耗尽")

    async def revise_question(
        self,
        key: str,
        original_card: str,
        coder_feedback: str,
    ) -> str:
        """根据代码手反馈修订单个子问题的建模方案卡片（代码手→建模手回流）。

        在代码手判定某子问题建模方案不可行并回传反馈后调用：把原方案卡片和
        不可行反馈一起交给建模手，令其在「修订模式」（见 MODELER_PROMPT 的
        「方案修订模式」段落）下只输出该子问题的修订后卡片，供 workflow
        replace_solution → rebuild_coder_prompt 重新驱动代码手。

        Args:
            key: 子问题键（如 ques1 / sensitivity_analysis）。
            original_card: 该子问题原建模方案卡片文本。
            coder_feedback: 代码手回传的不可行原因与修订建议。

        Returns:
            修订后的建模方案卡片文本。

        Raises:
            ValueError: JSON 解析重试次数耗尽或返回内容不含有效卡片时抛出。
        """
        revise_prompt = (
            "请修订以下建模方案，代码手反馈该方案不可行：\n"
            f"子问题键：{key}\n"
            f"该子问题原方案卡片：\n{original_card}\n\n"
            f"代码手反馈（不可行原因与建议）：\n{coder_feedback}\n\n"
            "请按「方案修订模式」规则，只输出修订后的『这一个子问题』的方案卡片。"
        )

        await self.append_chat_history({"role": "user", "content": revise_prompt})

        attempt = 0
        while attempt < MAX_JSON_RETRIES:
            response = await self._chat(
                history=self.chat_history,
                agent_name=self.__class__.__name__,
            )
            json_str = response.content
            if not json_str:
                raise ValueError("修订返回的 JSON 字符串为空，请检查输入内容。")

            parsed = repair_json(json_str)
            if parsed:
                # 取修订后的单个子问题卡片（key 可能被模型直接作为键或仅输出单卡片文本）
                new_card = parsed.get(key)
                if isinstance(new_card, str) and new_card.strip():
                    return new_card.strip()
                # 兼容：模型可能直接输出单卡片文本（无 key 包装），取第一个字符串值
                first_value = next(
                    (v for v in parsed.values() if isinstance(v, str) and v.strip()),
                    None,
                )
                if first_value:
                    return first_value.strip()

            attempt += 1
            logger.warning(
                f"修订 JSON 解析失败 (第{attempt}/{MAX_JSON_RETRIES}次)，请求模型重新生成"
            )
            cleaned = json_str.replace("```json", "").replace("```", "").strip()
            parse_err: json.JSONDecodeError | None = None
            try:
                json.loads(cleaned)
            except json.JSONDecodeError as e:
                parse_err = e
            retry_msg: dict = {"role": "assistant", "content": json_str}
            if response.reasoning_content:
                retry_msg["reasoning_content"] = response.reasoning_content
            await self.append_chat_history(retry_msg)
            await self.append_chat_history(
                {
                    "role": "user",
                    "content": get_json_error_feedback(cleaned, parse_err),
                }
            )

        raise ValueError(
            f"ModelerAgent 修订 {key} 的 JSON 解析重试次数耗尽，无法返回修订卡片"
        )
