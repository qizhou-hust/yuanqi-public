"""可选适配器：pymoo 多目标进化（Apache-2.0）。只在调用时 import pymoo；未安装则抛 AdapterUnavailable。

号向（显式、测试强制）：
  我们：g(x) ≤ 0 为可行  →  pymoo：out["G"] = g（pymoo 同样以 G ≤ 0 为可行，不变号）
  我们：h(x) = 0         →  pymoo：out["H"] = h（pymoo 对等式用其内部容差判可行，见 pymoo 文档）
  目标 sense="max"       →  pymoo 最小化 −f，回映射时恢复符号
进化算法没有最优性证书：结果只标为启发式搜索（search_kind），不给任何"最优/可信"结论。
可选的局部复核（kkt_review=True）：对每个 Pareto 点用自研 nlp.minimize 解 ε-约束子问题
  min F_p(x)  s.t.  F_j(x) − F_j(x*) ≤ 0 (j ≠ p),  g(x) ≤ 0,  h(x) = 0,  l ≤ x ≤ u，从 x* 出发，
并报告：x* 处该子问题的一阶 KKT 残差（乘子按积极集最小二乘重估）、精修点的 KKT 残差/终止原因与改进量。
"""
from __future__ import annotations

import math

from .. import nlp as _nlp
from . import AdapterUnavailable

SEARCH_KIND = "evolutionary_heuristic_no_certificate"
ALGORITHMS = ("nsga2",)


def available():
    try:
        import pymoo  # noqa: F401
    except ImportError:
        return False
    return True


def _split3(out):
    if isinstance(out, tuple):
        F = list(out[0])
        G = list(out[1]) if len(out) > 1 and out[1] is not None else []
        H = list(out[2]) if len(out) > 2 and out[2] is not None else []
        return F, G, H
    return list(out), [], []


def _val(t):
    return t.v if isinstance(t, _nlp.D.Dual) else float(t)


def to_pymoo_out(fun, x, senses=None):
    """fun(x) → (F[...], G[...]) 或 (F, G, H)。返回 pymoo 的 out 字典（纯 Python，不需要 pymoo）：
    F 按 sense 取号（max → −f），G、H 原样（g ≤ 0 可行，与 pymoo 一致）。"""
    F, G, H = _split3(fun([float(t) for t in x]))
    sg = [(-1.0 if s == "max" else 1.0) for s in (senses or ["min"] * len(F))]
    return {"F": [s * _val(f) for s, f in zip(sg, F)], "G": [_val(g) for g in G], "H": [_val(h) for h in H]}


def make_problem(fun, lb, ub, n_obj, n_ieq, n_eq=0, senses=None):
    """构造 pymoo ElementwiseProblem（需要 pymoo）。"""
    try:
        import numpy as np
        from pymoo.core.problem import ElementwiseProblem
    except ImportError as e:
        raise AdapterUnavailable("pymoo 未安装：pymoo_moo 适配器不可用（核心求解器不受影响）") from e

    class _P(ElementwiseProblem):
        def __init__(self):
            super().__init__(n_var=len(lb), n_obj=n_obj, n_ieq_constr=n_ieq, n_eq_constr=n_eq,
                             xl=np.array(lb, dtype=float), xu=np.array(ub, dtype=float))

        def _evaluate(self, x, out, *args, **kwargs):
            o = to_pymoo_out(fun, list(x), senses)
            out["F"] = o["F"]
            if n_ieq:
                out["G"] = o["G"]
            if n_eq:
                out["H"] = o["H"]
    return _P()


def _eps_problem(fun, p, ref, senses):
    sg = [(-1.0 if s == "max" else 1.0) for s in senses]

    def sub(x):
        F, G, H = _split3(fun(x))
        Fm = [s * f for s, f in zip(sg, F)]
        eps = [Fm[j] - sg[j] * ref[j] for j in range(len(F)) if j != p]
        return Fm[p], list(G) + eps, list(H)
    return sub


