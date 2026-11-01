"""ISO 281:2007 滚动轴承额定寿命：基本额定寿命 L10、当量动载荷、修正额定寿命 Lnm = a1·aISO·L10。

资料与核对口径（本机私有 PDF "ISO 281 2007.pdf"，57 页扫描英文版，第二版 2007-02-15；PDF 页 = 印刷页 + 6）：
逐式渲染原图核对；代码只写条款号、式号、表号、页码，不复制原文。本标准不含数值算例 → 证据等级 null。

本轮范围（主线框架，宁窄勿错）：
  - 向心球轴承：式(3) P = X·Fr + Y·Fa；表3 仅"Radial contact ball bearings"（深沟球）行；式(4) L10 = (C/P)^3；5.3.2 载荷限制。
  - 向心滚子轴承：式(14)(15)；表8（α ≠ 0 单/双列）；式(16) L10 = (C/P)^(10/3)；7.3.2 载荷限制。
  - 修正寿命：式(23)；表12 a1；式(27)–(29) κ、ν1；表13 ec 指导范围；式(31)–(33)（向心球）、式(34)–(36)（向心滚子）aISO；
    9.3.3.4 限制（aISO ≤ 50、κ > 4 取 4、κ < 0,1 不可算）。
  - 推力轴承（v0.14 EXTC 起）：6.2 式(10)(11)+表5、6.3 式(12)+6.3.2；8.2 式(20)(21)+表11、8.3 式(22)+8.3.2；
    推力 aISO 式(37)–(39)（球）、式(40)–(42)（滚子）。额定动载荷 Ca 仍由调用方给出（式(5)–(9)、(17)–(19) 未收录）。
  - 未收录（阻断/TODO）：推力轴承额定载荷计算式、角接触球轴承与调心球轴承的表3行、额定动载荷 C 的计算式（5.1 等）、
    疲劳载荷极限 Cu（附录B）、附录A ec 详细法、Figure 2 ν1 读图。Cu、C、C0 一律由调用方给出（制造商目录）。
单位：力 N；转速 r/min；直径 mm；粘度 mm²/s；寿命 10⁶ 转。
"""
from __future__ import annotations

import math

from ._base import MissingInput, OutOfDomain, Unconfirmed, bad, choice, make_registry, nonneg, num, pos

STD = "ISO 281:2007"
FORMULAS, _formula = make_registry(r"^ISO 281:2007", "ISO 281:2007 不含数值算例；测试仅为独立重写对拍与分段连续性自洽检查，不构成外部参照")
_KS_R2 = {"level": "E5", "test": "tests/test_m36_kisssoft_v015.py::TestIso281KISSsoft",
          "source": "KISSsoft Release 2026 W050 R2-6206-RZ（Fr = R1(b) 实际支反力 664,9168/664,9203 N；W50 sha256 eb004fe163bc…，run.json sha256 f9ccaa21d98c…；提取件 data/kisssoft_v015/R2-6206-RZ.json）"
                    "与解析平衡输入对照 665,1111 N；覆盖：向心球轴承、Fa = 0（X = 1、Y = 0）"}

KINDS = ("radial_ball", "radial_roller")


# ------------------------------------------------------------------ 当量动载荷
_T3_RADIAL_CONTACT = (  # 表3 向心（深沟）球轴承："相对轴向载荷"、Y（Fa/Fr > e，X = 0,56）、e；PDF14/印8
    (0.172, 2.30, 0.19), (0.345, 1.99, 0.22), (0.689, 1.71, 0.26), (1.03, 1.55, 0.28), (1.38, 1.45, 0.30),
    (2.07, 1.31, 0.34), (3.45, 1.15, 0.38), (5.17, 1.04, 0.42), (6.89, 1.00, 0.44))


@_formula("iso281.table3.radial_contact", f"{STD} 5.2.1 表3 'Radial contact ball bearings' 行：Fa/Fr ≤ e 时 X=1、Y=0；Fa/Fr > e 时 X=0,56、"
          "Y 与 e 按'相对轴向载荷'取值，中间值线性插值（脚注 b）；单列与双列同值（PDF14/印8 原图已核）",
          note="'相对轴向载荷' f0·Fa/C0r（或 Fa/(i·Z·Dw²)）由调用方给出：f0 见 ISO 76（本机未收录）；"
               "超出表列范围 0,172–6,89 无外推规则 → 阻断；Fa = 0 时 Fa/Fr = 0 ≤ e 恒成立，不需相对轴向载荷")
