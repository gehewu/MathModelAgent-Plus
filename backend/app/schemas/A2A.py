"""Agent 间通信数据模型定义。"""

from pydantic import BaseModel
from typing import Any


class CoordinatorToModeler(BaseModel):
    """协调者传递给建模手的数据结构。"""
    questions: dict
    ques_count: int


class ModelerToCoder(BaseModel):
    """建模手传递给代码手的数据结构。"""
    questions_solution: dict[str, str]


class CoderToWriter(BaseModel):
    """代码手传递给写作手的数据结构。"""
    code_response: str | None = None
    code_output: str | None = None
    created_images: list[str] | None = None
    code_snippets: list[str] | None = None
    # 建模方案不可行回流信号：当代码手判定原建模方案不可行(硬约束无法满足/数据与方案根本假设冲突)时填充，
    # 携带不可行原因与修订建议；None 表示方案可行、无需回流。由 workflow 检测后触发建模手修订。
    scheme_feedback: str | None = None


class WriterResponse(BaseModel):
    """写作手的响应数据结构。"""
    response_content: Any
    footnotes: list[tuple[str, str]] | None = None
