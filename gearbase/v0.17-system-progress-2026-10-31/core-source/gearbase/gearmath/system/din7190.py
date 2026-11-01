"""DIN 7190-1:2017-02 圆柱面过盈配合：纯弹性设计主流程（方法 1：给定接合压力 p；方法 2：给定过盈量 U）。

资料与核对口径（本机私有 PDF "DIN 7190-1 2017 English.pdf"，46 页英译本，页眉 DIN 7190-1:2017-02；PDF 页 = 印刷页）：
逐式渲染原图核对，代码只写条款号、式号、页码。
  - 4.1 式(1)–(7)、(10)–(12)（PDF7–9）；4.2 纯弹性 式(13)–(25)（PDF9–11）。
  - 附录A A.1–A.4 纯弹性算例（PDF28–30）：测试逐步复现 → 相关式证据 E4（标准配套算例复现）。
未收录（TODO/阻断）：4.3 弹塑性（式(26)–(43)）、第5章 附着系数 ν 表、第8章 装配/热装（式(48)–(53)）、
第10章 离心力（式(54)–(58)）、6.3 交变载荷设计规则（式(44)–(47)）。ν_ru、ν_rl、S_r、S_P、g_F 一律由调用方给出。
单位：长度 mm（过盈量 U、Rz 以 mm 传入，µm 请先 /1000）；应力、压力、弹性模量 N/mm²；力 N；力矩 N·mm。
"""
from __future__ import annotations

import math

from ._base import OutOfDomain, Unconfirmed, bad, make_registry, nonneg, num, pos

STD = "DIN 7190-1:2017"
FORMULAS, _formula = make_registry(r"^DIN 7190-1", "无标准配套算例覆盖该式：测试仅为独立重写对拍（自洽）")
_TEST = "tests/test_m36_din7190.py::TestAnnexA"


def _ex(*names):
    return {"level": "E4", "source": f"{STD} 附录A " + "、".join(names) + "（PDF28–30/印28–30）", "test": _TEST}


# KISSsoft 同输入外部对拍（v0.14 EXTC）：只登记"由 U 直接给定"的 A2/A4（输入逐字段与附录一致、U 未经本库换算），
# A1/A3 的 U 由本库式(18)(19)+式(7) 从 p 换算 → 往返一致，不独立，不登记。
_KS_TEST = "tests/test_m36_kisssoft_v014.py::TestFitKISSsoft"
_KS_R5 = {"level": "E5", "test": "tests/test_m36_kisssoft_v015.py::TestDin7190KISSsoft",
          "source": "KISSsoft Release 2026 M010 R5-fit-A1..A4-T500（T_nom = 500 N·m；M10 sha256 A1 59491f3e8a0a…/A2 40c6992f7e44…/A3 2bdc3fb69d0b…/A4 d84f2db10eca…；提取件 data/kisssoft_v015/R5-fit-T500.json）："
                    "Sr = 式(1)(S_r = 1)/T_nom 逐例一致；Tlimit（避免微滑的最大转矩，供应商模板定义）不属式(1)，仅记录"}


def _ks(*cases):
    sh = {"A2": "8f1f36d13256", "A4": "f3a29daea22c"}
    return {"level": "E5", "test": _KS_TEST,
            "source": "KISSsoft Release 2026 M010 " + "、".join(f"P4-fit-{c}-mapped-v2（result.json sha256 {sh[c]}…）" for c in cases)
                      + "；提取件 data/kisssoft_v014/P4-fit-*.json"}


@_formula("din7190.eq1", f"{STD} 4.1 式(1) T = (π/2)·D_F²·l_F·ν_ru·p/S_r（PDF7/印7 原图已核）",
          external=_KS_R5)
def transferable_torque(*, D_F, l_F, nu_ru, p, S_r):
    return math.pi / 2.0 * pos("D_F", D_F) ** 2 * pos("l_F", l_F) * pos("nu_ru", nu_ru) * nonneg("p", p) / pos("S_r", S_r)


