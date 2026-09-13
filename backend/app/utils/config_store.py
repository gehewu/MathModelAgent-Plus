"""多套模型配置存储模块，负责 model_config.toml 的读写与 settings 应用。

设计说明：model_config.toml 预留了 config1/config2/current 多配置结构，
本模块补齐其读写逻辑，使前端保存的 API 配置能持久化，并在后端启动时自动加载
当前选中的配置，解决「配置只存内存、重启即丢」的问题。
"""

import os
import tomllib
from pathlib import Path

from app.config.setting import ApiType, settings
from app.utils.log_util import logger

# model_config.toml 路径（相对后端工作目录）
MODEL_CONFIG_PATH = os.path.join("app", "config", "model_config.toml")

# 每个 Agent 可持久化的配置字段（与 settings 字段名一一对应）
_AGENT_FIELDS = [
    "API_KEY",
    "MODEL",
    "BASE_URL",
    "API_TYPE",
    "MAX_TOKENS",
    "CONTEXT_WINDOW",
]

_AGENTS = ["COORDINATOR", "MODELER", "CODER", "WRITER"]


def _toml_str(value) -> str:
    """将值序列化为 TOML 字面量（basic string，支持任意 UTF-8 字符）。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _dump_simple_toml(configs: dict, current: str) -> str:
    """将配置字典序列化为 TOML 格式（表名用 quoted key，支持中文等特殊字符）。"""
    lines = []
    for name, cfg in configs.items():
        table = '"' + str(name).replace("\\", "\\\\").replace('"', '\\"') + '"'
        lines.append(f"[{table}]")
        for key, value in cfg.items():
            lines.append(f"{key}={_toml_str(value)}")
        lines.append("")
    lines.append("[current]")
    lines.append(f"current = {_toml_str(current)}")
    return "\n".join(lines)


def _load_raw() -> dict:
    """读取 model_config.toml 原始内容，文件不存在时返回空结构。"""
    if not os.path.exists(MODEL_CONFIG_PATH):
        return {"configs": {}, "current": "config1"}
    try:
        with open(MODEL_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        configs = {k: v for k, v in data.items() if k != "current"}
        current = data.get("current", {}).get("current", "config1")
        return {"configs": configs, "current": current}
    except Exception as e:
        logger.error(f"读取 model_config.toml 失败: {e}")
        return {"configs": {}, "current": "config1"}


# toml 字段 -> 前端 ModelConfig camelCase 字段 的映射
_TOML_TO_CAMEL = {
    "API_KEY": "apiKey",
    "MODEL": "modelId",
    "BASE_URL": "baseUrl",
    "API_TYPE": "apiType",
    "MAX_TOKENS": "maxTokens",
    "CONTEXT_WINDOW": "contextWindow",
}


def _extract_agent_config(config: dict, agent: str) -> dict:
    """从单个配置段中提取指定 Agent 的配置，输出与前端 ModelConfig 一致的 camelCase 结构。"""
    prefix = f"{agent}_"
    result: dict = {}
    raw = {k: v for k, v in config.items() if k.startswith(prefix)}
    for field, camel_key in _TOML_TO_CAMEL.items():
        key = prefix + field
        if key not in raw:
            continue
        value = raw[key]
        if field == "API_TYPE":
            # 字符串转 ApiType 枚举，非法值忽略（保留默认）
            try:
                value = ApiType(value)
            except (ValueError, TypeError):
                continue
        elif field in ("MAX_TOKENS", "CONTEXT_WINDOW"):
            value = int(value)
        result[camel_key] = value
    return result


def get_configs() -> dict:
    """获取所有配置段（前端展示用），返回与 save-api-config 一致的 camelCase 结构。"""
    raw = _load_raw()
    configs = {}
    for name, config in raw["configs"].items():
        agents = {}
        for agent in _AGENTS:
            agents[agent.lower()] = _extract_agent_config(config, agent)
        configs[name] = agents
    return {
        "configs": configs,
        "current": raw["current"],
    }


def get_config_names() -> list[str]:
    """获取所有配置名列表。"""
    return list(_load_raw()["configs"].keys())


def get_current_config_name() -> str:
    """获取当前选中的配置名。"""
    return _load_raw()["current"]


# 视觉模型配置：camelCase -> toml 字段 的映射
_VISION_TO_TOML = {
    "enabled": "VISION_ENABLED",
    "apiKey": "VISION_API_KEY",
    "model": "VISION_MODEL",
    "baseUrl": "VISION_BASE_URL",
    "apiType": "VISION_API_TYPE",
    "maxTokens": "VISION_MAX_TOKENS",
}


def save_config(config_name: str, agents: dict, vision: dict | None = None) -> None:
    """保存一组 Agent 配置（及可选视觉模型配置）到指定配置名，并设为当前配置。

    Args:
        config_name: 配置名（如 config1）。
        agents: camelCase 结构，如 {"coordinator": {"apiKey": ...}}。
        vision: 可选的视觉模型配置（camelCase，如 {"enabled": True, "apiKey": ...}）。
    """
    raw = _load_raw()
    section: dict = {}
    for agent in _AGENTS:
        prefix = f"{agent}_"
        agent_data = agents.get(agent.lower(), {}) or {}
        mapping = {
            "API_KEY": "apiKey",
            "MODEL": "modelId",
            "BASE_URL": "baseUrl",
            "API_TYPE": "apiType",
            "MAX_TOKENS": "maxTokens",
            "CONTEXT_WINDOW": "contextWindow",
        }
        for toml_key, camel_key in mapping.items():
            value = agent_data.get(camel_key)
            if value is None or value == "":
                continue
            section[prefix + toml_key] = value
    # 视觉模型配置（存在才写，避免覆盖其它配置段）
    if vision:
        for camel_key, toml_key in _VISION_TO_TOML.items():
            value = vision.get(camel_key)
            if value is None or value == "":
                continue
            section[toml_key] = value
    raw["configs"][config_name] = section
    raw["current"] = config_name

    Path(MODEL_CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(_dump_simple_toml(raw["configs"], raw["current"]))
    logger.info(f"模型配置已保存: {config_name} -> {MODEL_CONFIG_PATH}")


def switch_config(config_name: str) -> bool:
    """切换到指定配置名并应用到运行时 settings。

    Returns:
        切换是否成功（配置不存在返回 False）。
    """
    raw = _load_raw()
    if config_name not in raw["configs"]:
        logger.warning(f"切换配置失败，配置不存在: {config_name}")
        return False
    raw["current"] = config_name
    with open(MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(_dump_simple_toml(raw["configs"], raw["current"]))
    apply_config_to_settings(config_name)
    logger.info(f"已切换当前配置: {config_name}")
    return True


def apply_config_to_settings(config_name: str | None = None) -> None:
    """将指定（或当前）配置应用到全局 settings。

    供后端启动时（lifespan）调用，使持久化的配置在重启后自动生效。
    """
    raw = _load_raw()
    name = config_name or raw["current"]
    config = raw["configs"].get(name)
    if not config:
        logger.info(f"无持久化配置可加载（{name}），使用 .env.dev 配置")
        return
    for agent in _AGENTS:
        prefix = f"{agent}_"
        for field in _AGENT_FIELDS:
            key = prefix + field
            if key not in config:
                continue
            value = config[key]
            if field == "API_TYPE":
                try:
                    value = ApiType(value)
                except (ValueError, TypeError):
                    continue
            elif field in ("MAX_TOKENS", "CONTEXT_WINDOW"):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            setattr(settings, key, value)
    # 视觉模型配置
    for toml_key in _VISION_TO_TOML.values():
        if toml_key not in config:
            continue
        value = config[toml_key]
        if toml_key == "VISION_API_TYPE":
            try:
                value = ApiType(value)
            except (ValueError, TypeError):
                continue
        elif toml_key == "VISION_MAX_TOKENS":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        setattr(settings, toml_key, value)
    logger.info(f"已应用持久化配置到运行时: {name}")
