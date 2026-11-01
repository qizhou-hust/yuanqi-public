"""ISO 1328-1:2013 齿面公差（公式图内实现，含 5.2.3 分档取整）。

原图已核（ISO 1328-1:2013 PDF）：
- 第1章适用范围（PDF7/印1）：5≤z≤1000，5 mm≤d≤15000 mm，0,5 mm≤m_n≤70 mm，4 mm≤b≤1200 mm，β≤45°；
  5.2.1（PDF32/印26）：式(5)–(12) 不得外推 → 写成公式域条件，越域即 out_of_domain；
- 5.2.2（PDF32）：级间公比 √2，A 级 = 5 级未取整值 × √2^(A−5)；本模块只实现 A=5（系数为 1）；
- 5.2.3（PDF32/印26）：>10 µm 取整数 µm；5,0 µm ≤ v ≤ 10 µm 取 0,5 µm；<5,0 µm 取 0,1 µm；
  参数以 mm 输入（"Parameters ... entered in millimetres"），故先把 d、b 除以 1 mm 得纯数；
- 式(10)（PDF33/印27）：fHβT = (0,05√d + 0,35√b + 4)·√2^(A−5)。

取整用 kernel 的 round_to（阶跃，导数恒 0，trace 计为非光滑节点）；分档边界用 where。
"恰在半格"时标准未规定进位方向：round_to 取远离零进位，并由 near_kinks 以裕度 0 标出。
"""
from __future__ import annotations

from ..kernel.graph import Formula

ISO1328 = "ISO 1328-1:2013"


def round_5_2_3(v):
    """5.2.3 分档取整的表达式（v 为以 µm 计的纯数表达式/变量名）。"""
    return f"where({v} > 10, round_to({v}, 1), where({v} >= 5, round_to({v}, 0.5), round_to({v}, 0.1)))"


def scope_domain(z, d, width, *, m_n="m_n", beta="beta"):
    """第1章适用范围（PDF7/印1），5.2.1 不得外推。内齿 z、d 为负号约定，取绝对值。"""
    return (f"abs({z}) >= 5", f"abs({z}) <= 1000",
            f"abs({d}) >= 5*root_mm", f"abs({d}) <= 15000*root_mm",
            f"{m_n} >= 0.5*root_mm", f"{m_n} <= 70*root_mm",
            f"{width} >= 4*root_mm", f"{width} <= 1200*root_mm",
            f"abs({beta}) <= 0.25*pi*rad")


def fhbeta5_formulas(width_of, *, width_note=""):
    """5 级螺旋线倾斜公差 fHβ5（式(10)，A=5）逐轮取整，再两轮取大。

    width_of(i) 给出第 i 轮用于式(10) 的齿宽变量名（双斜齿为 b_B，TR30 4.2.11）。
    两轮取大：ISO 6336-1:2019 7.5.3.4（PDF63/印55）只写"5 级 fHβ 公差"，未指明哪一轮；取较大者为
    保守口径（与原 v0.7 实现一致），在 note 中注明，不是标准条文。
    """
    out = []
    for i in (1, 2):
        w = width_of(i)
        raw = f"f_Hbeta5_raw_{i}"
        out.append(Formula(f"iso1328.fHbeta5.raw.{i}", raw, "1",
                           f"0.05*sqrt(abs(d_{i})/root_mm) + 0.35*sqrt({w}/root_mm) + 4",
                           f"{ISO1328} 式(10) A=5（PDF33/印27 原图已核），d、b 以 mm 计入（5.2.3 末段，PDF32）{width_note}",
                           scope_domain(f"z_{i}", f"d_{i}", w)))
        out.append(Formula(f"iso1328.fHbeta5.{i}", f"f_Hbeta5_{i}", "um", f"{round_5_2_3(raw)}*root_um",
                           f"{ISO1328} 5.2.3 分档取整（PDF32/印26 原图已核）",
                           note="round_to 为阶跃：导数恒 0，near_kinks 可报告靠近取整边界"))
    out.append(Formula("iso1328.fHbeta5.pair", "f_Hbeta5", "um", "max(f_Hbeta5_1, f_Hbeta5_2)",
                       "ISO 6336-1:2019 7.5.3.4 / TR30 4.2.10（PDF13/印8）：fHβ5 按 ISO 1328-1:2013 5 级并取整",
                       note="两轮取大为保守口径；ISO 6336-1 7.5.3.4（PDF63）未指明齿轮，非标准条文"))
    return out