def kkt_review(fun, x_star, lb, ub, *, senses, primary=0, **nlp_options):
    """对一个 Pareto 候选点做 ε-约束局部复核（自研 NLP，精确导数）。"""
    lb_, ub_ = _nlp._bounds(lb, ub, len(x_star))
    F, G, H = _split3(fun([float(t) for t in x_star]))
    ref = [_val(f) for f in F]
    sub = _eps_problem(fun, primary, ref, senses)
    oracle = _nlp.dual_oracle(sub)
    f0, g0, h0, df0, Jg0, Jh0 = oracle(list(x_star))
    try:
        lam, mu = _nlp.estimate_multipliers(list(x_star), lb_, ub_, g0, h0, df0, Jg0, Jh0)
        at = _nlp.kkt_residuals(list(x_star), lb_, ub_, f0, g0, h0, df0, Jg0, Jh0, lam, mu)
        opts = dict(_nlp.DEFAULTS)
        opts.update({k: v for k, v in nlp_options.items() if k in opts})
        at_point = {"residuals": at["residuals"], "kkt_satisfied": _nlp.kkt_ok(at, opts),
                    "multipliers": {"ineq": lam, "eq": mu}}
    except ValueError as e:
        at_point = {"residuals": None, "kkt_satisfied": None, "error": str(e)}
    r = _nlp.minimize(x0=list(x_star), lb=lb_, ub=ub_, oracle=oracle, **nlp_options)
    sg = [(-1.0 if s == "max" else 1.0) for s in senses]
    Fr = [_val(t) for t in _split3(fun(list(r.x)))[0]]
    return {"method": "epsilon_constraint_local_nlp", "primary_objective": primary,
            "at_candidate": at_point,
            "refined": {"x": list(r.x), "F": Fr, "termination": r.termination, "kkt_satisfied": r.kkt_satisfied,
                        "residuals": r.residuals, "evaluations": r.evaluations,
                        "primary_improvement": sg[primary] * (ref[primary] - Fr[primary]),
                        "max_shift": max((abs(a - b) for a, b in zip(r.x, x_star)), default=0.0)},
            "meaning": ("ε-约束子问题的一阶 KKT 局部复核：refined 不劣于候选点（其余目标不变差）；"
                        "不证明 Pareto 最优性，也不覆盖前沿的完整性")}


def minimize_moo(fun, lb, ub, *, n_obj, senses=None, algorithm="nsga2", pop_size=40, n_gen=60, seed=1,
                 kkt_review_points=False, primary=0, **nlp_options):
    """pymoo NSGA-II 多目标。fun(x) → (F, G) 或 (F, G, H)（g ≤ 0 可行）；fun 若对 dual.Dual 可求值，
    可开启 kkt_review_points 做逐点局部 KKT 复核。返回字典（点集、后端信息、可选复核）。"""
    try:
        import pymoo
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.optimize import minimize as _pm_minimize
    except ImportError as e:
        raise AdapterUnavailable("pymoo 未安装：pymoo_moo 适配器不可用（核心求解器不受影响）") from e
    if algorithm not in ALGORITHMS:
        raise ValueError(f"algorithm={algorithm!r} 不在 {ALGORITHMS}")
    senses = list(senses or ["min"] * n_obj)
    lb_, ub_ = _nlp._bounds(lb, ub, len(lb))
    if not all(math.isfinite(t) for t in lb_ + ub_):
        raise ValueError("进化算法需要有限变量界")
    x_mid = [0.5 * (a + b) for a, b in zip(lb_, ub_)]
    o = to_pymoo_out(fun, x_mid, senses)
    if len(o["F"]) != n_obj:
        raise ValueError(f"目标个数 {len(o['F'])} ≠ n_obj={n_obj}")
    prob = make_problem(fun, lb_, ub_, n_obj, len(o["G"]), len(o["H"]), senses)
    res = _pm_minimize(prob, NSGA2(pop_size=pop_size), ("n_gen", n_gen), seed=seed, verbose=False)
    points = []
    if res.X is not None:
        X = res.X.tolist()
        if X and not isinstance(X[0], list):
            X = [X]
        for x in X:
            F, G, H = _split3(fun([float(t) for t in x]))
            Fv, Gv, Hv = [_val(t) for t in F], [_val(t) for t in G], [_val(t) for t in H]
            pt = {"x": [float(t) for t in x], "F": Fv, "G": Gv, "H": Hv,
                  "max_g": max(Gv, default=-math.inf), "max_abs_h": max((abs(t) for t in Hv), default=0.0)}
            if kkt_review_points:
                pt["kkt_review"] = kkt_review(fun, pt["x"], lb_, ub_, senses=senses, primary=primary, **nlp_options)
            points.append(pt)
    sg = [(-1.0 if s == "max" else 1.0) for s in senses]
    points.sort(key=lambda p: [s * f for s, f in zip(sg, p["F"])])
    return {"points": points, "search_kind": SEARCH_KIND, "constraint_convention": "g ≤ 0 可行（pymoo G ≤ 0 同号）",
            "senses": senses,
            "backend": {"package": "pymoo", "version": getattr(pymoo, "__version__", "unknown"),
                        "algorithm": algorithm, "pop_size": pop_size, "n_gen": n_gen, "seed": seed},
            "not_claimed": ["pareto_optimality", "front_completeness", "global_optimality"]}
