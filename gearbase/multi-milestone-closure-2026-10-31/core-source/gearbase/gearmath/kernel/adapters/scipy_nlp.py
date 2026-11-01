"""可选适配器：SciPy SLSQP（BSD）。只在调用时 import scipy；未安装则抛 AdapterUnavailable。

号向转换（显式、测试强制）：
  我们：g(x) ≤ 0 为可行  →  SciPy：{'type': 'ineq', 'fun': −g, 'jac': −Jg}（SciPy 要求 fun ≥ 0）
  我们：h(x) = 0         →  SciPy：{'type': 'eq', 'fun': h, 'jac': Jh}
  变量界 l ≤ x ≤ u       →  bounds=[(l, u)]，无穷界写 None
外部求解器自报的状态与乘子不作证据：返回前用原始 g、h、导数按最小二乘重估乘子（λ ≥ 0），
并用 nlp.kkt_residuals 复算四项 KKT 残差。后端自报乘子经号向换算后只放进 history 供对照：
  SLSQP（SciPy ≥ 1.16 的 res.multipliers，先全部等式、后全部不等式；后端拉格朗日 L = f − Σ m·c）：
      我们的 λ = +m_ineq（因 c = −g），μ = −m_eq            （实测核对，见测试 TestScipyLiveSuite）
  trust-constr（res.v，每个约束对象一项，有界时最后一项为变量界；L = f + Σ v·c，上侧积极 v > 0）：
      NonlinearConstraint(g, −inf, 0) → λ = v；NonlinearConstraint(h, 0, 0) → μ = v；
      变量界项 v_k > 0 → ν^U_k = v_k，v_k < 0 → ν^L_k = −v_k
"""
from __future__ import annotations

import math

from .. import nlp as _nlp
from . import AdapterUnavailable


def available():
    try:
        import scipy.optimize  # noqa: F401
    except ImportError:
        return False
    return True


def to_scipy_constraints(oracle, m, p):
    """把 oracle(x) → (f, g, h, ∇f, Jg, Jh) 转成 SciPy 约束字典列表（纯 Python，不需要 SciPy）。"""
    cons = []
    if m:
        cons.append({"type": "ineq",
                     "fun": lambda x: [-t for t in oracle(list(map(float, x)))[1]],
                     "jac": lambda x: [[-t for t in row] for row in oracle(list(map(float, x)))[4]]})
    if p:
        cons.append({"type": "eq",
                     "fun": lambda x: list(oracle(list(map(float, x)))[2]),
                     "jac": lambda x: [list(row) for row in oracle(list(map(float, x)))[5]]})
    return cons


def to_scipy_bounds(lb, ub):
    return [(None if not math.isfinite(l) else l, None if not math.isfinite(u) else u) for l, u in zip(lb, ub)]


def slsqp_multipliers(res, m, p):
    """SLSQP 自报乘子 → 我们的号向（λ 对 g ≤ 0，μ 对 h = 0）。后端未提供时返回 None。"""
    mult = getattr(res, "multipliers", None)
    if mult is None:
        return None
    mult = [float(t) for t in mult]
    if len(mult) != m + p:
        return None
    return {"ineq": mult[p:p + m], "eq": [-t for t in mult[:p]]}


def trust_constr_multipliers(res, m, p, has_bounds, n):
    """trust-constr 的 res.v → 我们的号向。约束对象顺序：[g（若 m>0）, h（若 p>0）]，有界时最后一项为界。"""
    v = [[float(t) for t in row] for row in getattr(res, "v", [])]
    out = {"ineq": [], "eq": [], "lower": [0.0] * n, "upper": [0.0] * n}
    k = 0
    if m:
        out["ineq"] = v[k]
        k += 1
    if p:
        out["eq"] = v[k]
        k += 1
    if has_bounds and k < len(v):
        out["upper"] = [max(t, 0.0) for t in v[k]]
        out["lower"] = [max(-t, 0.0) for t in v[k]]
    return out


def _finish(ev, x, lb, ub, opts, active_tol, src, history, nit):
    f, g, h, df, Jg, Jh = ev(x)
    lam, mu = _nlp.estimate_multipliers(x, lb, ub, g, h, df, Jg, Jh, active_tol=active_tol)
    kk = _nlp.kkt_residuals(x, lb, ub, f, g, h, df, Jg, Jh, lam, mu)
    ok = _nlp.kkt_ok(kk, opts)
    return _nlp.NLPResult(x=x, f=f, g=g, h=h,
                          multipliers={"ineq": lam, "eq": mu, "lower": kk["bound_multipliers"]["lower"],
                                       "upper": kk["bound_multipliers"]["upper"]},
                          residuals=kk["residuals"], kkt_satisfied=ok,
                          termination="kkt_tolerances_met" if ok else "external_solver_stopped",
                          outer_iterations=nit, inner_iterations=0, evaluations=ev.n, history=history,
                          tolerances={k: opts[k] for k in ("tol_stationarity", "tol_feasibility", "tol_complementarity")},
                          gradient_source=src)