@_formula("din7190.eq1_inverse", f"{STD} 4.1 式(1) 改写：传递扭矩 T 所需接合压力 p = 2·T·S_r/(π·D_F²·l_F·ν_ru)（PDF7/印7 原图已核；本库改写）")
def pressure_for_torque(*, T, D_F, l_F, nu_ru, S_r):
    return 2.0 * nonneg("T", T) * pos("S_r", S_r) / (math.pi * pos("D_F", D_F) ** 2 * pos("l_F", l_F) * pos("nu_ru", nu_ru))


@_formula("din7190.eq2", f"{STD} 4.1 式(2) F_ax = π·D_F·l_F·ν_rl·p/S_r（PDF7/印7 原图已核）")
def transferable_axial_force(*, D_F, l_F, nu_rl, p, S_r):
    return math.pi * pos("D_F", D_F) * pos("l_F", l_F) * pos("nu_rl", nu_rl) * nonneg("p", p) / pos("S_r", S_r)


@_formula("din7190.eq4_5", f"{STD} 4.1 式(4) U_g = A_oI − A_uA > 0、式(5) U_k = A_uI − A_oA > 0（同名义尺寸；PDF8/印8 原图已核）")
def interference_limits(*, A_oI, A_uI, A_oA, A_uA):
    Ug = num("A_oI", A_oI) - num("A_uA", A_uA)
    Uk = num("A_uI", A_uI) - num("A_oA", A_oA)
    if not (Ug > 0 and Uk > 0):
        raise OutOfDomain("deviations", f"式(4)(5) 要求 U_g > 0 且 U_k > 0，得 U_g={Ug}、U_k={Uk}（非过盈配合）")
    return {"U_g": Ug, "U_k": Uk}


@_formula("din7190.eq7", f"{STD} 4.1 式(7) U_w = U − g_F·(Rz_A + Rz_I)，无经验值时 g_F = 0,4（PDF8/印8 原图已核）",
          note="g_F 须显式给出（式中印 0,4 为'无经验值时'的取值，本库不默认）", evidence=_ex("A.1", "A.2", "A.3", "A.4"),
          external=_ks("A2", "A4"))
def effective_interference(*, U, Rz_A, Rz_I, g_F):
    Uw = pos("U", U) - pos("g_F", g_F) * (nonneg("Rz_A", Rz_A) + nonneg("Rz_I", Rz_I))
    if Uw <= 0:
        raise OutOfDomain("U", f"有效过盈 U_w = {Uw} ≤ 0")
    return Uw


@_formula("din7190.eq7_inverse", f"{STD} 4.1 式(7) 反解 U = U_w + g_F·(Rz_A + Rz_I)（PDF8/印8 原图已核；附录A A.1/A.3 用法同）",
          evidence=_ex("A.1", "A.3"))
def interference_from_effective(*, U_w, Rz_A, Rz_I, g_F):
    return pos("U_w", U_w) + pos("g_F", g_F) * (nonneg("Rz_A", Rz_A) + nonneg("Rz_I", Rz_I))


@_formula("din7190.eq10_11", f"{STD} 4.1 式(10) Q_A = D_F/D_aA、式(11) Q_I = D_iI/D_F（PDF9/印9 原图已核）", evidence=_ex("A.1", "A.3"),
          external=_ks("A2", "A4"))
def diameter_ratios(*, D_F, D_aA, D_iI):
    DF, DaA, DiI = pos("D_F", D_F), pos("D_aA", D_aA), nonneg("D_iI", D_iI)
    if not DiI < DF < DaA:
        raise OutOfDomain("diameters", "须 D_iI < D_F < D_aA")
    return {"Q_A": DF / DaA, "Q_I": DiI / DF}


@_formula("din7190.eq12", f"{STD} 4.1 式(12) ξ_w = U_w/D_F（PDF9/印9 原图已核）", evidence=_ex("A.1", "A.2", "A.3", "A.4"),
          external=_ks("A2", "A4"))
def reference_effective_interference(*, U_w, D_F):
    return pos("U_w", U_w) / pos("D_F", D_F)


