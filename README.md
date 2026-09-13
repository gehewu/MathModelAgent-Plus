<h1 align="center">🤖 MathModelAgent-Plus 📐</h1>
<p align="center">
    <img src="./docs/icon.png" height="250px">
</p>
<h4 align="center">
    基于 MathModelAgent 的二次开发增强版<br>
    面向数学建模竞赛：自动完成建模、求解、绘图，并生成可直接提交的论文
</h4>

> **本项目是 [MathModelAgent](https://github.com/jihe520/MathModelAgent) 的 fork（二次开发版），非原作者仓库。**
> 如需上游原生能力与最新进展，请访问上游仓库。

<p align="center">
    <img src="./docs/chat.png">
    <img src="./docs/coder.png">
</p>

## 💡 写在前面

本项目最初是为了在竞赛周期内快速学习模型与算法而开发的。经过约 40 次论文输出，系统可在 **40 分钟 ~ 3 小时**内产出完整论文，成本控制在 **￥2 ~ ￥10**。需要说明的是，受排版等因素限制，产出的论文**不能直接用于参赛**，它的定位是帮助快速学习不同场景下合适的模型与算法。虽然各类 Agent 层出不穷，但学习不能松懈——**人工 + AI 才是最优解**。祝各位同学学习顺利！

---

## 📌 上游声明

- **上游项目**：[MathModelAgent](https://github.com/jihe520/MathModelAgent) ｜ 作者：[@jihe520](https://github.com/jihe520)
- **本仓库性质**：非官方 fork，由二次开发者在原项目基础上做**竞赛向增强**，与原作者无隶属关系。
- **许可证**：上游为「**个人免费使用，请勿商业用途，禁止闭源分发**」。本仓库**完全遵守该许可**——保持开源、不作商业用途；如需商业使用，请联系原作者。
- **二开范围**：主要集中在 **Web 模式**（`backend/` + `frontend/`）的**建模质量、论文合规、工程稳健性**；上游的 `skills/` 层已从本仓库移除，本仓库不维护该部分。
- **责任边界**：本仓库的改动、Bug 与效果由二次开发者负责，请**不要**将本仓库的问题提交到上游仓库。

---

## 🚀 二开增强概览

相对上游，本 fork 在**四个方向**做了系统性增强（每条均已实测验证，详见下文「二开内容详解」）：

### 📝 论文更合规（对齐国赛评阅标准）

- **对齐国赛书写规范** — 依据《2026 年数学建模竞赛模板》逐条校准写作手：关键词 4-6 个、摘要第三人称 + 800-1000 字 + 不预设问题递进、必须写明「模型名称 + 数学类型」、模型假设 4-8 条、正文表格 ≤15 行、参考文献 5-15 篇等。
- **AI 工具使用声明（2026 新规）** — 补齐上游缺失的章节，论文末尾顺序符合「模型评价 → AI 声明 → 参考文献 → 附录」，并明确 AI 工具不得列入参考文献。
- **真实文献强制** — 综述/参考文献必须基于 `search_papers` 真实检索（含 DOI），禁止凭记忆编造。

### 🎯 用户意图不丢失

- **用户要求贯通（`user_notes` + 原文直通）** — 实测发现：用户在题目之外提出的建模建议会被协调手**整段丢弃**。现已双通道保障——结构化字段分发到建模手/代码手/写作手，同时原始文本直通建模手作为权威版本。

### 📊 建模与图表质量可控

- **视觉反馈闭环** — 修复「`plt.savefig` 保存的图约 87% 未被评估」的漏洞，改为文件层 MD5 快照扫描。
- **视觉一致性核对** — 视觉模型不再只看图打分：解析代码手的图片元数据卡，核对「自述 vs 图中实际」是否一致，不一致时即使画质 9 分也强制重绘。
- **算法取舍铁律** — 把竞赛实战经验（十大避坑算法 + 十大创新方向 + 防炫技红线）编译进建模手提示词，优先级高于决策树。
- **五层工程约束** — 物理正确性 / 结果可信度 / 建模适当性 / 数学严谨性 / 结论锐度。

### ⚙️ 工程更稳健

- **执行超时治理** — 分档超时 + 复杂度预审 + 结构化反思 + 精度受限求解；超时后**重启内核**（SIGINT 停不掉原生计算）。
- **论文 PDF 编译** — `res.md` 经 pandoc + xelatex 直接产出 PDF，支持按需/自动两种触发，工具链缺失时优雅降级。
- **代码手 → 建模手回流** — 方案数学上不可行时触发建模手修订并重求解，而非让代码手硬凑。
- **数据链路与前端修复** — 脏数据注入、JSON 容错、子目录递归扫描、附件支持 PDF/DOCX、历史任务空白等。

---

## 🛠️ 二开内容详解

### 🧠 建模与论文质量

- **结构化建模卡片** — 建模手每个子问题输出固定字段卡片（问题类型 / 目标函数 / 决策变量 / 约束条件 / 模型选择理由 / 求解方法 / 验证策略 / 可视化方案）。代码手拿到精确规格、写作手拿到完整素材，减少“一段话自由发挥”导致的理解偏差。
  `backend/app/core/prompts/modeler.py`
- **论文模板要素化** — 标题 / 摘要 / 问题重述 / 问题分析模板重写为「占位符要素框架」（如 `【模型名称】【关键量化结果】`），让模型知道每处该填什么、避免漏写关键信息。
  `backend/app/config/md_template.toml`（`firstPage` / `RepeatQues` / `analysisQues`）
- **补全近乎空壳的模板** — 灵敏度分析（参数选择 / 扰动设置 / 结果分析三段式）、模型评价（优点 ≥3 条用数据佐证 / 缺点 / 改进与推广）、参考文献（GB/T 7714 格式 + 强制真实检索）。
  `backend/app/config/md_template.toml`（`sensitivity_analysis` / `judge` / `references`）
- **对齐国赛论文书写规范（BZD 规范）** — 依据《2026 年数学建模竞赛模板》逐条校准写作手提示词与模板：关键词 **4-6 个**（问题词 / 模型词 / 算法词三方向）；摘要第三人称 + 800-1000 字 + 引言段两句 + 一问一段且**不预设问题递进** + 9 条禁忌；必须写明「模型名称 + 数学类型」（**软件名不能代替算法**）；问题重述三部分（研究背景 / 问题回顾 / 研究综述约 500 字）；问题分析用连贯段落（不机械拆小节）+ 整体求解框架图；模型假设 **4-8 条**（内容 + 依据 + 作用，禁把数据预处理写成假设）；模型章节五步闭环 + **优化模型集中表达** + 正文表格 ≤15 行 + 按模型类型选检验指标；模型评价 500-800 字（优点 3-5 条带证据 / 不足 2-4 条 / 改进逐项对应 / 推广说明迁移对象）；参考文献 **5-15 篇**且正文与文末一一对应。
  `backend/app/core/prompts/writer.py`、`backend/app/config/md_template.toml`
- **AI 工具使用声明（2026 新规）** — 新增论文末尾章节，论文末尾顺序为「模型评价 → AI 工具使用声明 → 参考文献 → 附录」；**AI 工具不得列入参考文献**。
  `backend/app/config/md_template.toml`（`ai_declaration`）、`core/flows.py`、`models/user_output.py`

### 💬 用户要求贯通（user_notes + 原文直通）

> 背景：协调手是 LLM，会把用户输入压缩进固定字段（`title` / `background` / `ques1..N`）。实测发现用户在题目之外提出的**建模建议**（如“用有限体积法”“不要套优化模型”“做三口径对照实验”）被**整段丢弃**——协调手输出里连 `background` 都没保留，建模手完全看不到。

- **A · 新增 `user_notes` 字段** — 协调手 JSON 增加该字段，并加三条硬规则：用户额外要求必须**原样完整**放入、**不得并入 background**、**不得当作新增小问**（不增加 `ques_count`）。建模手提示词新增「**用户要求优先**」章节（优先级高于决策树）：必须遵循、必须在方案卡片中显式落实、与题目冲突时要说明、不得臆造。`user_notes` 同时注入**代码手**（含回流重建路径）与**写作手**提示——代码手看不到用户原文，只能靠这里拿到要求。
  `backend/app/core/prompts/coordinator.py`、`core/prompts/modeler.py`、`core/flows.py`
- **B · 原文直通（保真兜底）** — 协调手天然是有损压缩器，加字段仍可能漏抄。`ModelerAgent.run()` 新增 `raw_ques` 参数，把用户提交的**原始文本**（未经转述）一并注入建模手对话，并声明「原文是权威版本，与 `user_notes` 冲突时以原文为准」。
  `backend/app/core/agents/modeler_agent.py`、`core/workflow.py`
- **顺带修复** — 协调手 JSON 示例缺逗号（`"title"` 之后、以及尾随逗号），易致协调手输出非法 JSON、触发解析重试，已补齐。
  `backend/app/core/prompts/coordinator.py`

### 🔬 算法取舍铁律（建模意见.md 注入，优先级最高）

> 将「建模意见.md」的算法经验编译进建模手系统提示词，作为**高于决策树的取舍铁律**：决策树回答「该用哪类」，铁律回答「哪类不该用 + 如何创新拿奖」。已同步修正决策树中的三处冲突推荐，消除 AHP/熵权/模糊综合评价被误作首选推荐的问题。

- **十大避坑算法（尽量不用，除非题目数据强约束）** — AHP（主观赋权）、GM(1,1)（仅短期单变量可用）、BP 神经网络（小样本过拟合）、SVM（大样本慢、参数靠猜）、K-means（需预设 K、球形假设）、模糊综合评价（全主观可操控）、多元线性回归（无深度上限低）、朴素贝叶斯（独立性假设几乎不成立）、单棵决策树 ID3/C4.5（过拟合，已被集成取代）、熵权法单独用（极端值主导权重）。
  **高优先级替代**：CRITIC / TOPSIS / VIKOR / 灰色关联 / LightGBM / XGBoost / DBSCAN / 层次聚类 / 高斯混合模型。
  `backend/app/core/prompts/modeler.py`
- **十大国奖级模型创新方向（加分项，主动沾边）** — 参数自适应优化、多模型对比择优、求解算法升级、同领域模型融合、跨领域交叉迁移、机理+数据双驱动、数据预处理与特征工程、模型检验与不确定性量化、动态时变与多阶段递推、多目标协同与分层决策（Pareto/双层规划替代加权求和）。
  `backend/app/core/prompts/modeler.py`
- **红线警告（防炫技）** — 求解算法升级**绝对禁止**在能用精确解（线性规划 / Dijkstra）时强行用遗传算法或模拟退火去“创新”，会被评委视为炫技、不专业；该创新仅限 **NP-hard 问题或大规模非线性优化**。
  `backend/app/core/prompts/modeler.py`

### 📊 图表质量

- **绘图配色统一** — 色板改为柔和色板（柔蓝 `#5B9BD5` / 珊瑚粉 `#ED7D7D` / 薄荷绿 `#7BC8A4` / 浅灰 `#B0B0B0` / 淡紫 `#9B8EC4` / 暖杏 `#F4A261`），在 `matplotlib_setup.py` 全局注入，改一处全局生效。
  `backend/app/tools/matplotlib_setup.py`
- **视觉反馈闭环（修复）** — 原先仅 iopub 输出触发视觉评估，`plt.savefig` 保存的图约 87% 未被评估。改为文件层 MD5 快照扫描，任何新保存的图都会被视觉模型评估；不达标时 `[REDRAW_REQUIRED]` 触发强制重绘（上限 `MAX_REDRAW_ROUNDS`，默认 2 次）。
  `backend/app/tools/base_interpreter.py`、`local_interpreter.py`、`e2b_interpreter.py`、`core/agents/coder_agent.py`、`config/setting.py`
- **视觉评估增强** — 评估 prompt 增加 6 维度打分（坐标轴 / 图例 / 数据可读性 / 配色 / 清晰度 / 整体），输出「评分：X/10」；`should_retry` 改为评分门控（<7 重绘）+ 关键词兜底两级判定，判断更准确。
  `backend/app/tools/vision_service.py`
- **视觉一致性核对（图 vs 代码手自述）** — 视觉模型不再只看图打分：解释器解析代码手输出的【图片元数据】卡，取可核实的关键字段（图表类型 / 数据来源 / 核心结论，`文件名`仅用于匹配、`适用章节`图里看不出故略）作为「自述」随图一起送审；视觉模型新增 `[一致性]` 段逐条核对自述与图中实际是否吻合，**判定不一致时评分不得超过 5/10**，且 `should_retry` 以一致性为最高优先级硬门控（不一致直接重绘，即使画质 9 分）。无元数据卡时自动退化为纯质量审查，不误判。可抓出“画质合格但内容说错”的问题（自述散点图实为柱状图、自述上升实为下降、坐标轴与自述变量不符等）。
  `backend/app/tools/vision_service.py`、`base_interpreter.py`、`local_interpreter.py`、`core/agents/coder_agent.py`
- **图片元数据卡 + 数据特征卡** — 代码手每张图输出元数据卡（文件名 / 图表类型 / 数据来源 / 核心结论 / 适用章节），结果汇总输出本子任务图片清单，让写作手精准引用图片、写出与图一致的分析，告别“只放图不解释”。
  `backend/app/core/prompts/coder.py`

### 📚 文献集成

- **OpenAlex 深度集成** — 写作手 `search_papers` 由单次改为可循环多次检索（上限 5 次），支持综述 / 参考文献分主题检索；参考文献与研究综述强制基于真实检索（含作者 / 年份 / 标题 / DOI）撰写，禁止凭记忆编造。
  `backend/app/core/agents/writer_agent.py`、`core/prompts/writer.py`、`config/md_template.toml`

### 📄 论文 PDF 编译

- **Markdown → PDF（pandoc + xelatex）** — 写作手产出的 `res.md` 经 pandoc + xelatex 直接编译为 `res.pdf`（中文 / 公式 / 表格 / 图片均正常），页边距 2.5cm；中文字体自动探测（Windows SimSun / SimHei，Linux Noto CJK，可用 `PDF_CJK_FONT` 指定）；编译前删除旧 PDF，避免「本次失败却下载到上次的旧文件」。
  `backend/app/tools/latex_compiler.py`
- **两种触发方式** — 前端「论文预览」新增「生成 PDF」按钮按需编译；设 `PDF_AUTO_COMPILE=true` 则任务完成后自动编译（编译失败只告警、不中断任务）。
  `backend/app/routers/files_router.py`（`POST /paper/{task_id}/compile`）、`core/workflow.py`、`frontend/src/components/PaperPreview.vue`
- **优雅降级** — 检测不到 pandoc / xelatex / 中文字体时返回可读原因（如「未检测到 xelatex」），不抛异常、不影响论文正文产出；Docker 镜像未装 TeX 发行版时走此路径。
  `backend/app/tools/latex_compiler.py`
- **下载白名单扩展** — 论文下载新增 `pdf` 类型（`res.pdf`）。
  `backend/app/routers/files_router.py`

### 🧭 模型与工程约束规范（五层约束）

> 参考国赛评阅视角，为 Agent 制定五层行为约束。三层纯 prompt 落地，一层依赖回流机制（见下节）。

- **第一层 · 物理/逻辑正确性** — 量纲与口径一致性（单位字典、量纲校验打印「左=右=一致」）、硬约束逐条审计（违反即判不可行、不强行汇报）、输入-输出闭环校验（读入/清洗/模型输入输出对账）、数据可行性前置检查（缺失率 >30% 或偏离 >5σ 必须先出清洗策略，否则显式声明弃用该列）。
  `backend/app/core/prompts/coder.py`
- **第二层 · 结果可信度** — 拒绝「完美主义」（诚实写出边界和不足）、每个结果必须有「绝对值 + 对比基准」（均值基线 / 理论上界 / 文献值，禁「效果良好」空泛表述）、承认不确定性（置信区间 / 误差范围 / 适用边界）、灵敏度分析必须实跑（每模型扰动 2-3 参数 ±10%/±20%，画图并区分高敏感/稳健）。
  `backend/app/core/prompts/coder.py`
- **第三层 · 建模适当性** — 奥卡姆剃刀（不炫技、简单优先、每个模型说清「为何不选更简单方案」）、方法选择论述（建模卡片含「模型选择理由」）。
  `backend/app/core/prompts/modeler.py`
- **第四层 · 数学严谨性** — 建模卡片强制含【符号说明】【量纲与口径】【硬约束判定】，支撑全文符号表不漏符号；公式逐项定义变量。写作端「约束审计」章节（加分项）逐条回答硬约束是否满足 / 如何满足 / 数值佐证。
  `backend/app/core/prompts/modeler.py`、`config/md_template.toml`、`core/prompts/writer.py`
- **第五层 · 结论锐度** — 摘要 / 模型评价末尾必须给「一句话管理层结论」（不依赖公式、直击问题、可执行，如「建议将 A 仓库库存调至 B 区域，可降低 X% 积压」），让决策者直接拍板。
  `backend/app/core/prompts/writer.py`、`config/md_template.toml`（`judge`）

### 🔄 代码手 → 建模手回流（分级不可行处理）

分层方案：代码手优先**自我调整**（改参数范围 / 换相近算法 / 调整实现），只有「硬约束经调整仍不可满足」或「方案数学上不可行」时才回流给建模手修订。

- **代码手自我调整** — 受既有 `MAX_RETRIES` 重试兜底，改参数 / 换相近算法 / 调实现路线，不惊动建模手。
- **回流触发标记** — 代码手无法自我解决时，按固定格式输出 `[MODEL_SCHEME_INFEASIBLE]` + 原因 + 建议，结束当前子任务不再硬凑；由 `_extract_scheme_feedback` 提取。
  `backend/app/core/prompts/coder.py`、`core/agents/coder_agent.py`
- **建模手修订** — `revise_question(key, original_card, coder_feedback)` 走「方案修订模式」（聚焦单子问题、先理解原因、按「调约束→修正假设→换方法」优先级修订、输出完整修订卡片）。
  `backend/app/core/prompts/modeler.py`、`core/agents/modeler_agent.py`
- **修订后重求解** — workflow 内嵌 `while`：检测回流 → 发布「触发建模手修订」警告 → 建模手修订 → `replace_solution` + `rebuild_coder_prompt` 重建该子任务提示 → 重新求解；上限 `MAX_SCHEME_REVISE_ROUNDS`（默认 2）防死循环。论文手写作时引用**修订后**方案（`flows.modeler_solution`），保证论文与代码实际求解一致。
  `backend/app/core/workflow.py`、`core/flows.py`、`config/setting.py`、`.env.dev`

### ⏱️ 执行超时与高耗时算法优化

代码执行层增加超时中断与「复杂度预审 → 反思 → 精度受限求解」状态机，防止高耗时算法（蒙特卡洛/网格搜索等）无限卡死任务：

- **执行超时分档** — 普通代码默认 180s（画图/读数据/EDA）；计算密集型（命中慢算法特征或首行 `# [EXEC_TYPE: COMPUTE]` 标记）用 600s。超时后重启 Jupyter 内核（SIGINT 停不掉原生计算）并返回 `[EXEC_TIMEOUT]` 触发反思流程。档位可在 `.env` 调（`EXEC_TIMEOUT_NORMAL` / `EXEC_TIMEOUT_COMPUTE`）。
  `backend/app/tools/local_interpreter.py`、`config/setting.py`、`.env.dev`
- **复杂度预审** — 提交计算密集型代码前先估算时间复杂度和数据规模（O(n³) n>5000、蒙特卡洛样本数、网格搜索组合数），铁定超时直接跳过首次执行、先进反思优化。
  `backend/app/core/prompts/coder.py`
- **结构化反思 + 精度受限求解** — 超时后按四步诊断（瓶颈定位→复杂度分析→优化方案→方案落地）并输出结构化 JSON（bottleneck / complexity / strategy / implementation / expected_speedup / round / fallback_needed）；反思达 2 次仍超时则执行「精度受限求解」：保留模型结构、只降计算量（粗网格/分层降采样/贝叶斯 20 次），并给出可计算的误差度量（置信区间/偏差/MAPE）；实在无法可信求解则输出 `[MODEL_SCHEME_INFEASIBLE]` 交给建模手修订，严禁整体换成线性近似当答案。
  `backend/app/core/agents/coder_agent.py`、`core/prompts/coder.py`
- **LLM 调用超时（互补修复）** — provider 加 `timeout=300` + `max_retries=0` 关闭 SDK 隐式重试；`llm.py` 重试间隔改 `await asyncio.sleep` 不阻塞事件循环。与执行层超时互补，彻底消除「模型调用 / 代码运行」两类卡死。
  `backend/app/core/llm/llm.py`、`core/llm/providers/*`

### 🔧 数据链路修复

- **`get_model_build_solve` 脏数据** — 原输出 Python 字典字面量（`{'response_content':...,'footnotes':...}`）被注入写作 prompt，导致摘要 / 总结引用脏数据。改为只提取 `response_content`，干净输出「问题N：正文」格式。
  `backend/app/models/user_output.py`
- **JSON 解析容错增强** — 模型输出含未转义 ASCII 双引号导致 `json.loads` 失败；新增 `get_json_error_feedback` 展示出错位置片段 + 显式引号规则；并修复协调手 `json_str` 潜在 `UnboundLocalError`；建模手输出脏 JSON 时用 `repair_json` 修复后补发规范化 JSON，修复「部分模型建模手册不显示」。
- **子目录递归扫描（修复）** — 大模型自建 `figures/`、`cleaned_data/` 等子目录存放图片/清洗后数据时，原 `os.listdir` 只扫根目录，导致视觉评估与图片/数据登记全部失效。改为 `os.walk` 递归，返回带相对路径（如 `figures/q1.png`）；`get_current_files("data")` 同时排除产物（`res.md/res.docx/notebook.ipynb`）。
  `backend/app/tools/base_interpreter.py`、`local_interpreter.py`、`utils/common_utils.py`
- **附件类型扩展 — 支持 PDF/DOCX** — 附件上传从 txt/csv/xlsx 扩展支持 `.pdf` `.docx`；代码手首次运行按类型分组列出数据文件与题目文档，检测到 PDF/DOCX 时注入读取指引（`fitz` 提取 PDF 文本 / `python-docx` 读取段落 / 表格提取）。新增 `python-docx` 依赖。
  `frontend/src/components/UserStepper.vue`、`backend/app/core/agents/coder_agent.py`、`utils/common_utils.py`、`pyproject.toml`

### 🖥️ 前端修复

- **历史任务空白** — 组件常驻挂载导致 `onMounted` 仅在 `open=false` 时触发一次、`loadTasks` 永不执行；改为 `watch(() => props.open, ...)`，每次打开重新加载。另：加载失败时从「静默空白」改为显示「加载失败 + 重试」，避免与「暂无历史任务」混淆。
  `frontend/src/components/TaskHistory.vue`
- **API 配置列表为空 / 切换不回填** — 同样 `onMounted` 问题，改为 `watch`；配套新增 `loadConfigIntoStore`，切换配置方案后回填表单，避免误点“保存”覆盖新方案。
  `frontend/src/pages/chat/components/ApiDialog.vue`、`src/stores/apiKeys.ts`

---

## ✨ 基础功能特性（继承自上游）

- 🔍 自动分析问题 → 数学建模 → 编写代码 → 纠正错误 → 撰写论文
- 💻 Code Interpreter：本地 Jupyter（代码保存为 notebook 便于再编辑）／云端 [E2B](https://e2b.dev/)
- 📝 生成编排好格式的论文，支持导出与 PDF 编译
- 🤝 multi-agents：协调手、建模手、代码手、论文手
- 🔄 multi-llms：每个 Agent 可设置不同的、合适的模型
- 💰 成本低：workflow agentless，不依赖 agent 框架
- 🧩 自定义模板：prompt inject 为每个 subtask 单独设置需求

---

## ⚙️ 新功能配置

以下为可选功能，默认关闭；开启后未配置外部依赖时自动降级跳过。

| 功能 | 配置开关 | 说明 |
| --- | --- | --- |
| 思考强度（推理强度） | `MODELER_REASONING_EFFORT` / `CODER_REASONING_EFFORT` | 建模手 / 代码手的推理强度（`low` / `medium` / `high`）；仅 OpenAI 兼容接口，**留空 = 不传该参数** |
| 论文 PDF 编译 | `PDF_AUTO_COMPILE` / `PDF_COMPILE_TIMEOUT` / `PDF_CJK_FONT` | 任务完成后自动编译 PDF；中文字体留空自动探测 |
| 视觉反馈 | `VISION_ENABLED` + `VISION_API_KEY` / `VISION_MODEL` | 画图后送视觉模型评估，不合格触发重绘 |
| 执行超时档位 | `EXEC_TIMEOUT_NORMAL` / `EXEC_TIMEOUT_COMPUTE` | 普通/计算密集代码的执行超时（默认 180s / 600s） |

启用思考强度：在 `backend/.env.dev` 中设置 `MODELER_REASONING_EFFORT=high`、`CODER_REASONING_EFFORT=medium` 即可（协调手 / 论文手不支持该参数；Anthropic 实现会忽略）。**注意**：部分模型与中转站不支持 `reasoning_effort`，会返回 400，此时把这两项留空即可恢复（默认即为留空）。

启用 PDF 编译：前端「论文预览」点「生成 PDF」按需编译；或设 `PDF_AUTO_COMPILE=true` 自动编译。**依赖系统安装 TeX 发行版**（如 MiKTeX / TeX Live）；未安装时给出明确提示，不影响论文正文产出。

---

## 🚀 部署与使用

### 下载

```bash
git clone https://github.com/gehewu/MathModelAgent-Plus.git
cd MathModelAgent-Plus
```

> 若只想使用上游原生版本，请访问 [jihe520/MathModelAgent](https://github.com/jihe520/MathModelAgent)。

### 🐳 方案一：Docker 部署

> 确保已安装 docker 环境

```bash
docker-compose up
```

访问：

- 前端界面：http://localhost:5173
- 后端 API：http://localhost:8000

配置：侧边栏 → 头像 → API Key

> **注意**：Docker 镜像默认**未安装 TeX 发行版**，PDF 编译会走「优雅降级」提示。如需在容器内编译 PDF，需自行在 `backend/Dockerfile` 中追加 `texlive-xetex` 与中文字体。

### 💻 方案二：本地部署（推荐开发者）

> 需安装 Python、Node.js、**Redis**

**step1 · 安装依赖**

```bash
# Redis：Windows https://github.com/tporadowski/redis/releases
#        Linux/macOS https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/

# 后端
cd backend
pip install uv
uv sync

# 前端
cd ../frontend
npm install -g pnpm
pnpm i
```

**step2 · 启动**

```bash
# 1. 启动 Redis
redis-server

# 2. 启动后端（Windows 可直接双击项目根目录的 win_start.bat 一键启动）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload

# 3. 启动前端
cd frontend && pnpm run dev
```

**step3 · 配置 API Key**

- 方式一：WebUI → 侧边栏 → 头像 → API Key
- 方式二：编辑 `backend/.env.dev`，填写各 Agent 的 API 配置

运行结果输出在 `backend/project/work_dir/<task_id>/`：

- `notebook.ipynb`：运行过程中产生的代码
- `res.md`：最终论文（Markdown）
- `res.pdf`：编译后的论文（需 TeX 环境或点击「生成 PDF」）

自定义提示词模板：[md_template.toml](./backend/app/config/md_template.toml)

---

## 📄 版权与许可

- 本项目基于 [MathModelAgent](https://github.com/jihe520/MathModelAgent)（作者 [@jihe520](https://github.com/jihe520)）二次开发，**沿用上游许可证**（[License](./docs/md/License.md)）：个人免费使用，**请勿商业用途**，**禁止闭源分发**。
- 本仓库同样**保持开源**；如需商业使用，请联系**原作者**。
- 本仓库新增代码的改动与问题由二次开发者负责，请勿提交至上游仓库。

## 🙏 致谢

感谢上游作者 [@jihe520](https://github.com/jihe520) 及以下项目：

- [OpenCodeInterpreter](https://github.com/OpenCodeInterpreter/OpenCodeInterpreter/tree/main)
- [TaskWeaver](https://github.com/microsoft/TaskWeaver)
- [Code-Interpreter](https://github.com/MrGreyfun/Local-Code-Interpreter/tree/main)
- [Latex](https://github.com/Veni222987/MathModelingLatexTemplate/tree/main)
- [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
- [ai-manus](https://github.com/Simpleyyt/ai-manus)

> [!CAUTION]
> AI 生成内容仅供参考；本项目处于实验探索阶段，仍有许多待优化之处。
