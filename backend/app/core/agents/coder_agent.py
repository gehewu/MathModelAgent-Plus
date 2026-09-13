"""代码手 Agent 模块，负责生成和执行 Python 代码完成建模任务。"""

import asyncio
from app.core.agents.agent import Agent
from app.config.setting import settings, ApiType
from app.utils.log_util import logger
from app.services.redis_manager import redis_manager
from app.schemas.response import SystemMessage, InterpreterMessage
from app.tools.base_interpreter import BaseCodeInterpreter
from app.core.llm.llm import LLM
from app.schemas.A2A import CoderToWriter
from app.core.prompts import CODER_PROMPT
from app.utils.common_utils import get_current_files
import json
from app.core.prompts import get_reflection_prompt, match_cases, format_cases
from app.core.functions import (
    coder_tools,
    coder_tools_anthropic,
    web_search_tools,
    web_search_tools_anthropic,
)
from app.tools.web_search import WebSearchTool

# TODO: 时间等待过久，stop 进程
# TODO: 支持 cuda
# TODO: 引入创新方案：


class CoderAgent(Agent):
    """代码手 Agent，通过 LLM 生成代码并在解释器中执行，支持错误反思和重试。"""

    def __init__(
        self,
        task_id: str,
        model: LLM,
        work_dir: str,  # 工作目录
        max_chat_turns: int
        | None = settings.MAX_CHAT_TURNS,  # 最大聊天次数，None表示无限制
        max_retries: int | None = settings.MAX_RETRIES,  # 最大反思次数，None表示无限制
        code_interpreter: BaseCodeInterpreter | None = None,
        context_window: int = 128000,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        super().__init__(task_id, model, context_window, cancel_event=cancel_event)
        self.work_dir = work_dir
        self.max_chat_turns = max_chat_turns
        self.current_chat_turns = 0
        self.max_retries = max_retries
        self.redraw_rounds = 0  # 视觉审查触发的强制重绘轮次（单子任务）
        # 建模方案不可行回流信号：代码手在 print 中输出固定标记时捕获反馈文本，
        # 由 workflow 读取后触发建模手修订该子任务方案（None 表示方案可行，无需回流）
        self.scheme_feedback: str | None = None
        # 执行超时反思计数：单子任务内代码执行触发超时的次数，超过上限则强制终极妥协
        self.exec_timeout_count = 0
        self.is_first_run = True
        self.system_prompt = CODER_PROMPT
        self.code_interpreter = code_interpreter
        self.web_search = WebSearchTool()
        # 当前子任务执行过的代码片段（供写作手引用实现细节）
        self.current_code_snippets: list[str] = []

    async def run(self, prompt: str, subtask_title: str) -> CoderToWriter:  # type: ignore[reportIncompatibleMethodOverride]
        """执行代码手子任务，生成并运行代码。

        Args:
            prompt: 子任务描述。
            subtask_title: 子任务标题，用于分段输出。

        Returns:
            CoderToWriter 对象，包含代码执行结果和生成的图片列表。
        """
        logger.info(f"{self.__class__.__name__}:开始:执行子任务: {subtask_title}")
        assert self.code_interpreter is not None, "code_interpreter 未初始化"
        self.code_interpreter.add_section(subtask_title)
        # 重置当前子任务的代码采集
        self.current_code_snippets = []
        self.redraw_rounds = 0
        self.scheme_feedback = None  # 每次子任务开始清空上轮返回不可行的滞留信号
        self.exec_timeout_count = 0  # 每次子任务开始清空执行超时计数

        # 根据 api_type 选择 tools 格式；Web Search 启用时追加搜索工具
        api_type = self.model.api_type
        base_tools = (
            coder_tools_anthropic if api_type == ApiType.ANTHROPIC else coder_tools
        )
        tools = base_tools
        if self.web_search.enabled:
            tools = base_tools + (
                web_search_tools_anthropic
                if api_type == ApiType.ANTHROPIC
                else web_search_tools
            )

        # 如果是第一次运行，则添加系统提示
        if self.is_first_run:
            logger.info("首次运行，添加系统提示和数据集文件信息")
            self.is_first_run = False
            await self.append_chat_history(
                {"role": "system", "content": self.system_prompt}
            )
            # 当前数据集文件 + 绘图规范提示
            current_files = get_current_files(self.work_dir, "data")
            # 按文件类型分组，提示 Agent 区别对待
            csv_xlsx = [f for f in current_files if f.endswith((".csv", ".xlsx"))]
            pdf_docx = [f for f in current_files if f.endswith((".pdf", ".docx"))]
            files_desc = f"数据文件: {csv_xlsx}" if csv_xlsx else "数据文件: 无"
            if pdf_docx:
                files_desc += f"\n题目/参考文档: {pdf_docx}"

            pdf_docx_hint = ""
            if pdf_docx:
                pdf_docx_hint = (
                    "\n\n**检测到 PDF/DOCX 文档，请先读取其内容再进行后续分析：**\n"
                    "- PDF 文件：`import fitz; doc = fitz.open(fname); text = "
                    '"\\n".join(page.get_text() for page in doc)`\n'
                    "- DOCX 文件：`from docx import Document; doc = Document(fname); "
                    'text = "\\n".join(p.text for p in doc.paragraphs)`\n'
                    "读取后，提取其中的题目描述、数据表格、约束条件等关键信息，"
                    "再进行后续数据处理和建模。若文档中含表格，可结合 `fitz` 的 "
                    "`page.get_tables()` 或 `pandas.read_html()` 提取。"
                )

            await self.append_chat_history(
                {
                    "role": "user",
                    "content": f"当前文件夹下的数据集文件{files_desc}\n\n"
                    "工作目录下有 figure_guide.md（科研绘图规范）。需要画图时，"
                    "必须先读取该文件并严格遵循其中的配色方案、防残图铁律、图表类型选择和标注规范。"
                    f"{pdf_docx_hint}",
                }
            )

        # 添加 sub_task
        logger.info(f"添加子任务提示: {prompt}")
        await self.append_chat_history({"role": "user", "content": prompt})

        retry_count = 0
        last_error_message = ""

        while True:
            if self.max_retries is not None and retry_count >= self.max_retries:
                logger.error(f"超过最大尝试次数: {self.max_retries}")
                await redis_manager.publish_message(
                    self.task_id,
                    SystemMessage(content="超过最大尝试次数", type="error"),
                )
                logger.warning(
                    f"任务失败，超过最大尝试次数{self.max_retries}, 最后错误信息: {last_error_message}"
                )
                # 重试耗尽：若错误信息含不可行标记，转为回流信号返回给建模手
                if not self.scheme_feedback:
                    self.scheme_feedback = self._extract_scheme_feedback(
                        last_error_message
                    )
                return CoderToWriter(
                    code_response=f"任务失败，超过最大尝试次数{self.max_retries}, 最后错误信息: {last_error_message}",
                    created_images=[],
                    code_snippets=self.current_code_snippets,
                    scheme_feedback=self.scheme_feedback,
                )

            if (
                self.max_chat_turns is not None
                and self.current_chat_turns >= self.max_chat_turns
            ):
                logger.error(f"超过最大聊天次数: {self.max_chat_turns}")
                await redis_manager.publish_message(
                    self.task_id,
                    SystemMessage(content="超过最大聊天次数", type="error"),
                )
                raise Exception(
                    f"Reached maximum number of chat turns ({self.max_chat_turns}). Task incomplete."
                )

            self.current_chat_turns += 1
            logger.info(f"当前对话轮次: {self.current_chat_turns}")

            try:
                response = await self._chat(
                    history=self.chat_history,
                    tools=tools,
                    tool_choice="auto",
                    agent_name=self.__class__.__name__,
                )

                # 如果有工具调用
                if response.tool_calls:
                    logger.info("检测到工具调用")
                    tool_call = response.tool_calls[0]
                    tool_id = tool_call.id

                    if tool_call.name == "execute_code":
                        logger.info(f"调用工具: {tool_call.name}")
                        await redis_manager.publish_message(
                            self.task_id,
                            SystemMessage(content=f"代码手调用{tool_call.name}工具"),
                        )

                        code = json.loads(tool_call.arguments)["code"]
                        self.current_code_snippets.append(code)

                        await redis_manager.publish_message(
                            self.task_id,
                            InterpreterMessage(
                                input={"code": code},
                            ),
                        )

                        # 更新对话历史 - 添加助手的响应
                        assistant_msg: dict = {
                            "role": "assistant",
                            "content": response.content,
                        }
                        if response.reasoning_content:
                            assistant_msg["reasoning_content"] = (
                                response.reasoning_content
                            )
                        if response.tool_calls:
                            assistant_msg["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": tc.arguments,
                                    },
                                }
                                for tc in response.tool_calls
                            ]
                        await self.append_chat_history(assistant_msg)

                        # 执行工具调用
                        logger.info("执行工具调用")
                        (
                            text_to_gpt,
                            error_occurred,
                            error_message,
                        ) = await self.code_interpreter.execute_code(code)

                        # 添加工具执行结果
                        if error_occurred:
                            # 即使发生错误也要添加tool响应
                            # 执行超时（error_message == "EXEC_TIMEOUT"）时，把完整的
                            # text_to_gpt（含超时反思指导）传给 LLM，而非简写 error_message。
                            is_exec_timeout = error_message == "EXEC_TIMEOUT"
                            await self.append_chat_history(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": "execute_code",
                                    "content": text_to_gpt if is_exec_timeout else error_message,
                                }
                            )

                            logger.warning(f"代码执行错误: {error_message}")
                            retry_count += 1
                            logger.info(
                                f"当前尝试次:{retry_count} / {self.max_retries}"
                            )
                            last_error_message = error_message

                            if is_exec_timeout:
                                # 执行超时：走「高耗时算法反思」流程 + 计数，超过上限强制终极妥协。
                                self.exec_timeout_count += 1
                                if self.exec_timeout_count >= 2:
                                    # 终极妥协：精度受限求解（保留模型结构+降计算量+报可计算误差）；
                                    # 实在不可信则诚实声明失败并触发建模手回流，严禁整体换成线性近似当答案。
                                    fallback_prompt = (
                                        "代码已多次执行超时（第 {c} 次）。请执行「精度受限求解」，"
                                        "在时限内给出可信结果，不要用线性近似强行套可能错误的数字：\n"
                                        "1. 保留原模型结构，只降计算量：\n"
                                        "   - 优化/规划：粗网格或粗步长 + 局部细化，或用带近似比保证的贪心/启发式（写明近似比）；\n"
                                        "   - 采样/仿真：分层降采样，并给出可计算的误差度量（标准差/置信区间/偏差）；\n"
                                        "   - 搜索/训练：贝叶斯或随机搜索（15-20 次），训练用分层降采样数据。\n"
                                        "2. 凡降采样/降精度/启发式，必须给出可计算的误差度量（置信区间/MAPE/与参照解偏差）"
                                        "并在注释与 print 中标注；拒绝只给点估计。\n"
                                        "3. 若仍无法得到可信结果，输出 [MODEL_SCHEME_INFEASIBLE]："
                                        "声明『该子问题未能在时限内求得可信解』，把耗时瓶颈与建议（换建模路径/改数据结构）"
                                        "写给建模手，不要编造精确数字。\n"
                                        "请直接输出精度受限版代码；如需更长执行时间，首行加 `# [EXEC_TYPE: COMPUTE]`。"
                                    ).format(c=self.exec_timeout_count)
                                    await redis_manager.publish_message(
                                        self.task_id,
                                        SystemMessage(
                                            content=(
                                                f"代码执行第 {self.exec_timeout_count} 次超时，"
                                                "已触发精度受限求解（保留模型+降计算量+报误差）"
                                            ),
                                            type="warning",
                                        ),
                                    )
                                    await self.append_chat_history(
                                        {"role": "user", "content": fallback_prompt}
                                    )
                                else:
                                    # 首次超时：按 CODER_PROMPT 反思流程做结构化诊断（复杂度/优化/落地）。
                                    # 按代码特征匹配相关优化案例，注入针对该瓶颈的 few-shot 优化示例与反思 JSON 示范。
                                    timeout_reflect_prompt = (
                                        "上次代码执行超时。请按 CODER_PROMPT 的『执行超时反思流程』"
                                        "做四步诊断（瓶颈定位→复杂度分析→优化方案→方案落地），"
                                        "并输出结构化反思 JSON（含 bottleneck/complexity/strategy/implementation/"
                                        "expected_speedup/round/fallback_needed）。"
                                        "优化后重新提交代码，可加 `# [EXEC_TYPE: COMPUTE]` 申请更长执行时间。"
                                    )
                                    matched_cases = match_cases(code)
                                    if matched_cases:
                                        timeout_reflect_prompt += (
                                            "\n\n参考以下针对你代码特征的优化示例（含反思 JSON 格式示范），"
                                            "仿照其深度做瓶颈诊断与优化，再提交优化后的代码：\n\n"
                                            + format_cases(matched_cases)
                                        )
                                    await redis_manager.publish_message(
                                        self.task_id,
                                        SystemMessage(
                                            content="代码执行超时，触发结构化反思与优化",
                                            type="warning",
                                        ),
                                    )
                                    await self.append_chat_history(
                                        {
                                            "role": "user",
                                            "content": timeout_reflect_prompt,
                                        }
                                    )
                            else:
                                # 普通错误：走原有错误反思。
                                reflection_prompt = get_reflection_prompt(
                                    error_message, code
                                )
                                await redis_manager.publish_message(
                                    self.task_id,
                                    SystemMessage(
                                        content="代码手反思纠正错误", type="error"
                                    ),
                                )
                                await self.append_chat_history(
                                    {"role": "user", "content": reflection_prompt}
                                )
                            continue
                        else:
                            # 成功执行的tool响应
                            await self.append_chat_history(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": "execute_code",
                                    "content": text_to_gpt,
                                }
                            )
                            # 视觉审查判定图表需重绘：注入指令强制重绘（带轮次上限，
                            # 不依赖主 LLM 自觉）；轮次用尽后交还给模型自行决定
                            if (
                                "[REDRAW_REQUIRED]" in text_to_gpt
                                and self.redraw_rounds < settings.MAX_REDRAW_ROUNDS
                            ):
                                self.redraw_rounds += 1
                                await redis_manager.publish_message(
                                    self.task_id,
                                    SystemMessage(
                                        content=(
                                            f"视觉审查判定图表需重绘"
                                            f"（第 {self.redraw_rounds}/{settings.MAX_REDRAW_ROUNDS} 次）"
                                        ),
                                        type="warning",
                                    ),
                                )
                                await self.append_chat_history(
                                    {
                                        "role": "user",
                                        "content": (
                                            "上一张图未通过视觉审查（质量不达标，或图内容与你的【图片元数据】自述不一致）。"
                                            "请阅读反馈中的[问题][建议]，必要时核对[一致性]指出的冲突点"
                                            "（如自述的图表类型/数据来源/核心结论与图中实际不符），"
                                            "重绘该图后再继续；不要直接结束当前子任务。"
                                        ),
                                    }
                                )
                                continue
                            # 成功执行后继续循环，等待下一步指令
                            continue
                    elif tool_call.name == "web_search":
                        logger.info(f"调用工具: {tool_call.name}")
                        query = json.loads(tool_call.arguments).get("query", "")

                        await redis_manager.publish_message(
                            self.task_id,
                            SystemMessage(content=f"代码手正在联网搜索：{query}"),
                        )

                        # 更新对话历史 - 添加助手的响应
                        assistant_msg: dict = {
                            "role": "assistant",
                            "content": response.content,
                        }
                        if response.reasoning_content:
                            assistant_msg["reasoning_content"] = (
                                response.reasoning_content
                            )
                        if response.tool_calls:
                            assistant_msg["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": tc.arguments,
                                    },
                                }
                                for tc in response.tool_calls
                            ]
                        await self.append_chat_history(assistant_msg)

                        try:
                            results = await self.web_search.search(query)
                            results_str = self.web_search.format_results(results)
                        except Exception as e:
                            logger.error(f"Web Search 失败: {e}")
                            results_str = f"搜索失败: {e}"

                        await self.append_chat_history(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "name": "web_search",
                                "content": results_str,
                            }
                        )
                        continue
                    else:
                        # 未知工具：返回反馈，避免模型循环调用未知工具
                        logger.warning(f"未知工具调用: {tool_call.name}")
                        await self.append_chat_history(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "name": tool_call.name,
                                "content": f"未知工具 {tool_call.name}，请仅使用已提供的工具",
                            }
                        )
                        continue
                else:
                    # 没有工具调用，表示任务完成
                    logger.info("没有工具调用，任务完成")
                    # 从模型最终输出中提取不可行回流标记（若存在），供 workflow 触发建模手修订
                    self.scheme_feedback = self._extract_scheme_feedback(
                        response.content or ""
                    )
                    return CoderToWriter(
                        code_response=response.content,
                        created_images=await self.code_interpreter.get_created_images(
                            subtask_title
                        ),
                        code_snippets=self.current_code_snippets,
                        scheme_feedback=self.scheme_feedback,
                    )

            except Exception as e:
                logger.error(f"执行过程中发生异常: {str(e)}")
                retry_count += 1
                last_error_message = str(e)
                continue
            logger.info(f"{self.__class__.__name__}:完成:执行子任务: {subtask_title}")

    @staticmethod
    def _extract_scheme_feedback(text: str) -> str | None:
        """从代码手输出文本中提取「建模方案不可行」回流标记的反馈内容。

        代码手在方案数学上不可满足（硬约束冲突/底层假设与数据矛盾）时，
        按 CODER_PROMPT 约定输出固定格式：
            [MODEL_SCHEME_INFEASIBLE]
            原因：<一句说明>
            建议：<给建模手的修订方向>
        此处正则提取该段并返回给 workflow，触发建模手修订该子问题方案。
        未检测到标记时返回 None（表示方案可行，无需回流）。

        Args:
            text: 代码手输出的文本（code_response 或错误信息）。

        Returns:
            提取到的不可行反馈文本；未检测到时返回 None。
        """
        marker = "[MODEL_SCHEME_INFEASIBLE]"
        idx = text.find(marker)
        if idx == -1:
            return None
        # 截取标记之后的段落，直到下一个空行/末尾
        tail = text[idx:]
        # 截到下一个连续空行或文件边界（一个段落）
        seg = tail.split("\n\n")[0].strip() if "\n\n" in tail else tail.strip()
        # 若截取的段落过短（只有标记本身无内容），退回整体
        if len(seg) <= len(marker) + 5:
            return tail.strip()
        return seg