@_formula("din7190.eq13_14", f"{STD} 4.2.1 式(13) K = (E_A/E_I)·((1+Q_I²)/(1−Q_I²) − μ_I) + (1+Q_A²)/(1−Q_A²) + μ_A；Q_I=0 时为式(14)"
          "（PDF9/印9 原图已核）", evidence=_ex("A.3"), external=_ks("A4"))
def aux_K(*, E_A, E_I, mu_A, mu_I, Q_A, Q_I):
    EA, EI, mA, mI = pos("E_A", E_A), pos("E_I", E_I), nonneg("mu_A", mu_A), nonneg("mu_I", mu_I)
    QA, QI = pos("Q_A", Q_A), nonneg("Q_I", Q_I)
    if not (QA < 1 and QI < 1):
        raise OutOfDomain("Q", "须 Q_A < 1、Q_I < 1")
    return EA / EI * ((1 + QI ** 2) / (1 - QI ** 2) - mI) + (1 + QA ** 2) / (1 - QA ** 2) + mA


def _equal_solid(Q_I, E_A, E_I, mu_A, mu_I):
    return Q_I == 0 and E_A == E_I and mu_A == mu_I


@_formula("din7190.eq15_17", f"{STD} 4.2.2 式(15) 外件 p ≤ (1−Q_A²)·R_eLA/(√3·S_PA)；式(16) 空心内件 p ≤ (1−Q_I²)·R_eLI/(√3·S_PI)；"
          "式(17) 实心内件 p ≤ 2·R_eLI/(√3·S_PI)（PDF10/印10 原图已核）",
          note="式(16) 在 Q_I → 0 时与式(17) 不连续（1/√3 vs 2/√3），照原文按 Q_I 是否为 0 分支", evidence=_ex("A.1", "A.3"))
def pressure_limits(*, Q_A, Q_I, R_eLA, R_eLI, S_PA, S_PI):
    QA, QI = pos("Q_A", Q_A), nonneg("Q_I", Q_I)
    pA = (1 - QA ** 2) * pos("R_eLA", R_eLA) / (math.sqrt(3.0) * pos("S_PA", S_PA))
    if QI > 0:
        pI, eqI = (1 - QI ** 2) * pos("R_eLI", R_eLI) / (math.sqrt(3.0) * pos("S_PI", S_PI)), "eq16"
    else:
        pI, eqI = 2.0 * pos("R_eLI", R_eLI) / (math.sqrt(3.0) * pos("S_PI", S_PI)), "eq17"
    return {"p_max_outer": pA, "p_max_inner": pI, "inner_equation": eqI}


@_formula("din7190.eq18_19", f"{STD} 4.2.2 式(18) ξ_w = K·p/E_A；实心内件且弹性常数相同时式(19) ξ_w = 2/(1−Q_A²)·p/E（PDF10/印10 原图已核）",
          evidence=_ex("A.1", "A.3"))
def xi_from_pressure(*, p, Q_A, Q_I, E_A, E_I, mu_A, mu_I):
    """返回 {"xi_w", "K"(式19 分支为 None), "equation"}。"""
    p = pos("p", p)
    if _equal_solid(nonneg("Q_I", Q_I), pos("E_A", E_A), pos("E_I", E_I), nonneg("mu_A", mu_A), nonneg("mu_I", mu_I)):
        return {"xi_w": 2.0 / (1 - pos("Q_A", Q_A) ** 2) * p / E_A, "K": None, "equation": "eq19"}
    K = aux_K(E_A=E_A, E_I=E_I, mu_A=mu_A, mu_I=mu_I, Q_A=Q_A, Q_I=Q_I)
    return {"xi_w": K * p / E_A, "K": K, "equation": "eq18"}


@_formula("din7190.eq20_23", f"{STD} 4.2.3 式(20) 外件 ξ_w ≤ K·(1−Q_A²)/(√3·S_PA)·R_eLA/E_A；式(21) 空心内件 ξ_w ≤ K·(1−Q_I²)/(√3·S_PI)·R_eLI/E_A；"
          "实心内件且弹性常数相同：式(22) ξ_w ≤ 2R_eLA/(√3·S_PA·E)、式(23) ξ_w ≤ 4R_eLI/(√3(1−Q_A²)·S_PI·E)（PDF10–11/印10–11 原图已核）",
          note="实心内件但弹性常数不同：原文方法 2 未给内件条件 → 阻断", evidence=_ex("A.2", "A.4"))
