"""DIN 6892:2012-08 平键连接 方法 B（第6章 6.1 简化计算：键侧有效挤压应力与许用值）主流程，及附录B 表B.1。

资料与核对口径（本机私有 PDF "DIN 6892 (2012-08-00).pdf"，48 页德文扫描，PDF 页 = 印刷页）：逐式渲染原图核对，
代码只写条款号、式号、表号、页码，不复制原文。
  - 6.1.2 式(1)–(3)（PDF9）、式(4)–(8)（PDF10）、式(9.1)(9.2)(10.1)(10.2) 及"p_max 取较大值"规则（PDF11）；
    6.1.2.3 式(11)、6.1.2.4 式(12)(13)（PDF12）；式(14) 与 a0/l_tr 取值规则（PDF13）；图4–6（PDF14–15）为读图 → K_λe 由调用方给出；
    6.1.2.5 式(15)(16)（PDF15）及其"校核可免"条件（PDF16）；6.1.3 式(17)–(20)（PDF16）；6.1.3.1 式(21)–(23)、图7（PDF17）；
    6.1.3.2 式(24)–(29)、图8（PDF18）；附录B 表B.1（PDF25）。
  - 附录D D.1.3（PDF32–34）与 D.2.3（PDF37–39）为方法 B 算例：测试逐步复现 → 相关式证据 E4（标准配套算例复现）。
本模块与 din6892.py（方法 C）分开登记：方法 C 的 φ（式(32)）与方法 B 的 φ（式(11)，最大挤压时两键取 0,9）含义不同。
未收录（TODO）：6.2 形状强度（表1 β_cb,t、式(30)，PDF19）、6.2.2 薄壁毂（PDF19–20）、6.2.3 设计规定、第5章 方法 A、
附录C（AGMA 键）、图4–6 读图（K_λe 由调用方给出）、附录A K_A 表（K_A 由调用方给出）。
单位：长度 mm；力矩 N·mm；力 N；应力 N/mm²。
"""
from __future__ import annotations

import math

from ._base import MissingInput, OutOfDomain, Unconfirmed, bad, choice, make_registry, nonneg, num, pos

STD = "DIN 6892:2012"
FORMULAS, _formula = make_registry(r"^DIN 6892", "无标准配套算例覆盖该式：测试仅为独立重写对拍（自洽）")
_TEST = "tests/test_m36_din6892_b.py::TestAnnexD_MethodB"
_KS_R4B = {"level": "E5", "test": "tests/test_m36_kisssoft_v015.py::TestDin6892BKISSsoft",
           "source": "KISSsoft Release 2026 M02A 方法 B 供应商例 R4-vendor-B-unchanged（D2 = 200，M2A sha256 14b3ba6c491c…；"
                     "K_λe = 1,085 取 KISSsoft 值作输入）；提取件 data/kisssoft_v015/R4-DIN6892.json；覆盖：i = 1、M_tRmin = 0、"
                     "延性轴/键与脆性毂；f_W 因 KISSsoft 用图7 端点插值而不同（已归因，不提升式(23)）"}


def _ex(*names):
    pages = {"D.1": "PDF32–34", "D.2": "PDF37–39"}
    return {"level": "E4", "source": f"{STD} 附录D " + "、".join(f"{n} 方法 B（{pages[n]}/印同）" for n in names), "test": _TEST}


# ------------------------------------------------------------------ 载荷
@_formula("din6892b.eq1", f"{STD} 6.1.2.1 式(1) M_teq = K_A·M_tnenn（PDF9/印9 原图已核）", evidence=_ex("D.1", "D.2"),
          note="K_A 按附录A（转引 DIN 3990-1）由调用方给出",
          external=_KS_R4B)
def M_teq(*, K_A, M_tnenn):
    K = pos("K_A", K_A)
    if K < 1:
        raise OutOfDomain("K_A", "应用系数须 ≥ 1")
    return K * nonneg("M_tnenn", M_tnenn)


