"""代码优化案例库：按需匹配注入到反思 prompt。

执行超时/性能瓶颈的典型优化 few-shot 示例，供代码手反思时参考具体优化思路
与结构化反思 JSON 的格式。只在实际触发超时/性能场景时按特征匹配注入，
避免在默认系统提示中常驻占用上下文。

注意：示例内含代码片段（带 `{var}` 花括号），一律用普通字符串而非 f-string 承载，
避免外层字符串与示例代码的花括号冲突。
"""

import json

# CASES: key -> 完整 teaching case。
# 每个 case 含 title/bottleneck/speedup/before(原代码)/reflection(反思JSON)/after(优化后代码)。
CASES: dict[str, dict] = {
    "monte_carlo": {
        "title": "蒙特卡洛优化(降采样 + 分层)",
        "bottleneck": "Python 循环执行大量随机采样，串行耗时过长",
        "speedup": "10-100x(降采样 + 并行)",
        "before": """# [EXEC_TYPE: COMPUTE]
# 复杂度预审：N=1000000 样本，单次 0.01s → 总计 10000s，必超时
results = []
for _ in range(1000000):  # 百万次模拟
    sim = simulate_once(params)
    results.append(sim)
mean_result = np.mean(results)""",
        "reflection": {
            "bottleneck": "第3-5行 百万次 simulate_once 串行调用",
            "complexity": "O(N), N=1000000, 单次0.01s → 理论10000s",
            "strategy": "数据降采样 + 分层抽样保证代表性",
            "implementation": "降至 N=10000(1% 采样)，分层抽样关键参数区间，并行化剩余样本",
            "expected_speedup": "100倍(10000样本 + 并行4核 → 约25s)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# [EXEC_TYPE: COMPUTE]
# 优化：降采样至 1% + 分层抽样 + 并行化
from joblib import Parallel, delayed

# 分层抽样：关键参数区间各抽 1000 样本
param_ranges = np.linspace(param_min, param_max, 10)
samples_per_layer = 1000
results = Parallel(n_jobs=4)(
    delayed(simulate_once)(p)
    for layer in param_ranges
    for p in np.random.uniform(layer, layer + step, samples_per_layer)
)
mean_result = np.mean(results)
print(f"【优化】采样降至 {len(results)} 样本(分层抽样)，预计误差 ±5%，实际耗时 {elapsed:.1f}s")""",
    },

    "grid_search": {
        "title": "网格搜索替换为贝叶斯优化",
        "bottleneck": "GridSearchCV 穷举所有参数组合，组合数 × CV 折数过多",
        "speedup": "20x(贝叶斯优化 20 次 vs 405 次)",
        "before": """# 复杂度预审：GridSearchCV 5折 × 3^4=81 组合 × 单次 30s → 12150s，必超时
from sklearn.model_selection import GridSearchCV
param_grid = {
    'n_estimators': [100, 500, 1000],
    'max_depth': [5, 10, 15],
    'learning_rate': [0.01, 0.1, 0.3],
    'subsample': [0.6, 0.8, 1.0]
}
grid = GridSearchCV(XGBRegressor(), param_grid, cv=5)
grid.fit(X_train, y_train)""",
        "reflection": {
            "bottleneck": "GridSearchCV 81组合 × 5折 = 405 次完整训练",
            "complexity": "O(组合数 × CV折数), 81×5×30s = 12150s",
            "strategy": "算法替换：网格搜索 → 贝叶斯优化(optuna 20次迭代)",
            "implementation": "用 optuna TPE 采样器，20 次迭代找到近似最优，耗时 < 600s",
            "expected_speedup": "20倍(20次 vs 405次)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# [EXEC_TYPE: COMPUTE]
# 优化：贝叶斯优化替代网格搜索
import optuna

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'max_depth': trial.suggest_int('max_depth', 5, 15),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0)
    }
    model = XGBRegressor(**params)
    scores = cross_val_score(model, X_train, y_train, cv=3, scoring='neg_mean_squared_error')
    return -scores.mean()

study = optuna.create_study(direction='minimize')
study.optimize(objective, n_trials=20, timeout=480)
best_params = study.best_params
print(f"【优化】贝叶斯优化 20 次迭代，最优参数: {best_params}")""",
    },

    "distance_matrix": {
        "title": "三重循环向量化(矩阵运算)",
        "bottleneck": "三重循环计算距离矩阵，O(n³) Python 解释器开销极大",
        "speedup": "1000倍(numpy/scipy C 实现 vs Python 循环)",
        "before": """# 复杂度预审：O(n³), n=5000 → 1.25e11 次，Python 必超时
distance_matrix = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        for k in range(dim):
            distance_matrix[i, j] += (data[i, k] - data[j, k]) ** 2
        distance_matrix[i, j] = np.sqrt(distance_matrix[i, j])""",
        "reflection": {
            "bottleneck": "第3-6行 三重循环计算欧氏距离矩阵",
            "complexity": "O(n²×dim), n=5000, dim=10 → 2.5e8 次 Python 循环",
            "strategy": "向量化：三重循环 → numpy 广播 + cdist",
            "implementation": "用 scipy.spatial.distance.cdist 一行完成，C 底层实现",
            "expected_speedup": "1000倍(numpy/scipy C 实现 vs Python 循环)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# 优化：向量化计算距离矩阵
from scipy.spatial.distance import cdist

distance_matrix = cdist(data, data, metric='euclidean')
print(f"【优化】向量化计算 {n}×{n} 距离矩阵，耗时 {elapsed:.2f}s(原三重循环需 >1000s)")""",
    },

    "qmc_sampling": {
        "title": "拟蒙特卡洛(QMC)替代真随机",
        "bottleneck": "真随机数空间覆盖不均匀，收敛慢需大量样本",
        "speedup": "3-10倍收敛速度提升",
        "before": """# [EXEC_TYPE: COMPUTE]
# 真随机蒙特卡洛：1万样本收敛慢
import numpy as np
samples = np.random.uniform(low, high, size=(10000, dim))
results = [simulate(s) for s in samples]
mean_result = np.mean(results)""",
        "reflection": {
            "bottleneck": "真随机数空间覆盖不均匀，尾部区域采样不足",
            "complexity": "收敛速度 O(1/√N)，需大量样本才能稳定",
            "strategy": "算法替换：真随机 → 拟蒙特卡洛(Sobol/Halton 低差异序列)",
            "implementation": "用 scipy.stats.qmc.Sobol 生成确定性低差异序列，空间覆盖更均匀",
            "expected_speedup": "3-10倍收敛速度提升(从 O(1/√N) 提升至接近 O(1/N))",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# [EXEC_TYPE: COMPUTE]
# 优化：拟蒙特卡洛(低差异序列)
from scipy.stats import qmc

sampler = qmc.Sobol(d=dim, scramble=True)
samples_unit = sampler.random(n=2000)  # 仅需 2000 样本(原需 1万)
samples = qmc.scale(samples_unit, low, high)  # 缩放到目标区间
results = [simulate(s) for s in samples]
mean_result = np.mean(results)
print(f"【优化】拟蒙特卡洛 Sobol 序列，{len(samples)} 样本达到原 1万样本精度，耗时 {elapsed:.1f}s")""",
    },

    "joblib_parallel": {
        "title": "并行化 + 向量化组合(joblib + NumPy)",
        "bottleneck": "外层串行 + 内层 Python 循环双重瓶颈",
        "speedup": "64倍(8核并行 × 8倍向量化)",
        "before": """# [EXEC_TYPE: COMPUTE]
# 复杂度预审：外层 1000 次独立任务 × 内层 10000 维计算 × 单次 0.5s → 500s
results = []
for task_id in range(1000):  # 1000 个独立参数组合
    param = param_list[task_id]
    sim_results = []
    for i in range(10000):
        sim_results.append(complex_function(param, i))
    results.append(np.mean(sim_results))""",
        "reflection": {
            "bottleneck": "外层串行 + 内层 Python 循环双重瓶颈",
            "complexity": "O(外层任务数 × 内层样本数), 1000×10000×0.00005s = 500s",
            "strategy": "双重优化：外层 joblib 并行 + 内层 numpy 向量化",
            "implementation": "用 joblib 把 1000 任务分给 8 核并行，每个任务内部向量化消除内循环",
            "expected_speedup": "64倍(8核并行 × 8倍向量化)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# [EXEC_TYPE: COMPUTE]
# 优化：joblib 并行 + NumPy 向量化
from joblib import Parallel, delayed
import numpy as np

def task_vectorized(param):
    # 向量化任务实现，用 numpy 一次性算完内层 10000 维
    indices = np.arange(10000)
    sim_results = complex_function_vectorized(param, indices)
    return np.mean(sim_results)

# 外层并行：1000 任务分给所有 CPU 核心
results = Parallel(n_jobs=-1, verbose=5)(
    delayed(task_vectorized)(param_list[i]) for i in range(1000)
)
print(f"【优化】并行化 {len(results)} 任务(8核)+ 内层向量化，耗时 {elapsed:.1f}s(原需 500s)")""",
    },

    "numba_jit": {
        "title": "Numba JIT 编译(无法向量化的复杂逻辑)",
        "bottleneck": "嵌套循环 + 复杂条件分支，Python 解释器开销极大",
        "speedup": "50-100倍(JIT 编译 + 自动并行)",
        "before": """# 复杂度预审：嵌套循环 + 复杂条件判断，无法向量化，预计 >300s
def simulate_complex_logic(n_steps, n_particles):
    states = np.zeros((n_steps, n_particles))
    for t in range(n_steps):
        for p in range(n_particles):
            if states[t-1, p] > threshold:
                states[t, p] = complex_rule_A(states[t-1, p])
            else:
                states[t, p] = complex_rule_B(states[t-1, p])
    return states

result = simulate_complex_logic(10000, 5000)""",
        "reflection": {
            "bottleneck": "嵌套循环 + 条件分支，Python 解释器开销极大",
            "complexity": "O(n_steps × n_particles), 10000×5000 = 5e7 次 Python 循环",
            "strategy": "Numba JIT 即时编译：将 Python 代码编译为机器码",
            "implementation": "用 @njit 装饰器，开启 parallel=True 自动并行",
            "expected_speedup": "50-100倍(JIT 编译 + 自动并行)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# [EXEC_TYPE: COMPUTE]
# 优化：Numba JIT 编译 + 自动并行
from numba import njit, prange

@njit(parallel=True)  # JIT 编译 + 自动并行化
def simulate_complex_logic_jit(n_steps, n_particles, threshold):
    states = np.zeros((n_steps, n_particles))
    for t in range(1, n_steps):
        for p in prange(n_particles):  # prange 自动并行
            if states[t-1, p] > threshold:
                states[t, p] = complex_rule_A(states[t-1, p])
            else:
                states[t, p] = complex_rule_B(states[t-1, p])
    return states

result = simulate_complex_logic_jit(10000, 5000, threshold)
print(f"【优化】Numba JIT 编译 + 自动并行，耗时 {elapsed:.1f}s(原纯 Python 需 >300s)")""",
    },

    "nested_loop": {
        "title": "嵌套循环优化",
        "bottleneck": "多重嵌套循环导致 O(n²) 或 O(n³) 复杂度",
        "speedup": "20-100x(NumPy 广播)",
        "before": """# 复杂度预审：O(n²), n=20000 → 4e8 次，Python 必超时
for i in range(n):
    for j in range(n):
        if condition(i, j):
            result[i] += compute(data[j])""",
        "reflection": {
            "bottleneck": "第2-4行 双重循环逐元素计算，Python 解释器开销大",
            "complexity": "O(n²), n=20000 → 4e8 次 Python 循环",
            "strategy": "向量化：双重循环 → NumPy 广播/掩码矩阵",
            "implementation": "用 np.meshgrid 或广播构造掩码，一次矩阵运算替代逐元素循环",
            "expected_speedup": "20-100倍(NumPy C 实现 vs Python 循环)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# 优化：NumPy 广播向量化
mask = data  # 预先构造条件掩码
result = (mask * data).sum(axis=1)  # 一次矩阵运算""",
    },

    "large_dataframe": {
        "title": "大 DataFrame 迭代优化",
        "bottleneck": "逐行 iterrows 迭代 pandas DataFrame，Python 循环耗时极大",
        "speedup": "100-1000x(向量化列运算)",
        "before": """# 复杂度预审：DataFrame 100万行，iterrows 逐行 Python 循环，必超时
for idx, row in df.iterrows():
    df.loc[idx, 'result'] = row['a'] * row['b'] + row['c']""",
        "reflection": {
            "bottleneck": "第2-3行 iterrows 逐行迭代 + 单点赋值双重开销",
            "complexity": "O(N), N=100万行 → 100万次 Python 循环",
            "strategy": "向量化：逐行迭代 → 整体列运算/apply",
            "implementation": "df['result'] = df['a'] * df['b'] + df['c']，复杂逻辑用 df.apply 或分块",
            "expected_speedup": "100-1000倍(向量化列运算 vs 逐行 Python)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# 优化：整体列运算
df['result'] = df['a'] * df['b'] + df['c']  # 直接列运算
# 若需复杂逻辑：df['result'] = df.apply(lambda x: func(x), axis=1)""",
    },

    "optimization_solver": {
        "title": "优化求解器选择",
        "bottleneck": "错误使用通用优化器求解线性/凸问题，慢且不稳定",
        "speedup": "100-1000x(精确解法)",
        "before": """# 复杂度预审：differential_evolution 迭代数千次，且不保证收敛，预计 >60s
from scipy.optimize import differential_evolution
result = differential_evolution(objective, bounds)  # 慢且不稳定""",
        "reflection": {
            "bottleneck": "用通用启发式优化器(differential_evolution)求解线性/凸规划",
            "complexity": "遗传算法需数千次迭代，且可能不收敛",
            "strategy": "算法替换：通用优化器 → 精确求解(linprog/cvxpy)",
            "implementation": "线性/凸问题用 scipy.optimize.linprog 或 cvxpy 精确求解，一次性收敛",
            "expected_speedup": "100-1000x(精确解 vs 启发式迭代)",
            "round": "1",
            "fallback_needed": False,
        },
        "after": """# 优化：精确解法
from scipy.optimize import linprog
result = linprog(c, A_ub=A, b_ub=b, bounds=bounds)  # 精确高效
# 若非线性凸优化：使用 cvxpy""",
    },
}


def match_cases(code: str, max_cases: int = 2) -> list[dict]:
    """根据代码特征返回最相关的 1-2 个完整优化案例（含反思 JSON 示范）。

    Args:
        code: 用户当前执行的代码片段。
        max_cases: 最多返回案例数（默认 2，防止 prompt 过长）。

    Returns:
        匹配的案例列表，每个案例含 title/bottleneck/before/reflection/after/speedup。
    """
    matched: list[dict] = []

    if "GridSearchCV" in code or "RandomizedSearchCV" in code:
        matched.append(CASES["grid_search"])

    if any(x in code for x in ("random.uniform", "np.random", "monte_carlo", "模拟")):
        matched.append(CASES["monte_carlo"])

    if "iterrows" in code or "itertuples" in code:
        matched.append(CASES["large_dataframe"])

    if "np.linalg.norm" in code and "for i in range" in code and "for j in range" in code:
        matched.append(CASES["distance_matrix"])

    if code.count("for ") >= 2 and "    for " in code:
        matched.append(CASES["nested_loop"])

    if any(x in code for x in ("differential_evolution", "genetic", "遗传算法", "模拟退火")):
        if "linprog" not in code and "线性" in code:
            matched.append(CASES["optimization_solver"])

    if any(x in code for x in ("qmc", "Sobol", "Halton", "低差异")):
        matched.append(CASES["qmc_sampling"])

    if any(x in code for x in ("numba", "njit")):
        matched.append(CASES["numba_jit"])

    # 去重并限制数量
    seen: set[str] = set()
    unique: list[dict] = []
    for case in matched:
        if case["title"] not in seen:
            seen.add(case["title"])
            unique.append(case)
            if len(unique) >= max_cases:
                break

    return unique


def format_cases(cases: list[dict]) -> str:
    """把匹配到的案例渲染成 few-shot markdown 块，供注入反思 prompt。

    Args:
        cases: match_cases 返回的案例列表。

    Returns:
        可直接拼接到反思 prompt 的 markdown 字符串；空列表返回空串。
    """
    if not cases:
        return ""

    blocks: list[str] = []
    for idx, case in enumerate(cases, 1):
        # 带外层 "reflection" 包裹，与 CODER_PROMPT 要求的标准输出格式一致。
        reflection_json = json.dumps(
            {"reflection": case["reflection"]}, ensure_ascii=False, indent=2
        )
        blocks.append(
            f"### 优化示例{idx}：{case['title']}\n\n"
            f"**原代码(超时/低效)：**\n```python\n{case['before']}\n```\n\n"
            f"**收到反思，结构化 JSON：**\n```json\n{reflection_json}\n```\n\n"
            f"**优化后代码：**\n```python\n{case['after']}\n```\n\n"
            f"**预计加速：{case['speedup']}**"
        )

    return "\n\n---\n\n".join(blocks) + "\n"