# ---------------------------------------------------------------------------------------------------------------
# M35：ISO 1328-1:2013 全部公差公式（任意精度等级 A=1..11）
#
# 逐条原图已核（ISO 1328-1:2013 扫描 PDF；PDF 页 = 印刷页 + 6）：
#   第1章适用范围 PDF7/印1；5.2.1 不得外推、5.2.2 级间公比 √2、5.2.3 分档取整 PDF32/印26；
#   式(5)(6)(7) PDF32/印26；式(8)–(12) PDF33/印27；式(9)(12) 用"未取整"的分项；
#   4.4.5 式(1)(2) 测量直径、4.4.6 式(3)(4) 滤波截止 PDF27/印21；4.4.8.5（PDF29/印23）公差一律按分度圆 d 计算；
#   附录D 式(D.1) PDF43/印37，式(D.2)(D.3) 及适用范围 PDF45/印39；附录E 式(E.1) 及适用范围 PDF47/印41；
#   附录F 式(F.1)–(F.4) 及适用范围 PDF50/印44，式(F.5) PDF51/印45；附录G 式(G.2) PDF54/印48。
#   附录A/B/C 为评定（回归、二阶拟合、滤波）方法，不含公差公式。
#
# 变量约定（下标 i 为齿轮序号）：d_i 分度圆直径（内齿为负，取 |d|）、z_i 齿数（内齿为负，取 |z|）、b_i 本轮齿宽、
# A1328_i 齿面公差等级（整数 1..11）、m_n、beta；root_mm = 1 mm、root_um = 1 µm 为单位常量（5.2.3 末段：参数以 mm 代入）。
# 原值（*_raw_i，纯数，单位 µm）= 5 级未取整值 × √2^(A−5)（5.2.2）；对外值按 5.2.3 分档取整（round_to，阶跃、导数恒 0）。
# 附录 D/E/F/G 正文未写取整规则：本库对其同样按 5.2.3 分档取整并在 note 注明（KISSsoft 2026 报告同口径，见 K01/K03/K04 对拍）；
# 未取整值另作 *_raw_i 输出保留。
# ---------------------------------------------------------------------------------------------------------------
_P26 = "PDF32/印26 原图已核"
_P27 = "PDF33/印27 原图已核"


def _round_note(annex):
    return (f"{annex} 正文未规定取整；按 5.2.3 分档取整为本库口径（非标准条文；KISSsoft 2026 报告同口径）。"
            "round_to 为阶跃：导数恒 0")