@_formula("din6892b.eq2_3", f"{STD} 6.1.2.1 式(2) F_eq = 2M_teq/d、式(3) F_max = 2M_tmax/d，力作用点取轴外径（PDF9/印9 原图已核）",
          evidence=_ex("D.1", "D.2"),
          external=_KS_R4B)
def circumferential_force(*, M_t, d):
    return 2.0 * nonneg("M_t", M_t) / pos("d", d)


# ------------------------------------------------------------------ 几何
@_formula("din6892b.eq4", f"{STD} 6.1.2.1 式(4) 轴槽承载深度 t1tr = t1 − (r + s1) − ½(d − √(d² − (b + 2s1)²))（PDF10/印10 原图已核）",
          evidence=_ex("D.1", "D.2"),
          external=_KS_R4B)
def t1_bearing(*, t1, r, s1, d, b):
    d, b, s1 = pos("d", d), pos("b", b), nonneg("s1", s1)
    if b + 2 * s1 >= d:
        raise OutOfDomain("b", "须 b + 2s1 < d")
    t = pos("t1", t1) - (nonneg("r", r) + s1) - 0.5 * (d - math.sqrt(d * d - (b + 2 * s1) ** 2))
    if t <= 0:
        raise OutOfDomain("t1tr", f"轴槽承载深度 t1tr = {t} ≤ 0")
    return t


@_formula("din6892b.eq5", f"{STD} 6.1.2.1 式(5) 毂槽承载深度 t2tr = h − t1 − (r + s2) + ½(d − √(d² − (b + 2s2)²))（PDF10/印10 原图已核）",
          evidence=_ex("D.1", "D.2"),
          external=_KS_R4B)
def t2_bearing(*, h, t1, r, s2, d, b):
    d, b, s2 = pos("d", d), pos("b", b), nonneg("s2", s2)
    if b + 2 * s2 >= d:
        raise OutOfDomain("b", "须 b + 2s2 < d")
    t = pos("h", h) - pos("t1", t1) - (nonneg("r", r) + s2) + 0.5 * (d - math.sqrt(d * d - (b + 2 * s2) ** 2))
    if t <= 0:
        raise OutOfDomain("t2tr", f"毂槽承载深度 t2tr = {t} ≤ 0")
    return t


_FORMS = {"A": "eq6", "E": "eq6", "C": "eq6", "B": "eq7", "D": "eq7", "F": "eq7", "G": "eq7", "H": "eq7", "J": "eq7", "AB": "eq8"}


@_formula("din6892b.eq6_8", f"{STD} 6.1.2.1 承载键长：圆头 A/E/C 式(6) l_tr = l_PF − b；平头 B/D/F/G/H/J 式(7) l_tr = l_PF；"
          "组合 AB 式(8) l_tr = l_PF − b/2；两键时 l_tr 只计一次（PDF10/印10 原图已核）",
          note="毂槽承载长度 l2tr 小于 l_tr 时轴槽长度的缩减（PDF11 首段，至多 1·b 超出段）由调用方按几何给出 l1tr、l2tr",
          evidence=_ex("D.1", "D.2"))
def l_bearing(*, form, l_PF, b):
    f = choice("form", form, tuple(_FORMS))
    l, b = pos("l_PF", l_PF), pos("b", b)
    lt = {"eq6": l - b, "eq7": l, "eq8": l - b / 2.0}[_FORMS[f]]
    if lt <= 0:
        raise OutOfDomain("l_PF", "承载键长 ≤ 0")
    return {"l_tr": lt, "equation": _FORMS[f]}


