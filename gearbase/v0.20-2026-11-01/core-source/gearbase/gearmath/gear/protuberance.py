"""残余凸台（protuberance）齿根几何：ISO 6336-3:2019 6.2.3 式(26)。

式(26)（PDF26/印18 原图已核）：
    E = π/4·mn − hfP·tanαn + spr/cosαn − (1 − sinαn)·ρfP/cosαn，spr = pr − q（图2），无根切时 spr = 0。
本库原 root.E（formulas.py）为 spr=0 的特例；这里按轮给出含 spr 的一般式，供 TR30 例8 与
KISSsoft K03（预加工+磨削、残余凸台）复用：调用方只需提供逐轮 hfP_i、rhofP_i（以 mn 为单位的系数）
与 s_pr_i（mm）。G、H、θ、sFn、ρF、hFe 的其余式(27)–(32) 不变，仍由主库 ROOT 公式按轮替换后使用。
适用前提（6.1 a)–c)）：30° 切点落在齿条刀圆角生成的过渡曲线上、ρfP>0、范成刀具加工。
"""
from __future__ import annotations

from ..kernel.graph import Formula, InputSpec

R3 = "ISO 6336-3:2019"


def protuberance_rack(i, hfP=None, rhofP=None, spr=None):
    """第 i 轮的式(26) 辅助量 E（mm）。参数名可替换，以便预加工/精加工刀具分别装配。"""
    hfP, rhofP, spr = hfP or f"hfP_{i}", rhofP or f"rhofP_{i}", spr or f"s_pr_{i}"
    return Formula(f"prot.rack_E.{i}", f"rack_E_{i}", "mm",
                   f"pi/4*m_n - {hfP}*m_n*tan(alpha_n) + {spr}/cos(alpha_n) - (1 - sin(alpha_n))*{rhofP}*m_n/cos(alpha_n)",
                   f"{R3} 6.2.3 式(26) 含残余凸台 spr=pr−q（PDF26/印18 原图已核；spr=0 即无凸台特例）",
                   (f"{rhofP} > 0", f"{spr} >= 0"))


PROTUBERANCE_INPUTS = [
    *[InputSpec(f"s_pr_{i}", "mm", f"第{i}轮残余凸台量 spr=pr−q（ISO 6336-3 图2）", (f"s_pr_{i} >= 0",)) for i in (1, 2)],
]


# ---------------- 预加工（凸台刀）+ 磨削后的有效齿根形状圆 dFf（数值包络，不进公式图） ----------------
# 依据与证据性质（逐项见 docs/M33-验收报告.md "KISSsoft 复算（例7、例8）"一节）：
# - 预加工刀具齿根圆角圆心：ISO 6336-3:2019 式(26)（PDF26/印18 原图已核）。在切削阶段（尚未磨削，q=0）用预加工齿条
#   h_fP0、ρ_fP、pr 代入，即 E0 = π/4·mn − h_fP0·mn·tanαn + pr/cosαn − (1−sinαn)·ρ_fP/cosαn，圆角与齿顶线相切（图2）。
#   与式(26) 用精加工 h_fP、s_pr=pr−q 的写法等价，条件是 (h_fP0−h_fP)·mn·sinαn = q（原表三位小数下差 1e-4 mm 量级）。
# - 展成运动：齿条在端面内纯滚动于分度圆（ISO/TR 6336-30:2022 A.6 dFf/dNf 同一原理，PDF50/印45 原图已核；
#   法面高度不变、法面水平尺寸除以 cosβ）；包络点取齿条廓线法线过节点的位置（啮合基本定律）。
# - 预加工展成变位 xEV = xE + q/(mn·sinαn)：ISO 21771-1:2024 9.5 式(249)(250)（用户提供原图已核，见 tr30_examples58）。
# - 凸台侧边：直线、压力角 α_prP0（TR30 表17 "Cutting tool protuberance angle"，PDF43/印38），与圆角相切。
#   该角是"凸台侧边压力角"还是"与主侧边夹角"原图未定义（例8 αn=20°、角 10° 时两种读法数值相同）；ISO 6336-3 图2
#   把凸台侧边画成与主侧边平行（示意），未给凸台高度。例8 的交点落在圆角包络上，结果对凸台角不敏感（9°/11° 不变）。
# - 有效 dFf 定义为"磨削后渐开线（xE）与预加工齿廓（xEV 展成）的最外交点"。资料包内没有该定义的原文
#   （ISO 21771 的 dFf 定义不在资料包）：无法确认，按"渐开线工作齿面的起点"含义使用。
# 证据性质：composition_of_verified_formulas + numerical_envelope；凸台高度 h_prP0 为派生量（旁证：与 KISSsoft
# Tool.RefProfile.hprP 一致），不作为输入。
import math as _m