def xy_radial_contact_ball(*, F_r, F_a, relative_axial_load):
    """深沟球轴承 X、Y。返回 {"X", "Y", "e", "branch"}；Fa = 0 时 relative_axial_load 须显式传 None。"""
    Fr, Fa = pos("F_r", F_r), nonneg("F_a", F_a)
    if Fa == 0:
        if relative_axial_load is not None:
            raise bad("relative_axial_load", "Fa = 0 时不使用相对轴向载荷，须为 None")
        return {"X": 1.0, "Y": 0.0, "e": None, "branch": "Fa=0"}
    r = pos("relative_axial_load", relative_axial_load)
    lo, hi = _T3_RADIAL_CONTACT[0][0], _T3_RADIAL_CONTACT[-1][0]
    if not lo <= r <= hi:
        raise Unconfirmed("relative_axial_load", f"{r} 超出表3 列值范围 [{lo}, {hi}]，标准未给外推规则")
    for (x0, y0, e0), (x1, y1, e1) in zip(_T3_RADIAL_CONTACT, _T3_RADIAL_CONTACT[1:]):
        if x0 <= r <= x1:
            w = (r - x0) / (x1 - x0)
            Y, e = y0 + w * (y1 - y0), e0 + w * (e1 - e0)
            break
    if Fa / Fr <= e:
        return {"X": 1.0, "Y": 0.0, "e": e, "branch": "Fa/Fr<=e"}
    return {"X": 0.56, "Y": Y, "e": e, "branch": "Fa/Fr>e"}


@_formula("iso281.table8", f"{STD} 7.2.1 表8 向心滚子轴承 α ≠ 0：单列 ≤e (1, 0)、>e (0,4, 0,4cotα)；双列 ≤e (1, 0,45cotα)、"
          ">e (0,67, 0,67cotα)；e = 1,5tanα（PDF22/印16 原图已核）；α = 0 仅受径向载荷时式(15) Pr = Fr（PDF21/印15 原图已核）",
          note="α = 0 且 Fa > 0：7.2.1 注要求咨询制造商 → 阻断")
def xy_radial_roller(*, rows, alpha_deg, F_r, F_a):
    n = choice("rows", rows, (1, 2))
    a = num("alpha_deg", alpha_deg)
    Fr, Fa = pos("F_r", F_r), nonneg("F_a", F_a)
    if a == 0:
        if Fa > 0:
            raise Unconfirmed("F_a", "α = 0 的向心滚子轴承受轴向载荷：标准要求咨询制造商（7.2.1 注）")
        return {"X": 1.0, "Y": 0.0, "e": None, "branch": "eq15"}
    if not 0 < a < 90:
        raise OutOfDomain("alpha_deg", "向心滚子轴承接触角须 0 ≤ α < 90°")
    t = math.tan(math.radians(a))
    e = 1.5 * t
    if Fa / Fr <= e:
        return {"X": 1.0, "Y": 0.0 if n == 1 else 0.45 / t, "e": e, "branch": "Fa/Fr<=e"}
    return {"X": 0.4 if n == 1 else 0.67, "Y": (0.4 if n == 1 else 0.67) / t, "e": e, "branch": "Fa/Fr>e"}


@_formula("iso281.eq3_14", f"{STD} 式(3) 向心球轴承、式(14) 向心滚子轴承 Pr = X·Fr + Y·Fa（PDF15/印9、PDF21/印15 原图已核）",
          external=_KS_R2)
def equivalent_radial_load(*, X, Y, F_r, F_a):
    return nonneg("X", X) * nonneg("F_r", F_r) + nonneg("Y", Y) * nonneg("F_a", F_a)