# ------------------------------------------------------------------ 系数
@_formula("din6892b.eq11", f"{STD} 6.1.2.3 式(11) K_v = 1/(i·φ)：i=1 时 φ=1；i=2 时 φ=0,75（等效挤压）、φ=0,9（最大挤压）（PDF12/印12 原图已核）",
          note="i=2 的 φ 以延性材料、足够制造精度为前提；脆性材料两键无可靠认识（同页）→ 由调用方判断；附录D 仅覆盖 i=1",
          evidence=_ex("D.1", "D.2"))
def K_v(*, i, pressure):
    n = choice("i", i, (1, 2))
    which = choice("pressure", pressure, ("eq", "max"))
    phi = 1.0 if n == 1 else {"eq": 0.75, "max": 0.9}[which]
    return 1.0 / (n * phi)


@_formula("din6892b.eq12_13", f"{STD} 6.1.2.4 式(12) 一键 K_λ = K_λe；式(13) 两键 K_λ = 2K_λe − 1（PDF12/印12 原图已核）",
          note="K_λe 由图4/5/6（PDF14–15）按 a0/l_tr、Q_A = d/D、l_tr/d 读取或按 [9] 计算，本库不读图 → 调用方给出；附录D 仅覆盖式(12)",
          evidence=_ex("D.1", "D.2"))
def K_lambda(*, i, K_lambda_e):
    n = choice("i", i, (1, 2))
    K = pos("K_lambda_e", K_lambda_e)
    if K < 1:
        raise OutOfDomain("K_lambda_e", "图4–6 纵轴 K_λe ≥ 1")
    return K if n == 1 else 2.0 * K - 1.0


@_formula("din6892b.eq14", f"{STD} 6.1.2.4 式(14) 阶梯毂替代直径 D = D2/((D2/D1)⁴(1 − c/l_tr) + c/l_tr)^¼；a0 < 0 取 a0/l_tr = 0、"
          "a0 > l_tr 取 1；K_λ 用两承载长度中较小者（PDF13/印13 原图已核）", evidence=_ex("D.1"),
          note="返回 D、Q_A = d/D、a0/l_tr、l_tr/d 供读图 4–6；三图只覆盖 a0/l_tr = 0、0,5、1，中间值在图间插值（PDF13）由调用方完成")
def hub_equivalent(*, d, D1, D2, c, l_tr, a0):
    d, D1, D2, lt = pos("d", d), pos("D1", D1), pos("D2", D2), pos("l_tr", l_tr)
    c = nonneg("c", c)
    if c > lt:
        raise OutOfDomain("c", "图3：c ≤ l_tr")
    D = D2 / ((D2 / D1) ** 4 * (1.0 - c / lt) + c / lt) ** 0.25
    if not d < D:
        raise OutOfDomain("D", "替代直径须大于轴径")
    a = num("a0", a0)
    ratio = 0.0 if a < 0 else (1.0 if a > lt else a / lt)
    return {"D": D, "Q_A": d / D, "a0_over_ltr": ratio, "ltr_over_d": lt / d}


@_formula("din6892b.eq15_16", f"{STD} 6.1.2.5 式(15) M_teq > q_eq·M_tRmin 时 K_Req = (M_teq − q_eq·M_tRmin)/M_teq，q_eq = 0,5；"
          "式(16) M_tmax > q_max·M_tRmin 时 K_Rmax = (M_tmax − q_max·M_tRmin)/M_tmax，q_max = 0,8（PDF15/印15 原图已核）；"
          "不满足条件时相应挤压校核可免（PDF16/印16 原图已核）", evidence=_ex("D.1", "D.2"),
          note="M_tRmin 按 DIN 7190 由调用方给出（无过盈配合时显式传 0）")
def K_R(*, M_t, M_tRmin, pressure):
    which = choice("pressure", pressure, ("eq", "max"))
    q = {"eq": 0.5, "max": 0.8}[which]
    M, MR = pos("M_t", M_t), nonneg("M_tRmin", M_tRmin)
    if M <= q * MR:
        return {"K_R": None, "check_required": False, "q": q}
    return {"K_R": (M - q * MR) / M, "check_required": True, "q": q}