def minimize_trust_constr(fun=None, x0=None, lb=None, ub=None, *, oracle=None, maxiter=5000, gtol=1e-11,
                          xtol=1e-14, barrier_tol=1e-11, active_tol=1e-6, **tolerances):
    """SciPy trust-constr（拟牛顿 BFGS Hessian）。号向见模块说明；返回前用我们的残差/乘子复核。"""
    try:
        import warnings

        from scipy.optimize import BFGS, Bounds, NonlinearConstraint
        from scipy.optimize import minimize as _sp_minimize
    except ImportError as e:
        raise AdapterUnavailable("SciPy 未安装：scipy_nlp 适配器不可用（核心求解器 nlp.minimize 不受影响）") from e
    opts = dict(_nlp.DEFAULTS)
    opts.update(tolerances)
    if oracle is None:
        oracle = _nlp.dual_oracle(fun)
    src = getattr(oracle, "gradient_source", "analytic")
    n = len(x0)
    lb, ub = _nlp._bounds(lb, ub, n)
    ev = _nlp._Counter(oracle)
    xs = [min(u, max(l, float(v))) for v, l, u in zip(x0, lb, ub)]
    _, g0, h0, *_ = ev(xs)
    m, p = len(g0), len(h0)
    cons = []
    if m:
        cons.append(NonlinearConstraint(lambda x: ev(list(map(float, x)))[1], -_nlp.INF, 0.0,
                                        jac=lambda x: ev(list(map(float, x)))[4], hess=BFGS()))
    if p:
        cons.append(NonlinearConstraint(lambda x: ev(list(map(float, x)))[2], 0.0, 0.0,
                                        jac=lambda x: ev(list(map(float, x)))[5], hess=BFGS()))
    has_bounds = any(math.isfinite(t) for t in lb + ub)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = _sp_minimize(lambda x: ev(list(map(float, x)))[0], xs, jac=lambda x: list(ev(list(map(float, x)))[3]),
                           hess=BFGS(), method="trust-constr", constraints=cons,
                           bounds=Bounds(lb, ub) if has_bounds else None,
                           options={"maxiter": maxiter, "gtol": gtol, "xtol": xtol, "barrier_tol": barrier_tol})
    x = [min(u, max(l, float(v))) for v, l, u in zip(res.x, lb, ub)]
    hist = [{"backend": "scipy.optimize.minimize(method='trust-constr')", "status": int(res.status),
             "message": str(res.message),
             "backend_multipliers_converted": trust_constr_multipliers(res, m, p, has_bounds, n)}]
    return _finish(ev, x, lb, ub, opts, active_tol, src, hist, int(getattr(res, "nit", 0)))


def minimize_slsqp(fun=None, x0=None, lb=None, ub=None, *, oracle=None, maxiter=500, ftol=1e-12,
                   active_tol=1e-6, **tolerances):
    try:
        from scipy.optimize import minimize as _sp_minimize
    except ImportError as e:
        raise AdapterUnavailable("SciPy 未安装：scipy_nlp 适配器不可用（核心求解器 nlp.minimize 不受影响）") from e
    opts = dict(_nlp.DEFAULTS)
    opts.update(tolerances)
    if oracle is None:
        oracle = _nlp.dual_oracle(fun)
    src = getattr(oracle, "gradient_source", "analytic")
    n = len(x0)
    lb, ub = _nlp._bounds(lb, ub, n)
    ev = _nlp._Counter(oracle)
    _, g0, h0, *_ = ev([min(u, max(l, float(v))) for v, l, u in zip(x0, lb, ub)])
    res = _sp_minimize(lambda x: ev(list(map(float, x)))[0], [min(u, max(l, float(v))) for v, l, u in zip(x0, lb, ub)],
                       jac=lambda x: list(ev(list(map(float, x)))[3]), method="SLSQP",
                       bounds=to_scipy_bounds(lb, ub), constraints=to_scipy_constraints(ev, len(g0), len(h0)),
                       options={"maxiter": maxiter, "ftol": ftol})
    x = [min(u, max(l, float(v))) for v, l, u in zip(res.x, lb, ub)]
    hist = [{"backend": "scipy.optimize.minimize(method='SLSQP')", "status": int(res.status),
             "message": str(res.message),
             "backend_multipliers_converted": slsqp_multipliers(res, len(g0), len(h0))}]
    return _finish(ev, x, lb, ub, opts, active_tol, src, hist, int(getattr(res, "nit", 0)))