# ------------------------------------------------------------------ 基本额定寿命
@_formula("iso281.eq4_16", f"{STD} 式(4) 向心球轴承 L10 = (Cr/Pr)^3（PDF16/印10）、式(16) 向心滚子轴承 L10 = (Cr/Pr)^(10/3)（PDF22/印16）；"
          "5.3.2 球轴承 Pr > min(C0r, 0,5Cr)、7.3.2 滚子轴承 Pr > 0,5Cr 时须咨询制造商（原图已核）",
          note="载荷限制按阻断处理（OutOfDomain）；极轻载荷的其它失效形式标准不覆盖，本库不判",
          external=_KS_R2)
def basic_rating_life(*, bearing_kind, C_r, P_r, C_0r):
    """L10（10⁶ 转）。球轴承须给 C_0r；滚子轴承 C_0r 须显式传 None（7.3.2 不用 C0r）。"""
    k = choice("bearing_kind", bearing_kind, KINDS)
    C, P = pos("C_r", C_r), pos("P_r", P_r)
    if k == "radial_ball":
        C0 = pos("C_0r", C_0r)
        if P > min(C0, 0.5 * C):
            raise OutOfDomain("P_r", f"5.3.2：Pr = {P} > min(C0r, 0,5Cr) = {min(C0, 0.5 * C)}，须咨询制造商")
        p = 3.0
    else:
        if C_0r is not None:
            raise bad("C_0r", "向心滚子轴承 7.3.2 不用 C0r，须为 None")
        if P > 0.5 * C:
            raise OutOfDomain("P_r", f"7.3.2：Pr = {P} > 0,5Cr = {0.5 * C}，须咨询制造商")
        p = 10.0 / 3.0
    return (C / P) ** p


def rating_life_hours(*, L_million_rev, n):
    """单位换算（非条文）：寿命小时 = L·10⁶ /(60·n)，n 为 r/min。"""
    return pos("L_million_rev", L_million_rev) * 1e6 / (60.0 * pos("n", n))


# ------------------------------------------------------------------ 修正额定寿命
_TABLE12 = {90.0: 1.0, 95.0: 0.64, 96.0: 0.55, 97.0: 0.47, 98.0: 0.37, 99.0: 0.25, 99.2: 0.22, 99.4: 0.19,
            99.6: 0.16, 99.8: 0.12, 99.9: 0.093, 99.92: 0.087, 99.94: 0.080, 99.95: 0.077}


@_formula("iso281.table12", f"{STD} 9.2 表12 可靠度寿命修正系数 a1，90 %–99,95 % 共 14 行（PDF27/印21 原图已核）",
          note="表中无插值规则 → 只接受表列可靠度，其它值阻断")
def a1(*, reliability_percent):
    r = num("reliability_percent", reliability_percent)
    for k, v in _TABLE12.items():
        if abs(r - k) < 1e-9:
            return v
    raise Unconfirmed("reliability_percent", f"{r} 不在表12 列值 {sorted(_TABLE12)} 中（表未给插值规则）")


@_formula("iso281.eq23", f"{STD} 9.1 式(23) Lnm = a1·aISO·L10（PDF26/印20 原图已核）")
def modified_rating_life(*, a_1, a_ISO, L10):
    return pos("a_1", a_1) * pos("a_ISO", a_ISO) * pos("L10", L10)


@_formula("iso281.eq28_29", f"{STD} 9.3.3.3.1 式(28) ν1 = 45000·n^−0,83·Dpw^−0,5（n < 1000 r/min）、式(29) ν1 = 4500·n^−0,5·Dpw^−0,5"
          "（n ≥ 1000 r/min）（PDF31/印25 原图已核）",
          note="Dpw 可用 0,5(d+D) 代（同页），由调用方显式给出；基于矿物油（9.3.3.3.2）")
def reference_viscosity(*, n, D_pw):
    n, D = pos("n", n), pos("D_pw", D_pw)
    return 45000.0 * n ** -0.83 * D ** -0.5 if n < 1000.0 else 4500.0 * n ** -0.5 * D ** -0.5


@_formula("iso281.eq27", f"{STD} 9.3.3.3.1 式(27) κ = ν/ν1（PDF31/印25 原图已核）")
def viscosity_ratio(*, nu, nu_1):
    return pos("nu", nu) / pos("nu_1", nu_1)


