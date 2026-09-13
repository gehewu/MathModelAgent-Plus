"""LaTeX 论文编译服务：把 Markdown 论文编译为 PDF。

写作手产出的是 Markdown（公式用 `$..$`/`$$..$$`，表格用 pipe 语法），
因此这里用 pandoc + xelatex 直接把 res.md 编译为 res.pdf，而不是拼接竞赛
LaTeX 模板。中文字体由 pick_cjk_font 自动探测，避免产出方框乱码。

未检测到工具链（pandoc / xelatex / 中文字体）时一律**优雅降级**：
返回 (False, 明确原因)，不抛异常，不影响论文正文产出。
"""

import os
import shutil
import subprocess

from app.config.setting import settings
from app.utils.log_util import logger

# 失败时回传的 stderr 截断长度（诊断用，避免日志/响应体过大）
_STDERR_TAIL = 2000

# 候选中文字体：按优先级探测，返回首个可用者（传给 xelatex 的 CJKmainfont）。
# Windows 用系统自带宋体/黑体/雅黑；Linux（含 Docker 的 fonts-noto-cjk）用 Noto/Fandol。
_WINDOWS_FONTS = [
    ("simsun.ttc", "SimSun"),
    ("simhei.ttf", "SimHei"),
    ("msyh.ttc", "Microsoft YaHei"),
]
_LINUX_FONTS = [
    ("NotoSerifCJK-Regular.ttc", "Noto Serif CJK SC"),
    ("NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),
    ("FandolSong-Regular.otf", "FandolSong"),
]


def pick_cjk_font() -> str | None:
    """探测可用的中文字体名（供 xelatex 的 CJKmainfont 使用）。

    Returns:
        可用的字体名；探测不到返回 None（调用方据此判定不可用，避免产出乱码 PDF）。
    """
    # 显式配置优先
    if settings.PDF_CJK_FONT:
        return settings.PDF_CJK_FONT

    if os.name == "nt":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for filename, font_name in _WINDOWS_FONTS:
            if os.path.exists(os.path.join(fonts_dir, filename)):
                return font_name
        return None

    # Linux / macOS：先按常见路径探测，再用 fontconfig 兜底
    candidates_dirs = [
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/truetype/arphic",
        "/usr/share/fonts",
        "/System/Library/Fonts",
    ]
    for filename, font_name in _LINUX_FONTS:
        for d in candidates_dirs:
            if os.path.exists(os.path.join(d, filename)):
                return font_name

    # fontconfig 兜底：查系统中任意一款中文字体
    try:
        out = subprocess.run(
            ["fc-list", ":lang=zh", "family"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        for line in out.splitlines():
            name = line.split(",")[0].strip()
            if name:
                logger.info(f"fontconfig 探测到中文字体: {name}")
                return name
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass
    return None


def _resolve_pandoc() -> str | None:
    """定位 pypandoc 内置的 pandoc 可执行文件路径。

    Windows 下 ``pypandoc.get_pandoc_path()`` 返回的路径不含 ``.exe`` 后缀
    （如 ``.../files/pandoc``），直接做存在性判断会误判为缺失，故这里补齐后缀。

    Returns:
        pandoc 可执行文件的绝对路径；不可用返回 None。
    """
    try:
        import pypandoc

        path = pypandoc.get_pandoc_path()
    except Exception:  # noqa: BLE001 - 任何导入/定位失败都视为不可用
        return None
    if not path:
        return None
    if os.path.exists(path):
        return path
    if os.path.exists(path + ".exe"):  # Windows
        return path + ".exe"
    return None


def is_available() -> tuple[bool, str]:
    """检测编译工具链是否就绪（pandoc 内置 + 系统 xelatex + 中文字体）。

    Returns:
        (是否可用, 原因说明)。不可用时原因为用户可读的提示。
    """
    if _resolve_pandoc() is None:
        return False, "未找到 pandoc 可执行文件（pypandoc 未正确安装）"

    if shutil.which("xelatex") is None:
        return False, "未检测到 xelatex（请安装 TeX 发行版，如 MiKTeX/TeX Live）"

    font = pick_cjk_font()
    if not font:
        return False, "未检测到中文字体（Windows 需宋体/黑体，Linux 需 Noto CJK）"

    return True, "工具链就绪"


def compile_markdown_to_pdf(
    md_path: str,
    pdf_path: str,
    work_dir: str,
    timeout: int | None = None,
) -> tuple[bool, str]:
    """用 pandoc + xelatex 把 Markdown 论文编译为 PDF。

    直接调用 pandoc 二进制（而非 pypandoc.convert_file），以便：
    1) 用 subprocess 超时硬性 kill，避免首次编译按需装包时无限挂起；
    2) 捕获 stderr 作为失败诊断。

    Args:
        md_path: 源 Markdown 文件绝对路径（通常为 res.md）。
        pdf_path: 目标 PDF 文件绝对路径（通常为 res.pdf）。
        work_dir: 工作目录，作为 cwd 使 `![](fig1.png)` 相对路径图片可解析。
        timeout: 编译超时（秒），默认取 settings.PDF_COMPILE_TIMEOUT。

    Returns:
        (是否成功, 说明)。失败时说明含原因或 stderr 尾部，便于前端展示。
    """
    ok, reason = is_available()
    if not ok:
        return False, f"无法生成 PDF：{reason}"
    if not os.path.exists(md_path):
        return False, f"论文源文件不存在: {os.path.basename(md_path)}"

    font = pick_cjk_font()
    # 字体在 is_available 中已校验非空，这里仅作类型窄化
    assert font is not None

    pandoc_path = _resolve_pandoc()
    assert pandoc_path is not None  # is_available 已校验
    if timeout is None:
        timeout = settings.PDF_COMPILE_TIMEOUT

    # 编译前删除旧 PDF，避免"本次编译失败但仍下载到上次的旧文件"
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError as e:
            logger.warning(f"删除旧 PDF 失败: {e}")

    cmd = [
        pandoc_path,
        os.path.basename(md_path),
        "-o",
        os.path.basename(pdf_path),
        "--pdf-engine=xelatex",
        "--standalone",
        "-f",
        "markdown+tex_math_dollars+pipe_tables",
        "-V",
        f"CJKmainfont={font}",
        "-V",
        "geometry:margin=2.5cm",
    ]

    logger.info(f"开始编译 PDF: {' '.join(cmd)} (cwd={work_dir})")
    try:
        result = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        msg = f"编译超时（>{timeout}s），已终止。首次编译可能需按需安装 LaTeX 宏包，请重试。"
        logger.warning(msg)
        return False, msg
    except OSError as e:
        msg = f"启动编译器失败: {e}"
        logger.error(msg)
        return False, msg

    if result.returncode != 0 or not os.path.exists(pdf_path):
        tail = (result.stderr or result.stdout or "")[-_STDERR_TAIL:]
        logger.error(f"PDF 编译失败(returncode={result.returncode}): {tail}")
        return False, f"编译失败（returncode={result.returncode}）：\n{tail}"

    size_kb = os.path.getsize(pdf_path) / 1024
    logger.info(f"PDF 编译完成: {pdf_path} ({size_kb:.0f} KB)")
    return True, f"编译成功，生成 {os.path.basename(pdf_path)}（{size_kb:.0f} KB）"