@_formula("din6892b.eq9_10", f"{STD} 6.1.2.1 式(9.1)/(10.1) 轴槽 p1 = K_v·K_λ·K_R·F/(l1tr·t1tr − a²/(2·tan15°))；式(9.2)/(10.2) 毂槽 "
          "p2 = K_v·K_λ·K_R·F/(l2tr·t2tr)；若式(9.x) 大于式(10.x)，p_max 取式(9.x) 值（PDF11/印11 原图已核）",
          note="a 为 G/J/H 型键的起模斜面长度（图2，PDF11）；其它键型由调用方显式传 0", evidence=_ex("D.1", "D.2"),
          external=_KS_R4B)
def pressure_shaft(*, K_v, K_lambda, K_R, F, l1tr, t1tr, a):
    area = pos("l1tr", l1tr) * pos("t1tr", t1tr) - nonneg("a", a) ** 2 / (2.0 * math.tan(math.radians(15.0)))
    if area <= 0:
        raise OutOfDomain("a", "起模斜面扣除后承载面积 ≤ 0")
    return pos("K_v", K_v) * pos("K_lambda", K_lambda) * pos("K_R", K_R) * nonneg("F", F) / area


def pressure_hub(*, K_v, K_lambda, K_R, F, l2tr, t2tr):
    return pos("K_v", K_v) * pos("K_lambda", K_lambda) * pos("K_R", K_R) * nonneg("F", F) / (pos("l2tr", l2tr) * pos("t2tr", t2tr))


# ------------------------------------------------------------------ 许用值
_TABLE_B1 = {  # (构件, 材料类) → (f_S 下限, f_S 上限, f_H 或 None('–')，脆性?)；PDF25
    ("key", "structural_steel_EN10025"): (1.1, 1.4, 1.0, False),
    ("key", "bright_steel_EN10277_5"): (1.1, 1.4, 1.0, False),
    ("key", "QT_steel_EN10083"): (1.1, 1.4, 1.0, False),
    ("key", "case_hardened_EN10084"): (1.1, 1.4, 1.15, False),
    ("shaft", "structural_steel_EN10025"): (1.3, 1.7, 1.0, False),
    ("shaft", "QT_steel_EN10083"): (1.3, 1.7, 1.0, False),
    ("shaft", "case_hardened_DIN17210"): (1.3, 1.7, 1.15, False),
    ("shaft", "nodular_iron_EN1563"): (1.3, 1.7, 1.0, False),
    ("shaft", "cast_steel_DIN1681"): (1.3, 1.7, 1.0, False),
    ("shaft", "grey_iron_EN1561"): (1.1, 1.4, None, True),
    ("hub", "structural_steel_EN10025"): (1.5, 1.5, 1.0, False),
    ("hub", "QT_steel_EN10083"): (1.5, 1.5, 1.0, False),
    ("hub", "case_hardened_DIN17210"): (1.5, 1.5, 1.15, False),
    ("hub", "nodular_iron_EN1563"): (1.5, 1.5, 1.0, False),
    ("hub", "cast_steel_DIN1681"): (1.5, 1.5, 1.0, False),
    ("hub", "grey_iron_EN1561"): (2.0, 2.0, None, True),
}


@_formula("din6892b.tableB1", f"{STD} 附录B 表B.1 支撑系数 f_S（区间）与硬度影响系数 f_H，按键/轴/毂与材料类；材料认识不足时取 f_S 下限"
          "（PDF25/印25 原图已核）", evidence=_ex("D.1", "D.2"),
          note="灰铸铁 f_H 为 '–'（按式(20) 用 Rm）；脆性 = 灰铸铁 EN 1561（式(20) 示例），其余按式(19)")