_TABLE13 = {  # 污染等级 → ((Dpw<100 下限, 上限), (Dpw≥100 下限, 上限))；PDF30/印24
    "extreme_cleanliness": ((1.0, 1.0), (1.0, 1.0)), "high_cleanliness": ((0.6, 0.8), (0.8, 0.9)),
    "normal_cleanliness": ((0.5, 0.6), (0.6, 0.8)), "slight_contamination": ((0.3, 0.5), (0.4, 0.6)),
    "typical_contamination": ((0.1, 0.3), (0.2, 0.4)), "severe_contamination": ((0.0, 0.1), (0.0, 0.1)),
    "very_severe_contamination": ((0.0, 0.0), (0.0, 0.0))}


@_formula("iso281.table13", f"{STD} 9.3.3.2 表13 污染系数 ec 指导范围（Dpw < 100 mm / ≥ 100 mm 两列；PDF30/印24 原图已核）",
          note="表为区间型指导值：本函数只返回区间供核对，ec 取值由调用方给定（不取中值、不默认）")
def ec_guide_range(*, level, D_pw):
    lv = choice("level", level, tuple(_TABLE13))
    return _TABLE13[lv][0 if pos("D_pw", D_pw) < 100.0 else 1]


_AISO = {  # 类型 → (A, 指数 x 于第一括号, 指数 y 于 ecCu/P, 外指数, [(κ 上界, B, c)])；aISO = 0,1[1 − (A − B/κ^c)^x·(ecCu/P)^y]^外
    "radial_ball": (2.5671, 0.83, 1.0 / 3.0, -9.3, ((0.4, 2.2649, 0.054381), (1.0, 1.9987, 0.19087), (4.0, 1.9987, 0.071739))),
    "radial_roller": (1.5859, 1.0, 0.4, -9.185, ((0.4, 1.3993, 0.054381), (1.0, 1.2348, 0.19087), (4.0, 1.2348, 0.071739))),
}


@_formula("iso281.eq31_36", f"{STD} 9.3.3.4 式(31)–(33) 向心球轴承（PDF34/印28）、式(34)–(36) 向心滚子轴承（PDF35/印29）；"
          "限制 aISO ≤ 50（ecCu/P > 5 时同样适用）、κ > 4 取 κ = 4、κ < 0,1 不可算（PDF33/印27）；式(26) aISO = f(ecCu/P, κ)（PDF29/印23）原图已核",
          note="方括号内 ≤ 0 时 aISO 无界，按 aISO ≤ 50 限值取 50（本库对'限于 50'的执行口径）；"
               "ec、Cu 由调用方给出（附录A/B 未收录）；推力轴承式(37)–(42) 未收录")
def a_iso(*, bearing_kind, kappa, ec_Cu_over_P):
    """返回 {"a_ISO", "kappa_used", "equation", "capped"}。"""
    k = choice("bearing_kind", bearing_kind, KINDS)
    kap = pos("kappa", kappa)
    x = nonneg("ec_Cu_over_P", ec_Cu_over_P)
    if kap < 0.1:
        raise OutOfDomain("kappa", "κ < 0,1：aISO 超出方程与图的范围（9.3.3.4）")
    kap_used = min(kap, 4.0)
    A, ex1, ex2, outer, pieces = _AISO[k]
    eqs = {"radial_ball": ("eq31", "eq32", "eq33"), "radial_roller": ("eq34", "eq35", "eq36")}[k]
    for i, (ub, B, c) in enumerate(pieces):
        if kap_used < ub or i == len(pieces) - 1:
            break
    inner = A - B / kap_used ** c
    if inner < 0 and ex1 != 1.0:
        # 球轴承式(31) 第一括号带 0,83 次幂：底数为负时实数幂无定义（κ 恰在 0,1 附近由发布系数舍入引起）；滚子式(34) 为一次幂，照式计算
        raise Unconfirmed("kappa", f"({A} − {B}/κ^{c}) < 0，0,83 次幂无实数定义（κ = {kap_used}）")
    bracket = 1.0 - inner ** ex1 * x ** ex2
    if bracket <= 0:
        return {"a_ISO": 50.0, "kappa_used": kap_used, "equation": eqs[i], "capped": True}
    a = 0.1 * bracket ** outer
    return {"a_ISO": min(a, 50.0), "kappa_used": kap_used, "equation": eqs[i], "capped": a > 50.0}


