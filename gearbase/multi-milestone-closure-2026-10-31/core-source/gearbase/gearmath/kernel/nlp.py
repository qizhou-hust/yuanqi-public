"""零依赖非线性规划求解器（纯数学，不含任何领域知识）。

规范形式（所有入口统一）：
    minimize f(x)   s.t.   g_i(x) ≤ 0,   h_j(x) = 0,   l ≤ x ≤ u
乘子号向（写死，测试强制）：
    L = f + Σ λ_i g_i + Σ μ_j h_j + Σ ν^U_k (x_k − u_k) + Σ ν^L_k (l_k − x_k)
    g ≤ 0 ⇒ λ ≥ 0（活跃约束 λ > 0）；ν^L, ν^U ≥ 0；μ 无号向限制。

算法：
  - 连续 NLP：增广拉格朗日外层（PHR 型，ALGENCAN 式罚参数更新）+ 带界拟牛顿内层
    （投影梯度识别绑定集，自由变量上用阻尼 BFGS 牛顿方向，投影 Armijo 线搜索）。
    导数来自 dual.py 前向对偶数（精确，非差分）；也可传入解析导数 oracle。
    内部做变量仿射缩放（有限界 → [0,1]）与函数梯度缩放；KKT 残差一律在原始量纲下复算。
  - 混合整数：分支定界（先深度优先找到首个可行整数解，再最佳界优先），节点为连续松弛；
    离散有序取值集合按 SOS 式区间二分分支；报告 gap。gap 只有在节点松弛为凸（局部解即全局解）
    时才是有效下界，结果中写明该假设。

结论口径：KKT 残差达标只表示"一阶必要条件在容差内成立的局部候选点"，
求解器本身不检查二阶条件与约束规范，不声称全局最优；二阶条件由独立函数 second_order_check
（拉格朗日函数 Hessian = 精确梯度的有限差分，投影到积极约束切空间）另行报告，不并入一阶结论；"局部不可行"只表示停在约束违反量的驻点，不等于已证明不可行。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import dual as D

INF = float("inf")

TERMINATION = ("kkt_tolerances_met",            # 原始 KKT 残差全部达标
               "local_infeasibility_detected",  # 约束违反量的驻点（非证明）
               "objective_unbounded_below",
               "max_outer_iterations",
               "inner_solver_stalled",
               "external_solver_stopped")      # 可选适配器：外部求解器自报停止，KKT 由本模块复算
BNB_TERMINATION = ("tree_exhausted", "node_limit", "no_integer_feasible_found")
SECOND_ORDER_STATUS = ("sosc_satisfied",   # 强积极约束切空间上约化 Hessian 正定（数值，有限差分）
                       "sonc_violated",    # 全部积极约束切空间上有负曲率（LICQ 成立时该点不是局部极小）
                       "inconclusive",     # 半正定/退化/容差内无法判定
                       "not_applicable")   # 无可用点等
CLAIM_SCOPE = "local"
MULTIPLIER_CONVENTION = ("L = f + Σλ_i·g_i + Σμ_j·h_j + Σν^U_k·(x_k − u_k) + Σν^L_k·(l_k − x_k)；"
                         "g ≤ 0 ⇒ λ ≥ 0，ν^L, ν^U ≥ 0，μ 无号向限制")
BNB_BOUND_ASSUMPTION = ("节点松弛的局部 KKT 解被当作该节点的下界；仅当松弛问题为凸时 gap 才是有效界，"
                        "非凸时 gap 只是启发性指标")

DEFAULTS = {
    "tol_stationarity": 1e-7,     # ‖∇L‖∞ / max(1, ‖∇f‖∞)
    "tol_feasibility": 1e-8,      # max(g⁺, |h|)，原始量纲
    "tol_complementarity": 1e-7,  # max|λ_i g_i| / max(1, ‖∇f‖∞)
    "max_outer": 60,
    "max_inner": 400,
    "rho0": 10.0,
    "rho_growth": 10.0,
    "rho_max": 1e12,
    "multiplier_max": 1e12,
    "gradient_scale": 10.0,       # 缩放后 ‖∇·‖∞ 至多为此值
    "unbounded_value": -1e20,
}


# ---------------------------------------------------------------- 导数 oracle

def _vg(val, n):
    if isinstance(val, D.Dual):
        return val.v, [float(val.d.get(i, 0.0)) for i in range(n)]
    return float(val), [0.0] * n


def _split(out):
    if isinstance(out, tuple):
        f = out[0]
        g = list(out[1]) if len(out) > 1 and out[1] is not None else []
        h = list(out[2]) if len(out) > 2 and out[2] is not None else []
        return f, g, h
    return out, [], []


def dual_oracle(fun):
    """fun(x) → f 或 (f, [g…]) 或 (f, [g…], [h…])，x 为对偶数列表。返回 x ↦ (f, g, h, ∇f, Jg, Jh)。"""
    def oracle(x):
        n = len(x)
        xs = [D.Dual(v, {i: 1.0}) for i, v in enumerate(x)]
        f, g, h = _split(fun(xs))
        fv, df = _vg(f, n)
        gv, Jg = zip(*[_vg(t, n) for t in g]) if g else ((), ())
        hv, Jh = zip(*[_vg(t, n) for t in h]) if h else ((), ())
        return fv, list(gv), list(hv), df, [list(r) for r in Jg], [list(r) for r in Jh]
    oracle.gradient_source = "forward_mode_dual"
    return oracle


class _Counter:
    def __init__(self, oracle):
        self.oracle, self.n = oracle, 0
        self._key = self._val = None

    def __call__(self, x):
        key = tuple(x)
        if key == self._key:
            return self._val
        self.n += 1
        out = self.oracle(list(x))
        self._key, self._val = key, out
        return out


# ---------------------------------------------------------------- 小型稠密线性代数

def _chol_solve(A, b):
    n = len(b)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 1e-14 * max(1.0, abs(A[i][i])):
                    return None
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def _dot(a, b):
    return sum(p * q for p, q in zip(a, b))


def _ninf(a):
    return max((abs(t) for t in a), default=0.0)


# ---------------------------------------------------------------- 带界拟牛顿（内层）

def _proj(z, lo, hi):
    return [min(h, max(l, v)) for v, l, h in zip(z, lo, hi)]


def _box_qn(phi, z, lo, hi, tol, max_iter, B=None):
    """min φ(z) s.t. lo ≤ z ≤ hi。φ 返回 (值, 梯度)。返回 (z, φ, ∇φ, B, 迭代数, 原因)。"""
    n = len(z)
    z = _proj(z, lo, hi)
    fz, gz = phi(z)
    fresh = B is None
    if B is None:
        B = [[float(i == j) for j in range(n)] for i in range(n)]
    it = 0
    reason = "max_iter"
    while it < max_iter:
        pg = [p - v for p, v in zip(_proj([v - g for v, g in zip(z, gz)], lo, hi), z)]
        pgn = _ninf(pg)
        if pgn <= tol:
            reason = "converged"
            break
        it += 1
        eps = min(1e-8, pgn)
        free = [i for i in range(n) if not ((z[i] <= lo[i] + eps and gz[i] > 0) or (z[i] >= hi[i] - eps and gz[i] < 0))]
        d = [0.0] * n
        sol = _chol_solve([[B[i][j] for j in free] for i in free], [-gz[i] for i in free]) if free else []
        if sol is not None:
            for t, i in enumerate(free):
                d[i] = sol[t]
        if sol is None or _dot(d, gz) > -1e-12 * _ninf(d) * _ninf(gz):
            B = [[float(i == j) for j in range(n)] for i in range(n)]
            fresh = True
            d = [0.0] * n
            for i in free:
                d[i] = -gz[i]
        accepted = None
        for direction in (d, [-g for g in gz]):
            a = 1.0
            for _ in range(60):
                zt = _proj([v + a * s for v, s in zip(z, direction)], lo, hi)
                step = [p - v for p, v in zip(zt, z)]
                if _ninf(step) == 0.0:
                    break
                try:
                    ft, gt = phi(zt)
                    ok = math.isfinite(ft)
                except (ArithmeticError, ValueError, TypeError, RuntimeError):
                    ok = False
                if ok and ft <= fz + 1e-4 * _dot(gz, step):
                    accepted = (zt, ft, gt, step)
                    break
                a *= 0.5
            if accepted:
                break
        if not accepted:
            reason = "line_search_failed"
            break
        zt, ft, gt, s = accepted
        y = [p - q for p, q in zip(gt, gz)]
        Bs = [_dot(row, s) for row in B]
        sBs, sy = _dot(s, Bs), _dot(s, y)
        if fresh and sy > 1e-16:
            c = _dot(y, y) / sy
            B = [[c * float(i == j) for j in range(n)] for i in range(n)]
            Bs, sBs = [c * t for t in s], c * _dot(s, s)
            fresh = False
        if sBs > 1e-300:
            th = 1.0 if sy >= 0.2 * sBs else 0.8 * sBs / (sBs - sy)
            r = [th * yi + (1 - th) * bi for yi, bi in zip(y, Bs)]
            sr = _dot(s, r)
            if sr > 1e-300:
                B = [[B[i][j] + r[i] * r[j] / sr - Bs[i] * Bs[j] / sBs for j in range(n)] for i in range(n)]
        small = _ninf(s) <= 1e-15 * max(1.0, _ninf(z)) and abs(fz - ft) <= 1e-15 * max(1.0, abs(fz))
        z, fz, gz = zt, ft, gt
        if small:
            reason = "small_step"
            break
    return z, fz, gz, B, it, reason


# ---------------------------------------------------------------- KKT 残差（原始量纲）

def kkt_residuals(x, lb, ub, f, g, h, df, Jg, Jh, lam, mu, bound_tol=1e-12):
    """给定点与乘子（λ 对 g≤0，μ 对 h=0），复算 KKT 四项残差。变量界乘子由驻点方程在积极界上恢复。

    返回 {"residuals": {...}, "bound_multipliers": {"lower": [...], "upper": [...]}}。
    stationarity / complementarity 按 max(1, ‖∇f‖∞) 归一化，绝对值另报。
    """
    n = len(x)
    r = list(df)
    for li, row in zip(lam, Jg):
        for k in range(n):
            r[k] += li * row[k]
    for mj, row in zip(mu, Jh):
        for k in range(n):
            r[k] += mj * row[k]
    nl, nu = [0.0] * n, [0.0] * n
    for k in range(n):
        tl = bound_tol * max(1.0, abs(lb[k])) if math.isfinite(lb[k]) else 0.0
        tu = bound_tol * max(1.0, abs(ub[k])) if math.isfinite(ub[k]) else 0.0
        if math.isfinite(lb[k]) and x[k] <= lb[k] + tl and r[k] > 0:
            nl[k], r[k] = r[k], 0.0
        elif math.isfinite(ub[k]) and x[k] >= ub[k] - tu and r[k] < 0:
            nu[k], r[k] = -r[k], 0.0
    scale = max(1.0, _ninf(df))
    bviol = max([0.0] + [lb[k] - x[k] for k in range(n) if math.isfinite(lb[k])]
                + [x[k] - ub[k] for k in range(n) if math.isfinite(ub[k])])
    primal = max([0.0, bviol] + [t for t in g] + [abs(t) for t in h])
    dual = max([0.0] + [-t for t in lam] + [-t for t in nl] + [-t for t in nu])
    comp = [abs(li * gi) for li, gi in zip(lam, g)]
    comp += [abs(nl[k] * (x[k] - lb[k])) for k in range(n) if nl[k]]
    comp += [abs(nu[k] * (ub[k] - x[k])) for k in range(n) if nu[k]]
    stat_abs, comp_abs = _ninf(r), max(comp, default=0.0)
    return {"residuals": {"stationarity": stat_abs / scale, "stationarity_abs": stat_abs,
                          "primal_feasibility": primal, "dual_feasibility": dual,
                          "complementarity": comp_abs / scale, "complementarity_abs": comp_abs,
                          "normalization": scale},
            "bound_multipliers": {"lower": nl, "upper": nu}}


def _lstsq(cols, b):
    """min ‖Σ c_j a_j − b‖₂（正规方程 + 部分主元消去）；奇异返回 None。"""
    m = len(cols)
    A = [[_dot(cols[p], cols[q]) for q in range(m)] + [_dot(cols[p], b)] for p in range(m)]
    for c in range(m):
        piv = max(range(c, m), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-14:
            return None
        A[c], A[piv] = A[piv], A[c]
        for r in range(m):
            if r != c:
                f = A[r][c] / A[c][c]
                A[r] = [A[r][t] - f * A[c][t] for t in range(m + 1)]
    return [A[i][m] / A[i][i] for i in range(m)]


def estimate_multipliers(x, lb, ub, g, h, df, Jg, Jh, active_tol=1e-6, max_active=14):
    """在给定点按最小二乘重估乘子（用于不返回乘子的外部求解器，或交叉校验）：
    min ‖∇f + Σλ_i∇g_i + Σμ_j∇h_j − ν^L + ν^U‖，λ, ν ≥ 0 只在积极约束/积极界上非零（枚举支撑集，小规模）。
    返回 (λ, μ)；变量界乘子随后由 kkt_residuals 从驻点方程恢复。"""
    n = len(x)
    act = [i for i, t in enumerate(g) if t >= -active_tol]
    bnd = [(k, -1.0) for k in range(n) if math.isfinite(lb[k]) and x[k] - lb[k] <= active_tol * max(1.0, abs(lb[k]))]
    bnd += [(k, 1.0) for k in range(n) if math.isfinite(ub[k]) and ub[k] - x[k] <= active_tol * max(1.0, abs(ub[k]))]
    cols_i = [Jg[i] for i in act] + [[sgn if t == k else 0.0 for t in range(n)] for k, sgn in bnd]
    if len(cols_i) > max_active:
        raise ValueError(f"积极约束 {len(cols_i)} 个 > {max_active}，不做支撑集枚举")
    rhs = [-t for t in df]
    best, best_r = None, INF
    import itertools
    for size in range(len(cols_i) + 1):
        for S in itertools.combinations(range(len(cols_i)), size):
            cols = [cols_i[j] for j in S] + [list(r) for r in Jh]
            sol = _lstsq(cols, rhs) if cols else []
            if sol is None or any(v < 0 for v in sol[:len(S)]):
                continue
            res = [rhs[k] - sum(sol[t] * cols[t][k] for t in range(len(cols))) for k in range(n)]
            rn = math.sqrt(_dot(res, res))
            if rn < best_r - 1e-15:
                best_r = rn
                lam = [0.0] * len(g)
                for t, j in enumerate(S):
                    if j < len(act):
                        lam[act[j]] = sol[t]
                best = (lam, list(sol[len(S):]))
    if best is None:
        return [0.0] * len(g), [0.0] * len(h)
    return best


def kkt_ok(res, opts):
    r = res["residuals"]
    return (r["stationarity"] <= opts["tol_stationarity"] and r["primal_feasibility"] <= opts["tol_feasibility"]
            and r["dual_feasibility"] <= opts["tol_feasibility"] and r["complementarity"] <= opts["tol_complementarity"])


# ---------------------------------------------------------------- 结果

@dataclass
class NLPResult:
    x: list
    f: float
    g: list
    h: list
    multipliers: dict                 # {"ineq": λ, "eq": μ, "lower": ν^L, "upper": ν^U}
    residuals: dict
    kkt_satisfied: bool
    termination: str
    outer_iterations: int
    inner_iterations: int
    evaluations: int
    history: list = field(default_factory=list)
    tolerances: dict = field(default_factory=dict)
    gradient_source: str = "forward_mode_dual"
    convention: str = MULTIPLIER_CONVENTION
    claim_scope: str = CLAIM_SCOPE

    @property
    def converged(self):
        return self.termination == "kkt_tolerances_met"

    @property
    def feasible(self):
        return self.residuals["primal_feasibility"] <= self.tolerances.get("tol_feasibility", DEFAULTS["tol_feasibility"])


def _bounds(lb, ub, n):
    lb = [(-INF if v is None else float(v)) for v in (lb if lb is not None else [None] * n)]
    ub = [(INF if v is None else float(v)) for v in (ub if ub is not None else [None] * n)]
    if len(lb) != n or len(ub) != n:
        raise ValueError("界的长度与 x0 不一致")
    for l, u in zip(lb, ub):
        if l > u:
            raise ValueError(f"下界 {l} 大于上界 {u}")
    return lb, ub


def minimize(fun=None, x0=None, lb=None, ub=None, *, oracle=None, **options):
    """连续 NLP。fun(x) 返回 f / (f, g) / (f, g, h)（x 为对偶数列表，导数自动精确得到）；
    或传 oracle(x: list[float]) → (f, g, h, ∇f, Jg, Jh)（解析导数）。"""
    opts = dict(DEFAULTS)
    unknown = set(options) - set(opts)
    if unknown:
        raise TypeError(f"未知选项 {sorted(unknown)}")
    opts.update(options)
    if oracle is None:
        if fun is None:
            raise ValueError("需要 fun 或 oracle")
        oracle = dual_oracle(fun)
    src = getattr(oracle, "gradient_source", "analytic")
    n = len(x0)
    lb, ub = _bounds(lb, ub, n)
    ev = _Counter(oracle)

    # 变量仿射缩放：有限双侧界 → [0,1]
    off = [l if (math.isfinite(l) and math.isfinite(u) and u > l) else 0.0 for l, u in zip(lb, ub)]
    span = [(u - l) if (math.isfinite(l) and math.isfinite(u) and u > l) else 1.0 for l, u in zip(lb, ub)]
    zlo = [(l - o) / s for l, o, s in zip(lb, off, span)]
    zhi = [(u - o) / s for u, o, s in zip(ub, off, span)]

    def x_of(z):
        out = []
        for k in range(n):
            v = off[k] + span[k] * z[k]
            out.append(min(ub[k], max(lb[k], v)))
        return out

    z = _proj([(float(v) - o) / s for v, o, s in zip(x0, off, span)], zlo, zhi)
    f0, g0, h0, df0, Jg0, Jh0 = ev(x_of(z))
    gs = opts["gradient_scale"]

    def _sc(row):
        m = max((abs(row[k]) * span[k] for k in range(n)), default=0.0)
        return min(1.0, gs / m) if m > 0 else 1.0
    sf = max(_sc(df0), 1e-10)
    sg = [max(_sc(r), 1e-10) for r in Jg0]
    sh = [max(_sc(r), 1e-10) for r in Jh0]
    m_, p_ = len(g0), len(h0)

    def scaled(zv):
        f, g, h, df, Jg, Jh = ev(x_of(zv))
        if len(g) != m_ or len(h) != p_:
            raise ValueError("约束个数在求值之间发生变化")
        return (sf * f, [sg[i] * g[i] for i in range(m_)], [sh[j] * h[j] for j in range(p_)],
                [sf * df[k] * span[k] for k in range(n)],
                [[sg[i] * Jg[i][k] * span[k] for k in range(n)] for i in range(m_)],
                [[sh[j] * Jh[j][k] * span[k] for k in range(n)] for j in range(p_)])

    lam, mu = [0.0] * m_, [0.0] * p_
    rho = opts["rho0"]
    eps = 1e-3
    V_prev = INF
    B = None
    inner_total = 0
    history = []
    termination = "max_outer_iterations"
    outer = 0
    final = None

    for outer in range(1, opts["max_outer"] + 1):
        lam_k, mu_k, rho_k = list(lam), list(mu), rho

        def phi(zv):
            f, g, h, df, Jg, Jh = scaled(zv)
            val, grad = f, list(df)
            for i in range(m_):
                t = lam_k[i] + rho_k * g[i]
                val += (max(0.0, t) ** 2 - lam_k[i] ** 2) / (2 * rho_k)
                if t > 0:
                    for k in range(n):
                        grad[k] += t * Jg[i][k]
            for j in range(p_):
                val += mu_k[j] * h[j] + 0.5 * rho_k * h[j] ** 2
                t = mu_k[j] + rho_k * h[j]
                for k in range(n):
                    grad[k] += t * Jh[j][k]
            return val, grad

        z, _, _, B, its, inner_reason = _box_qn(phi, z, zlo, zhi, eps, opts["max_inner"], B)
        inner_total += its
        fz, gz, hz, dfz, Jgz, Jhz = scaled(z)
        lam_n = [max(0.0, lam_k[i] + rho_k * gz[i]) for i in range(m_)]
        mu_n = [mu_k[j] + rho_k * hz[j] for j in range(p_)]
        x = x_of(z)
        f, g, h, df, Jg, Jh = ev(x)
        lam_o = [lam_n[i] * sg[i] / sf for i in range(m_)]
        mu_o = [mu_n[j] * sh[j] / sf for j in range(p_)]
        kk = kkt_residuals(x, lb, ub, f, g, h, df, Jg, Jh, lam_o, mu_o)
        final = (x, f, g, h, lam_o, mu_o, kk)
        infeas_s = max([0.0] + [t for t in gz] + [abs(t) for t in hz])
        history.append({"outer": outer, "rho": rho_k, "inner_iterations": its, "inner_stop": inner_reason,
                        "f": f, **{k: kk["residuals"][k] for k in ("stationarity", "primal_feasibility",
                                                                    "complementarity")}})
        if kkt_ok(kk, opts):
            termination = "kkt_tolerances_met"
            break
        if f < opts["unbounded_value"]:
            termination = "objective_unbounded_below"
            break
        # 局部不可行判定：罚参数已很大、仍明显不可行，且约束违反量 θ=½Σ(g⁺²)+½Σh² 的投影梯度≈0
        if rho_k >= 1e6 and kk["residuals"]["primal_feasibility"] > 1e3 * opts["tol_feasibility"]:
            gt = [0.0] * n
            for i in range(m_):
                if gz[i] > 0:
                    for k in range(n):
                        gt[k] += gz[i] * Jgz[i][k]
            for j in range(p_):
                for k in range(n):
                    gt[k] += hz[j] * Jhz[j][k]
            pt = _ninf([p - v for p, v in zip(_proj([v - t for v, t in zip(z, gt)], zlo, zhi), z)])
            if pt <= 1e-6 * max(infeas_s, 1e-300) or rho_k >= opts["rho_max"]:
                termination = "local_infeasibility_detected"
                break
        if inner_reason in ("line_search_failed", "small_step") and eps <= 1e-12 and rho_k >= opts["rho_max"]:
            termination = "inner_solver_stalled"
            break
        V = max([0.0] + [abs(t) for t in hz] + [abs(min(-gz[i], lam_k[i] / rho_k)) for i in range(m_)])
        lam = [min(t, opts["multiplier_max"]) for t in lam_n]
        mu = [max(-opts["multiplier_max"], min(t, opts["multiplier_max"])) for t in mu_n]
        if V > 0.5 * V_prev and V > 1e-14 and rho < opts["rho_max"]:
            rho = min(rho * opts["rho_growth"], opts["rho_max"])
            B = None
        V_prev = V
        eps = max(eps * 0.1, 1e-12)

    x, f, g, h, lam_o, mu_o, kk = final
    tol = {k: opts[k] for k in ("tol_stationarity", "tol_feasibility", "tol_complementarity")}
    return NLPResult(x=x, f=f, g=g, h=h,
                     multipliers={"ineq": lam_o, "eq": mu_o, "lower": kk["bound_multipliers"]["lower"],
                                  "upper": kk["bound_multipliers"]["upper"]},
                     residuals=kk["residuals"], kkt_satisfied=kkt_ok(kk, opts), termination=termination,
                     outer_iterations=outer, inner_iterations=inner_total, evaluations=ev.n,
                     history=history, tolerances=tol, gradient_source=src)


# ---------------------------------------------------------------- 分支定界（整数 / 有序离散集合）

@dataclass
class MixedResult:
    x: list | None
    f: float | None
    nlp: NLPResult | None             # 整数固定后最终连续解（含乘子与 KKT 残差）
    termination: str
    nodes: int
    lower_bound: float
    gap_abs: float
    gap_rel: float
    pruned: dict
    evaluations: int
    bound_assumption: str = BNB_BOUND_ASSUMPTION
    claim_scope: str = CLAIM_SCOPE


def minimize_mixed(fun=None, x0=None, lb=None, ub=None, *, integers=(), discrete=None, oracle=None,
                   node_limit=2000, gap_abs=1e-9, gap_rel=1e-9, int_tol=1e-6, **options):
    """混合整数 NLP 分支定界。integers：整数变量下标；discrete：{下标: 允许取值序列}（有序数值集合）。
    节点松弛：整数变量在 [lb,ub] 连续；离散变量在当前允许子集的 [min,max] 连续。
    分支：整数取 floor/ceil；离散集合在松弛值处二分（SOS 式），叶节点即单值固定。"""
    n = len(x0)
    lb, ub = _bounds(lb, ub, n)
    integers = list(integers)
    discrete = {k: sorted(float(v) for v in vs) for k, vs in (discrete or {}).items()}
    for k in integers:
        lb[k], ub[k] = math.ceil(lb[k] - int_tol), math.floor(ub[k] + int_tol)
    for k, vs in discrete.items():
        if not vs:
            raise ValueError(f"离散变量 {k} 没有取值")
        lb[k], ub[k] = max(lb[k], vs[0]), min(ub[k], vs[-1])
    if oracle is None:
        oracle = dual_oracle(fun)
    ev = _Counter(oracle)
    ev.gradient_source = getattr(oracle, "gradient_source", "analytic")

    def solve(l, u, start):
        return minimize(x0=[min(b, max(a, v)) for v, a, b in zip(start, l, u)], lb=l, ub=u, oracle=ev, **options)

    def fractional(x, l, u):
        best, score = None, 0.0
        for k in integers:
            fr = abs(x[k] - round(x[k]))
            if fr > int_tol and fr > score:
                best, score = k, fr
        for k, vs in discrete.items():
            allowed = [v for v in vs if l[k] - 1e-12 <= v <= u[k] + 1e-12]
            dist = min(abs(x[k] - v) for v in allowed)
            if dist > int_tol * max(1.0, abs(x[k])) and dist > score:
                best, score = k, dist
        return best

    def snap(x, l, u):
        y = list(x)
        for k in integers:
            y[k] = float(round(y[k]))
        for k, vs in discrete.items():
            allowed = [v for v in vs if l[k] - 1e-12 <= v <= u[k] + 1e-12]
            y[k] = min(allowed, key=lambda v: abs(v - y[k]))
        return y

    open_nodes = [(-INF, 0, list(lb), list(ub), list(x0))]
    inc_x = inc_f = inc_res = None
    nodes = 0
    pruned = {"bound": 0, "infeasible": 0, "unconverged": 0}
    termination = "tree_exhausted"
    seq = 0

    def tol_of(f):
        return max(gap_abs, gap_rel * abs(f))

    while open_nodes:
        if nodes >= node_limit:
            termination = "node_limit"
            break
        if inc_f is None:
            node = open_nodes.pop()                                   # 深度优先
        else:
            i = min(range(len(open_nodes)), key=lambda t: (open_nodes[t][0], open_nodes[t][1]))
            node = open_nodes.pop(i)                                  # 最佳界优先
        bound, _, l, u, start = node
        if inc_f is not None and bound >= inc_f - tol_of(inc_f):
            pruned["bound"] += 1
            continue
        nodes += 1
        r = solve(l, u, start)
        if r.termination == "local_infeasibility_detected":
            pruned["infeasible"] += 1
            continue
        if not r.converged and not r.feasible:
            pruned["unconverged"] += 1
            continue
        nb = max(bound, r.f) if r.converged else bound
        if inc_f is not None and nb >= inc_f - tol_of(inc_f):
            pruned["bound"] += 1
            continue
        k = fractional(r.x, l, u)
        if k is None:
            y = snap(r.x, l, u)
            fl, fu = list(l), list(u)
            for j in integers + list(discrete):
                fl[j] = fu[j] = y[j]
            rf = solve(fl, fu, y)
            if rf.converged and (inc_f is None or rf.f < inc_f):
                inc_x, inc_f, inc_res = rf.x, rf.f, rf
            continue
        v = r.x[k]
        if k in discrete:
            vs = [t for t in discrete[k] if l[k] - 1e-12 <= t <= u[k] + 1e-12]
            down_hi = max(t for t in vs if t <= v)
            up_lo = min(t for t in vs if t > v)
        else:
            down_hi, up_lo = math.floor(v), math.ceil(v)
        ld, ud = list(l), list(u)
        ud[k] = down_hi
        lu, uu = list(l), list(u)
        lu[k] = up_lo
        down, up = (nb, seq + 1, ld, ud, list(r.x)), (nb, seq + 2, lu, uu, list(r.x))
        seq += 2
        # 深度优先时，后压栈者先处理：离松弛值更近的一侧先探
        first, second = (down, up) if (v - down_hi) <= (up_lo - v) else (up, down)
        open_nodes.extend([second, first])

    if inc_f is None:
        termination = "no_integer_feasible_found" if termination == "tree_exhausted" else termination
        return MixedResult(None, None, None, termination, nodes, -INF, INF, INF, pruned, ev.n)
    lbound = min([inc_f] + [nd[0] for nd in open_nodes]) if termination == "node_limit" else inc_f
    ga = max(0.0, inc_f - lbound)
    return MixedResult(inc_x, inc_f, inc_res, termination, nodes, lbound, ga, ga / max(1.0, abs(inc_f)),
                       pruned, ev.n)


# ---------------------------------------------------------------- 二阶条件（独立检查，不并入一阶结论）

def _jacobi_eigenvalues(A, tol=1e-14, max_sweeps=100):
    """对称矩阵特征值（循环 Jacobi，零依赖）。返回升序列表。"""
    n = len(A)
    a = [list(map(float, r)) for r in A]
    for _ in range(max_sweeps):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off <= tol ** 2 * max(1e-300, sum(a[i][i] ** 2 for i in range(n))) or off == 0.0:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if a[p][q] == 0.0:
                    continue
                th = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1.0 if th >= 0 else -1.0) / (abs(th) + math.sqrt(th * th + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
    return sorted(a[i][i] for i in range(n))


def _null_basis(rows, n, rank_tol=1e-10):
    """rows 张成空间的正交补（Gram–Schmidt，零依赖）。返回 (正交基列表, 秩)。"""
    basis = []
    for r in rows:
        v = list(map(float, r))
        nr = math.sqrt(_dot(v, v))
        for b in basis:
            c = _dot(v, b)
            v = [vi - c * bi for vi, bi in zip(v, b)]
        nv = math.sqrt(_dot(v, v))
        if nv > rank_tol * max(1.0, nr):
            basis.append([t / nv for t in v])
    rank = len(basis)
    Z = []
    for k in range(n):
        v = [float(i == k) for i in range(n)]
        for b in basis + Z:
            c = _dot(v, b)
            v = [vi - c * bi for vi, bi in zip(v, b)]
        nv = math.sqrt(_dot(v, v))
        if nv > 1e-8:
            Z.append([t / nv for t in v])
    return Z, rank


def second_order_check(oracle, x, lb, ub, multipliers, *, active_tol=1e-6, mult_tol=1e-8, fd_rel_step=1e-5,
                       eig_rel_tol=1e-6):
    """在 KKT 点检查二阶条件（数值）。

    拉格朗日函数 Hessian ∇²L = ∇²f + Σλ_i∇²g_i + Σμ_j∇²h_j 由"精确梯度（对偶数或解析 oracle）的有限差分"得到
    （中心差分；贴界时改单侧，不越界求值），对称化后投影到：
      Z_s = 强积极约束（λ_i > mult_tol·scale 的不等式、全部等式、ν > mult_tol·scale 的界、lb = ub 的固定变量）梯度的零空间；
      Z_a = 全部积极约束（含 λ≈0 的弱积极）梯度的零空间。
    判定：Zsᵀ∇²L Zs 正定 → sosc_satisfied（临界锥 ⊂ span Zs，二阶充分条件在容差内成立）；
          Zaᵀ∇²L Za 有负特征值 → sonc_violated（Za ⊂ 临界锥；LICQ 成立时违反二阶必要条件，不是局部极小）；
          否则 inconclusive。零维切空间时 sosc 平凡成立。
    特征值判定容差 = eig_rel_tol · max(max|∇²L|, max(1, ‖∇f‖∞))，曲率小于它记为"无法判定"。
    这是独立的数值检查（差分误差、容差判定），不并入一阶 KKT 结论，也不是证明。"""
    n = len(x)
    lb, ub = _bounds(lb, ub, n)
    lam = list(multipliers.get("ineq", []))
    mu = list(multipliers.get("eq", []))
    nl = list(multipliers.get("lower", [0.0] * n))
    nu = list(multipliers.get("upper", [0.0] * n))
    calls = [0]

    def gradL(xv):
        calls[0] += 1
        _, _, _, df, Jg, Jh = oracle(list(xv))
        gr = list(df)
        for li, row in zip(lam, Jg):
            for k in range(n):
                gr[k] += li * row[k]
        for mj, row in zip(mu, Jh):
            for k in range(n):
                gr[k] += mj * row[k]
        return gr

    f, g, h, df, Jg, Jh = oracle(list(x))
    scale = max(1.0, _ninf(df))
    H = [[0.0] * n for _ in range(n)]
    steps = []
    for k in range(n):
        hk = fd_rel_step * max(1.0, abs(x[k]))
        up_ok = x[k] + hk <= ub[k]
        dn_ok = x[k] - hk >= lb[k]
        xu, xd = list(x), list(x)
        if up_ok and dn_ok:
            xu[k] += hk
            xd[k] -= hk
            kind = "central"
        elif up_ok:
            xu[k] += hk
            kind = "forward"
        elif dn_ok:
            xd[k] -= hk
            kind = "backward"
        else:
            steps.append("fixed")
            continue
        gu, gd = gradL(xu), gradL(xd)
        span = xu[k] - xd[k]
        for i in range(n):
            H[i][k] = (gu[i] - gd[i]) / span
        steps.append(kind)
    asym = max((abs(H[i][j] - H[j][i]) for i in range(n) for j in range(n)), default=0.0)
    H = [[0.5 * (H[i][j] + H[j][i]) for j in range(n)] for i in range(n)]
    hmax = max((abs(t) for r in H for t in r), default=0.0)

    strong, weak, licq_rows = [list(r) for r in Jh], [], [list(r) for r in Jh]
    n_active = {"eq": len(Jh), "ineq_strong": 0, "ineq_weak": 0, "bound_strong": 0, "bound_weak": 0, "fixed": 0}
    for i, gi in enumerate(g):
        if gi >= -active_tol * max(1.0, _ninf(Jg[i]) * max(1.0, _ninf(x))):
            licq_rows.append(list(Jg[i]))
            if i < len(lam) and lam[i] > mult_tol * scale:
                strong.append(list(Jg[i]))
                n_active["ineq_strong"] += 1
            else:
                weak.append(list(Jg[i]))
                n_active["ineq_weak"] += 1
    for k in range(n):
        e = [float(t == k) for t in range(n)]
        if math.isfinite(lb[k]) and math.isfinite(ub[k]) and ub[k] - lb[k] <= 1e-15 * max(1.0, abs(ub[k])):
            strong.append(e)
            n_active["fixed"] += 1
            continue
        at_l = math.isfinite(lb[k]) and x[k] - lb[k] <= active_tol * max(1.0, abs(lb[k]))
        at_u = math.isfinite(ub[k]) and ub[k] - x[k] <= active_tol * max(1.0, abs(ub[k]))
        if at_l or at_u:
            licq_rows.append(e)
            nu_k = nl[k] if at_l else nu[k]
            if nu_k > mult_tol * scale:
                strong.append(e)
                n_active["bound_strong"] += 1
            else:
                weak.append(e)
                n_active["bound_weak"] += 1
    Zs, _ = _null_basis(strong, n)
    Za, _ = _null_basis(strong + weak, n)
    _, rank_licq = _null_basis(licq_rows, n)

    def reduced(Z):
        if not Z:
            return []
        HZ = [[sum(H[i][k] * z[k] for k in range(n)) for i in range(n)] for z in Z]
        R = [[_dot(Z[a], HZ[b]) for b in range(len(Z))] for a in range(len(Z))]
        return _jacobi_eigenvalues(R)

    es, ea = reduced(Zs), reduced(Za)
    tol = eig_rel_tol * max(hmax, scale)      # scale = max(1, ‖∇f‖∞)，与一阶残差归一化同口径
    if not Zs:
        status = "sosc_satisfied"
    elif es[0] > tol:
        status = "sosc_satisfied"
    elif ea and ea[0] < -tol:
        status = "sonc_violated"
    else:
        status = "inconclusive"
    return {"property": "second_order", "status": status,
            "hessian_source": "finite_difference_of_exact_gradient", "fd_rel_step": fd_rel_step, "fd_kinds": steps,
            "hessian_asymmetry_abs": asym, "hessian_max_abs": hmax, "eigen_tolerance": tol,
            "tangent_dim_strong": len(Zs), "tangent_dim_all_active": len(Za),
            "eigenvalues_strong": es, "eigenvalues_all_active": ea,
            "active_counts": n_active, "licq_holds": rank_licq == len(licq_rows),
            "strict_complementarity": n_active["ineq_weak"] == 0 and n_active["bound_weak"] == 0,
            "gradient_evaluations": calls[0],
            "meaning": ("二阶条件的数值检查（约化 Hessian 特征值，有限差分）：独立字段，不并入一阶 KKT 结论，"
                        "不是证明；sonc_violated 的结论依赖 LICQ（见 licq_holds）")}