def xi_limits(*, Q_A, Q_I, E_A, E_I, mu_A, mu_I, R_eLA, R_eLI, S_PA, S_PI):
    QA, QI = pos("Q_A", Q_A), nonneg("Q_I", Q_I)
    EA, EI = pos("E_A", E_A), pos("E_I", E_I)
    RA, RI, SA, SI = pos("R_eLA", R_eLA), pos("R_eLI", R_eLI), pos("S_PA", S_PA), pos("S_PI", S_PI)
    s3 = math.sqrt(3.0)
    if _equal_solid(QI, EA, EI, nonneg("mu_A", mu_A), nonneg("mu_I", mu_I)):
        return {"xi_max_outer": 2 * RA / (s3 * SA * EA), "xi_max_inner": 4 * RI / (s3 * (1 - QA ** 2) * SI * EA),
                "equations": ("eq22", "eq23"), "K": None}
    if QI == 0:
        raise Unconfirmed("Q_I", "实心内件且弹性常数不同：4.2.3 未给内件 ξ_w 限值式")
    K = aux_K(E_A=EA, E_I=EI, mu_A=mu_A, mu_I=mu_I, Q_A=QA, Q_I=QI)
    return {"xi_max_outer": K * (1 - QA ** 2) / (s3 * SA) * RA / EA, "xi_max_inner": K * (1 - QI ** 2) / (s3 * SI) * RI / EA,
            "equations": ("eq20", "eq21"), "K": K}


@_formula("din7190.eq24_25", f"{STD} 4.2.3 式(24) p = ξ_w·E_A/K；实心内件且弹性常数相同时式(25) p = (1−Q_A²)/2·E·ξ_w（PDF11/印11 原图已核）",
          evidence=_ex("A.2", "A.4"), external=_ks("A2", "A4"))
def pressure_from_xi(*, xi_w, Q_A, Q_I, E_A, E_I, mu_A, mu_I):
    xi = pos("xi_w", xi_w)
    if _equal_solid(nonneg("Q_I", Q_I), pos("E_A", E_A), pos("E_I", E_I), nonneg("mu_A", mu_A), nonneg("mu_I", mu_I)):
        return {"p": (1 - pos("Q_A", Q_A) ** 2) / 2.0 * E_A * xi, "K": None, "equation": "eq25"}
    K = aux_K(E_A=E_A, E_I=E_I, mu_A=mu_A, mu_I=mu_I, Q_A=Q_A, Q_I=Q_I)
    return {"p": xi * E_A / K, "K": K, "equation": "eq24"}


def _common(D_F, D_aA, D_iI):
    return diameter_ratios(D_F=D_F, D_aA=D_aA, D_iI=D_iI)


def elastic_design_for_pressure(*, p, D_F, D_aA, D_iI, l_F, E_A, E_I, mu_A, mu_I, R_eLA, R_eLI, S_PA, S_PI,
                                Rz_A, Rz_I, g_F, nu_ru, S_r):
    """方法 1（4.2.2）主流程：式(10)(11) → 式(15)–(17) 检查 → 式(18)/(19) → 式(12) → 式(7) 求所需过盈 U；并给式(1) 可传扭矩。
    超出纯弹性条件（式15–17 不满足）→ OutOfDomain（弹塑性 4.3 未收录）。"""
    q = _common(D_F, D_aA, D_iI)
    lim = pressure_limits(Q_A=q["Q_A"], Q_I=q["Q_I"], R_eLA=R_eLA, R_eLI=R_eLI, S_PA=S_PA, S_PI=S_PI)
    p = pos("p", p)
    if p > lim["p_max_outer"]:
        raise OutOfDomain("p", f"式(15) 不满足：p = {p} > {lim['p_max_outer']}（外件非纯弹性；4.3 弹塑性未收录）")
    if p > lim["p_max_inner"]:
        raise OutOfDomain("p", f"式({lim['inner_equation'][2:]}) 不满足：p = {p} > {lim['p_max_inner']}")
    x = xi_from_pressure(p=p, Q_A=q["Q_A"], Q_I=q["Q_I"], E_A=E_A, E_I=E_I, mu_A=mu_A, mu_I=mu_I)
    Uw = x["xi_w"] * pos("D_F", D_F)
    U = interference_from_effective(U_w=Uw, Rz_A=Rz_A, Rz_I=Rz_I, g_F=g_F)
    T = transferable_torque(D_F=D_F, l_F=l_F, nu_ru=nu_ru, p=p, S_r=S_r)
    return {**q, **lim, "xi_w": x["xi_w"], "K": x["K"], "xi_equation": x["equation"], "U_w": Uw, "U": U, "T": T,
            "S_PA_actual": lim["p_max_outer"] * pos("S_PA", S_PA) / p, "S_PI_actual": lim["p_max_inner"] * pos("S_PI", S_PI) / p,
            "ref": f"{STD} 4.2.2 方法 1（PDF9–10 原图已核）"}