from ..kernel.methods import NumericalMethod, converged

PROTUBERANCE_DFF_SOURCES = {
    "fillet_centre": "ISO 6336-3:2019 6.2.3 式(26)（PDF26/印18 原图已核），切削阶段 q=0 → s_pr=pr",
    "generation": "ISO/TR 6336-30:2022 Annex A.6 dFf 齿条展成原理（PDF50/印45 原图已核），端面纯滚动",
    "pre_finish_shift": "ISO 21771-1:2024 9.5 式(249)(250)：xEV = xE + q/(mn·sinαn)",
    "protuberance_angle": "ISO/TR 6336-30:2022 表17（PDF43/印38）Cutting tool protuberance angle（口径原图未定义）",
    "dFf_definition": "无法确认：磨削渐开线与预加工齿廓最外交点（ISO 21771 定义不在资料包）",
}


def _inv(a):
    return _m.tan(a) - a


def _protuberance_geometry(p):
    mn, an, apr, rho = p["m_n"], p["alpha_n"], p["alpha_pr"], p["rhofP"] * p["m_n"]
    vt = p["hfP_cut"] * mn                     # 刀尖线深度（自基准线起，指向齿轮中心为正）
    vc = vt - rho
    uc = _m.pi * mn / 4 - vt * _m.tan(an) + p["pr_cut"] / _m.cos(an) - rho * (1 - _m.sin(an)) / _m.cos(an)   # 式(26)
    ut, vtp = uc + rho * _m.cos(apr), vc + rho * _m.sin(apr)      # 凸台侧边与圆角切点
    vi = (_m.pi * mn / 4 - ut - vtp * _m.tan(apr)) / (_m.tan(an) - _m.tan(apr))   # 凸台侧边与主侧边交点深度
    return {"uc": uc, "vc": vc, "ut": ut, "vtp": vtp, "vi": vi, "vt": vt, "rho": rho,
            "h_prP0": (vt - vi) / mn, "pr_check": (uc + vc * _m.tan(an) - _m.pi * mn / 4) * _m.cos(an) + rho}