# ------------------------------------------------------------------ 主流程
def bearing_life(*, bearing_kind, F_r, F_a, C_r, C_0r, xy, n, reliability_percent, a_ISO_inputs):
    """单个向心轴承寿命主流程：X/Y → 式(3)/(14) → 式(4)/(16) → 表12 a1 → 式(31)–(36) aISO → 式(23)。

    xy：球轴承 {"relative_axial_load": 值或 None}；滚子轴承 {"rows": 1|2, "alpha_deg": α}。
    a_ISO_inputs：None（显式声明不算修正寿命，结果中 Lnm 为 None 且注明）或
                  {"kappa": κ, "ec": ec, "C_u": Cu}（三者必需）。
    n：r/min，用于小时换算。
    """
    k = choice("bearing_kind", bearing_kind, KINDS)
    if xy is None:
        raise MissingInput("xy")
    if k == "radial_ball":
        f = xy_radial_contact_ball(F_r=F_r, F_a=F_a, relative_axial_load=xy.get("relative_axial_load"))
    else:
        f = xy_radial_roller(rows=xy.get("rows"), alpha_deg=xy.get("alpha_deg"), F_r=F_r, F_a=F_a)
    P = equivalent_radial_load(X=f["X"], Y=f["Y"], F_r=F_r, F_a=F_a)
    L10 = basic_rating_life(bearing_kind=k, C_r=C_r, P_r=P, C_0r=C_0r)
    out = {"X": f["X"], "Y": f["Y"], "e": f["e"], "xy_branch": f["branch"], "P": P, "L10": L10,
           "L10h": rating_life_hours(L_million_rev=L10, n=n), "a_1": a1(reliability_percent=reliability_percent)}
    if a_ISO_inputs is None:
        out.update({"a_ISO": None, "Lnm": None, "Lnm_note": "调用方未提供 κ/ec/Cu：修正寿命未计算"})
        return out
    for key in ("kappa", "ec", "C_u"):
        if a_ISO_inputs.get(key) is None:
            raise MissingInput(f"a_ISO_inputs.{key}")
    ec = num("ec", a_ISO_inputs["ec"])
    if not 0 <= ec <= 1:
        raise OutOfDomain("ec", "表13 范围 0 ≤ ec ≤ 1")
    ai = a_iso(bearing_kind=k, kappa=a_ISO_inputs["kappa"], ec_Cu_over_P=ec * pos("C_u", a_ISO_inputs["C_u"]) / P)
    Lnm = modified_rating_life(a_1=out["a_1"], a_ISO=ai["a_ISO"], L10=L10)
    out.update({"a_ISO": ai["a_ISO"], "a_ISO_detail": ai, "Lnm": Lnm, "Lnmh": rating_life_hours(L_million_rev=Lnm, n=n)})
    return out


# ------------------------------------------------------------------ 推力轴承（第6、8章，v0.14 EXTC）
THRUST_KINDS = ("thrust_ball", "thrust_roller")
_T5 = (  # α、单向 X（Fa/Fr>e，Y=1）、双向 ≤e (X, Y)、双向 >e X（Y=1）、e；PDF18/印12
    (45.0, 0.66, 1.18, 0.59, 0.66, 1.25), (50.0, 0.73, 1.37, 0.57, 0.73, 1.49), (55.0, 0.81, 1.6, 0.56, 0.81, 1.79),
    (60.0, 0.92, 1.9, 0.55, 0.92, 2.17), (65.0, 1.06, 2.3, 0.54, 1.06, 2.68), (70.0, 1.28, 2.9, 0.53, 1.28, 3.43),
    (75.0, 1.66, 3.89, 0.52, 1.66, 4.67), (80.0, 2.43, 5.86, 0.52, 2.43, 7.09), (85.0, 4.8, 11.75, 0.51, 4.8, 14.29))