def table_B1(*, component, material_class):
    comp = choice("component", component, ("key", "shaft", "hub"))
    cls = choice("material_class", material_class, tuple(sorted({k[1] for k in _TABLE_B1})))
    row = _TABLE_B1.get((comp, cls))
    if row is None:
        raise OutOfDomain("material_class", f"表B.1 无 {comp}/{cls} 行")
    return {"f_S_min": row[0], "f_S_max": row[1], "f_H": row[2], "brittle": row[3]}


@_formula("din6892b.eq19_20", f"{STD} 6.1.3 式(19) 延性 p_zul = f_S·f_H·R_e（或 R_p0,2）；式(20) 脆性 p_zul = f_S·R_m；尺寸影响 K1 忽略"
          "（PDF16/印16 原图已核）", evidence=_ex("D.1", "D.2"),
          external=_KS_R4B)
def p_zul(*, component, material_class, f_S, f_H, R_e, R_m):
    """f_S 须在表B.1 区间内、f_H 须等于表值（灰铸铁 f_H、R_e 须为 None 并给 R_m；其余 R_m 须为 None 并给 R_e）。"""
    t = table_B1(component=component, material_class=material_class)
    fS = pos("f_S", f_S)
    if not t["f_S_min"] - 1e-12 <= fS <= t["f_S_max"] + 1e-12:
        raise OutOfDomain("f_S", f"表B.1 {component}/{material_class} f_S 区间 [{t['f_S_min']}, {t['f_S_max']}]，收到 {fS}")
    if t["brittle"]:
        if f_H is not None or R_e is not None:
            raise bad("f_H/R_e", "脆性材料按式(20)：f_H、R_e 须为 None")
        return {"p_zul": fS * pos("R_m", R_m), "equation": "eq20", "brittle": True}
    if R_m is not None:
        raise bad("R_m", "延性材料按式(19) 用 R_e/R_p0,2：R_m 须为 None")
    fH = pos("f_H", f_H)
    if abs(fH - t["f_H"]) > 1e-12:
        raise OutOfDomain("f_H", f"表B.1 {component}/{material_class} f_H = {t['f_H']}，收到 {fH}")
    return {"p_zul": fS * fH * pos("R_e", R_e), "equation": "eq19", "brittle": False}


@_formula("din6892b.eq21_23", f"{STD} 6.1.3.1 式(21) M_tmaxRück ≤ q_eq·M_tRmin（单侧受载）→ f_W = 1；式(22) M_tmax > q_max·M_tRmin 且 "
          "M_tmaxRück > q_max·M_tRmin（双侧受载）→ 式(23) f_W = 2·N_W^−0,1 且 f_W ≤ 1；图7 横轴 10²–10¹⁰（PDF17/印17 原图已核）",
          note="式(21)(22) 之间的情形（q_eq·M_tRmin < M_tmaxRück ≤ q_max·M_tRmin 等）原文未覆盖 → 阻断；N_W > 10¹⁰ 超出图7 → 阻断",
          evidence=_ex("D.1", "D.2"))
def f_W(*, M_tmax, M_tmaxRueck, M_tRmin, N_W):
    Mmax, Mr, MR = nonneg("M_tmax", M_tmax), nonneg("M_tmaxRueck", M_tmaxRueck), nonneg("M_tRmin", M_tRmin)
    if Mr <= 0.5 * MR:
        if N_W is not None:
            raise bad("N_W", "式(21) 单侧受载 f_W = 1，不用 N_W，须为 None")
        return {"f_W": 1.0, "equation": "eq21"}
    if Mmax > 0.8 * MR and Mr > 0.8 * MR:
        N = pos("N_W", N_W)
        if N > 1e10:
            raise Unconfirmed("N_W", "N_W > 10¹⁰ 超出图7 范围")
        return {"f_W": min(1.0, 2.0 * N ** -0.1), "equation": "eq22_23"}
    raise Unconfirmed("M_tmaxRueck", "介于式(21) 与式(22) 条件之间的情形原文未给 f_W")