def protuberance_dff(p, n=200):
    """返回 (dFf_mm, detail)。p 键：z, m_n, alpha_n, beta, hfP_cut, rhofP, pr_cut, alpha_pr（rad）, x_cut, x_fin。

    全部为显式输入，缺任何一项抛 KeyError；不设默认。n 为每条廓线分支的扫描区间数（交点由二分求到机器精度）。"""
    need = ("z", "m_n", "alpha_n", "beta", "hfP_cut", "rhofP", "pr_cut", "alpha_pr", "x_cut", "x_fin")
    missing = [k for k in need if k not in p or p[k] is None]
    if missing:
        raise KeyError(f"凸台 dFf 缺输入：{missing}")
    z, mn, an, b, apr = p["z"], p["m_n"], p["alpha_n"], p["beta"], p["alpha_pr"]
    q = (p["x_cut"] - p["x_fin"]) * mn * _m.sin(an)
    if z <= 0:
        raise ValueError("仅外齿（z>0）齿条展成")
    if not 0 < apr < an:
        raise ValueError("凸台侧边压力角须在 (0, αn) 内")
    if not p["pr_cut"] > q > 0:
        raise ValueError(f"须有残余凸台 s_pr=pr−q>0（pr={p['pr_cut']}, q={q}）")
    g = _protuberance_geometry(p)
    if not 0 < g["vi"] < g["vtp"]:
        raise ValueError("凸台侧边与主侧边交点不在齿条基准线与圆角切点之间，几何不封闭")
    at = _m.atan(_m.tan(an) / _m.cos(b))
    r = z * mn / _m.cos(b) / 2
    rb = r * _m.cos(at)
    vr = p["x_cut"] * mn
    s_fin = (_m.pi * mn / 4 - p["x_fin"] * mn * _m.tan(an)) / _m.cos(b)

    def contact(u, v, nu, nv):
        """法面刀具点 (u,v) 与法向 (nu,nv) → 端面包络点的齿轮系极坐标 (R, θ)。"""
        ut_, d = u / _m.cos(b), v - vr
        nx, ny = nu * _m.cos(b), -nv
        s = (-d) * nx / ny - ut_
        x, y, ph = ut_ + s, r - d, s / r
        xg, yg = x * _m.cos(ph) - y * _m.sin(ph), x * _m.sin(ph) + y * _m.cos(ph)
        return _m.hypot(xg, yg), _m.atan2(xg, yg)

    uc, vc, rho, ut, vtp, vi = g["uc"], g["vc"], g["rho"], g["ut"], g["vtp"], g["vi"]
    branches = {
        "fillet": (apr, _m.pi / 2 - 1e-9, lambda t: contact(uc + rho * _m.cos(t), vc + rho * _m.sin(t), _m.cos(t), _m.sin(t))),
        "protuberance": (vi, vtp, lambda v: contact(ut - (v - vtp) * _m.tan(apr), v, _m.cos(apr), _m.sin(apr))),
        "main_pre": (0.0, vi, lambda v: contact(_m.pi * mn / 4 - v * _m.tan(an), v, _m.cos(an), _m.sin(an))),
    }

    def eta_fin(R):
        return None if R < rb else s_fin / r + _inv(_m.acos(min(1.0, rb / R))) - _inv(at)

    def gap(fn, t):
        R, th = fn(t)
        e = eta_fin(R)
        return None if e is None else th - e

    hits = []
    for name, (lo, hi, fn) in branches.items():
        ts = [lo + (hi - lo) * j / n for j in range(n + 1)]
        vals = [gap(fn, t) for t in ts]
        for j in range(n):
            a, c = vals[j], vals[j + 1]
            if a is None or c is None or (a > 0) == (c > 0):
                continue
            ta, tc = ts[j], ts[j + 1]
            for _ in range(200):
                tm = (ta + tc) / 2
                fm = gap(fn, tm)
                if fm is None:
                    break
                if (fm > 0) == (a > 0):
                    ta, a = tm, fm
                else:
                    tc = tm
            R, th = fn((ta + tc) / 2)
            hits.append((R, th, name))
    if not hits:
        raise ArithmeticError("磨削渐开线与预加工齿廓无交点")
    R, th, branch = max(hits)

    # 交点须在预加工齿槽边界上：同一半径处其它分支不得切得更深
    def theta_at(fn, lo, hi, Rt):
        out = []
        ts = [lo + (hi - lo) * j / n for j in range(n + 1)]
        rs = [fn(t)[0] - Rt for t in ts]
        for j in range(n):
            if (rs[j] > 0) != (rs[j + 1] > 0):
                ta, tc = ts[j], ts[j + 1]
                for _ in range(200):
                    tm = (ta + tc) / 2
                    if (fn(tm)[0] - Rt > 0) == (rs[j] > 0):
                        ta = tm
                    else:
                        tc = tm
                out.append(fn((ta + tc) / 2)[1])
        return out
    deeper = [(name, t) for name, (lo, hi, fn) in branches.items() for t in theta_at(fn, lo, hi, R) if t > th + 1e-12]
    if deeper:
        raise ArithmeticError(f"交点被其它分支切除，不在齿槽边界上：{deeper}")
    return 2 * R, {"branch": branch, "all_crossings_mm": sorted(2 * h[0] for h in hits), "q_mm": q,
                   "s_pr_mm": p["pr_cut"] - q, "h_prP0_derived": g["h_prP0"], "pr_reconstructed_mm": g["pr_check"],
                   "protuberance_flank_meets_main_at_depth_mm": vi}


PROTUBERANCE_DFF = NumericalMethod("protuberance.dFf.envelope", "d_Ff", "mm",
                                   lambda p, level: protuberance_dff(p, n=50 * 2 ** level)[0], order=2.0)


def protuberance_dff_converged(p):
    """数值方法外壳：逐级加密扫描（50/100/200 区间）并检查收敛（最后两级相对变化 <1e-9）。"""
    result = converged(PROTUBERANCE_DFF, p, levels=(1, 2, 3), rel_tol=1e-9)
    value, detail = protuberance_dff(p, n=400)
    return result, {**detail, "value_finest_check": value, "sources": PROTUBERANCE_DFF_SOURCES,
                    "evidence_nature": "composition_of_verified_formulas + numerical_envelope（dFf 定义无法确认）"}
