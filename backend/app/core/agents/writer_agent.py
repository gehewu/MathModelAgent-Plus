"""写作手 Agent 模块，负责基于建模结果撰写学术论文。"""

import asyncio
from app.core.agents.agent import Agent
from app.core.llm.llm import LLM
from app.core.prompts import get_writer_prompt
from app.schemas.enums import CompTemplate, FormatOutPut
from app.config.setting import ApiType
from app.tools.openalex_scholar import OpenAlexScholar
from app.utils.log_util import logger
from app.services.redis_manager import redis_manager
from app.schemas.response import SystemMessage, WriterMessage
import json
from app.core.functions import writer_tools, writer_tools_anthropic
from app.schemas.A2A import WriterResponse


# TODO: 并行 parallel
# TODO: 获取当前文件下的文件
# TODO: 引用cites tool

# 单次 search_papers 整体超时（秒）：防网络黑洞拖死整个写作环节。
# 超过则本次跳过检索、继续写作，不让文献检索阻塞整篇论文生成。
_SEARCH_CALL_TIMEOUT = 25


class WriterAgent(Agent):
    """写作手 Agent，基于建模和代码执行结果撰写竞赛论文。"""
    def __init__(
        self,
        task_id: str,
        model: LLM,
        comp_template: CompTemplate = CompTemplate.CHINA,
        format_output: FormatOutPut = FormatOutPut.Markdown,
        scholar: OpenAlexScholar | None = None,
        context_window: int = 128000,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        super().__init__(task_id, model, context_window, cancel_event=cancel_event)
        self.format_out_put = format_output
        self.comp_template = comp_template
        self.scholar = scholar
        self.is_first_run = True
        self.system_prompt = get_writer_prompt(format_output)
        self.available_images: list[str] = []

    async def run(  # type: ignore[reportIncompatibleMethodOverride]
        self,
        prompt: str,
        available_images: list[str] | None = None,
        sub_title: str | None = None,
    ) -> WriterResponse:
        """
        执行写作任务
        Args:
            prompt: 写作提示
            available_images: 可用的图片相对路径列表（如 20250420-173744-9f87792c/编号_分布.png）
            sub_title: 子任务标题
        """
        logger.info(f"subtitle是:{sub_title}")

        # 根据 api_type 选择 tools 格式
        api_type = self.model.api_type
        tools = writer_tools_anthropic if api_type == ApiType.ANTHROPIC else writer_tools

        if self.is_first_run:
            self.is_first_run = False
            await self.append_chat_history(
                {"role": "system", "content": self.system_prompt}
            )

        if available_images:
            self.available_images = available_images
            image_lines = "\n".join(
                [f"- ![{img}]({img})" for img in available_images]
            )
            image_prompt = (
                f"\n\n【必须插入的图片列表】\n"
                f"以下图片是代码手生成的，你必须在论文相关段落后用 Markdown 格式逐一插入：\n"
                f"{image_lines}\n"
                f"插入格式为独占一行的 ![描述](文件名)，每张图片后需配3行以上的分析解读。\n"
            )
            logger.info(f"image_prompt是:{image_prompt}")
            prompt = prompt + image_prompt

        logger.info(f"{self.__class__.__name__}:开始:执行对话")

        await self.append_chat_history({"role": "user", "content": prompt})

        # 获取历史消息用于本次对话
        response = await self._chat(
            history=self.chat_history,
            tools=tools,
            tool_choice="auto",
            agent_name=self.__class__.__name__,
            sub_title=sub_title,
        )

        footnotes = []
        response_content: str = ""

        # 允许写作手多次调用 search_papers（综述/参考文献常需分主题多次检索）。
        # 用循环处理直至模型不再请求工具；设置上限，避免死循环。
        search_count = 0
        MAX_SEARCHES = 5
        while response.tool_calls:
            tool_call = response.tool_calls[0]
            if tool_call.name != "search_papers":
                logger.warning(f"写作手调用未知工具: {tool_call.name}，终止本轮检索")
                break
            if search_count >= MAX_SEARCHES:
                logger.warning(f"search_papers 调用超过 {MAX_SEARCHES} 次，停止检索")
                break
            search_count += 1

            tool_id = tool_call.id
            logger.info(f"调用工具: search_papers 第{search_count}次")
            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=f"写作手调用{tool_call.name}工具"),
            )

            query = json.loads(tool_call.arguments)["query"]
            await redis_manager.publish_message(
                self.task_id,
                WriterMessage(content=query),
            )

            # 更新对话历史 - 添加助手的响应（含 tool_calls）
            assistant_msg: dict = {"role": "assistant", "content": response.content}
            if response.reasoning_content:
                assistant_msg["reasoning_content"] = response.reasoning_content
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in response.tool_calls
            ]
            await self.append_chat_history(assistant_msg)

            try:
                assert self.scholar is not None, "scholar 未初始化"
                # 单次检索加整体超时保护：即使 openalex 内部超时设计失效，这里也能
                # 在 25s 内强制降级，避免网络黑洞拖住整个写作流程。
                papers = await asyncio.wait_for(
                    self.scholar.search_papers(query),
                    timeout=_SEARCH_CALL_TIMEOUT,
                )
            except Exception as e:
                # 网络不通/超时：不中断任务，降级跳过本次检索，让写作手继续写。
                # 写作手收到空结果会自行处理（综述无文献、参考文献基于常识与理论）。
                error_msg = f"搜索文献失败/超时: {str(e)}"
                logger.warning(error_msg)
                await redis_manager.publish_message(
                    self.task_id,
                    SystemMessage(
                        content=f"[文献检索] 网络不可达跳过（{type(e).__name__}），写作手将不使用文献继续撰写",
                        type="warning",
                    ),
                )
                papers = []
            # TODO: pass to frontend
            papers_str = self.scholar.papers_to_str(papers)
            logger.info(f"搜索文献结果\n{papers_str}")
            await self.append_chat_history(
                {
                    "role": "tool",
                    "content": papers_str,
                    "tool_call_id": tool_id,
                    "name": "search_papers",
                }
            )
            response = await self._chat(
                history=self.chat_history,
                tools=tools,
                tool_choice="auto",
                agent_name=self.__class__.__name__,
                sub_title=sub_title,
            )

        # 循环结束后，response 无 tool_calls，取其最终文本
        response_content = response.content or ""
        assistant_final: dict = {"role": "assistant", "content": response_content}
        if response.reasoning_content:
            assistant_final["reasoning_content"] = response.reasoning_content
        self.chat_history.append(assistant_final)
        logger.info(f"{self.__class__.__name__}:完成:执行对话")
        return WriterResponse(response_content=response_content, footnotes=footnotes)

    async def summarize(self) -> str:
        """总结对话内容，生成任务执行摘要。"""
        try:
            await self.append_chat_history(
                {"role": "user", "content": "请简单总结以上完成什么任务取得什么结果:"}
            )
            # 获取历史消息用于本次对话
            response = await self._chat(
                history=self.chat_history, agent_name=self.__class__.__name__
            )
            response_content = response.content or ""
            summary_msg: dict = {"role": "assistant", "content": response_content}
            if response.reasoning_content:
                summary_msg["reasoning_content"] = response.reasoning_content
            await self.append_chat_history(summary_msg)
            return response_content
        except Exception as e:
            logger.error(f"总结生成失败: {str(e)}")
            # 返回一个基础总结，避免完全失败
            return "由于网络原因无法生成详细总结，但已完成主要任务处理。"
