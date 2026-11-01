"""问题编译器：把"齿轮设计问题"翻译成纯数学优化器能理解的 Problem。

优化器本身不知道齿轮；齿轮知识只在这里（变量含义）和公式库（物理关系）里。
"""
from __future__ import annotations

from ..kernel.optimize import Choice, Constraint, Continuous, Integer, Objective, Problem
from .rating import CHECKS, c001_g1, rate


def stage_sizing_problem(target_ratio=1.8, ratio_tol=0.02, max_b_over_d1=1.2):
    """单级直齿尺寸设计：变量 z1、模数、齿宽、小轮变位；目标 齿坯体积 与 工作中心距 最小。"""
    variables = [
        Integer("z1", 17, 30),
        Choice("m_n", (1.5, 2.0, 2.5, 3.0), ordered=True),
        Continuous("b", 10.0, 40.0),
        Continuous("x1", -0.2, 0.6),
    ]

    def evaluate(x):
        z1 = int(x["z1"])
        z2 = round(target_ratio * z1)
        m = c001_g1(z1=z1, z2=z2, m_n=x["m_n"], b=x["b"], x1=x["x1"], x2=0.0)
        r = rate(m, extra=("V_blank", "a_w", "d_1"))
        if r["status"].startswith("blocked"):
            raise RuntimeError({k: r.get(k) for k in ("status", "missing", "missing_editions", "errors")})
        v = r["result"].values
        cons = {c["id"]: c["limit"] - c["value"] for c in r["checks"]}
        cons["ratio_error"] = abs(z2 / z1 - target_ratio) / target_ratio - ratio_tol
        cons["b_over_d1"] = v["b"] / v["d_1"] - max_b_over_d1
        cons["domain"] = 1.0 if r["domain_violations"] else -1.0
        return {"objectives": {"volume_mm3": v["V_blank"], "center_distance_mm": v["a_w"]},
                "constraints": cons,
                "info": {"z2": z2, "S_H_1": v["S_H_1"], "S_F_1": v["S_F_1"], "eps_alpha": v["eps_alpha"],
                         "model_sha256": r["model_sha256"]}}

    wrt = {"b": "b", "x1": "x_1"}            # 连续设计变量 → 模型输入名

    def gradient(x):
        """连续变量（b、x1）的精确偏导：公式图前向对偶数（rate(wrt=…)），非差分。整数/选项变量固定。"""
        z1 = int(x["z1"])
        z2 = round(target_ratio * z1)
        m = c001_g1(z1=z1, z2=z2, m_n=x["m_n"], b=x["b"], x1=x["x1"], x2=0.0)
        r = rate(m, wrt=tuple(wrt.values()), extra=("V_blank", "a_w", "d_1"))
        if r["status"].startswith("blocked"):
            raise RuntimeError({k: r.get(k) for k in ("status", "missing", "missing_editions", "errors")})
        res = r["result"]

        def d(q):
            return {var: res.duals[q].d.get(inp, 0.0) for var, inp in wrt.items()}
        b_, d1 = res.values["b"], res.values["d_1"]
        db, dd1 = d("b"), d("d_1")
        cons = {c["id"]: {var: -t for var, t in d(c["quantity"]).items()} for c in r["checks"]}
        cons["ratio_error"] = {var: 0.0 for var in wrt}
        cons["b_over_d1"] = {var: db[var] / d1 - b_ * dd1[var] / d1 ** 2 for var in wrt}
        cons["domain"] = {var: 0.0 for var in wrt}      # 阶跃指示，几乎处处导数为 0（非光滑，见约束注释）
        return {"objectives": {"volume_mm3": d("V_blank"), "center_distance_mm": d("a_w")}, "constraints": cons}

    return Problem(variables, evaluate, [Objective("volume_mm3", "min"), Objective("center_distance_mm", "min")],
                   description="C001 G1 级尺寸设计（K/Z 证据系数按 C001 值保持不变，仅作架构演示）",
                   constraints=[Constraint("ratio_error", note="传动比相对误差 − 容差"),
                                Constraint("b_over_d1", note="b/d1 − 上限"),
                                Constraint("domain", note="越域 +1，域内 −1（非光滑，KKT 无意义）")],
                   parameters={"target_ratio": target_ratio, "ratio_tol": ratio_tol, "max_b_over_d1": max_b_over_d1},
                   evaluator_id="gearmath.gear.problem.stage_sizing_problem", gradient=gradient)