def tolerance_formulas(i):
    """第 i 轮的 ISO 1328-1:2013 式(5)–(12) + 附录 D/E/G 公差（含 5.2.2 等级系数与 5.2.3 取整）。"""
    i = str(i)
    d, z, b = f"abs(d_{i})/root_mm", f"abs(z_{i})", f"b_{i}/root_mm"
    mn = "m_n/root_mm"
    dom = scope_domain(f"z_{i}", f"d_{i}", f"b_{i}") + (f"A1328_{i} >= 1", f"A1328_{i} <= 11")
    q = f"q1328_{i}"
    out = [Formula(f"iso1328.class_factor.{i}", q, "1", f"exp((A1328_{i} - 5)*log(2)/2)",
                   f"{ISO1328} 5.2.2 级间公比 √2：A 级 = 5 级未取整值 × √2^(A−5)（{_P26}）",
                   (f"A1328_{i} >= 1", f"A1328_{i} <= 11"))]

    def raw_and_rounded(key, name, expr, ref, domain=dom, note_raw="", note_round=None):
        out.append(Formula(f"iso1328.{key}.raw.{i}", f"{name}_raw_{i}", "1", expr, ref, domain, note=note_raw))
        out.append(Formula(f"iso1328.{key}.{i}", f"{name}_{i}", "um", f"{round_5_2_3(f'{name}_raw_{i}')}*root_um",
                           f"{ISO1328} 5.2.3 分档取整：>10 µm 取整，5,0–10 µm 取 0,5，<5,0 µm 取 0,1（{_P26}）",
                           note=note_round or "round_to 为阶跃：导数恒 0，near_kinks 可报告靠近取整边界"))

    raw_and_rounded("fpT", "fpT", f"(0.001*{d} + 0.4*{mn} + 5)*{q}",
                    f"{ISO1328} 5.3.1 式(5) 单个齿距公差 fpT，第1章适用范围（PDF7/印1）与 5.2.1 不得外推（{_P26}）")
    raw_and_rounded("FpT", "FpT", f"(0.002*{d} + 0.55*sqrt({d}) + 0.7*{mn} + 12)*{q}",
                    f"{ISO1328} 5.3.2 式(6) 齿距累积总公差 FpT（{_P26}）")
    raw_and_rounded("fHaT", "fHaT", f"(0.4*{mn} + 0.001*{d} + 4)*{q}",
                    f"{ISO1328} 5.3.3.1 式(7) 齿廓倾斜公差 fHαT，按 ± 使用（{_P26}）")
    raw_and_rounded("ffaT", "ffaT", f"(0.55*{mn} + 5)*{q}",
                    f"{ISO1328} 5.3.3.2 式(8) 齿廓形状公差 ffαT（{_P27}）")
    raw_and_rounded("FaT", "FaT", f"sqrt(fHaT_raw_{i}**2 + ffaT_raw_{i}**2)",
                    f"{ISO1328} 5.3.3.3 式(9) 齿廓总公差 FαT，用未取整的 fHαT、ffαT（{_P27}）")
    raw_and_rounded("fHbT", "fHbT", f"(0.05*sqrt({d}) + 0.35*sqrt({b}) + 4)*{q}",
                    f"{ISO1328} 5.3.4.1 式(10) 螺旋线倾斜公差 fHβT，按 ± 使用（{_P27}）")
    raw_and_rounded("ffbT", "ffbT", f"(0.07*sqrt({d}) + 0.45*sqrt({b}) + 4)*{q}",
                    f"{ISO1328} 5.3.4.2 式(11) 螺旋线形状公差 ffβT（{_P27}）")
    raw_and_rounded("FbT", "FbT", f"sqrt(fHbT_raw_{i}**2 + ffbT_raw_{i}**2)",
                    f"{ISO1328} 5.3.4.3 式(12) 螺旋线总公差 FβT，用未取整的 fHβT、ffβT（{_P27}）")
    # 附录 E（规范性）：径向跳动公差，适用范围 E.4：等级 1–11、z、d、mn（不含 b、β）
    dom_e = tuple(p for p in dom if "b_" not in p and "beta" not in p)
    raw_and_rounded("FrT", "FrT", f"0.9*FpT_raw_{i}",
                    f"{ISO1328} 附录E E.4 式(E.1) FrT = 0,9·FpT（未取整 FpT 展开式），适用范围见 E.4（PDF47/印41 原图已核）",
                    dom_e, note_round=_round_note("附录E"))
    # 附录 G（资料性）：相邻齿距差公差
    raw_and_rounded("fuT", "fuT", f"sqrt(2)*fpT_raw_{i}",
                    f"{ISO1328} 附录G G.2 式(G.2) fuT = √2·fpT（PDF54/印48 原图已核）",
                    note_raw="fpT 取未取整值（K01 小轮：未取整 10.68→15.1→15 与 KISSsoft 一致；取整后 11→15.6→16 不一致）",
                    note_round=_round_note("附录G"))
    # 附录 D（资料性）：扇形齿距公差 Fpz/8T，k ≈ z/8 取最近整数（D.1），k ≥ 2，z ≥ 12；适用范围同 FpT（D.5）
    out.append(Formula(f"iso1328.k_pz8.{i}", f"k_pz8_{i}", "1", f"round_to({z}/8, 1)",
                       f"{ISO1328} 附录D D.2 注3 式(D.1) k ≈ z/8 取最近整数（PDF43/印37 原图已核）",
                       (f"k_pz8_{i} >= 2", f"abs(z_{i}) >= 12"),
                       note="恰为半整数时 round_to 远离零进位（K01 大轮 z=76：9.5→10，与 KISSsoft Fpz/8T=27 一致）"))
    raw_and_rounded("Fpz8T", "Fpz8T", f"fpT_raw_{i} + 4*k_pz8_{i}/{z}*(0.001*{d} + 0.55*sqrt({d}) + 0.3*{mn} + 7)*{q}",
                    f"{ISO1328} 附录D D.5 式(D.2) FpkT，k = k_pz8（PDF45/印39 原图已核），适用范围同 FpT",
                    dom, note_raw="用式(D.2) 而非简化式(D.3)；fpT 取 A 级未取整值",
                    note_round=_round_note("附录D"))
    return out