@_formula("iso281.table5", f"{STD} 6.2 表5 推力球轴承 X、Y、e：列值行 α = 45°–85°（中间 α 线性插值，脚注 a；45° 仅供 45°–50° 插值，"
          "推力轴承 α > 45°，脚注 c）；通式行 α ≠ 90°：单向/双向 Fa/Fr > e 时 X = 1,25·tanα·(1 − ⅔·sinα)、Y = 1；双向 Fa/Fr ≤ e 时 "
          "X = (20/13)·tanα·(1 − ⅓·sinα)、Y = (10/13)·(1 − ⅓·sinα)；e = 1,25·tanα；单向 Fa/Fr ≤ e 不适用（脚注 b）（PDF18/印12 原图已核）；"
          "α = 90° 只受轴向载荷式(11) Pa = Fa（PDF18/印12 原图已核）",
          note="basis 由调用方显式选择 'rows'（列值+插值，α ∈ (45°, 85°]）或 'formula'（通式行，45° < α < 90°）；列值为通式的两位圆整")
def xy_thrust_ball(*, direction, alpha_deg, basis, F_r, F_a):
    dr = choice("direction", direction, ("single", "double"))
    a = num("alpha_deg", alpha_deg)
    Fr, Fa = nonneg("F_r", F_r), pos("F_a", F_a)
    if a == 90.0:
        if Fr > 0:
            raise Unconfirmed("F_r", "α = 90° 推力球轴承只能承受轴向载荷（式(11)）")
        return {"X": 0.0, "Y": 1.0, "e": None, "branch": "eq11"}
    bs = choice("basis", basis, ("rows", "formula"))
    if bs == "rows":
        if not 45.0 < a <= 85.0:
            raise OutOfDomain("alpha_deg", "表5 列值行适用 45° < α ≤ 85°（45° 只供插值）")
        for r0, r1 in zip(_T5, _T5[1:]):
            if r0[0] <= a <= r1[0]:
                w = (a - r0[0]) / (r1[0] - r0[0])
                Xs, Xd1, Yd1, Xd2, e = (r0[k] + w * (r1[k] - r0[k]) for k in range(1, 6))
                break
    else:
        if not 45.0 < a < 90.0:
            raise OutOfDomain("alpha_deg", "推力球轴承 α > 45°（脚注 c），通式行 α ≠ 90°")
        t, sn = math.tan(math.radians(a)), math.sin(math.radians(a))
        Xs = Xd2 = 1.25 * t * (1.0 - 2.0 / 3.0 * sn)
        Xd1, Yd1, e = 20.0 / 13.0 * t * (1.0 - sn / 3.0), 10.0 / 13.0 * (1.0 - sn / 3.0), 1.25 * t
    le = Fr > 0 and Fa / Fr <= e
    if dr == "single":
        if le:
            raise OutOfDomain("F_a", "表5 脚注 b：单向推力轴承 Fa/Fr ≤ e 不适用")
        return {"X": Xs, "Y": 1.0, "e": e, "branch": "single Fa/Fr>e"}
    if le:
        return {"X": Xd1, "Y": Yd1, "e": e, "branch": "double Fa/Fr<=e"}
    return {"X": Xd2, "Y": 1.0, "e": e, "branch": "double Fa/Fr>e"}


@_formula("iso281.table11", f"{STD} 8.2 表11 推力滚子轴承 α ≠ 90°：单向 Fa/Fr > e 时 X = tanα、Y = 1（≤ e 不适用）；双向 ≤ e 时 "
          "X = 1,5·tanα、Y = 0,67，> e 时 X = tanα、Y = 1；e = 1,5·tanα（PDF25/印19 原图已核）；α = 90° 式(21) Pa = Fa（PDF25/印19 原图已核）")
