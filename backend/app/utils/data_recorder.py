"""数据记录模块，记录 Agent 的对话历史和 Token 使用情况。"""

import json
import os
from pathlib import Path
from app.utils.log_util import logger
from typing import Any, Dict


# 模型价格表（每 1000 token，单位：元），用于成本估算
_MODEL_PRICES: Dict[str, Dict[str, float]] = {
    "deepseek-v4-flash": {"prompt": 0.001, "completion": 0.002},
    "deepseek-chat": {"prompt": 0.001, "completion": 0.002},
    "deepseek-reasoner": {"prompt": 0.004, "completion": 0.016},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
    "gpt-4-turbo-preview": {"prompt": 0.01, "completion": 0.03},
}


class UsageTracker:
    """按任务记录各 Agent 的 token 用量与费用，持久化到 logs/token_usage/。

    供 LLM.chat 调用链使用，/track 接口据此返回统计。
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.token_usage: Dict[str, Dict[str, float | int]] = {}
        self.total_cost = 0.0

    def _path(self) -> Path:
        return Path("logs") / "token_usage" / f"{self.task_id}.json"

    def record(
        self,
        agent_name: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """记录一次 LLM 调用的 token 用量并持久化。

        Args:
            agent_name: Agent 名称（如 CoderAgent）。
            model: 模型 ID。
            prompt_tokens: 输入 token 数。
            completion_tokens: 输出 token 数。
        """
        usage = self.token_usage.setdefault(
            agent_name,
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "chat_count": 0,
                "cost": 0.0,
            },
        )
        usage["prompt_tokens"] += prompt_tokens
        usage["completion_tokens"] += completion_tokens
        usage["total_tokens"] += prompt_tokens + completion_tokens
        usage["chat_count"] += 1
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        usage["cost"] = round(usage["cost"] + cost, 6)
        self.total_cost = round(self.total_cost + cost, 6)
        self._persist()

    def _calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """按价格表估算一次调用的费用（元）。"""
        prices = _MODEL_PRICES.get(
            model, {"prompt": 0.0001, "completion": 0.0001}
        )
        prompt_cost = (prompt_tokens / 1000.0) * prices["prompt"]
        completion_cost = (completion_tokens / 1000.0) * prices["completion"]
        return prompt_cost + completion_cost

    def _persist(self) -> None:
        """将统计写入 logs/token_usage/{task_id}.json（失败不阻塞主流程）。"""
        try:
            path = self._path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {"agents": self.token_usage, "total_cost": self.total_cost},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"写入 token 统计失败: {e}")

    def get_stats(self) -> Dict:
        """获取统计快照。"""
        return {"agents": self.token_usage, "total_cost": self.total_cost}


# TODO: 记录数据
class DataRecorder:
    """记录 Agent 对话历史、Token 使用量和 API 调用费用。"""
    def __init__(self, log_work_dir: str = ""):
        self.total_cost = 0.0
        self.agents_chat_history = {}
        # {"agent_name": [{}, {}, ...]
        #
        # }
        self.chat_completion = {}
        # {"agent_name": [ChatCompletion, ChatCompletion, ...]
        #
        # }
        self.log_work_dir = log_work_dir
        self.token_usage = {}

        self.initialized = True

    def print_summary(self):
        """打印统计摘要"""
        logger.info("\n=== Token Usage and Cost Summary ===")

        # 创建表格数据
        headers = ["Agent", "Chats", "Prompt", "Completion", "Total", "Cost ($)"]
        rows = []

        for agent_name, usage in self.token_usage.items():
            rows.append(
                [
                    agent_name,
                    usage["chat_count"],
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                    usage["total_tokens"],
                    f"{usage['cost']:.4f}",
                ]
            )

        # 添加总计行
        total_chats = sum(usage["chat_count"] for usage in self.token_usage.values())
        total_prompt = sum(
            usage["prompt_tokens"] for usage in self.token_usage.values()
        )
        total_completion = sum(
            usage["completion_tokens"] for usage in self.token_usage.values()
        )
        total_tokens = sum(usage["total_tokens"] for usage in self.token_usage.values())

        rows.append(
            [
                "TOTAL",
                total_chats,
                total_prompt,
                total_completion,
                total_tokens,
                f"{self.total_cost:.4f}",
            ]
        )

        # 使用 RichPrinter 打印表格
        from utils.RichPrinter import RichPrinter

        RichPrinter.table(
            headers=headers,
            rows=rows,
            title="Token Usage and Cost Summary",
            column_styles=["cyan", "magenta", "blue", "blue", "blue", "green"],
        )

    def write_to_json(self, to_save: dict, file_name: str):
        if self.log_work_dir:
            json_path = os.path.join(self.log_work_dir, file_name)
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(to_save, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"写入json文件失败: {e}")

    def append_chat_history(self, msg: dict, agent_name: str) -> None:
        """添加聊天历史记录"""
        if agent_name not in self.agents_chat_history:
            self.agents_chat_history[agent_name] = []
        self.agents_chat_history[agent_name].append(msg)
        self.write_to_json(self.agents_chat_history, "chat_history.json")

    def chat_completion_to_dict(self, completion: Any) -> Dict:
        """将 ChatCompletion 对象转换为可序列化的字典"""
        return {
            "id": completion.id,
            "choices": [
                {
                    "index": choice.index,
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in (choice.message.tool_calls or [])
                        ]
                        if hasattr(choice.message, "tool_calls")
                        else None,
                    },
                    "finish_reason": choice.finish_reason,
                }
                for choice in completion.choices
            ],
            "created": completion.created,
            "model": completion.model,
            "usage": {
                "completion_tokens": completion.usage.completion_tokens,
                "prompt_tokens": completion.usage.prompt_tokens,
                "total_tokens": completion.usage.total_tokens,
            }
            if hasattr(completion, "usage")
            else None,
            "system_fingerprint": completion.system_fingerprint
            if hasattr(completion, "system_fingerprint")
            else None,
        }

    def append_chat_completion(self, completion: Any, agent_name: str) -> None:
        """添加聊天完成记录"""
        if agent_name not in self.chat_completion:
            self.chat_completion[agent_name] = []

        # 将 ChatCompletion 对象转换为可序列化的字典
        completion_dict = self.chat_completion_to_dict(completion)
        self.chat_completion[agent_name].append(completion_dict)

        # 更新 token 使用统计
        self.update_token_usage(completion, agent_name)

        # 写入 JSON 文件
        self.write_to_json(self.chat_completion, "chat_completion.json")

    def update_token_usage(self, completion: Any, agent_name: str) -> None:
        """更新 token 使用统计和费用
        Args:
            completion: ChatCompletion 对象
            agent_name: 代理名称
        """
        if not hasattr(completion, "usage"):
            return

        if agent_name not in self.token_usage:
            self.token_usage[agent_name] = {
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0,
                "chat_count": 0,
                "cost": 0.0,  # 添加费用字段
            }

        usage = completion.usage
        model = completion.model

        # 更新 token 统计
        self.token_usage[agent_name]["completion_tokens"] += usage.completion_tokens
        self.token_usage[agent_name]["prompt_tokens"] += usage.prompt_tokens
        self.token_usage[agent_name]["total_tokens"] += usage.total_tokens
        self.token_usage[agent_name]["chat_count"] += 1

        # 计算本次请求的费用
        cost = self.calculate_cost(model, usage.prompt_tokens, usage.completion_tokens)
        self.token_usage[agent_name]["cost"] += cost
        self.total_cost += cost  # 更新总费用

        # 写入 JSON 文件
        self.write_to_json(self.token_usage, "token_usage.json")

    def calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """计算API调用费用
        Args:
            model: 模型名称
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
        Returns:
            float: 费用（rmb）
        """
        # 定义模型价格（每1000个token的价格，单位：rmb）
        model_prices = {
            "gpt-4-turbo-preview": {"prompt": 0.01, "completion": 0.03},
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
            "qwen-max-latest": {"prompt": 0.0024, "completion": 0.0096},  # 示例价格
        }

        # 获取模型价格，如果模型不在列表中使用默认价格
        model_price = model_prices.get(
            model,
            {"prompt": 0.0001, "completion": 0.0001},  # 默认价格
        )

        # 计算费用（将token数转换为千分比）
        prompt_cost = (prompt_tokens / 1000.0) * model_price["prompt"]
        completion_cost = (completion_tokens / 1000.0) * model_price["completion"]

        return prompt_cost + completion_cost