@_formula("din6892b.eq24_29", f"{STD} 6.1.3.2 延性：N_L ≤ 10³ 式(24) f_L = 1,5；10³ < N_L ≤ 10⁸ 式(25) f_L = 1,8 − 0,1·lg N_L；"
          "N_L > 10⁸ 式(26) f_L = 1,0；脆性：N_L ≤ 10³ 式(27) 1,3；10³ < N_L ≤ 10⁶ 式(28) 1,6 − 0,1·lg N_L；N_L > 10⁶ 式(29) 1,0"
          "（PDF18/印18 原图已核）", evidence=_ex("D.1", "D.2"),
          note="N_L ≤ 10³ 区段原文注明尚需系统试验（PDF17）",
          external=_KS_R4B)
def f_L(*, brittle, N_L):
    if brittle is None:
        raise MissingInput("brittle")
    if not isinstance(brittle, bool):
        raise bad("brittle", "应为 True/False")
    N = pos("N_L", N_L)
    if not brittle:
        return 1.5 if N <= 1e3 else (1.8 - 0.1 * math.log10(N) if N <= 1e8 else 1.0)
    return 1.3 if N <= 1e3 else (1.6 - 0.1 * math.log10(N) if N <= 1e6 else 1.0)


@_formula("din6892b.eq17_18", f"{STD} 6.1.3 式(17) p_eq,zul = f_W·p_zul、S_Feq = p_eq,zul/p_eq；式(18) p_max,zul = f_L·p_zul、"
          "S_Fmax = p_max,zul/p_max；两承载面均须校核（PDF16/印16 原图已核）", evidence=_ex("D.1", "D.2"),
          note="键与轴槽、毂槽两侧面接触：键按 max(p1, p2) 校核（附录D D.1/D.2 用法同）",
          external=_KS_R4B)
def criterion(*, p, p_zul, factor):
    pz = pos("factor", factor) * pos("p_zul", p_zul)
    pv = pos("p", p)
    return {"p_perm": pz, "S": pz / pv, "ok": pv <= pz}


