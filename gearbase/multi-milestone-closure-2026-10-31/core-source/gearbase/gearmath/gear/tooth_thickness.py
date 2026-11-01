"""M35：齿厚与测量尺寸（公法线长度 Wk 与跨齿数 k、量球距 MdK、法向弦齿厚）及齿厚偏差 → 测量值换算。

来源状态（如实）：本项目几何引用 ISO 21771（DIN 3960 已废止），但 ISO 21771 原文不在证据包；以下公式按经典渐开线几何
推导（渐开线函数、基圆切线、当量齿轮），每条 ref 标明"ISO 21771 原文不在证据包"，注册表 source_check = not_in_evidence，
不标已核。独立证据只来自对拍（逐例偏差见 gear/manufacturing_check.py 与 C 分路报告）：
  - KISSsoft 2026 报告 K01–K05 第 10/12 章 Wk、Wk.e/i、dMWk.m、MdK、MdK.e/i、sn、sn.e/i、hac、sc、sc.e/i；
  - ISO/TR 6336-30:2022 例1–8 表中的 Wk（由表列产形变位 xE 正算）与例6 内齿 MdK。

推导要点（下标 i 为齿轮序号；内齿按 ISO 6336/TR30 带符号约定：z、d、db、da、MdK 为负）：
  - 法向分度圆弧齿厚 sn = mn(π/2 + 2x tanαn)；齿厚偏差 Asn 等价于变位 Δx = Asn/(2 mn tanαn)；
  - Wk = mn cosαn [π(k − 0.5) + z inv αt] + 2 x mn sinαn（法向，跨 k 齿）；偏差：ΔWk = Asn cosαn；
  - 量具与齿面在基圆切平面内接触；接触点直径 dMWk = sqrt(db² + (Wk cosβb)²)；
    推荐跨齿数（接触点落在 d + 2 x mn 上）k = (z/π)[...]+0.5 取最近整数，仅为推荐，k 为输入（制造决定）；
  - 斜齿 Wk 可测条件 b > Wk sinβb（量具接触线在齿宽内）；
  - 量球（端面内）：inv αKt = inv αt + DM/(mn z cosαn) − π/(2z) + 2x tanαn/z，dK = db/cos αKt，
    偶数齿 MdK = dK + DM，奇数齿 MdK = dK cos(π/(2|z|)) + DM（带符号统一式，内齿 z、db、MdK 为负，与 internal_gear.py 同式）；
  - 法向弦齿厚在当量直齿轮上：zn = z/(cos²βb cosβ)，ψ = sn/(mn zn)，s̄c = mn zn sinψ，
    弦齿高 h̄ac = (da − d)/2 + (mn zn/2)(1 − cosψ)；
  - 带偏差的弦齿厚按"卡尺高度固定为名义 h̄ac"换算：当量齿轮上弦到中心距离 h0 = rna − h̄ac，
    半角 φ 满足 φ = (sn + Asn)/(mn zn) + inv αn − inv αy，cos αy = rbn cosφ / h0（不动点），s̄c = 2 h0 tanφ。
"""
from __future__ import annotations

from ..kernel.graph import Formula, InputSpec

F, S = Formula, InputSpec
G = "ISO 21771:2007"
NIE = "；ISO 21771 原文不在证据包，按经典渐开线几何推导"


def _parity(i):
    """偶数齿 → 1，奇数齿 → cos(π/(2|z|))；z 为整数（输入声明域保证）。"""
    return (f"where(abs(abs(z_{i}) - 2*round_to(abs(z_{i})/2, 1)) < 0.5, 1, cos(pi/(2*abs(z_{i}))*rad))")


