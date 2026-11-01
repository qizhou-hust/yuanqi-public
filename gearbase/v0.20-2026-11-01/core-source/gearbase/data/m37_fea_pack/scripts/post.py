"""后处理数学：主应力、积分点→表面外推（不做节点平滑）、Richardson 外推、penalty 外推、Hertz 椭圆拟合。零依赖。"""
from __future__ import annotations

import math


def principal_max(s):
    """s = (sxx, syy, szz, sxy, sxz, syz)；平面问题 sxz=syz≈0。返回第一主应力（三维张量最大特征值）。"""
    sxx, syy, szz, sxy, sxz, syz = (list(s) + [0.0] * 6)[:6]
    if abs(sxz) + abs(syz) > 1e-9 * (abs(sxx) + abs(syy) + abs(szz) + 1e-30):
        return _eig3_max(sxx, syy, szz, sxy, sxz, syz)
    c = 0.5 * (sxx + syy)
    r = math.hypot(0.5 * (sxx - syy), sxy)
    return max(c + r, szz)


def _eig3_max(a, b, c, d, e, f):
    # 对称 3x3 [[a,d,e],[d,b,f],[e,f,c]] 最大特征值（三角公式）
    p1 = d * d + e * e + f * f
    q = (a + b + c) / 3
    p2 = (a - q) ** 2 + (b - q) ** 2 + (c - q) ** 2 + 2 * p1
    p = math.sqrt(p2 / 6)
    if p == 0:
        return q
    B = [[(a - q) / p, d / p, e / p], [d / p, (b - q) / p, f / p], [e / p, f / p, (c - q) / p]]
    detB = (B[0][0] * (B[1][1] * B[2][2] - B[1][2] * B[2][1]) - B[0][1] * (B[1][0] * B[2][2] - B[1][2] * B[2][0])
            + B[0][2] * (B[1][0] * B[2][1] - B[1][1] * B[2][0]))
    r = max(-1.0, min(1.0, detB / 2))
    phi = math.acos(r) / 3
    return q + 2 * p * math.cos(phi)