# ---------------------------------------------------------------- 可整数松弛的编译（M35-R3）

RELAXATION_NOTES = {
    "z1": "integer 变量；连续松弛时公式直接用连续 z1 求值（齿轮几何/强度公式对 z 光滑，无取整）",
    "z2": ("integer 变量；原问题 z2 = round(i·z1) 是阶跃，这里不平滑，而改写为两条线性约束 "
           "z2 − i·z1 − 0.5 ≤ 0、i·z1 − z2 − 0.5 ≤ 0：在整数点上与 round 等价（i·z1 的小数部分恰为 0.5 的"
           "平分点除外，见 parameters.rounding_ties），松弛中保持为线性约束"),
    "m_n": "有序选项；松弛时在相邻允许值之间连续取值（公式对 m_n 光滑），分支按 SOS 式二分",
    "ratio_error": "原 |z2/z1 − i|/i − tol ≤ 0 含绝对值折点，拆成 upper/lower 两条光滑约束（精确等价，非光滑化）",
    "domain": "越域指示 +1/−1 是阶跃，原样保留（导数取 0，非光滑）；松弛点若越域会显示为约束违反",
    "piecewise": ("公式图中的 where/min/max（及 round_to，若在依赖链上）按命中分支精确求值与求导，未光滑；"
                  "每次求值在 info.piecewise_branches 记录分支签名，求解报告 nonsmooth_regimes 列出跨越的节点"),
}


