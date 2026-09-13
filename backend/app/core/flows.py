"""工作流程定义模块，管理建模任务的求解和写作流程。"""

from app.models.user_output import UserOutput
from app.tools.base_interpreter import BaseCodeInterpreter
from app.core.agents.modeler_agent import ModelerToCoder


class Flows:
    """管理数学建模任务的求解流程和写作流程。"""
    def __init__(self, questions: dict[str, str | int]):
        self.flows: dict[str, dict] = {}
        self.questions: dict[str, str | int] = questions
        # 建模手给出的建模方案（含模型选择理由、公式、求解方法），供写作手引用
        self.modeler_solution: dict[str, str] = {}

    def set_modeler_solution(self, solutions: dict[str, str]) -> None:
        """设置建模手方案，供写作阶段引用。

        Args:
            solutions: 各子问题的建模方案（key 为 eda/ques1.../sensitivity_analysis）。
        """
        self.modeler_solution = solutions or {}

    def replace_solution(self, key: str, revised: str) -> None:
        """替换单个子问题的建模方案（供代码手→建模手回流修订时使用）。

        Args:
            key: 子问题键（如 ques1 / sensitivity_analysis）。
            revised: 修订后的建模方案文本。
        """
        self.modeler_solution[key] = revised

    def set_flows(self, ques_count: int):
        """根据问题数量设置流程节点。

        Args:
            ques_count: 问题数量。
        """
        ques_str = [f"ques{i}" for i in range(1, ques_count + 1)]
        seq = [
            "firstPage",
            "RepeatQues",
            "analysisQues",
            "modelAssumption",
            "symbol",
            "eda",
            *ques_str,
            "sensitivity_analysis",
            "judge",
            "references",
        ]
        self.flows = {key: {} for key in seq}

    def get_solution_flows(
        self, questions: dict[str, str | int], modeler_response: ModelerToCoder
    ):
        """生成求解阶段的流程配置。

        Args:
            questions: 包含各问题描述的字典。
            modeler_response: 建模手的响应，包含各问题的解决方案。

        Returns:
            求解流程配置字典，键为任务名，值包含 coder_prompt 等信息。
        """
        questions_quesx = {
            key: value
            for key, value in questions.items()
            if key.startswith("ques") and key != "ques_count"
        }
        solutions = modeler_response.questions_solution
        # 用户额外要求：代码手看不到用户原文（协调手也不会把它放进 quesN），
        # 故直接注入各 coder_prompt，避免"建模手忘了转达"导致用户要求落空。
        notes_block = self._user_notes_block()
        ques_flow = {
            key: {
                "coder_prompt": f"""
                        参考建模手给出的解决方案{solutions.get(key, "")}
                        完成如下问题{value}{notes_block}
                    """,
            }
            for key, value in questions_quesx.items()
        }
        flows = {
            "eda": {
                "coder_prompt": f"""
                        参考建模手给出的解决方案{solutions.get("eda", "对数据进行探索性分析")}
                        对当前目录下数据进行EDA分析(数据清洗,可视化),清洗后的数据保存当前目录下,**不需要复杂的模型**{notes_block}
                    """,
            },
            **ques_flow,
            "sensitivity_analysis": {
                "coder_prompt": f"""
                        参考建模手给出的解决方案{solutions.get("sensitivity_analysis", "对模型进行灵敏度分析")}
                        完成敏感性分析{notes_block}
                    """,
            },
        }
        return flows

    def _user_notes_block(self) -> str:
        """生成注入各 Agent 提示的「用户额外要求」文本块。

        协调手把用户输入压缩进固定字段时，题目之外的要求（指定方法、禁用项、
        输出格式等）容易丢失；这些内容对代码手/写作手同样有效，故统一从这里取用。
        未提供时返回空串，prompt 保持原样。

        Returns:
            以换行开头的提示块；无 user_notes 时为空字符串。
        """
        notes = str(self.questions.get("user_notes", "") or "").strip()
        if not notes:
            return ""
        return f"\n\n                        【用户额外要求（必须遵守）】\n                        {notes}"

    def rebuild_coder_prompt(self, key: str) -> str:
        """重建单个子任务的代码手提示（供代码手→建模手回流修订后重新求解）。

        用法：代码手判定某子问题建模方案不可行并回传反馈后，workflow 调建模手修订
        该方案（replace_solution 更新 modeler_solution[key]），再据此重建该子任务的
        coder_prompt，用修订后的方案重新驱动代码手求解。与 get_solution_flows 的
        提示生成规则保持一致（同一套 f-string 模板）。

        Args:
            key: 子任务键（eda / quesN / sensitivity_analysis）。

        Returns:
            重建后的 coder_prompt 字符串。

        Raises:
            ValueError: key 不在求解流程范围内（不是 eda/quesN/sensitivity_analysis）时抛出。
        """
        solution = self.modeler_solution.get(key, "")
        question = self.questions.get(key, "")
        # 与 get_solution_flows 保持一致：回流重跑同样带上用户额外要求
        notes_block = self._user_notes_block()

        if key == "eda":
            return f"""
参考建模手给出的解决方案{solution or "对数据进行探索性分析"}
对当前目录下数据进行EDA分析(数据清洗,可视化),清洗后的数据保存当前目录下,**不需要复杂的模型**{notes_block}
"""
        if key == "sensitivity_analysis":
            return f"""
参考建模手给出的解决方案{solution or "对模型进行灵敏度分析"}
完成敏感性分析{notes_block}
"""
        if key.startswith("ques"):
            return f"""
参考建模手给出的解决方案{solution}
完成如下问题{question}{notes_block}
"""
        raise ValueError(f"未知的子任务类型，无法重建代码手提示: {key}")

    def get_write_flows(
        self, user_output: UserOutput, config_template: dict, bg_ques_all: str
    ):
        """生成写作阶段的流程配置。

        Args:
            user_output: 用户输出对象，包含已求解的结果。
            config_template: 论文模板配置。
            bg_ques_all: 问题背景和题目信息。

        Returns:
            写作流程配置字典，键为章节名，值为写作提示。
        """
        model_build_solve = user_output.get_model_build_solve()
        flows = {
            "firstPage": f"""问题背景{bg_ques_all},不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["firstPage"]}，撰写标题，摘要，关键词""",
            "RepeatQues": f"""问题背景{bg_ques_all},不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["RepeatQues"]}，撰写问题重述""",
            "analysisQues": f"""问题背景{bg_ques_all},不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["analysisQues"]}，撰写问题分析""",
            "modelAssumption": f"""问题背景{bg_ques_all},不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["modelAssumption"]}，撰写模型假设""",
            "symbol": f"""不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["symbol"]}，撰写符号说明部分""",
            "judge": f"""不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["judge"]}，撰写模型的评价部分""",
            "ai_declaration": f"""不需要编写代码,按照如下模板撰写：{config_template["ai_declaration"]}，撰写AI工具使用声明""",
            "references": f"""不需要编写代码,根据模型的求解的信息{model_build_solve}，按照如下模板撰写：{config_template["references"]}，撰写参考文献""",
        }
        return flows

    def get_writer_prompt(
        self,
        key: str,
        coder_response: str,
        code_interpreter: BaseCodeInterpreter,
        config_template: dict,
        modeler_solution: str = "",
        code_snippets: list[str] | None = None,
    ) -> str:
        """根据不同的key生成对应的writer_prompt

        Args:
            key: 任务类型
            coder_response: 代码执行结果
            code_interpreter: 代码解释器，用于获取代码输出。
            config_template: 论文模板配置。
            modeler_solution: 建模手对本子问题的建模方案（方法/算法介绍素材）。
            code_snippets: 代码手执行过的代码片段（供引用实现细节）。

        Returns:
            str: 生成的writer_prompt
        """
        code_output = code_interpreter.get_code_output(key)

        # 建模方案：方法/算法介绍的核心素材（模型选择理由、公式、求解思路）
        modeler_info = ""
        if modeler_solution:
            modeler_info = (
                "建模手给出的建模方案（必须据此详细介绍模型与算法，"
                "包括模型选择理由、数学表达式、变量定义和求解方法）：\n"
                f"{modeler_solution}"
            )

        # 代码片段：限制长度避免上下文膨胀，仅作实现细节参考
        snippets_str = ""
        if code_snippets:
            joined = "\n".join(code_snippets).strip()
            if joined:
                snippets_str = (
                    "代码手执行的代码（可引用其中的具体实现细节，如参数取值、算法步骤）：\n"
                    f"{joined[:2000]}"
                )

        extra_info = "\n".join(part for part in [modeler_info, snippets_str] if part)

        questions_quesx_keys = self.get_questions_quesx_keys()
        bgc = self.questions["background"]
        # 用户额外要求一并注入写作提示（协调手可能已在 background 中丢失）
        notes_block = self._user_notes_block()
        quesx_writer_prompt = {
            key: f"""
                    问题背景{bgc},不需要编写代码,代码手得到的结果{coder_response},{code_output}
                    {extra_info}
                    按照如下模板撰写：{config_template[key]}{notes_block}
                """
            for key in questions_quesx_keys
        }

        writer_prompt = {
            "eda": f"""
                    问题背景{bgc},不需要编写代码,代码手得到的结果{coder_response},{code_output}
                    {extra_info}
                    按照如下模板撰写：{config_template["eda"]}{notes_block}
                """,
            **quesx_writer_prompt,
            "sensitivity_analysis": f"""
                    问题背景{bgc},不需要编写代码,代码手得到的结果{coder_response},{code_output}
                    {extra_info}
                    按照如下模板撰写：{config_template["sensitivity_analysis"]}{notes_block}
                """,
        }

        if key in writer_prompt:
            return writer_prompt[key]
        else:
            raise ValueError(f"未知的任务类型: {key}")

    def get_questions_quesx_keys(self) -> list[str]:
        """获取问题1,2...的键"""
        return list(self.get_questions_quesx().keys())

    def get_questions_quesx(self) -> dict[str, str | int]:
        """获取问题1,2,3...的键值对"""
        # 获取所有以 "ques" 开头的键值对
        questions_quesx = {
            key: value
            for key, value in self.questions.items()
            if key.startswith("ques") and key != "ques_count"
        }
        return questions_quesx

    def get_seq(self, ques_count: int) -> dict[str, str]:
        """获取论文章节顺序。

        Args:
            ques_count: 问题数量。

        Returns:
            以章节名为键的有序字典。
        """
        ques_str = [f"ques{i}" for i in range(1, ques_count + 1)]
        seq = [
            "firstPage",
            "RepeatQues",
            "analysisQues",
            "modelAssumption",
            "symbol",
            "eda",
            *ques_str,
            "sensitivity_analysis",
            "judge",
            "references",
        ]
        return {key: "" for key in seq}