def solve(A, b):
    """高斯消元（部分选主元）。"""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for k in range(n):
        piv = max(range(k, n), key=lambda i: abs(M[i][k]))
        if abs(M[piv][k]) < 1e-300:
            raise ArithmeticError("奇异矩阵")
        M[k], M[piv] = M[piv], M[k]
        for i in range(k + 1, n):
            fct = M[i][k] / M[k][k]
            for j in range(k, n + 1):
                M[i][j] -= fct * M[k][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def lstsq(rows, y):
    m = len(rows[0])
    A = [[sum(r[i] * r[j] for r in rows) for j in range(m)] for i in range(m)]
    b = [sum(r[i] * yy for r, yy in zip(rows, y)) for i in range(m)]
    return solve(A, b)


def extrapolate_element(ip_xy, ip_vals, targets):
    """单元内积分点 → 目标点（表面）外推：对每个应力分量在物理坐标中做多项式最小二乘
    （面内不同积分点位置 ≥6 → 二次 6 项，否则线性 3 项），坐标先按单元尺度归一化。
    ip_xy：[(x,y)]；ip_vals：[[6 分量]]；targets：[(x,y)]。返回 [[6 分量] per target]。"""
    uniq = {}
    for (x, y), v in zip(ip_xy, ip_vals):
        k = (round(x, 9), round(y, 9))
        uniq.setdefault(k, []).append(v)
    pts = list(uniq)
    vals = [[sum(c) / len(vs) for c in zip(*vs)] for vs in uniq.values()]   # 厚度方向重复点取平均
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    L = max(max(math.hypot(p[0] - cx, p[1] - cy) for p in pts), 1e-12)
    quad = len(pts) >= 6

    def basis(x, y):
        u, v = (x - cx) / L, (y - cy) / L
        return [1, u, v, u * u, u * v, v * v] if quad else [1, u, v]
    rows = [basis(*p) for p in pts]
    out = []
    coefs = [lstsq(rows, [v[c] for v in vals]) for c in range(len(vals[0]))]
    for t in targets:
        bt = basis(*t)
        out.append([sum(a * b for a, b in zip(co, bt)) for co in coefs])
    return out, ("quadratic" if quad else "linear"), len(pts)


def richardson(hs, fs, p_assumed=2.0, p_range=(0.5, 5.0)):
    """三级（或更多级，用最细三级）网格 Richardson 外推。hs 由粗到细。
    返回 observed_order、extrapolated、GCI_fine（Roache, Fs=1.25）、单调性、逐级相对变化。"""
    if len(hs) < 2:
        return {"status": "insufficient_levels"}
    rel = [abs(fs[i + 1] - fs[i]) / abs(fs[i + 1]) for i in range(len(fs) - 1)]
    out = {"levels_h": list(hs), "values": list(fs), "relative_changes": rel}
    if len(hs) < 3:
        r = hs[-2] / hs[-1]
        ext = fs[-1] + (fs[-1] - fs[-2]) / (r ** p_assumed - 1)
        out.update(status="two_level_assumed_order", observed_order=None, order_used=p_assumed, extrapolated=ext,
                   gci_fine=1.25 * abs(fs[-1] - fs[-2]) / (r ** p_assumed - 1) / abs(fs[-1]))
        return out
    h1, h2, h3 = hs[-3:]
    f1, f2, f3 = fs[-3:]
    r21, r32 = h1 / h2, h2 / h3
    e21, e32 = f2 - f1, f3 - f2
    monotone = e21 * e32 > 0
    p = None
    if monotone and e32 != 0:
        # 非等比时固定点迭代（Celik et al. 2008）
        p = math.log(abs(e21 / e32)) / math.log(r21)
        for _ in range(50):
            s = 1.0 if e21 / e32 > 0 else -1.0
            q = math.log((r21 ** p - s) / (r32 ** p - s)) if r21 != r32 else 0.0
            pn = abs(math.log(abs(e21 / e32)) + q) / math.log(r21)
            if abs(pn - p) < 1e-10:
                p = pn
                break
            p = pn
    if p is not None and p_range[0] <= p <= p_range[1]:
        used, status = p, "observed_order"
    else:
        used, status = p_assumed, ("oscillatory_assumed_order" if not monotone else "order_out_of_range_assumed_order")
    ext = f3 + e32 / (r32 ** used - 1)
    gci = 1.25 * abs(e32) / (r32 ** used - 1) / abs(f3) if f3 else None
    out.update(status=status, monotone=monotone, observed_order=p, order_used=used, extrapolated=ext, gci_fine=gci,
               spread_last3=(max(fs[-3:]) - min(fs[-3:])) / abs(f3))
    return out


def penalty_extrapolate(Ks, fs):
    """f(K) = f_inf - c/K 最小二乘；返回外推值、残差、与最大 K 结果之差。"""
    rows = [[1.0, 1.0 / k] for k in Ks]
    a, b = lstsq(rows, fs)
    res = [f - (a + b / k) for k, f in zip(Ks, fs)]
    i = max(range(len(Ks)), key=lambda j: Ks[j])
    return {"penalties": list(Ks), "values": list(fs), "model": "f(K)=f_inf - c/K", "f_inf": a, "c": -b,
            "max_abs_residual_rel": max(abs(r) for r in res) / abs(a) if a else None,
            "rel_diff_stiffest_vs_inf": abs(fs[i] - a) / abs(a) if a else None}


def hertz_line(q, R1, R2, E1, nu1, E2, nu2):
    """平面应变 Hertz 线接触：q 单位长度载荷 N/mm；R 曲率半径（凸为正）。"""
    R = 1 / (1 / R1 + 1 / R2)
    Es = 1 / ((1 - nu1 ** 2) / E1 + (1 - nu2 ** 2) / E2)
    a = math.sqrt(4 * q * R / (math.pi * Es))
    return {"half_width_mm": a, "p0_MPa": 2 * q / (math.pi * a), "R_eff_mm": R, "E_star_MPa": Es}


def ellipse_fit(s, p, frac=0.15):
    """p(s)=p0*sqrt(1-((s-s0)/a)^2)：对 p>frac*pmax 的点在 p^2 上做二次最小二乘。"""
    pm = max(p)
    pts = [(si, pi) for si, pi in zip(s, p) if pi > frac * pm]
    if len(pts) < 4:
        return None
    sc = sum(x for x, _ in pts) / len(pts)
    A, B, C = lstsq([[1, x - sc, (x - sc) ** 2] for x, _ in pts], [y * y for _, y in pts])
    if C >= 0:
        return None
    s0 = -B / (2 * C)
    p02 = A - B * B / (4 * C)
    if p02 <= 0:
        return None
    return {"p0": math.sqrt(p02), "a": math.sqrt(-p02 / C), "s0": s0 + sc, "n_points": len(pts)}