def single_flank_formulas(i):
    """附录 F（资料性）单面啮合综合公差（方法 B）：fisT,max / fisT,min / FisT 与式(F.4) 角度换算。
    f_isdesign_i（设计值 fis(design)，µm）须由用户给出（F.1.5 末段：按应用设计与测试条件分析确定），不设默认。"""
    i = str(i)
    dom = (f"abs(z_{i}) >= 5", f"abs(z_{i}) <= 400", f"abs(d_{i}) >= 5*root_mm", f"abs(d_{i}) <= 2500*root_mm",
           f"m_n >= 1*root_mm", f"m_n <= 50*root_mm", f"A1328_{i} >= 1", f"A1328_{i} <= 11")
    ref = f"{ISO1328} 附录F F.1.5"
    amp = f"(0.375*m_n/root_mm + 5)*q1328_{i}"
    out = [
        Formula(f"iso1328.fisTmax.raw.{i}", f"fisTmax_raw_{i}", "1", f"f_isdesign_{i}/root_um + {amp}",
                f"{ref} 式(F.1)，适用范围 1≤mn≤50 mm、5≤z≤400、5≤d≤2500 mm（PDF50/印44 原图已核）", dom),
        Formula(f"iso1328.fisTmin.raw.{i}", f"fisTmin_raw_{i}", "1", f"max(f_isdesign_{i}/root_um - {amp}, 0)",
                f"{ref} 式(F.2)(F.3) 取较大者（PDF50/印44 原图已核）", dom),
        Formula(f"iso1328.FisT.raw.{i}", f"FisT_raw_{i}", "1", f"FpT_raw_{i} + fisTmax_raw_{i}",
                f"{ISO1328} 附录F F.1.6 式(F.5) FisT = FpT + fisT,max（PDF51/印45 原图已核）", dom,
                note="FpT 取未取整值（K01/K03/K04 与 KISSsoft 一致）"),
    ]
    for key in ("fisTmax", "fisTmin", "FisT"):
        out.append(Formula(f"iso1328.{key}.{i}", f"{key}_{i}", "um", f"{round_5_2_3(f'{key}_raw_{i}')}*root_um",
                           f"{ISO1328} 附录F 式(F.1)–(F.5) 值按 5.2.3 分档取整（{_P26}）", note=_round_note("附录F")))
    out.append(Formula(f"iso1328.fisT_angle.{i}", f"fisTmax_ang_{i}", "rad", f"2*fisTmax_raw_{i}*root_um/abs(d_{i})*rad",
                       f"{ISO1328} 附录F 式(F.4) 角度换算 fisT(µrad) = 2000·fisT(µm)/d(mm)，按分度圆 d（PDF50/印44 原图已核）",
                       note="以 rad 输出；1 µrad = 1e-6 rad"))
    return out


def measurement_diameter_formulas(i):
    """4.4.5 式(1)(2) 测量直径 dM 与 4.4.6 式(3)(4) 滤波截止波长（PDF27/印21 原图已核）。"""
    i = str(i)
    return [
        Formula(f"iso1328.dM.{i}", f"dM_{i}", "mm", f"da_{i} - 2*m_n",
                f"{ISO1328} 4.4.5 式(1) 外齿 dM = da − 2mn、式(2) 内齿 |dM| = |da| + 2mn（PDF27/印21 原图已核）",
                note="带符号约定（内齿 da、dM 为负）下两式合一为 dM = da − 2mn；仅在测量直径未另行规定时使用"),
    ]


def filter_cutoff_formulas(i):
    """4.4.6 式(3)(4)：推荐的齿廓/螺旋线形状滤波截止波长 λα、λβ（PDF27/印21 原图已核）。"""
    i = str(i)
    return [
        Formula(f"iso1328.lambda_a.{i}", f"lambda_a_{i}", "mm", f"max(L_alpha_{i}/30, 0.25*root_mm)",
                f"{ISO1328} 4.4.6 式(3) λα = Lα/30，且不小于 0,25 mm（PDF27/印21 原图已核）"),
        Formula(f"iso1328.lambda_b.{i}", f"lambda_b_{i}", "mm", f"max(b_{i}/30, lambda_a_{i})",
                f"{ISO1328} 4.4.6 式(4) λβ = b/30，且不小于 λα（PDF27/印21 原图已核）"),
    ]


# 模块顶层：供注册表导出（两轮各一套，公式对象与装配时生成的逐字相同）
TOLERANCES = [f for i in (1, 2) for f in tolerance_formulas(i)]
SINGLE_FLANK = [f for i in (1, 2) for f in single_flank_formulas(i)]
MEASUREMENT_DIAMETER = [f for i in (1, 2) for f in measurement_diameter_formulas(i)]
FILTER_CUTOFF = [f for i in (1, 2) for f in filter_cutoff_formulas(i)]