def geometry_formulas(i, internal):
    """第 i 轮的分度圆/齿顶圆/齿根圆（基本齿条按轮给 haP_i、hfP_i）。外齿分度圆用库公式 geo.d（z ≥ 5），内齿另给带符号式。"""
    i = str(i)
    out = []
    if internal:
        out.append(F(f"mfg.d.int.{i}", f"d_{i}", "mm", f"z_{i}*m_t",
                     f"{G} 分度圆直径（内齿带符号：z、d 为负）{NIE}", (f"z_{i} <= -5",)))
    out += [
        F(f"mfg.da.{i}", f"da_{i}", "mm", f"d_{i} + 2*m_n*(haP_{i} + x_{i})",
          f"{G} 齿顶圆直径（按轮基本齿条 haP_i、名义变位，不含齿顶缩短；内齿带符号同式）{NIE}"),
        F(f"mfg.df.{i}", f"df_{i}", "mm", f"d_{i} - 2*m_n*(hfP_{i} - x_{i})",
          f"{G} 齿根圆直径（按轮基本齿条 hfP_i、名义变位；内齿带符号同式）{NIE}",
          note="名义值；按产形变位（含齿厚偏差）的齿根圆见 ISO 6336-3 / TR30 适配器"),
    ]
    return out


def thickness_formulas(i):
    """齿厚、偏差等价变位（外齿与内齿通用）。"""
    i = str(i)
    out = [F(f"mfg.sn.{i}", f"s_n_{i}", "mm", f"m_n*(pi/2 + 2*x_{i}*tan(alpha_n))",
             f"{G} 法向分度圆弧齿厚 sn（无侧隙名义值）{NIE}")]
    for e, word in (("e", "上"), ("i", "下")):
        out.append(F(f"mfg.sn.{e}.{i}", f"s_n{e}_{i}", "mm", f"s_n_{i} + A_sn_{e}_{i}",
                     f"{G} 含齿厚{word}偏差的法向弧齿厚 sn + Asn,{e}{NIE}"))
        out.append(F(f"mfg.xA.{e}.{i}", f"x_A{e}_{i}", "1", f"x_{i} + A_sn_{e}_{i}/(2*m_n*tan(alpha_n))",
                     f"{G} 齿厚{word}偏差等价变位 x + Asn,{e}/(2 mn tanαn)（由 sn 式对 x 求逆）{NIE}"))
    return out


def span_formulas(i):
    """公法线长度（外齿）：名义、上/下偏差、推荐跨齿数、接触点直径。"""
    i = str(i)
    wk = f"m_n*cos(alpha_n)*(pi*(k_span_{i} - 0.5) + z_{i}*inv(alpha_t)/rad)"
    can = (f"b_{i} > W_k0_{i}*sin(beta_b)", f"z_{i} > 0")
    out = [
        F(f"mfg.Wk.{i}", f"W_k0_{i}", "mm", f"{wk} + 2*x_{i}*m_n*sin(alpha_n)",
          f"{G} 公法线长度 Wk（法向，跨 k 齿，无侧隙名义值）{NIE}", can,
          note="域：外齿；斜齿可测条件 b > Wk·sinβb（K04 大轮 KISSsoft 报告'gear too thin'与之一致）"),
    ]
    for e, word in (("e", "上"), ("i", "下")):
        out.append(F(f"mfg.Wk.{e}.{i}", f"W_k{e}_{i}", "mm", f"W_k0_{i} + A_sn_{e}_{i}*cos(alpha_n)",
                     f"{G} 含齿厚{word}偏差的公法线长度 Wk + Asn,{e}·cosαn{NIE}", can))
    out += [
        F(f"mfg.Wk.m.{i}", f"W_km_{i}", "mm", f"(W_ke_{i} + W_ki_{i})/2", f"{G} 公法线长度公差带中值{NIE}"),
        F(f"mfg.dMWk.{i}", f"d_MWk_{i}", "mm", f"sqrt(db_{i}**2 + (W_km_{i}*cos(beta_b))**2)",
          f"{G} 公法线量具接触点直径（按公差带中值 Wk，基圆切平面内几何）{NIE}"),
        F(f"mfg.k_rec.raw.{i}", f"k_rec_raw_{i}", "1",
          f"((db_{i}*tan(acos(db_{i}/(d_{i} + 2*x_{i}*m_n)))/cos(beta_b) - 2*x_{i}*m_n*sin(alpha_n))"
          f"/(m_n*cos(alpha_n)) - z_{i}*inv(alpha_t)/rad)/pi + 0.5",
          f"{G} 跨齿数推荐值（接触点落在 d + 2x·mn 圆上）{NIE}", (f"z_{i} > 0", f"d_{i} + 2*x_{i}*m_n > db_{i}")),
        F(f"mfg.k_rec.{i}", f"k_rec_{i}", "1", f"max(round_to(k_rec_raw_{i}, 1), 1)",
          f"{G} 跨齿数推荐值取最近整数（至少 1）{NIE}",
          note="仅为推荐；参数表中的 k 为输入（制造决定），对拍中 KISSsoft/TR30 所选 k 与推荐值不总一致"),
    ]
    return out