def xy_thrust_roller(*, direction, alpha_deg, F_r, F_a):
    dr = choice("direction", direction, ("single", "double"))
    a = num("alpha_deg", alpha_deg)
    Fr, Fa = nonneg("F_r", F_r), pos("F_a", F_a)
    if a == 90.0:
        if Fr > 0:
            raise Unconfirmed("F_r", "α = 90° 推力滚子轴承只能承受轴向载荷（式(21)）")
        return {"X": 0.0, "Y": 1.0, "e": None, "branch": "eq21"}
    if not 45.0 < a < 90.0:
        raise OutOfDomain("alpha_deg", "推力轴承取 45° < α < 90°（沿用表5 脚注 c 的推力轴承口径；第8章未另述 α 下限，本库按此阻断）")
    t = math.tan(math.radians(a))
    e = 1.5 * t
    le = Fr > 0 and Fa / Fr <= e
    if dr == "single":
        if le:
            raise OutOfDomain("F_a", "表11 脚注 a：单向推力轴承 Fa/Fr ≤ e 不适用")
        return {"X": t, "Y": 1.0, "e": e, "branch": "single Fa/Fr>e"}
    if le:
        return {"X": 1.5 * t, "Y": 0.67, "e": e, "branch": "double Fa/Fr<=e"}
    return {"X": t, "Y": 1.0, "e": e, "branch": "double Fa/Fr>e"}


@_formula("iso281.eq10_20", f"{STD} 式(10) 推力球轴承、式(20) 推力滚子轴承 Pa = X·Fr + Y·Fa（PDF18/印12、PDF25/印19 原图已核）")
def equivalent_axial_load(*, X, Y, F_r, F_a):
    return nonneg("X", X) * nonneg("F_r", F_r) + nonneg("Y", Y) * nonneg("F_a", F_a)


@_formula("iso281.eq12_22", f"{STD} 式(12) 推力球轴承 L10 = (Ca/Pa)^3（PDF19/印13）、式(22) 推力滚子轴承 L10 = (Ca/Pa)^(10/3)（PDF25/印19）；"
          "6.3.2、8.3.2 Pa > 0,5Ca 须咨询制造商（PDF19/印13、PDF26/印20 原图已核）",
          note="载荷限制按阻断处理（OutOfDomain）")
def basic_rating_life_thrust(*, bearing_kind, C_a, P_a):
    k = choice("bearing_kind", bearing_kind, THRUST_KINDS)
    C, P = pos("C_a", C_a), pos("P_a", P_a)
    if P > 0.5 * C:
        raise OutOfDomain("P_a", f"{'6.3.2' if k == 'thrust_ball' else '8.3.2'}：Pa = {P} > 0,5Ca = {0.5 * C}，须咨询制造商")
    return (C / P) ** (3.0 if k == "thrust_ball" else 10.0 / 3.0)


@_formula("iso281.eq37_42", f"{STD} 9.3.3.4 推力球轴承式(37)–(39)：形式同式(31)–(33)，ecCu/P 换为 ecCu/(3P)（PDF36/印30）；"
          "推力滚子轴承式(40)–(42)：形式同式(34)–(36)，ecCu/P 换为 ecCu/(2,5P)（PDF37/印31）；限制 aISO ≤ 50、κ > 4 取 4、κ < 0,1 不可算"
          "（PDF33/印27 原图已核）")
def a_iso_thrust(*, bearing_kind, kappa, ec_Cu_over_P):
    """返回 {"a_ISO", "kappa_used", "equation", "capped"}；口径与 a_iso 相同（方括号 ≤ 0 时取 50）。"""
    k = choice("bearing_kind", bearing_kind, THRUST_KINDS)
    x = nonneg("ec_Cu_over_P", ec_Cu_over_P)
    base, div, eqs = (("radial_ball", 3.0, ("eq37", "eq38", "eq39")) if k == "thrust_ball"
                      else ("radial_roller", 2.5, ("eq40", "eq41", "eq42")))
    r = a_iso(bearing_kind=base, kappa=kappa, ec_Cu_over_P=x / div)
    return {**r, "equation": eqs[int(r["equation"][-1]) - (1 if k == "thrust_ball" else 4)]}


