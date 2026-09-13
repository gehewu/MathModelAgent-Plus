"""文件管理路由模块，提供文件下载、列表和目录打开等接口。"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.tools.latex_compiler import compile_markdown_to_pdf, is_available
from app.utils.common_utils import (
    ensure_safe_task_id,
    get_current_files,
    get_work_dir,
)
from app.config.setting import settings
import os
import subprocess
from icecream import ic  # type: ignore[import-unresolved]
from fastapi import HTTPException

router = APIRouter()

# 论文可下载文件类型白名单：type -> (文件名, 下载文件名)
_PAPER_FILES = {
    "md": ("res.md", "res.md"),
    "docx": ("res.docx", "res.docx"),
    "pdf": ("res.pdf", "res.pdf"),
    "ipynb": ("notebook.ipynb", "notebook.ipynb"),
}


@router.get("/download_url")
async def get_download_url(task_id: str, filename: str):
    return {
        "download_url": f"{settings.SERVER_HOST}/static/{task_id}/{filename}"
    }


@router.get("/download_all_url")
async def get_download_all_url(task_id: str):
    return {
        "download_url": f"{settings.SERVER_HOST}/static/{task_id}/all.zip"
    }


@router.get("/paper/{task_id}")
async def get_paper(task_id: str):
    """获取任务论文（res.md 内容）及可下载文件清单。

    Args:
        task_id: 任务 ID。

    Returns:
        包含论文 Markdown 内容和可用文件类型列表的字典。
    """
    safe_task_id = ensure_safe_task_id(task_id)
    try:
        work_dir = get_work_dir(safe_task_id)
    except FileNotFoundError:
        return {"content": "", "available": []}

    md_path = os.path.join(work_dir, "res.md")
    content = ""
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

    available = [
        file_type
        for file_type, (filename, _) in _PAPER_FILES.items()
        if os.path.exists(os.path.join(work_dir, filename))
    ]
    return {"content": content, "available": available}


@router.post("/paper/{task_id}/compile")
async def compile_paper_pdf(task_id: str):
    """把论文 res.md 编译为 res.pdf（pandoc + xelatex）。

    Args:
        task_id: 任务 ID。

    Returns:
        {"success": bool, "message": str}。工具链不可用或编译失败时 success=False，
        message 为可读原因（不抛异常，避免前端拿到 500）。

    Raises:
        HTTPException: 任务工作目录不存在时抛出。
    """
    safe_task_id = ensure_safe_task_id(task_id)
    try:
        work_dir = get_work_dir(safe_task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="任务工作目录不存在")

    md_path = os.path.join(work_dir, "res.md")
    if not os.path.exists(md_path):
        return {"success": False, "message": "论文尚未生成（res.md 不存在）"}

    ok, reason = is_available()
    if not ok:
        return {"success": False, "message": f"无法生成 PDF：{reason}"}

    pdf_path = os.path.join(work_dir, "res.pdf")
    # 同步编译放线程执行，避免阻塞事件循环（首次编译可能数十秒）
    success, message = await asyncio.to_thread(
        compile_markdown_to_pdf, md_path, pdf_path, work_dir
    )
    return {"success": success, "message": message}


@router.get("/paper/{task_id}/download")
async def download_paper(task_id: str, file: str):
    """下载论文文件（res.md / res.docx / notebook.ipynb）。

    Args:
        task_id: 任务 ID。
        file: 文件类型（md / docx / ipynb），白名单校验。

    Returns:
        文件流。

    Raises:
        HTTPException: 文件类型非法或文件不存在时抛出。
    """
    safe_task_id = ensure_safe_task_id(task_id)
    if file not in _PAPER_FILES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file}")

    filename, download_name = _PAPER_FILES[file]
    try:
        work_dir = get_work_dir(safe_task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="任务工作目录不存在")
    file_path = os.path.join(work_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type="application/octet-stream",
    )


@router.get("/files")
async def get_files(task_id: str):
    work_dir = get_work_dir(task_id)
    files = get_current_files(work_dir, "all")
    file_all = []

    for i in files:
        file_type = i.split(".")[-1]
        file_all.append({"filename": i, "file_type": file_type})

    return file_all


@router.get("/open_folder")
async def open_folder(task_id: str):
    ic(task_id)
    # 打开工作目录
    work_dir = get_work_dir(task_id)

    # 打开工作目录
    if os.name == "nt":
        subprocess.run(["explorer", work_dir])
    elif os.name == "posix":
        subprocess.run(["open", work_dir])
    else:
        raise HTTPException(status_code=500, detail=f"不支持的操作系统: {os.name}")

    return {"message": "打开工作目录成功", "work_dir": work_dir}
