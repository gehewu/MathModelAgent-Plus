"""本地代码解释器模块，通过本地 Jupyter 内核执行 Python 代码。"""

from app.tools.base_interpreter import BaseCodeInterpreter
from app.tools.matplotlib_setup import build_matplotlib_init_code
from app.tools.notebook_serializer import NotebookSerializer
import asyncio
import jupyter_client
from app.utils.log_util import logger
import os
from app.services.redis_manager import redis_manager
from app.config.setting import settings
from app.schemas.response import (
    OutputItem,
    ResultModel,
    StdErrModel,
    SystemMessage,
)

# 长档超时（计算密集型）的慢算法特征：命中任一特征即用长档，避免模型忘加
# `# [EXEC_TYPE: COMPUTE]` 标记而被短档掐死。快代码走短档，计算的自动升长档。
_COMPUTE_HEAVY_PATTERNS = (
    "GridSearchCV",
    "RandomizedSearchCV",
    "iterrows",
    "itertuples",
    "differential_evolution",
    "genetic",
    "模拟退火",
    "np.linalg.norm",
)


def _is_compute_heavy(code: str) -> bool:
    """判断代码是否属计算密集型，决定用长档还是短档超时。

    显式标记 `# [EXEC_TYPE: COMPUTE]` 命中即长档；否则按慢算法特征 + 多重循环
    启发式识别。快代码误判为长档无实际代价（超时是上界不是下限，快代码照样秒回），
    但慢代码漏判会被短档掐死且无法补救，故宁可多判。

    Args:
        code: 待执行的代码字符串。

    Returns:
        True 表示计算密集型，应用长档超时。
    """
    if "[EXEC_TYPE: COMPUTE]" in code:
        return True
    if any(p in code for p in _COMPUTE_HEAVY_PATTERNS):
        return True
    # 多重循环（两层及以上且有缩进内层）→ 大概率计算密集
    if code.count("for ") >= 2 and "    for " in code:
        return True
    return False