def ball_formulas(i):
    """量球距 MdK（外齿与内齿带符号统一式；量球在端面内）：名义、上/下偏差。"""
    i = str(i)
    out = []
    for suffix, x, word in (("0", f"x_{i}", "无侧隙名义"), ("e", f"x_Ae_{i}", "含齿厚上偏差"),
                            ("i", f"x_Ai_{i}", "含齿厚下偏差")):
        ak = f"alpha_K{suffix}_{i}"
        out.append(F(f"mfg.alphaK.{suffix}.{i}", ak, "rad",
                     f"inv_inverse(inv(alpha_t) + (D_M_{i}/(m_n*z_{i}*cos(alpha_n)) - pi/(2*z_{i}) "
                     f"+ 2*{x}*tan(alpha_n)/z_{i})*rad)",
                     f"{G} 量球中心所在圆的端面压力角 inv αKt（{word}；带符号统一式，内齿 z 为负）{NIE}"))
        out.append(F(f"mfg.MdK.{suffix}.{i}", f"M_dK{suffix}_{i}", "mm", f"db_{i}/cos({ak})*{_parity(i)} + D_M_{i}",
                     f"{G} 量球距 MdK（{word}）：偶数齿 dK + DM，奇数齿 dK·cos(π/(2|z|)) + DM；内齿 db、MdK 为负{NIE}",
                     note="量球在端面内；斜齿量柱（MdR）不同，未实现"))
    return out


def chordal_formulas(i):
    """法向弦齿厚与弦齿高（外齿，当量直齿轮）；带偏差弦齿厚按卡尺高度固定为名义 h̄ac 换算。"""
    i = str(i)
    rn, rbn = f"(m_n*zn_{i}/2)", f"(m_n*zn_{i}/2*cos(alpha_n))"
    ext = (f"z_{i} > 0",)
    out = [
        F(f"mfg.psi.{i}", f"psi_c_{i}", "rad", f"s_n_{i}/(m_n*zn_{i})*rad",
          f"{G} 当量齿轮分度圆上的齿厚半角 ψ = sn/(mn zn){NIE}", ext),
        F(f"mfg.sc.{i}", f"s_c_{i}", "mm", f"m_n*zn_{i}*sin(psi_c_{i})", f"{G} 法向弦齿厚 s̄c = mn zn sinψ{NIE}", ext),
        F(f"mfg.hac.{i}", f"h_ac_{i}", "mm", f"(da_{i} - d_{i})/2 + {rn}*(1 - cos(psi_c_{i}))",
          f"{G} 弦齿高 h̄ac = (da − d)/2 + (mn zn/2)(1 − cosψ){NIE}", ext),
        F(f"mfg.h0.{i}", f"h_c0_{i}", "mm", f"{rn} + (da_{i} - d_{i})/2 - h_ac_{i}",
          f"{G} 当量齿轮中心到弦的距离（卡尺高度固定为名义 h̄ac）{NIE}", ext + (f"h_c0_{i} > {rbn}",)),
    ]
    for e, word in (("e", "上"), ("i", "下")):
        phi = f"phi_c{e}_{i}"
        out.append(F(f"mfg.phi.{e}.{i}", phi, "rad",
                     f"s_n{e}_{i}/(m_n*zn_{i})*rad + inv(alpha_n) - inv(acos({rbn}*cos({phi})/h_c0_{i}))",
                     f"{G} 含齿厚{word}偏差、卡尺高度固定时弦端点处齿厚半角 φ（不动点）{NIE}", ext,
                     kind="fixed_point", start=0.0))
        out.append(F(f"mfg.sc.{e}.{i}", f"s_c{e}_{i}", "mm", f"2*h_c0_{i}*tan({phi})",
                     f"{G} 含齿厚{word}偏差的法向弦齿厚（卡尺高度 = 名义 h̄ac）{NIE}", ext))
    return out