def elastic_check_for_interference(*, U, D_F, D_aA, D_iI, l_F, E_A, E_I, mu_A, mu_I, R_eLA, R_eLI, S_PA, S_PI,
                                   Rz_A, Rz_I, g_F, nu_ru, S_r):
    """方法 2（4.2.3）主流程：式(7) → 式(12) → 式(20)–(23) 检查 → 式(24)/(25) 求 p → 式(1) 可传扭矩。
    返回含 elastic_outer / elastic_inner 判定；不满足时不阻断（结果如实给出），但 p 仅在两者均满足时可视为纯弹性结果。"""
    q = _common(D_F, D_aA, D_iI)
    Uw = effective_interference(U=U, Rz_A=Rz_A, Rz_I=Rz_I, g_F=g_F)
    xi = reference_effective_interference(U_w=Uw, D_F=D_F)
    lim = xi_limits(Q_A=q["Q_A"], Q_I=q["Q_I"], E_A=E_A, E_I=E_I, mu_A=mu_A, mu_I=mu_I,
                    R_eLA=R_eLA, R_eLI=R_eLI, S_PA=S_PA, S_PI=S_PI)
    ok_o, ok_i = xi <= lim["xi_max_outer"], xi <= lim["xi_max_inner"]
    out = {**q, "U_w": Uw, "xi_w": xi, **lim, "elastic_outer": ok_o, "elastic_inner": ok_i,
           "ref": f"{STD} 4.2.3 方法 2（PDF10–11 原图已核）"}
    if not (ok_o and ok_i):
        out.update({"p": None, "T": None, "note": "纯弹性条件不满足；弹塑性计算（4.3）未收录 → p 不给出"})
        return out
    pr = pressure_from_xi(xi_w=xi, Q_A=q["Q_A"], Q_I=q["Q_I"], E_A=E_A, E_I=E_I, mu_A=mu_A, mu_I=mu_I)
    out.update({"p": pr["p"], "p_equation": pr["equation"],
                "T": transferable_torque(D_F=D_F, l_F=l_F, nu_ru=nu_ru, p=pr["p"], S_r=S_r)})
    return out


UNCONFIRMED = {
    "din7190.4_3": f"{STD} 4.3 弹塑性（式(26)–(43)，含 ln、附录B 图）：本轮未收录 → 超出纯弹性即阻断",
    "din7190.clause5_nu": f"{STD} 第5章 附着系数 ν_ru/ν_rl 表：未收录，由调用方给出",
    "din7190.clause8": f"{STD} 第8章 压入力/热装温度（式(48)–(53)）：未收录",
    "din7190.clause10": f"{STD} 第10章 离心力（式(54)–(58)）与疲劳说明：未收录",
    "din7190.6_3": f"{STD} 6.3 交变载荷设计规则（式(44)–(47)）：未收录",
    "din7190.ductility": f"{STD} 4.1 式(8)(9) 延性判据：仅弹塑性设计需要，本轮未收录",
}