class LocalCodeInterpreter(BaseCodeInterpreter):
    """基于本地 Jupyter 内核的代码解释器。"""

    def __init__(
        self,
        task_id: str,
        work_dir: str,
        notebook_serializer: NotebookSerializer,
    ):
        super().__init__(task_id, work_dir, notebook_serializer)
        self.km, self.kc = None, None
        self.interrupt_signal = False

    async def initialize(self):
        # 本地内核一般不需异步上传文件，直接切换目录即可
        # 初始化 Jupyter 内核管理器和客户端
        logger.info("初始化本地内核")
        # 设置 UTF-8 编码环境，避免 Windows 中文环境下 GBK 编码导致的乱码问题
        kernel_env = os.environ.copy()
        kernel_env["PYTHONIOENCODING"] = "utf-8"
        kernel_env["PYTHONUTF8"] = "1"
        self.km, self.kc = jupyter_client.manager.start_new_kernel(
            kernel_name="python3", env=kernel_env
        )
        font_msg, font_type = self._pre_execute_code()
        if font_msg:
            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(content=font_msg, type=font_type),
            )

    def _pre_execute_code(self) -> tuple[str | None, str]:
        """执行 matplotlib 初始化，并解析字体加载结果供前端展示。

        Returns:
            (消息文案, SystemMessage.type)；无可用信息时文案为 None。
        """
        init_code = build_matplotlib_init_code(self.work_dir)
        execution = self.execute_code_(init_code)
        stdout = "\n".join(text for mark, text in execution if mark == "stdout")
        for line in stdout.splitlines():
            line = line.strip()
            if "中文字体已加载" in line:
                # 去掉日志前缀，前端只展示关键结论
                content = line.removeprefix("[matplotlib_setup] ").strip()
                return content, "success"
            if "未找到中文字体" in line:
                content = line.removeprefix("[matplotlib_setup] ").strip()
                return content, "warning"
        return None, "info"

    async def execute_code(self, code: str) -> tuple[str, bool, str]:
        logger.info(f"执行代码: {code}")
        #  添加代码到notebook
        self.notebook_serializer.add_code_cell_to_notebook(code)

        text_to_gpt: list[str] = []
        content_to_display: list[OutputItem] | None = []
        error_occurred: bool = False
        error_message: str = ""

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="开始执行代码"),
        )
        # 执行前图片快照：用于执行后检测新增/变化的图（savefig 场景视觉评估兜底）
        before_images = self._snapshot_image_hashes()
        # 执行 Python 代码
        logger.info("开始在本地执行代码...")
        # 超时分档：命中慢算法特征或显式 `# [EXEC_TYPE: COMPUTE]` 标记 → 长档（计算密集型），否则短档。
        # 用 _is_compute_heavy 自动识别，避免模型忘加标记被短档掐死；快代码误判长档无实际代价。
        # execute_code_ 是同步忙等，放到线程跑 + wait_for 限时，超时后重启内核并上报超时信号，
        # 供 CoderAgent 进入反思/优化流程，避免高耗时算法（如蒙特卡洛）无限卡死任务。
        timeout = (
            settings.EXEC_TIMEOUT_COMPUTE
            if _is_compute_heavy(code)
            else settings.EXEC_TIMEOUT_NORMAL
        )
        try:
            execution = await asyncio.wait_for(
                asyncio.to_thread(self.execute_code_, code),
                timeout=timeout,
            )
            logger.info("代码执行完成，开始处理结果...")
        except asyncio.TimeoutError:
            logger.warning(f"代码执行超时（>{timeout}s），已中断")
            # 重启内核：SIGINT 对原生/编译计算（numba/BLAS/scipy C 例程）停不掉，会继续空转烧 CPU，
            # 且下次反思重跑会排队在卡死内核后面。重启=杀旧进程换新进程，是唯一能清掉卡死计算的办法。
            # 重启只丢内核内存变量，不影响工作目录文件；优化代码本就独立从磁盘重载数据。
            try:
                if self.km is not None:
                    self.restart_jupyter_kernel()
            except Exception as ke:
                logger.warning(f"重启内核失败，退化为仅中断: {ke}")
                try:
                    if self.km is not None:
                        self.km.interrupt_kernel()
                except Exception:
                    pass
            await redis_manager.publish_message(
                self.task_id,
                SystemMessage(
                    content=(
                        f"代码执行超时（>{timeout}s），已中断。"
                        "请进入反思模式：分析复杂度、优化算法、降低规模或改用更简单模型。"
                    ),
                    type="warning",
                ),
            )
            return (
                f"[EXEC_TIMEOUT] 代码执行超过 {timeout}s 被中断。"
                "请立即反思并优化（见 CODER_PROMPT 的『执行超时反思流程』）："
                "定位瓶颈行、分析时间复杂度、给出优化方案（向量化/降采样/换算法），"
                "并输出结构化反思 JSON。",
                True,
                "EXEC_TIMEOUT",
            )

        await redis_manager.publish_message(
            self.task_id,
            SystemMessage(content="代码执行完成"),
        )

        # 未截断的原始 stdout：供视觉审查解析图片元数据卡（截断可能切掉卡片）
        raw_stdout: list[str] = []
        for mark, out_str in execution:
            if mark in ("stdout", "execute_result_text", "display_text"):
                raw_stdout.append(out_str)
                text_to_gpt.append(self._truncate_text(f"[{mark}]\n{out_str}"))
                #  添加text到notebook
                content_to_display.append(
                    ResultModel(res_type="result", format="text", msg=out_str)
                )
                self.notebook_serializer.add_code_cell_output_to_notebook(out_str)

            elif mark in (
                "execute_result_png",
                "execute_result_jpeg",
                "display_png",
                "display_jpeg",
            ):
                mime = "image/png" if "png" in mark else "image/jpeg"
                # 视觉模型质量评估反馈（启用时；失败则降级为不展示）
                feedback = ""
                if self.vision.enabled:
                    try:
                        feedback = await self.vision.analyze_image(out_str, mime=mime)
                    except Exception as e:
                        logger.warning(f"视觉评估失败，降级为不展示: {e}")
                if feedback:
                    self._append_vision_feedback(text_to_gpt, f"{mark} 图片", feedback)
                else:
                    text_to_gpt.append(f"[{mark} 图片已生成，内容为 base64，未展示]")

                #  添加image到notebook
                if "png" in mark:
                    self.notebook_serializer.add_image_to_notebook(out_str, "image/png")
                    content_to_display.append(
                        ResultModel(res_type="result", format="png", msg=out_str)
                    )
                else:
                    self.notebook_serializer.add_image_to_notebook(
                        out_str, "image/jpeg"
                    )
                    content_to_display.append(
                        ResultModel(res_type="result", format="jpeg", msg=out_str)
                    )

            elif mark == "error":
                error_occurred = True
                error_message = self.delete_color_control_char(out_str)
                error_message = self._truncate_text(error_message)
                logger.error(f"执行错误: {error_message}")
                text_to_gpt.append(error_message)
                #  添加error到notebook
                self.notebook_serializer.add_code_cell_error_to_notebook(out_str)
                content_to_display.append(StdErrModel(msg=out_str))

        logger.info(f"text_to_gpt: {text_to_gpt}")

        # 文件层视觉评估：覆盖 plt.savefig+plt.close 保存的图（iopub 不产生图片输出）
        await self._assess_new_images(before_images, text_to_gpt, raw_stdout)

        combined_text = "\n".join(text_to_gpt)

        await self._push_to_websocket(content_to_display)

        return (
            combined_text,
            error_occurred,
            error_message,
        )

    def execute_code_(self, code) -> list[tuple[str, str]]:
        assert self.kc is not None
        assert self.km is not None
        self.kc.execute(code)
        logger.info(f"执行代码: {code}")
        # Get the output of the code
        msg_list = []
        while True:
            try:
                iopub_msg = self.kc.get_iopub_msg(timeout=1)
                msg_list.append(iopub_msg)
                if (
                    iopub_msg["msg_type"] == "status"
                    and iopub_msg["content"].get("execution_state") == "idle"
                ):
                    break
            except Exception:
                if self.interrupt_signal:
                    self.km.interrupt_kernel()
                    self.interrupt_signal = False
                continue

        all_output: list[tuple[str, str]] = []
        for iopub_msg in msg_list:
            if iopub_msg["msg_type"] == "stream":
                if iopub_msg["content"].get("name") == "stdout":
                    output = iopub_msg["content"]["text"]
                    all_output.append(("stdout", output))
            elif iopub_msg["msg_type"] == "execute_result":
                if "data" in iopub_msg["content"]:
                    if "text/plain" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["text/plain"]
                        all_output.append(("execute_result_text", output))
                    if "text/html" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["text/html"]
                        all_output.append(("execute_result_html", output))
                    if "image/png" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["image/png"]
                        all_output.append(("execute_result_png", output))
                    if "image/jpeg" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["image/jpeg"]
                        all_output.append(("execute_result_jpeg", output))
            elif iopub_msg["msg_type"] == "display_data":
                if "data" in iopub_msg["content"]:
                    if "text/plain" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["text/plain"]
                        all_output.append(("display_text", output))
                    if "text/html" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["text/html"]
                        all_output.append(("display_html", output))
                    if "image/png" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["image/png"]
                        all_output.append(("display_png", output))
                    if "image/jpeg" in iopub_msg["content"]["data"]:
                        output = iopub_msg["content"]["data"]["image/jpeg"]
                        all_output.append(("display_jpeg", output))
            elif iopub_msg["msg_type"] == "error":
                # TODO: 正确返回格式
                if "traceback" in iopub_msg["content"]:
                    output = "\n".join(iopub_msg["content"]["traceback"])
                    cleaned_output = self.delete_color_control_char(output)
                    all_output.append(("error", cleaned_output))
        return all_output

    async def get_created_images(self, section: str) -> list[str]:
        """获取新创建的图片列表（递归扫描子目录，覆盖 figures/ 等大模型自建目录）"""
        current_images = set(self._list_images())

        # 计算新增的图片（按相对路径，如 figures/xxx.png）
        new_images = current_images - self.last_created_images

        # 更新last_created_images为当前的图片集合
        self.last_created_images = current_images

        logger.info(f"新创建的图片列表: {new_images}")
        return list(new_images)  # 最后转换为list返回

    async def cleanup(self):
        # 关闭内核
        assert self.kc is not None
        assert self.km is not None
        self.kc.shutdown()
        logger.info("关闭内核")
        self.km.shutdown_kernel()

    def send_interrupt_signal(self):
        self.interrupt_signal = True

    def restart_jupyter_kernel(self):
        """Restart the Jupyter kernel and recreate the work directory."""
        assert self.kc is not None
        self.kc.shutdown()
        # 设置 UTF-8 编码环境，避免 Windows 中文环境下 GBK 编码导致的乱码问题
        kernel_env = os.environ.copy()
        kernel_env["PYTHONIOENCODING"] = "utf-8"
        kernel_env["PYTHONUTF8"] = "1"
        self.km, self.kc = jupyter_client.manager.start_new_kernel(
            kernel_name="python3", env=kernel_env
        )
        self.interrupt_signal = False
        self._create_work_dir()
        self._pre_execute_code()

    def _create_work_dir(self):
        """Ensure the working directory exists after a restart."""
        os.makedirs(self.work_dir, exist_ok=True)