def measurement_inputs(i, *, internal):
    """第 i 轮测量相关输入声明。"""
    i = str(i)
    z_dom = (f"z_{i} - round_to(z_{i}, 1) >= 0", f"z_{i} - round_to(z_{i}, 1) <= 0") + \
        ((f"z_{i} <= -5",) if internal else (f"z_{i} >= 1",))
    return [
        S(f"z_{i}", "1", "齿数（整数；内齿为负）", z_dom),
        S(f"x_{i}", "1", "法向变位系数（名义）"),
        S(f"b_{i}", "mm", "本轮齿宽（双斜齿取单侧螺旋齿宽）", (f"b_{i} > 0",)),
        S(f"haP_{i}", "1", "基本齿条齿顶高系数", (f"haP_{i} > 0",)),
        S(f"hfP_{i}", "1", "基本齿条齿根高系数", (f"hfP_{i} > 0",)),
        S(f"rhofP_{i}", "1", "基本齿条齿根圆角半径系数", (f"rhofP_{i} >= 0",)),
        S(f"A_sn_e_{i}", "mm", "法向齿厚上偏差 Asn,e（带符号，减薄为负）"),
        S(f"A_sn_i_{i}", "mm", "法向齿厚下偏差 Asn,i（带符号，减薄为负）"),
        S(f"k_span_{i}", "1", "公法线跨齿数 k（整数，制造决定）",
          (f"k_span_{i} >= 1", f"k_span_{i} - round_to(k_span_{i}, 1) >= 0", f"k_span_{i} - round_to(k_span_{i}, 1) <= 0")),
        S(f"D_M_{i}", "mm", "量球直径 DM（实际使用值）", (f"D_M_{i} > 0",)),
        S(f"A1328_{i}", "1", "ISO 1328-1:2013 齿面公差等级 A（整数 1..11）",
          (f"A1328_{i} >= 1", f"A1328_{i} <= 11", f"A1328_{i} - round_to(A1328_{i}, 1) >= 0",
           f"A1328_{i} - round_to(A1328_{i}, 1) <= 0")),
        S(f"da_{i}", "mm", "齿顶圆直径（tip_diameter='input' 时为输入；内齿为负）"),
        S(f"f_isdesign_{i}", "um", "单面啮合综合偏差设计值 fis(design)（附录F，须由应用分析给出）", (f"f_isdesign_{i} >= 0",)),
        S(f"L_alpha_{i}", "mm", "齿廓评定长度 Lα（4.4.6 式(3)）", (f"L_alpha_{i} > 0",)),
    ]


SHARED_INPUTS = [
    S("m_n", "mm", "法向模数", ("m_n > 0",)),
    S("alpha_n", "deg", "法向压力角", ("alpha_n > 0", "alpha_n < pi/2")),
    S("beta", "deg", "分度圆螺旋角（取绝对值，旋向另行声明）", ("beta >= 0", "beta < pi/2")),
    S("root_mm", "mm", "长度单位常量 1 mm", ("root_mm >= 1", "root_mm <= 1")),
    S("root_um", "um", "长度单位常量 1 µm", ("root_um >= 0.001", "root_um <= 0.001")),
]

# 模块顶层：供注册表导出（外齿 i=1,2；内齿分度圆式 i=1,2）
GEOMETRY = [f for i in (1, 2) for f in geometry_formulas(i, internal=True)]
THICKNESS = [f for i in (1, 2) for f in thickness_formulas(i)]
SPAN = [f for i in (1, 2) for f in span_formulas(i)]
BALLS = [f for i in (1, 2) for f in ball_formulas(i)]
CHORDAL = [f for i in (1, 2) for f in chordal_formulas(i)]