# ------------------------------------------------------------------ 主流程
def method_b(*, d, b, h, t1, r, s1, s2, l1tr, l2tr, a, i, K_A, M_tnenn, M_tmax, M_tmaxRueck, M_tRmin, K_lambda_e,
             N_W, N_L, shaft, hub, key):
    """DIN 6892 方法 B（6.1）主流程：式(1)–(5) → 式(11)–(13) → 式(15)(16) → 式(9)(10) → 式(19)(20) → 式(21)–(29) → 式(17)(18)。

    l1tr、l2tr：轴槽/毂槽承载长度（式(6)–(8) 与 PDF11 缩减规则由调用方确定）；K_lambda_e：图4–6 读值（调用方给出）。
    shaft/hub/key：{"material_class", "f_S", "f_H", "R_e", "R_m"}（含义见 p_zul）。
    返回各中间量、三构件 eq/max 两项判据与安全系数；某项按式(15)(16) 条件可免校核时记 'not_required'。"""
    for nm, spec in (("shaft", shaft), ("hub", hub), ("key", key)):
        if spec is None:
            raise MissingInput(nm)
        for k in ("material_class", "f_S"):
            if spec.get(k) is None:
                raise MissingInput(f"{nm}.{k}")
    Meq = M_teq(K_A=K_A, M_tnenn=M_tnenn)
    Mmax = pos("M_tmax", M_tmax)
    F_eq, F_max = circumferential_force(M_t=Meq, d=d), circumferential_force(M_t=Mmax, d=d)
    t1tr = t1_bearing(t1=t1, r=r, s1=s1, d=d, b=b)
    t2tr = t2_bearing(h=h, t1=t1, r=r, s2=s2, d=d, b=b)
    Kl = K_lambda(i=i, K_lambda_e=K_lambda_e)
    KReq, KRmax = K_R(M_t=Meq, M_tRmin=M_tRmin, pressure="eq"), K_R(M_t=Mmax, M_tRmin=M_tRmin, pressure="max")
    out = {"M_teq": Meq, "F_eq": F_eq, "F_max": F_max, "t1tr": t1tr, "t2tr": t2tr, "K_lambda": Kl,
           "K_Req": KReq["K_R"], "K_Rmax": KRmax["K_R"], "ref": f"{STD} 6.1 方法 B（PDF9–18、PDF25 原图已核）"}
    p = {}
    for which, F, KR in (("eq", F_eq, KReq), ("max", F_max, KRmax)):
        if not KR["check_required"]:
            p[which] = None
            continue
        Kv = K_v(i=i, pressure=which)
        p[which] = {"p1": pressure_shaft(K_v=Kv, K_lambda=Kl, K_R=KR["K_R"], F=F, l1tr=l1tr, t1tr=t1tr, a=a),
                    "p2": pressure_hub(K_v=Kv, K_lambda=Kl, K_R=KR["K_R"], F=F, l2tr=l2tr, t2tr=t2tr), "K_v": Kv}
    if p["eq"] and p["max"]:       # PDF11：式(9.x) 大于式(10.x) 时 p_max 取式(9.x)
        for k in ("p1", "p2"):
            p["max"][k] = max(p["max"][k], p["eq"][k])
    out["pressures"] = p
    fw = f_W(M_tmax=Mmax, M_tmaxRueck=M_tmaxRueck, M_tRmin=M_tRmin, N_W=N_W)
    out["f_W"], out["f_W_equation"] = fw["f_W"], fw["equation"]
    checks, notes = {}, []
    for nm, spec, face in (("shaft", shaft, ("p1",)), ("hub", hub, ("p2",)), ("key", key, ("p1", "p2"))):
        pz = p_zul(component=nm, material_class=spec["material_class"], f_S=spec["f_S"], f_H=spec.get("f_H"),
                   R_e=spec.get("R_e"), R_m=spec.get("R_m"))
        fl = f_L(brittle=pz["brittle"], N_L=N_L)
        c = {"p_zul": pz["p_zul"], "p_zul_equation": pz["equation"], "f_L": fl}
        for which, fac in (("eq", fw["f_W"]), ("max", fl)):
            if p[which] is None:
                c[which] = "not_required"
                continue
            pv = max(p[which][f] for f in face)
            c[which] = {"p": pv, **criterion(p=pv, p_zul=pz["p_zul"], factor=fac)}
        checks[nm] = c
        if nm == "hub" and pz["brittle"] and nonneg("M_tRmin", M_tRmin) > 0:
            notes.append("脆性毂且有过盈配合：毂强度须另按 DIN 7190 校核（PDF16）")
    out["checks"] = checks
    out["ok"] = all(c[w] == "not_required" or c[w]["ok"] for c in checks.values() for w in ("eq", "max"))
    out["notes"] = notes
    return out


UNCONFIRMED = {
    "din6892b.fig4_6": f"{STD} 图4–6 K_λe 读图（PDF14–15）与文献[9] 精确法：不读图，K_λe 由调用方给出",
    "din6892b.6_2": f"{STD} 6.2 形状强度（表1 β_cb/β_ct 与式(30)，PDF19）、6.2.2 薄壁毂（PDF19–20）、6.2.3：未收录",
    "din6892b.l1tr_reduction": f"{STD} 6.1.2.1 l2tr < l_tr 时 l1tr 缩减规则（PDF11）：由调用方按几何给出 l1tr、l2tr",
    "din6892b.method_A": f"{STD} 第5章 方法 A：原文无通用步骤（PDF9）",
    "din6892b.annexA_KA": f"{STD} 附录A K_A 表：未收录，K_A 由调用方给出",
    "din6892b.fW_gap": f"{STD} 式(21)/(22) 之间的受载情形：原文未给 f_W → 阻断",
}
