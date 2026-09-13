"""工作流模块，编排多 Agent 协作完成数学建模任务。"""

import asyncio
import os
from app.core.agents import WriterAgent, CoderAgent, CoordinatorAgent, ModelerAgent
from app.schemas.request import Problem
from app.schemas.response import SystemMessage
from app.tools.openalex_scholar import OpenAlexScholar
from app.utils.log_util import logger
from app.utils.common_utils import create_work_dir, get_config_template
from app.models.user_output import UserOutput
from app.config.setting import settings
from app.tools.interpreter_factory import create_interpreter
from app.services.redis_manager import redis_manager
from app.tools.notebook_serializer import NotebookSerializer
from app.core.flows import Flows
from app.core.llm.llm_factory import LLMFactory


class WorkFlow:
    """工作流基类。"""

    def __init__(self):
        pass

    def execute(self) -> None:
        """执行工作流。"""
        # RichPrinter.workflow_start()
        # RichPrinter.workflow_end()
        pass


class MathModelWorkFlow(WorkFlow):
    """数学建模工作流，协调协调者、建模手、代码手和写作手完成完整建模任务。"""
    task_id: str  #
    work_dir: str  # worklow work dir
    ques_count: int = 0  # 问题数量
    questions: dict[str, str | int] = {}  # 问题
    cancel_event: asyncio.Event | None = None  # 取消信号

    async def _check_cancelled(self) -> None:
        """检查是否收到取消信号，若已取消则发布通知并抛出 CancelledError。"""
        if self.cancel_event and self.cancel_event.is_set():
            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content="任务已停止", type="warning"),
            )
            raise asyncio.CancelledError("任务被用户停止")

    async def execute(self, problem: Problem):  # type: ignore[reportIncompatibleMethodOverride]
        """执行数学建模工作流。

        Args:
            problem: 包含题目信息、模板配置等的 Problem 对象。
        """
        self.task_id = problem.task_id
        self.work_dir = create_work_dir(self.task_id)

        # 在创建 LLM 前预校验配置，避免进入 Agent 循环后才发现缺配置
        missing = []
        for name, model_val, key_val in [
            ("Coordinator", settings.COORDINATOR_MODEL, settings.COORDINATOR_API_KEY),
            ("Modeler", settings.MODELER_MODEL, settings.MODELER_API_KEY),
            ("Coder", settings.CODER_MODEL, settings.CODER_API_KEY),
            ("Writer", settings.WRITER_MODEL, settings.WRITER_API_KEY),
        ]:
            if not model_val or not str(model_val).strip():
                missing.append(f"{name} 模型 ID")
            if not key_val or not str(key_val).strip():
                missing.append(f"{name} API Key")
        if missing:
            raise ValueError(f"以下配置缺失，请先在设置中填写并保存：{', '.join(missing)}")

        llm_factory = LLMFactory(self.task_id)
        coordinator_llm, modeler_llm, coder_llm, writer_llm = llm_factory.get_all_llms()

        coordinator_agent = CoordinatorAgent(
            self.task_id, coordinator_llm,
            context_window=settings.COORDINATOR_CONTEXT_WINDOW,
            cancel_event=self.cancel_event,
        )

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="识别用户意图和拆解问题ing..."),
        )

        await self._check_cancelled()

        try:
            coordinator_response = await coordinator_agent.run(problem.ques_all)
            self.questions = coordinator_response.questions
            self.ques_count = coordinator_response.ques_count
        except Exception as e:
            #  非数学建模问题
            logger.error(f"CoordinatorAgent 执行失败: {e}")
            raise e

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="识别用户意图和拆解问题完成,任务转交给建模手"),
        )

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="建模手开始建模ing..."),
        )

        await self._check_cancelled()

        modeler_agent = ModelerAgent(
            self.task_id, modeler_llm,
            context_window=settings.MODELER_CONTEXT_WINDOW,
            cancel_event=self.cancel_event,
        )

        # 原文直通：协调手会压缩输入、可能丢弃用户在题目外提出的建模要求，
        # 故把用户原始文本一并交给建模手，作为用户要求的权威依据。
        modeler_response = await modeler_agent.run(
            coordinator_response, raw_ques=problem.ques_all
        )

        user_output = UserOutput(work_dir=self.work_dir, ques_count=self.ques_count)

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="正在创建代码沙盒环境"),
        )

        notebook_serializer = NotebookSerializer(work_dir=self.work_dir)
        code_interpreter = await create_interpreter(
            kind="local",
            task_id=self.task_id,
            work_dir=self.work_dir,
            notebook_serializer=notebook_serializer,
            timeout=3000,
        )
        
        assert settings.OPENALEX_EMAIL is not None, "OPENALEX_EMAIL 未配置"
        scholar = OpenAlexScholar(
            task_id=self.task_id,
            email=settings.OPENALEX_EMAIL,
            api_key=settings.OPENALEX_API_KEY,
        )

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="创建完成"),
        )

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="初始化代码手"),
        )

        # modeler_agent
        coder_agent = CoderAgent(
            task_id=problem.task_id,
            model=coder_llm,
            work_dir=self.work_dir,
            max_chat_turns=settings.MAX_CHAT_TURNS,
            max_retries=settings.MAX_RETRIES,
            code_interpreter=code_interpreter,
            context_window=settings.CODER_CONTEXT_WINDOW,
            cancel_event=self.cancel_event,
        )

        writer_agent = WriterAgent(
            task_id=problem.task_id,
            model=writer_llm,
            comp_template=problem.comp_template,
            format_output=problem.format_output,
            scholar=scholar,
            context_window=settings.WRITER_CONTEXT_WINDOW,
            cancel_event=self.cancel_event,
        )

        flows = Flows(self.questions)
        # 将建模手方案注入流程配置，供写作手逐节引用（方法/算法介绍素材）
        flows.set_modeler_solution(modeler_response.questions_solution)

        ################################################ solution steps
        solution_flows = flows.get_solution_flows(self.questions, modeler_response)
        config_template = get_config_template(problem.comp_template)

        for key, value in solution_flows.items():
            await self._check_cancelled()

            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=f"代码手开始求解{key}"),
            )

            coder_response = await coder_agent.run(
                prompt=value["coder_prompt"], subtask_title=key
            )

            # 分层回流（代码手→建模手）：代码手判定本子问题方案不可行且未超上限时，
            # 触发建模手修订该子问题方案，用修订方案重建 coder_prompt 重新求解。
            scheme_revise_rounds = 0
            while (
                coder_response.scheme_feedback
                and scheme_revise_rounds < settings.MAX_SCHEME_REVISE_ROUNDS
            ):
                scheme_revise_rounds += 1
                await redis_manager.publish_message(
                    self.task_id,
                    SystemMessage(
                        content=(
                            f"代码手判定{key}方案不可行，触发建模手修订"
                            f"（第 {scheme_revise_rounds}/{settings.MAX_SCHEME_REVISE_ROUNDS} 次）"
                        ),
                        type="warning",
                    ),
                )
                revised_card = await modeler_agent.revise_question(
                    key=key,
                    original_card=modeler_response.questions_solution.get(key, ""),
                    coder_feedback=coder_response.scheme_feedback,
                )
                flows.replace_solution(key, revised_card)
                rebuilt_prompt = flows.rebuild_coder_prompt(key)
                coder_response = await coder_agent.run(
                    prompt=rebuilt_prompt, subtask_title=key
                )

            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=f"代码手求解成功{key}", type="success"),
            )

            writer_prompt = flows.get_writer_prompt(
                key,
                coder_response.code_response or "",
                code_interpreter,
                config_template,
                # 使用回流修订后的方案（未修订时即原始方案）
                modeler_solution=flows.modeler_solution.get(key, ""),
                code_snippets=coder_response.code_snippets,
            )

            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=f"论文手开始写{key}部分"),
            )

            ## TODO: 图片引用错误
            writer_response = await writer_agent.run(
                writer_prompt,
                available_images=coder_response.created_images,
                sub_title=key,
            )

            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=f"论文手完成{key}部分"),
            )

            user_output.set_res(key, writer_response)

        # 关闭沙盒

        await code_interpreter.cleanup()
        logger.info(user_output.get_res())

        ################################################ write steps

        write_flows = flows.get_write_flows(
            user_output, config_template, problem.ques_all
        )
        for key, value in write_flows.items():
            await self._check_cancelled()

            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=f"论文手开始写{key}部分"),
            )

            writer_response = await writer_agent.run(prompt=value, sub_title=key)

            user_output.set_res(key, writer_response)

        logger.info(user_output.get_res())

        user_output.save_result()

        # 可选：任务完成后自动编译论文 PDF。PDF 是附加产物，编译失败只告警、不中断任务。
        if settings.PDF_AUTO_COMPILE:
            from app.tools.latex_compiler import compile_markdown_to_pdf

            md_path = os.path.join(self.work_dir, "res.md")
            pdf_path = os.path.join(self.work_dir, "res.pdf")
            ok, msg = await asyncio.to_thread(
                compile_markdown_to_pdf, md_path, pdf_path, self.work_dir
            )
            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(
                    content=(
                        "论文 PDF 编译完成"
                        if ok
                        else f"论文 PDF 编译未成功：{msg}"
                    ),
                    type="success" if ok else "warning",
                ),
            )
