"""共享的提示词工具函数。"""

import json


def get_json_error_feedback(json_str: str, error: json.JSONDecodeError | None) -> str:
    """生成 JSON 解析失败后的修正反馈，包含出错位置附近原文，帮助模型针对性改正。

    Args:
        json_str: 模型返回的（已去除围栏标记的）JSON 文本。
        error: 解析错误对象；解析失败但无具体位置时传 None。

    Returns:
        给模型的修正反馈文本。
    """
    snippet = ""
    if error is not None:
        pos = error.pos
        start = max(0, pos - 30)
        end = min(len(json_str), pos + 30)
        snippet = f"\n出错位置附近文本：…{json_str[start:end]}…"
    return (
        "⚠️ 上次响应 JSON 格式错误，请修正后重新严格输出完整 JSON。"
        f"{snippet}\n"
        "常见原因与修正：\n"
        '1. 字符串值内出现未转义的 ASCII 双引号（"）会提前结束字符串，'
        '如需在文本中表达引号，请改用中文引号“”或将引号转义为 \\"。\n'
        "2. 属性名必须用双引号包裹，键值之间用冒号，条目之间用逗号，括号必须闭合。\n"
        "3. 不要输出 ```json 围栏或任何解释文字，直接输出合法 JSON。"
    )


def get_reflection_prompt(error_message, code) -> str:
    """生成代码错误反思提示词。

    Args:
        error_message: 错误信息。
        code: 出错的代码。

    Returns:
        反思提示词字符串。
    """
    return f"""The code execution encountered an error:
{error_message}

Please analyze the error, identify the cause, and provide a corrected version of the code. 
Consider:
1. Syntax errors
2. Missing imports
3. Incorrect variable names or types
4. File path issues
5. Any other potential issues
6. If a task repeatedly fails to complete, try breaking down the code, changing your approach, or simplifying the model. If you still can't do it, I'll "chop" you 🪓 and cut your power 😡.
7. Don't ask user any thing about how to do and next to do,just do it by yourself.

Previous code:
{code}

Please provide an explanation of what went wrong and Remenber call the function tools to retry 
"""


def get_completion_check_prompt(prompt, text_to_gpt) -> str:
    """生成任务完成检查提示词。

    Args:
        prompt: 原始任务描述。
        text_to_gpt: 最新执行结果。

    Returns:
        完成检查提示词字符串。
    """
    return f"""
Please analyze the current state and determine if the task is fully completed:

Original task: {prompt}

Latest execution results:
{text_to_gpt}  # 修改：使用合并后的结果

Consider:
1. Have all required data processing steps been completed?
2. Have all necessary files been saved?
3. Are there any remaining steps needed?
4. Is the output satisfactory and complete?
5. 如果一个任务反复无法完成，尝试切换路径、简化路径或直接跳过，千万别陷入反复重试，导致死循环。
6. 尽量在较少的对话轮次内完成任务
7. If the task is complete, please provide a short summary of what was accomplished and don't call function tool.
8. If the task is not complete, please rethink how to do and call function tool
9. Don't ask user any thing about how to do and next to do,just do it by yourself
10. have a good visualization?
"""
