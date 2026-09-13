<h1 align="center">🤖 MathModelAgent 📐</h1>
<p align="center">
    <img src="./docs/icon.png" height="250px">
</p>
<h4 align="center">
    专为数学建模设计的 Agent<br>
    自动完成数学建模，生成一份完整的可以直接提交的论文。
</h4>

<h5 align="center">简体中文 | <a href="README_EN.md">English</a></h5>

## 🌟 愿景：

3 天的比赛时间变为 1 小时
自动完整一份可以获奖级别的建模论文

<p align="center">
    <img src="./docs/chat.png">
    <img src="./docs/coder.png">
</p>

## ✨ 功能特性

- 🔍 自动分析问题，数学建模，编写代码，纠正错误，撰写论文
- 💻 Code Interpreter
  - local Interpreter: 基于 jupyter , 代码保存为 notebook 方便再编辑
  - 云端 code interpreter: [E2B](https://e2b.dev/) 和 [daytona](https://app.daytona.io/)
- 📝 生成一份编排好格式的论文
- 🤝 multi-agents: 建模手，代码手，论文手等
- 🔄 multi-llms: 每个 agent 设置不同的、合适的模型
- 🤖 支持所有模型: [litellm](https://docs.litellm.ai/docs/providers)
- 💰 成本低：workflow agentless，不依赖 agent 框架
- 🧩 自定义模板：prompt inject 为每个 subtask 单独设置需求
- 🌐 Web Search: Agent 自主搜索互联网获取真实数据（Tavily API）
- 📚 RAG 知识库: 从本地知识库检索建模方法、代码模板、论文写作参考（ChromaDB + Rerank）
- 🤝 HIL 人机协作: 关键节点暂停等待用户审批，支持 6 种决策动作（confirm / edit / regenerate / ask / skip / abort）
- 🛡️ 四层容错: 有限重试 → Fallback Hand Off → Evaluator Shadow Mode → Feedback Rerun

---

## 🛠️ 近期优化（Web 模式）

> 以下为二次开发过程中针对 **Web 模式**（`backend/` + `frontend/`）实现的改进，不影响 skills 模式。

### 🧠 建模与论文质量

- **结构化建模卡片** — 建模手每个子问题输出固定字段卡片（问题类型 / 目标函数 / 决策变量 / 约束条件 / 模型选择理由 / 求解方法 / 验证策略 / 可视化方案）。代码手拿到精确规格、写作手拿到完整素材，减少"一段话自由发挥"导致的理解偏差。
  `backend/app/core/prompts/modeler.py`
- **论文模板要素化** — 标题 / 摘要 / 问题重述 / 问题分析模板重写为「占位符要素框架」（如 `【模型名称】【关键量化结果】`），让模型知道每处该填什么、避免漏写关键信息。
  `backend/app/config/md_template.toml`（`firstPage` / `RepeatQues` / `analysisQues`）
- **补全近乎空壳的模板** — 灵敏度分析（参数选择 / 扰动设置 / 结果分析三段式）、模型评价（优点 ≥3 条用数据佐证 / 缺点 / 改进与推广）、参考文献（GB/T 7714 格式 + ≥8 篇 + 强制真实检索）。
  `backend/app/config/md_template.toml`（`sensitivity_analysis` / `judge` / `references`）

### 🔬 算法取舍铁律（建模意见.md 注入，优先级最高）

> 将「建模意见.md」的算法经验编译进建模手系统提示词，作为**高于决策树的取舍铁律**：决策树回答「该用哪类」，铁律回答「哪类不该用 + 如何创新拿奖」。已同步修正决策树中的三处冲突推荐，消除 AHP/熵权/模糊综合评价被误作首选推荐的问题。

- **十大避坑算法（尽量不用，除非题目数据强约束）** — AHP（主观赋权）、GM(1,1)（仅短期单变量可用）、BP 神经网络（小样本过拟合）、SVM（大样本慢、参数靠猜）、K-means（需预设 K、球形假设）、模糊综合评价（全主观可操控）、多元线性回归（无深度上限低）、朴素贝叶斯（独立性假设几乎不成立）、单棵决策树 ID3/C4.5（过拟合，已被集成取代）、熵权法单独用（极端值主导权重）。
  **高优先级替代**：CRITIC / TOPSIS / VIKOR / 灰色关联 / LightGBM / XGBoost / DBSCAN / 层次聚类 / 高斯混合模型。
  `backend/app/core/prompts/modeler.py`
- **十大国奖级模型创新方向（加分项，主动沾边）** — 参数自适应优化、多模型对比择优、求解算法升级、同领域模型融合、跨领域交叉迁移、机理+数据双驱动、数据预处理与特征工程、模型检验与不确定性量化、动态时变与多阶段递推、多目标协同与分层决策（Pareto/双层规划替代加权求和）。
  `backend/app/core/prompts/modeler.py`
- **红线警告（防炫技）** — 求解算法升级**绝对禁止**在能用精确解（线性规划 / Dijkstra）时强行用遗传算法或模拟退火去"创新"，会被评委视为炫技、不专业；该创新仅限 **NP-hard 问题或大规模非线性优化**。
  `backend/app/core/prompts/modeler.py`

### 📊 图表质量

- **绘图配色统一** — 色板改为柔和色板（柔蓝 `#5B9BD5` / 珊瑚粉 `#ED7D7D` / 薄荷绿 `#7BC8A4` / 浅灰 `#B0B0B0` / 淡紫 `#9B8EC4` / 暖杏 `#F4A261`），在 `matplotlib_setup.py` 全局注入，改一处全局生效。
  `backend/app/tools/matplotlib_setup.py`
- **视觉反馈闭环（修复）** — 原先仅 iopub 输出触发视觉评估，`plt.savefig` 保存的图约 87% 未被评估。改为文件层 MD5 快照扫描，任何新保存的图都会被视觉模型评估；不达标时 `[REDRAW_REQUIRED]` 触发强制重绘（上限 `MAX_REDRAW_ROUNDS`，默认 2 次）。
  `backend/app/tools/base_interpreter.py`、`local_interpreter.py`、`e2b_interpreter.py`、`core/agents/coder_agent.py`、`config/setting.py`
- **视觉评估增强** — 评估 prompt 增加 6 维度打分（坐标轴 / 图例 / 数据可读性 / 配色 / 清晰度 / 整体），输出「评分：X/10」；`should_retry` 改为评分门控（<7 重绘）+ 关键词兜底两级判定，判断更准确。
  `backend/app/tools/vision_service.py`
- **视觉一致性核对（图 vs 代码手自述）** — 视觉模型不再只看图打分：解释器解析代码手输出的【图片元数据】卡，取可核实的关键字段（图表类型 / 数据来源 / 核心结论，`文件名`仅用于匹配、`适用章节`图里看不出故略）作为「自述」随图一起送审；视觉模型新增 `[一致性]` 段逐条核对自述与图中实际是否吻合，**判定不一致时评分不得超过 5/10**，且 `should_retry` 以一致性为最高优先级硬门控（不一致直接重绘，即使画质 9 分）。无元数据卡时自动退化为纯质量审查，不误判。可抓出"画质合格但内容说错"的问题（自述散点图实为柱状图、自述上升实为下降、坐标轴与自述变量不符等）。
  `backend/app/tools/vision_service.py`、`base_interpreter.py`、`local_interpreter.py`、`core/agents/coder_agent.py`
- **图片元数据卡 + 数据特征卡** — 代码手每张图输出元数据卡（文件名 / 图表类型 / 数据来源 / 核心结论 / 适用章节），结果汇总输出本子任务图片清单，让写作手精准引用图片、写出与图一致的分析，告别"只放图不解释"。
  `backend/app/core/prompts/coder.py`

### 📚 文献集成

- **OpenAlex 深度集成** — 写作手 `search_papers` 由单次改为可循环多次检索（上限 5 次），支持综述 / 参考文献分主题检索；参考文献与研究综述强制基于真实检索（含作者 / 年份 / 标题 / DOI）撰写，禁止凭记忆编造。
  `backend/app/core/agents/writer_agent.py`、`core/prompts/writer.py`、`config/md_template.toml`

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

代码执行层增加超时中断与「复杂度预审 → 反思 → 终极妥协」状态机，防止高耗时算法（蒙特卡洛/网格搜索等）无限卡死任务：

- **执行超时分档** — 普通代码默认 180s（画图/读数据/EDA）；计算密集型（命中慢算法特征或首行 `# [EXEC_TYPE: COMPUTE]` 标记）用 600s。超时后重启 Jupyter 内核（SIGINT 停不掉原生计算）并返回 `[EXEC_TIMEOUT]` 触发反思流程。档位可在 `.env` 调（`EXEC_TIMEOUT_NORMAL` / `EXEC_TIMEOUT_COMPUTE`）。
  `backend/app/tools/local_interpreter.py`、`config/setting.py`、`.env.dev`
- **复杂度预审** — 提交计算密集型代码前先估算时间复杂度和数据规模（O(n³) n>5000、蒙特卡洛样本数、网格搜索组合数），铁定超时直接跳过首次执行、先进反思优化。
  `backend/app/core/prompts/coder.py`
- **结构化反思 + 终极妥协（精度受限求解）** — 超时后按四步诊断（瓶颈定位→复杂度分析→优化方案→方案落地）并输出结构化 JSON（bottleneck / complexity / strategy / implementation / expected_speedup / round / fallback_needed）；反思达 2 次仍超时则执行「精度受限求解」：保留模型结构、只降计算量（粗网格/分层降采样/贝叶斯 20 次），并给出可计算的误差度量（置信区间/偏差/MAPE）；实在无法可信求解则输出 `[MODEL_SCHEME_INFEASIBLE]` 交给建模手修订，严禁整体换成线性近似当答案。
  `backend/app/core/agents/coder_agent.py`、`core/prompts/coder.py`
- **LLM 调用超时（互补修复）** — provider 加 `timeout=300` + `max_retries=0` 关闭 SDK 隐式重试；`llm.py` 重试间隔改 `await asyncio.sleep` 不阻塞事件循环。与执行层超时互补，彻底消除「模型调用 / 代码运行」两类卡死。
  `backend/app/core/llm/llm.py`、`core/llm/providers/*`

### 🔧 数据链路修复

- **`get_model_build_solve` 脏数据** — 原输出 Python 字典字面量（`{'response_content':...,'footnotes':...}`）被注入写作 prompt，导致摘要 / 总结引用脏数据。改为只提取 `response_content`，干净输出「问题N：正文」格式。
  `backend/app/models/user_output.py`
- **JSON 解析容错增强** — 模型输出含未转义 ASCII 双引号导致 `json.loads` 失败；新增 `get_json_error_feedback` 展示出错位置片段 + 显式引号规则；并修复协调手 `json_str` 潜在 `UnboundLocalError`。
- **子目录递归扫描（修复）** — 大模型自建 `figures/`、`cleaned_data/` 等子目录存放图片/清洗后数据时，原 `os.listdir` 只扫根目录，导致视觉评估与图片/数据登记全部失效。改为 `os.walk` 递归，返回带相对路径（如 `figures/q1.png`）；`get_current_files("data")` 同时排除产物（`res.md/res.docx/notebook.ipynb`）。
  `backend/app/tools/base_interpreter.py`、`local_interpreter.py`、`utils/common_utils.py`
- **附件类型扩展 — 支持 PDF/DOCX** — 附件上传从 txt/csv/xlsx 扩展支持 `.pdf` `.docx`；代码手首次运行按类型分组列出数据文件与题目文档，检测到 PDF/DOCX 时注入读取指引（`fitz` 提取 PDF 文本 / `python-docx` 读取段落 / 表格提取）。新增 `python-docx` 依赖。
  `frontend/src/components/UserStepper.vue`、`backend/app/core/agents/coder_agent.py`、`utils/common_utils.py`、`pyproject.toml`
  `backend/app/core/prompts/shared.py`、`__init__.py`、`core/agents/coordinator_agent.py`、`modeler_agent.py`

### 🖥️ 前端修复

- **历史任务空白** — 组件常驻挂载导致 `onMounted` 仅在 `open=false` 时触发一次、`loadTasks` 永不执行；改为 `watch(() => props.open, ...)`，每次打开重新加载。
  `frontend/src/components/TaskHistory.vue`
- **API 配置列表为空 / 切换不回填** — 同样 `onMounted` 问题，改为 `watch`；配套新增 `loadConfigIntoStore`，切换配置方案后回填表单，避免误点"保存"覆盖新方案。
  `frontend/src/pages/chat/components/ApiDialog.vue`、`src/stores/apiKeys.ts`

### ⚠️ 已知问题（未修复）已修复

- **524 Cloudflare 超时阻塞** — 中转站返回 524，SDK 隐式重试 × 120s ≈ 6 min/次，`time.sleep` 阻塞事件循环，重试 10 次可阻塞近 1 小时。属中转站性能问题，暂未修复（可切换国内 `config1` 方案规避）。

---

---

我在平台中托管了一个在线版本，方便使用，欢迎体验：

https://mathmodel.top/home

## SKILLS

项目蒸馏成完全由 SKILLS 驱动
不再做 Harness 层

### Intro

MathModelAgent SKILL —— 直接在 Harness 中驱动的数学建模自动化方案.

**💰 开源免费，接入任意模型**
完全开源免费，可接入任何模型。

**🧠 端到端自动化**
从问题分析、建模、编码、绘图到论文排版和验收，一条 `/1start-mathmodel` 命令全自动完成，中间阶段自动串联，无需人工干预。

**📄 17 套 Typst 论文模板**
内置中英文主流赛事模板（国赛、华数杯、华为杯、MCM/ICM 等），自动匹配赛事类型，生成排版精良、可直接提交的 PDF 论文。

**📐 内置建模知识库**
包含完整的建模规范、模型选择决策树（AHP、TOPSIS、ARIMA、GA 等）、常见易错模式和 MCM/ICM 评分标准，每个阶段自动参考，降低模型幻觉。

**✅ 9 步自动验收**
文本泄漏检测 → 数值一致性校验 → Typst 编译 → PDF 可视化检查，确保论文零低级错误。

**🔧 可组合、可扩展**
每个阶段是独立 Skill，可单独调用（如只跑分析、只写论文）；模板和知识库可自由扩展；支持 Typst 生态排版。

skills 中包含一个科研绘图模板skill,可以绘制一些炫酷的科研图表

![figure](./docs/figure_templates.png)

### Install & Usage

安装 SKILL

```
npx skills add jihe520/MathModelAgent --all
```

运行

```
// claude
claude --dangerously-skip-permissions
claude: /1start-mathmodel 完成这个数学建模任务

// codex
codex --yolo
codex: $start-mathmodel 完成这个数学建模任务
```

其他命令

```
/doctor:  检查环境配置
/typst-author: typst 知识
```

### What Can You Contribute?

项目以后只会做 SKLLS 层的迭代和优化，不会再做其他部分。

如果你希望寻找 Agent 开发岗位，你可以研究该项目 Agent 设计并贡献，我会尽量合并.

你能做什么：

- 优化贡献比赛 typst Template , 你可以找一些 LaTeX 转成 typst
- 优化 SKILL Workflow
- 在不同的 Harness 上测试 不同的 LLM, 提供反馈和案例放在 example 仓库

Harness SKILL 的优化需要大量黑盒测试和调优.

### Thinking

- 两年前，我做了一个 Mulit-Agent 的数学建模项目并开源出来，收到了社区的欢迎和很多 star, 感谢大家支持。
- 感谢开源的 latex 模板，我在此基础上转化为 typst 模板
- 此 SKILL 是一个基础模板，你可以基于此构建更适合你自己的 MathModel SKILL
- For Agent DEVs : 两年前，我都是自己实现一套 Agent 框架，现在和以后更多的 Agent 产品直接基于 Harness 如 Codex / Claude Code / Pi  + SKILLS 来构建

---

---

## 🚀 后期计划

- [X] 添加并完成 webui、cli
- [X] 完善的教程、文档
- [ ] 提供 web 服务
- [ ] 英文支持（美赛）
- [ ] 集成 latex 模板
- [X] 接入视觉模型（视觉反馈闭环：画图 → 视觉评估 → 强制重绘）
- [X] 添加正确文献引用
- [X] 更多测试案例
- [X] docker 部署
- [ ] human in loop ( HIL ): 关键节点暂停等待用户审批，支持 6 种决策动作（confirm/edit/regenerate/ask/skip/abort）
  <!-- TODO: 数据模型已实现，但工作流集成不完整 -->
- [ ] feedback: 评估器评分 + 反馈注入重跑，先 Writer 后 Coder
  <!-- TODO: 核心逻辑未实现，仅有 Agent 基类中的 TODO 注释 -->
- [X] codeinterpreter 接入云端 如 e2b 等供应商..
- [ ] 多语言: R 语言, matlab
- [ ] 绘图 napki,draw.io,plantuml,svg, mermaid.js
- [ ] 添加 benchmark
- [ ] web search tool: Tavily API 搜索互联网获取真实数据
  <!-- NOTE: 原计划 Tavily API 未实现，当前使用 OpenAlex 替代 -->
- [ ] RAG 知识库: ChromaDB + Rerank 检索建模方法、代码模板、论文写作参考
  <!-- TODO: 仅配置项存在，核心检索逻辑未实现 -->
- [ ] A2A hand off: Fallback 自动切换备用模型 + 有限重试 + Evaluator Shadow Mode
  <!-- TODO: 配置项和核心逻辑均未实现，仅有基础重试机制 -->
- [ ] chat / agent mode

## 视频demo

<video src="https://github.com/user-attachments/assets/954cb607-8e7e-45c6-8b15-f85e204a0c5d"></video>

> [!CAUTION]
> 项目处于实验探索迭代demo阶段，有许多需要改进优化改进地方，我(项目作者)很忙，有时间会优化更新
> 欢迎贡献

## 📖 使用教程

提供三种部署方式，请选择最适合你的方案：

1. [docker(最简单)](#-方案一docker-部署推荐最简单)
2. [本地部署](#-方案二-本地部署)
3. [脚本本地部署(社区)](#-方案三自动脚本部署来自社区)

下载项目

```bash
git clone https://github.com/jihe520/MathModelAgent.git # 克隆项目
```

> 如果你想运行 命令行版本 cli 切换到 [master](https://github.com/jihe520/MathModelAgent/tree/master) 分支,部署更简单，但未来不会更新

### 🐳 方案一：Docker 部署（推荐：安全简单）

> 确保电脑安装了 docker 环境

1. 启动服务

在项目文件夹下运行:

```bash
docker-compose up
```

2. 访问

现在你可以访问：

- 前端界面：http://localhost:5173
- 后端API：http://localhost:8000

3. 配置

侧边栏 -> 头像 -> API Key

### 💻 方案二: 本地部署（推荐项目开发者部署）

> 确保电脑中安装好 Python, Nodejs, **Redis** 环境

#### step1:安装依赖

1. 下载Redis(记得设置环境变量redis_path)

- windows 下载地址：[https://github.com/tporadowski/redis/releases](https://github.com/tporadowski/redis/releases)
- linux or mac 下载地址：[https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/)

2. 安装后端依赖

```bash
# ============ 安装依赖 ============
# 1. 切换到 backend 目录
cd backend
# 2. 安装 uv 包管理器（推荐）
pip install uv
# 3. 同步项目依赖
uv sync
```

```bash
# ============ MacOS / Linux 安装命令 ============
# 1. 设置环境变量
export ENV=DEV
export REDIS_URL=redis://localhost:6379/0
```

```powershell
# ============ Windows PowerShell 安装命令 ============
# 1. 设置环境变量
$env:ENV="DEV"
$env:REDIS_URL="redis://localhost:6379/0"
# 2. 设置 PowerShell 执行策略策略为 RemoteSigned
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
# 3. 创建虚拟环境
python -m venv venv
```

3.安装前端依赖

```bash
cd frontend # 切换到 frontend 目录下
npm install -g pnpm
pnpm i
```

#### step2:启动项目

**windows用户直接双击运行项目中的win_start.bat 即可启动项目**

1.启动 Redis

```bash
redis-server
```

2.启动后端

```bash
# ============ MacOS / Linux 安装命令 ============
# 1. 激活虚拟环境
source .venv/bin/activate
# 2. 启动后端服务（激活后可直接使用 uvicorn 命令）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload
```

```bash
# ============ Windows PowerShell 安装命令 ============
# 1. 切换到 backend 目录
cd .\backend\
# 2. 激活虚拟环境
.\venv\Scripts\Activate.ps1
# 3. 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload
```

3.启动前端

```bash
cd .\frontend\
pnpm run dev
```

修改 backend/.env.dev 的环境变量 **REDIS_URL**

配置API Key

1. 使用 WebUI
    侧边栏 -> 头像 -> API Key
2. 修改 backend/.env.dev 文件
    先将.env.example文件 改为.env.dev
    然后在.env.dev中 修改各 Agent API 配置

### 🚀 方案三：自动脚本部署（来自社区）

有没有自动部署的脚本 ？
[mmaAutoSetupRun](https://github.com/Fitia-UCAS/mmaAutoSetupRun)

[教程](./docs/md/tutorial.md)

运行的结果和产生在 `backend/project/work_dir/xxx/*`目录下

- notebook.ipynb: 保存运行过程中产生的代码
- res.md: 保存最后运行产生的结果为 markdown 格式

需要自定义自定义提示词模板 template ？
Prompt Inject : [prompt](./backend/app/config/md_template.toml)

网络状况太差难以配置Docker等设置？
网络不畅时的配置过程示例：[网络环境极差时的MathModelAgent配置过程](docs/md/网络环境极差时的MathModelAgent配置过程.md)

## ⚙️ 新功能配置

MathModelAgent 支持以下可选功能，默认已关闭，开启后未配置外部依赖时自动降级跳过。详见 [升级说明](./升级说明.md)。

| 功能                 | 配置开关                                | 说明                                                    |
| -------------------- | --------------------------------------- | ------------------------------------------------------- |
| Web Search           | `SEARCH_ENABLED` + `TAVILY_API_KEY` | Agent 自主联网搜索真实数据（Tavily API）                |
| RAG 知识库           | `RAG_ENABLED`                         | 从本地知识库检索建模方法和代码模板（ChromaDB + Rerank） |
| HIL 人机协作         | `HIL_ENABLED`                         | 关键节点暂停等待用户审批，支持 6 种决策动作             |
| Fallback Hand Off    | `FALLBACK_*` 系列                     | 主模型故障自动切换备用模型                              |
| Evaluator + Feedback | `EVALUATOR_*` 系列                    | 输出质量评估 + 反馈重跑                                 |

快速启用 Web Search：注册 [Tavily](https://tavily.com) 获取 API Key，在 `backend/.env.dev` 中设置 `TAVILY_API_KEY=tvly-xxx`。

## 🤝 贡献和开发

[DeepWiki](https://deepwiki.com/jihe520/MathModelAgent) | [Zread](https://zread.ai/jihe520/MathModelAgent)

> [!TIP]
> 如果你有跑出来好的案例可以提交 PR 在该仓库下:
> [MathModelAgent-Example](https://github.com/jihe520/MathModelAgent-Example)

- 项目处于**开发实验阶段**（我有时间就会更新），变更较多，还存在许多 Bug，我正着手修复。
- 希望大家一起参与，让这个项目变得更好
- 非常欢迎使用和提交  **PRs** 和 issues
- 需求参考 后期计划

clone 项目后，下载 **Todo Tree** 插件，可以查看代码中所有具体位置的 todo

`.cursor/*` 有项目整体架构、rules、mcp 可以方便开发使用

## 📄 版权License

个人免费使用，请勿商业用途，商业用途联系我（作者）

[License](./docs/md/License.md)

## 🙏 Reference

Thanks to the following projects:

- [OpenCodeInterpreter](https://github.com/OpenCodeInterpreter/OpenCodeInterpreter/tree/main)
- [TaskWeaver](https://github.com/microsoft/TaskWeaver)
- [Code-Interpreter](https://github.com/MrGreyfun/Local-Code-Interpreter/tree/main)
- [Latex](https://github.com/Veni222987/MathModelingLatexTemplate/tree/main)
- [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
- [ai-manus](https://github.com/Simpleyyt/ai-manus)

## 其他

### 💖 Sponsor

[☕️ 给作者买一杯咖啡](./docs/md/sponser.md)

https://linux.do/

#### 企业

<div align="center">
    <a href="https://share.302.ai/UoTruU" target="_blank">
    <img src="./docs/302ai.jpg">
    </a>
</div>

[302.AI](https://share.302.ai/UoTruU) 是一个按用量付费的企业级AI资源平台，提供市场上最新、最全面的AI模型和API，以及多种开箱即用的在线AI应用

#### 用户

[danmo-tyc](https://github.com/danmo-tyc)

### 👥 GROUP

有问题可以进群问

点击链接加入腾讯频道【MathModelAgent】：https://pd.qq.com/s/7rfbai3au

点击链接加入群聊 779159301【MathModelAgent】：https://qm.qq.com/q/Fw2cCJPoki

[Discord](https://discord.gg/3Jmpqg5J)

> [!CAUTION]
> 免责声明: 注意，AI 生成仅供参考，目前水平直接参加国赛获奖是不可能的，但我相信 AI 和 该项目未来的成长。