def stage_sizing_problem_relaxable(target_ratio=1.8, ratio_tol=0.02, max_b_over_d1=1.2, z1_range=(17, 30),
                                   m_values=(1.5, 2.0, 2.5, 3.0), piecewise_trace=True):
    """与 stage_sizing_problem 同一设计问题，但齿数声明为 integer 变量且允许连续求值（可做整数松弛 + 分支定界）。

    差异（都写进 IR 的 constraints / parameters）：
      - z2 成为 integer 变量，z2 = round(i·z1) 改写成两条线性约束（整数点上等价，平分点除外）；
      - ratio_error 拆为 upper/lower 两条光滑约束；
      - 求值不对 z 取整：整数点上目标/校核与 stage_sizing_problem 完全一致（测试核对）。
    """
    from ..kernel.expr import switches

    i_r = float(target_ratio)
    lo1, hi1 = int(z1_range[0]), int(z1_range[1])
    z2_lo, z2_hi = round(i_r * lo1), round(i_r * hi1)
    ties = [z for z in range(lo1, hi1 + 1) if abs((i_r * z) % 1.0 - 0.5) < 1e-9]
    variables = [
        Integer("z1", lo1, hi1),
        Integer("z2", int(z2_lo), int(z2_hi)),
        Choice("m_n", tuple(m_values), ordered=True),
        Continuous("b", 10.0, 40.0),
        Continuous("x1", -0.2, 0.6),
    ]
    wrt = {"b": "b", "x1": "x_1", "z1": "z_1", "z2": "z_2", "m_n": "m_n"}

    cache = {}

    def _rate(x):
        """一次 rate(wrt=…) 同时给出值与对偶数导数；最近一个点缓存，供紧随其后的 gradient(x) 复用。"""
        key = tuple(float(x[k]) for k in ("z1", "z2", "m_n", "b", "x1"))
        if cache.get("key") == key:
            return cache["m"], cache["r"]
        m = c001_g1(z1=key[0], z2=key[1], m_n=key[2], b=key[3], x1=key[4], x2=0.0)
        r = rate(m, wrt=tuple(wrt.values()), extra=("V_blank", "a_w", "d_1"))
        if r["status"].startswith("blocked"):
            raise RuntimeError({k: r.get(k) for k in ("status", "missing", "missing_editions", "errors")})
        cache.update(key=key, m=m, r=r)
        return m, r

    def evaluate(x):
        m, r = _rate(x)
        v = r["result"].values
        z1, z2 = float(x["z1"]), float(x["z2"])
        cons = {c["id"]: c["limit"] - c["value"] for c in r["checks"]}
        cons["z2_rounding.upper"] = z2 - i_r * z1 - 0.5
        cons["z2_rounding.lower"] = i_r * z1 - z2 - 0.5
        cons["ratio_error.upper"] = (z2 / z1 - i_r) / i_r - ratio_tol
        cons["ratio_error.lower"] = -(z2 / z1 - i_r) / i_r - ratio_tol
        cons["b_over_d1"] = v["b"] / v["d_1"] - max_b_over_d1
        cons["domain"] = 1.0 if r["domain_violations"] else -1.0
        info = {"z2": z2, "S_H_1": v["S_H_1"], "S_F_1": v["S_F_1"], "eps_alpha": v["eps_alpha"],
                "model_sha256": r["model_sha256"]}
        if piecewise_trace:
            info["piecewise_branches"] = [(f"{t['quantity']}#{t['node']}", t["branch"]) for t in switches(m, r["result"])]
        return {"objectives": {"volume_mm3": v["V_blank"], "center_distance_mm": v["a_w"]},
                "constraints": cons, "info": info}

    def gradient(x):
        """全部变量（含松弛的 z1、z2、m_n）的精确偏导：公式图前向对偶数 rate(wrt=…)。"""
        _, r = _rate(x)
        res = r["result"]

        def d(q):
            return {var: res.duals[q].d.get(inp, 0.0) for var, inp in wrt.items()}
        z1, z2 = float(x["z1"]), float(x["z2"])
        b_, d1 = res.values["b"], res.values["d_1"]
        db, dd1 = d("b"), d("d_1")
        zero = {var: 0.0 for var in wrt}
        cons = {c["id"]: {var: -t for var, t in d(c["quantity"]).items()} for c in r["checks"]}
        cons["z2_rounding.upper"] = dict(zero, z1=-i_r, z2=1.0)
        cons["z2_rounding.lower"] = dict(zero, z1=i_r, z2=-1.0)
        cons["ratio_error.upper"] = dict(zero, z1=-z2 / z1 ** 2 / i_r, z2=1.0 / (z1 * i_r))
        cons["ratio_error.lower"] = dict(zero, z1=z2 / z1 ** 2 / i_r, z2=-1.0 / (z1 * i_r))
        cons["b_over_d1"] = {var: db[var] / d1 - b_ * dd1[var] / d1 ** 2 for var in wrt}
        cons["domain"] = dict(zero)          # 阶跃指示：几乎处处导数 0（非光滑，见约束注释）
        return {"objectives": {"volume_mm3": d("V_blank"), "center_distance_mm": d("a_w")}, "constraints": cons}

    N = RELAXATION_NOTES
    return Problem(variables, evaluate, [Objective("volume_mm3", "min"), Objective("center_distance_mm", "min")],
                   description="C001 G1 级尺寸设计（可整数松弛编译：z1、z2 为 integer，求值不取整）",
                   constraints=[Constraint("z2_rounding.upper", note=N["z2"]),
                                Constraint("z2_rounding.lower", note=N["z2"]),
                                Constraint("ratio_error.upper", note=N["ratio_error"]),
                                Constraint("ratio_error.lower", note=N["ratio_error"]),
                                Constraint("b_over_d1", note="b/d1 − 上限"),
                                Constraint("domain", note=N["domain"])],
                   parameters={"target_ratio": target_ratio, "ratio_tol": ratio_tol, "max_b_over_d1": max_b_over_d1,
                               "z1_range": [lo1, hi1], "rounding_ties": ties,
                               "relaxation": dict(N)},
                   evaluator_id="gearmath.gear.problem.stage_sizing_problem_relaxable", gradient=gradient)