def thrust_bearing_life(*, bearing_kind, F_r, F_a, C_a, xy, n, reliability_percent, a_ISO_inputs):
    """单个推力轴承寿命主流程：表5/表11 → 式(10)/(20) → 式(12)/(22) → 表12 a1 → 式(37)–(42) → 式(23)。

    xy：{"direction": "single"|"double", "alpha_deg": α, "basis": "rows"|"formula"}（滚子轴承 basis 须为 None）。
    a_ISO_inputs：None（显式不算修正寿命）或 {"kappa", "ec", "C_u"}。"""
    k = choice("bearing_kind", bearing_kind, THRUST_KINDS)
    if xy is None:
        raise MissingInput("xy")
    if k == "thrust_ball":
        f = xy_thrust_ball(direction=xy.get("direction"), alpha_deg=xy.get("alpha_deg"), basis=xy.get("basis"), F_r=F_r, F_a=F_a)
    else:
        if xy.get("basis") is not None:
            raise bad("xy.basis", "推力滚子轴承表11 无列值行，basis 须为 None")
        f = xy_thrust_roller(direction=xy.get("direction"), alpha_deg=xy.get("alpha_deg"), F_r=F_r, F_a=F_a)
    P = equivalent_axial_load(X=f["X"], Y=f["Y"], F_r=F_r, F_a=F_a)
    L10 = basic_rating_life_thrust(bearing_kind=k, C_a=C_a, P_a=P)
    out = {"X": f["X"], "Y": f["Y"], "e": f["e"], "xy_branch": f["branch"], "P": P, "L10": L10,
           "L10h": rating_life_hours(L_million_rev=L10, n=n), "a_1": a1(reliability_percent=reliability_percent)}
    if a_ISO_inputs is None:
        out.update({"a_ISO": None, "Lnm": None, "Lnm_note": "调用方未提供 κ/ec/Cu：修正寿命未计算"})
        return out
    for key in ("kappa", "ec", "C_u"):
        if a_ISO_inputs.get(key) is None:
            raise MissingInput(f"a_ISO_inputs.{key}")
    ec = num("ec", a_ISO_inputs["ec"])
    if not 0 <= ec <= 1:
        raise OutOfDomain("ec", "表13 范围 0 ≤ ec ≤ 1")
    ai = a_iso_thrust(bearing_kind=k, kappa=a_ISO_inputs["kappa"], ec_Cu_over_P=ec * pos("C_u", a_ISO_inputs["C_u"]) / P)
    Lnm = modified_rating_life(a_1=out["a_1"], a_ISO=ai["a_ISO"], L10=L10)
    out.update({"a_ISO": ai["a_ISO"], "a_ISO_detail": ai, "Lnm": Lnm, "Lnmh": rating_life_hours(L_million_rev=Lnm, n=n)})
    return out


UNCONFIRMED = {
    "iso281.thrust": f"{STD} 推力轴承额定动载荷 Ca 计算式（式(5)–(9)、(17)–(19)，表4/9/10）及组合安装 8.1.3：未收录 → Ca 由调用方给出；"
                     "Pa/L10/aISO 已收录（式(10)–(12)、(20)–(22)、(37)–(42)）",
    "iso281.table3.other_types": f"{STD} 表3 角接触球、调心球、磁电机轴承行：本轮未收录（只收深沟球行）",
    "iso281.ratings": f"{STD} 额定动载荷 C 的计算式（式(1)(2) 等，表2/4/7）：未收录；C、C0 由制造商目录给出",
    "iso281.annexB_Cu": f"{STD} 附录B 疲劳载荷极限 Cu：未收录；Cu 由调用方给出",
    "iso281.annexA_ec": f"{STD} 附录A ec 详细法（图A.1–A.14 及式）：未收录；ec 由调用方给出",
    "iso281.fig2": f"{STD} 图2 ν1 读图：不读图，用式(28)(29)",
    "iso281.f0": "ISO 76 f0 系数（表3 相对轴向载荷所需）：本机未收录 → 相对轴向载荷须由调用方给出",
    "iso281.thrust_alpha90_radial": f"{STD} α = 90° 推力轴承仅承受轴向载荷（式(11)(21)）：F_r > 0 → 阻断",
    "iso281.table5_single_le_e": f"{STD} 表5/表11 单向推力轴承 Fa/Fr ≤ e 不适用（脚注）→ 阻断",
}
