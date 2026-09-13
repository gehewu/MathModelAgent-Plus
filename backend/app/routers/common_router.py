"""通用路由模块，提供配置查询、消息获取和健康检查等接口。"""

import datetime
import json
from pathlib import Path

from aiofile import async_open
from fastapi import APIRouter, HTTPException
from app.config.setting import settings
from app.utils.common_utils import (
    TASK_ID_PATTERN,
    ensure_safe_task_id,
    get_config_template,
)
from app.schemas.enums import CompTemplate
from app.services.redis_manager import redis_manager
from app.utils.log_util import logger

router = APIRouter()


def _require_safe_task_id(task_id: str) -> str:
    """验证并返回安全的任务 ID。

    Args:
        task_id: 待验证的任务 ID。

    Returns:
        验证通过的任务 ID。

    Raises:
        HTTPException: 任务 ID 非法时返回 400。
    """
    try:
        return ensure_safe_task_id(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法任务ID") from exc


async def _load_task_messages_from_file(task_id: str) -> list[dict]:
    """从文件加载指定任务的历史消息。

    Args:
        task_id: 任务 ID。

    Returns:
        消息列表，文件不存在时返回空列表。
    """
    safe_task_id = _require_safe_task_id(task_id)
    message_file = Path("logs/messages") / f"{safe_task_id}.json"
    if not message_file.exists():
        return []

    try:
        async with async_open(message_file, "r", encoding="utf-8") as f:
            content = await f.read()
            data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"读取任务消息文件失败: {str(e)}")
        return []


@router.get("/")
async def root():
    return {"message": "Hello World"}


@router.get("/config")
async def config():
    return {
        "environment": settings.ENV,
        "deepseek_model": settings.DEEPSEEK_MODEL,
        "deepseek_base_url": settings.DEEPSEEK_BASE_URL,
        "max_chat_turns": settings.MAX_CHAT_TURNS,
        "max_retries": settings.MAX_RETRIES,
        "CORS_ALLOW_ORIGINS": settings.CORS_ALLOW_ORIGINS,
    }


@router.get("/writer_seque")
async def get_writer_seque():
    # 返回论文顺序
    config_template: dict = get_config_template(CompTemplate.CHINA)
    return list(config_template.keys())


@router.get("/messages")
async def get_task_messages(task_id: str):
    return await _load_task_messages_from_file(task_id)


@router.get("/tasks")
async def list_tasks():
    """列出所有历史任务（按工作目录最后修改时间倒序）。

    Returns:
        任务列表，每项包含 task_id、创建时间（目录 mtime）和是否已生成论文。
    """
    work_dir_root = Path("project/work_dir")
    if not work_dir_root.is_dir():
        return {"tasks": []}

    tasks = []
    for entry in work_dir_root.iterdir():
        if not entry.is_dir():
            continue
        task_id = entry.name
        # 只保留符合任务 ID 格式的目录，避免混入其他文件
        if not TASK_ID_PATTERN.fullmatch(task_id):
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        tasks.append(
            {
                "task_id": task_id,
                "created_at": datetime.datetime.fromtimestamp(mtime).isoformat(
                    timespec="seconds"
                ),
                "has_paper": (entry / "res.md").is_file(),
            }
        )

    tasks.sort(key=lambda t: t["created_at"], reverse=True)
    return {"tasks": tasks}


@router.get("/track")
async def track(task_id: str):
    """获取任务各 Agent 的 token 用量与费用统计。"""
    safe_task_id = _require_safe_task_id(task_id)
    usage_file = Path("logs/token_usage") / f"{safe_task_id}.json"
    if not usage_file.exists():
        return {"agents": {}, "total_cost": 0.0, "total_tokens": 0}

    try:
        data = json.loads(usage_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"读取 token 统计失败: {e}")
        return {"agents": {}, "total_cost": 0.0, "total_tokens": 0}

    agents = data.get("agents", {})
    total_tokens = sum(
        int(a.get("total_tokens", 0)) for a in agents.values()
    )
    return {
        "agents": agents,
        "total_cost": data.get("total_cost", 0.0),
        "total_tokens": total_tokens,
    }


@router.get("/status")
async def get_service_status():
    """获取后端和 Redis 的运行状态。"""
    status = {
        "backend": {"status": "running", "message": "Backend service is running"},
        "redis": {"status": "unknown", "message": "Redis connection status unknown"}
    }

    # 检查Redis连接状态
    try:
        redis_client = await redis_manager.get_client()
        await redis_client.ping()  # type: ignore[reportGeneralTypeIssues]
        status["redis"] = {"status": "running", "message": "Redis connection is healthy"}
    except Exception as e:
        logger.error(f"Redis connection failed: {str(e)}")
        status["redis"] = {"status": "error", "message": f"Redis connection failed: {str(e)}"}

    return status
