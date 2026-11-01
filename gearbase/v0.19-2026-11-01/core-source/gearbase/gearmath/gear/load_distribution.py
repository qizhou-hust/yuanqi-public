"""齿向载荷系数 K_Hβ（ISO 6336-1:2019 方法C，7.5）与齿间载荷系数 K_Hα/K_Fα（方法B，8.3）公式库。

链路（K_Hβ）：Fm/b → f_sh（式59）→ f_ma（式66）→ 表12 B1/B2 → F_βx（式54/55，下限式58）
→ y_β（式46/48/50，按材料组与速度限幅，式52 取两轮均值）→ F_βy（式45）→ K_Hβ（式41/43）。
链路（K_Hα）：f_pb（8.3.2，取两轮基节/齿廓形状偏差的较大者，可乘 0.5）→ y_α（式77-80）
→ F_tH/b → K_Hα=K_Fα（式73/74，按 εγ≤2 / >2 分支）→ 限值（式75/76，下限 1）。

所有式号、条款、PDF 页码均已对照 ISO 6336-1:2019 扫描件页面图像核对（PDF 页 = 印刷页 + 8）。
条款/式号只做引用，不复制标准原文。复用 gear/dynamic.py 的 line_load、K_V、c_gamma_alpha、c_gamma_beta、
eps_gamma、c_unit；复用 gear/formulas.py 的 d_1、v、eps_alpha、Z_eps。不实现：人字齿式(60)、式(56) 的
f_sh2/f_ca/f_be 扩展项、式(62)-(65) 的 f_ma 其它取法（f_ma 只按式66）。
下标 _1 = 小轮，_2 = 大轮。偏差类量单位 µm。
"""
from __future__ import annotations

from ..kernel.graph import Formula, InputSpec, Model
from .dynamic import CONSTANTS as DYN_CONSTANTS
from .inputs import input_specs

F = Formula
R1 = "ISO 6336-1:2019"


def _code(var, values):
    """枚举码 1..n → 取值（嵌套 where；码为无量纲整数输入，按半整数分界）。"""
    expr = str(values[-1])
    for k in range(len(values) - 1, 0, -1):
        expr = f"where({var} < {k + 0.5}, {values[k - 1]}, {expr})"
    return expr


def _y_group(i, lin_a, cap_a5, cap_a10, lin_b, cap_b5, cap_b10, lin_c, cap_c, base):
    """跑合量（按材料组 mat_group_i 分三支，每支按速度 v 限幅）；各支同量纲 µm。"""
    g = f"mat_group_{i}"
    a = (f"min({lin_a}*MPa_unit/sigma_Hlim_{i}*{base}, where(v <= 5*v_unit, {base}, "
         f"where(v <= 10*v_unit, {cap_a5}*MPa_unit/sigma_Hlim_{i}*y_unit, {cap_a10}*MPa_unit/sigma_Hlim_{i}*y_unit)))")
    b = (f"min({lin_b}*{base}, where(v <= 5*v_unit, {base}, "
         f"where(v <= 10*v_unit, {cap_b5}*y_unit, {cap_b10}*y_unit)))")
    c = f"min({lin_c}*{base}, {cap_c}*y_unit)"
    return f"where({g} < 1.5, {a}, where({g} < 2.5, {b}, {c}))"


# ---------------- K_Hβ 方法C（7.5） ----------------
KHBETA = [
    F("ld.Fm_b", "Fm_b", "N/mm", "line_load*K_V",
      f"{R1} 7.2.2 单位齿宽平均载荷 Fm/b = Ft·KA·Kγ·Kv/b（PDF 52 页）"),
    F("ld.K_prime", "K_prime", "1",
      f"where(d_1/d_sh >= 1.15 and pinion_stiffening > 0.5, "
      f"{_code('pinion_arrangement', (0.48, -0.48, 1.33, -0.36, -0.6))}, "
      f"{_code('pinion_arrangement', (0.8, -0.8, 1.33, -0.6, -1.0))})",
      f"{R1} 7.5.3.5.2 图13 常数 K'（布置 a-e；d1/dsh≥1.15 且非键连接/热装时按有加强取值，图13 注a；PDF 68 页）"),
    F("ld.f_sh", "f_sh", "um",
      "0.023*Fm_b/c_unit*(abs(B_star + K_prime*l_sh*s_sh/d_1**2*(d_1/d_sh)**4 - 0.3) + 0.3)*(b/d_1)**2",
      f"{R1} 7.5.3.5.2 式(59) 小轮及轴弯扭变形当量啮合误差 f_sh（直齿/单斜齿；k_unit=0.023 mm·µm/N；PDF 65 页）"),
    F("ld.f_ma", "f_ma", "um", "sqrt(f_Hbeta_1**2 + f_Hbeta_2**2)",
      f"{R1} 7.5.4.4 式(66) 制造误差引起的啮合错位 f_ma（平均质量控制水平；PDF 70 页）"),
    F("ld.B_1", "B_1", "1", _code("helix_mod", (1, 1, 0.5, 0.1, 0.1, 0.7)),
      f"{R1} 7.5.3.4 表12 常数 B1（齿向修形 1 无/2 鼓形 Cβ=0.5fma/3 鼓形 Cβ=0.5(fma+fsh)/4 螺旋角修正/"
      "5 修正+鼓形/6 端修；PDF 63 页）"),
    F("ld.B_2", "B_2", "1", _code("helix_mod", (1, 0.5, 0.5, 1.0, 0.5, 0.7)), f"{R1} 7.5.3.4 表12 常数 B2（PDF 63 页）"),
    F("ld.f_Hbeta", "f_Hbeta", "um", "max(f_Hbeta_1, f_Hbeta_2)",
      f"{R1} 7.5.3.4 式(58) 中的 fHβ：取两轮螺旋线倾斜公差较大者（解释口径，与 KISSsoft K01/K03 一致）"),
    F("ld.F_bx_min", "F_bx_min", "um", "max(0.005*Fm_b/c_unit, 0.5*f_Hbeta)",
      f"{R1} 7.5.3.4 式(58) F_βx 下限（0.005 mm·µm/N·Fm/b 与 0.5 fHβ 取大；PDF 64 页）"),
    F("ld.F_bx_add", "F_bx_add", "um", "1.33*B_1*f_sh + B_2*f_ma",
      f"{R1} 7.5.3.4 式(54) 接触斑点未验证（叠加型）初始当量啮合误差（PDF 63 页）"),
    F("ld.F_bx_comp", "F_bx_comp", "um", "abs(1.33*B_1*f_sh - f_Hbeta5)",
      f"{R1} 7.5.3.4 式(55) 接触斑点位置有利（补偿型）初始当量啮合误差，fHβ5 为 5 级螺旋线倾斜公差（PDF 63 页）"),
    F("ld.F_bx", "F_bx", "um", "max(where(contact_favourable > 0.5, F_bx_comp, F_bx_add), F_bx_min)",
      f"{R1} 7.5.3.4 式(54)/(55)（按图12 判定的接触斑点位置选择），并取 ≥ F_βx,min（PDF 63/64/67 页）"),
    *[F(f"ld.y_beta_{i}", f"y_beta_{i}", "um",
        _y_group(i, 320, 25600, 12800, 0.55, 45, 22, 0.15, 6, "F_bx"),
        f"{R1} 7.5.3.2 式(46)/(48)/(50) 齿向跑合量 y_β{i}（材料组 1:St/V/GGG(perl.,bai.)/GTS，2:GG/GGG(ferr.)，"
        "3:Eh/IF/NT/NV；速度限幅与 y_β≤F_βx；PDF 60 页）") for i in ("1", "2")],
    F("ld.y_beta", "y_beta", "um", "(y_beta_1 + y_beta_2)/2", f"{R1} 7.5.3.2 式(52) 两轮均值（同材料时即本值；PDF 60 页）"),
    F("ld.F_by", "F_by", "um", "F_bx - y_beta", f"{R1} 7.5.2 式(45) 有效当量啮合误差 F_βy（PDF 59 页）"),
    F("ld.q_beta", "q_beta", "1", "F_by*c_gamma_beta/(2*Fm_b)",
      f"{R1} 7.5.1 a)/b) 判据量 F_βy·cγβ/(2Fm/b)（≥1 为部分接触；PDF 58/59 页）"),
    F("ld.K_Hbeta", "K_Hbeta", "1", "where(q_beta >= 1, 2*sqrt(q_beta), 1 + q_beta)",
      f"{R1} 7.5.1 式(41)（≥1 时 √(2Fβy cγβ/(Fm/b))）/ 式(43)（<1 时 1+Fβy cγβ/(2Fm/b)）；q=1 处连续（PDF 58/59 页）"),
    F("ld.b_cal_rel", "b_cal_rel", "1", "where(q_beta >= 1, sqrt(1/q_beta), 0.5 + 1/(2*q_beta))",
      f"{R1} 7.5.1 式(42)/(44) 计算接触宽度比 b_cal/b（PDF 58/59 页）"),
]

# ---------------- K_Hα / K_Fα 方法B（8.3） ----------------
KHALPHA = [
    F("ld.f_pb_a", "f_pb_a", "um", "k_pb*max(f_pbT_1, f_pbT_2, f_falpha_1, f_falpha_2)",
      f"{R1} 8.3.2 f_pb 取两轮基节偏差较大者；ffα 更大时以 ffα 代替（注）；有补偿性齿廓修形时可取 50%（k_pb=0.5）"
      "（先取大再折半，与 KISSsoft K02 一致；PDF 74 页）"),
    *[F(f"ld.y_alpha_{i}", f"y_alpha_{i}", "um",
        _y_group(i, 160, 12800, 6400, 0.275, 22, 11, 0.075, 3, "f_pb_a"),
        f"{R1} 8.3.6.2 式(77)/(78)/(79) 齿廓跑合量 y_α{i}（材料组同 y_β；速度限幅；PDF 76 页）") for i in ("1", "2")],
    F("ld.y_alpha", "y_alpha", "um", "(y_alpha_1 + y_alpha_2)/2", f"{R1} 8.3.6.2 式(80) 两轮均值（PDF 76 页）"),
    F("ld.FtH_b", "FtH_b", "N/mm", "Fm_b*K_Hbeta", f"{R1} 8.3.2 F_tH = Ft·KA·Kγ·Kv·KHβ（单位齿宽；PDF 74 页）"),
    F("ld.q_alpha", "q_alpha", "1", "c_gamma_alpha*(f_pb_a - y_alpha)/FtH_b", f"{R1} 8.3.3 图16 横坐标 q_α（PDF 75 页）"),
    F("ld.K_alpha_raw", "K_alpha_raw", "1",
      "where(eps_gamma <= 2, eps_gamma/2*(0.9 + 0.4*q_alpha), 0.9 + 0.4*sqrt(2*(eps_gamma - 1)/eps_gamma)*q_alpha)",
      f"{R1} 8.3.2 式(73)（εγ≤2）/ 式(74)（εγ>2）；εγ=2 处连续（PDF 74 页）"),
    F("ld.K_Halpha_lim", "K_Halpha_lim", "1", "eps_gamma/(eps_alpha*Z_eps**2)", f"{R1} 8.3.4 式(75) K_Hα 上限（PDF 75 页）"),
    F("ld.K_Falpha_lim", "K_Falpha_lim", "1", "eps_gamma/(0.25*eps_alpha + 0.75)", f"{R1} 8.3.5 式(76) K_Fα 上限（PDF 75 页）"),
    F("ld.K_Halpha", "K_Halpha", "1", "max(min(K_alpha_raw, K_Halpha_lim), 1)",
      f"{R1} 8.3.4 超上限取上限、小于 1 取 1（PDF 75 页）"),
    F("ld.K_Falpha", "K_Falpha", "1", "max(min(K_alpha_raw, K_Falpha_lim), 1)",
      f"{R1} 8.3.5 超上限取上限、小于 1 取 1（PDF 75 页）"),
]

LOAD_DISTRIBUTION = KHBETA + KHALPHA

# 单位约定常数（标准常数，不是用户可调参数）；c_unit 复用 dynamic.CONSTANTS
LD_CONSTANTS = [
    ("MPa_unit", 1.0, "MPa", f"{R1} 7.5.3.2/8.3.6.2 跑合量经验式中 σHlim 以 N/mm² 计"),
    ("y_unit", 1.0, "um", f"{R1} 7.5.3.2/8.3.6.2 跑合量上限以 µm 计"),
    ("v_unit", 1.0, "m/s", f"{R1} 7.5.3.2/8.3.6.2 速度分界以 m/s 计"),
]

_S = InputSpec
_P = (("1", "小轮"), ("2", "大轮"))
LD_INPUTS = [
    _S("pinion_arrangement", "1", "图13 小轮布置 1..5 = a)..e)", ("pinion_arrangement >= 1", "pinion_arrangement <= 5")),
    _S("pinion_stiffening", "1", "小轮与轴一体（1）/键连接或热装（0），图13 注a", ("pinion_stiffening >= 0", "pinion_stiffening <= 1")),
    _S("B_star", "1", "式(59) B*（全部功率经单一啮合时直齿/单斜齿为 1）", ("B_star >= 1",)),
    _S("l_sh", "mm", "小轮轴承跨距 l", ("l_sh > 0",)),
    _S("s_sh", "mm", "小轮偏置距离 s", ("s_sh >= 0",)),
    _S("d_sh", "mm", "小轮轴外径 dsh", ("d_sh > 0",)),
    _S("helix_mod", "1", "表12 齿向修形类型 1..6", ("helix_mod >= 1", "helix_mod <= 6")),
    _S("contact_favourable", "1", "图12 接触斑点位置有利（1→式55）/否（0→式54）",
       ("contact_favourable >= 0", "contact_favourable <= 1")),
    *[_S(f"f_Hbeta_{i}", "um", f"螺旋线倾斜公差 fHβ（{w}）", (f"f_Hbeta_{i} > 0",)) for i, w in _P],
    _S("f_Hbeta5", "um", "5 级螺旋线倾斜公差 fHβ5（式55）", ("f_Hbeta5 > 0",)),
    *[_S(f"f_pbT_{i}", "um", f"基节偏差 fpb（{w}）；全链模型中由 gear/dynamic.py 按 method.f_pb 推出", (f"f_pbT_{i} > 0",)) for i, w in _P],
    _S("k_pb", "1", "8.3.2 有补偿性齿廓修形时 f_pb 折减系数（0.5 或 1）", ("k_pb >= 0.5", "k_pb <= 1")),
    *[_S(f"mat_group_{i}", "1", f"跑合材料组 1/2/3（{w}，见 y_β 公式说明）", (f"mat_group_{i} >= 1", f"mat_group_{i} <= 3"))
      for i, w in _P],
    *[_S(name, unit, f"标准常数：{ref}") for name, _, unit, ref in LD_CONSTANTS],
]

# 部分模型：只求本模块公式，上游量作为证据输入（用于与外部软件的中间量逐项对比）
UPSTREAM_INPUTS = [
    _S("line_load", "N/mm", "Ft·KA·Kγ/b", ("line_load > 0",)),
    _S("K_V", "1", "动载系数", ("K_V >= 1",)),
    _S("c_gamma_alpha", "N/(mm*um)", "啮合刚度 cγα", ("c_gamma_alpha > 0",)),
    _S("c_gamma_beta", "N/(mm*um)", "啮合刚度 cγβ", ("c_gamma_beta > 0",)),
    _S("c_unit", "N/(mm*um)", "单位约定 1 N/(mm·µm)"),
    _S("d_1", "mm", "小轮分度圆直径", ("d_1 > 0",)),
    _S("b", "mm", "有效齿宽", ("b > 0",)),
    _S("v", "m/s", "分度圆线速度", ("v > 0",)),
    _S("eps_alpha", "1", "端面重合度", ("eps_alpha > 0",)),
    _S("eps_gamma", "1", "总重合度", ("eps_gamma > 0",)),
    _S("Z_eps", "1", "重合度系数", ("Z_eps > 0",)),
    *[_S(f"sigma_Hlim_{i}", "MPa", f"接触疲劳极限（{w}）", (f"sigma_Hlim_{i} > 0",)) for i, w in _P],
    *[_S(f"f_falpha_{i}", "um", f"齿廓形状公差 ffα（{w}）", (f"f_falpha_{i} > 0",)) for i, w in _P],
]


def set_ld_constants(m):
    """写入本模块单位约定常数与 dynamic 的 c_unit（只写模型声明了的）。"""
    for name, v, unit, ref in LD_CONSTANTS + [c for c in DYN_CONSTANTS if c[0] == "c_unit"]:
        if not m.specs or name in m.specs:
            m.set(name, v, unit, "standard_constant", ref)
    return m


def standalone_model(khbeta_external=False):
    """只含 K_Hβ/K_Hα 公式的部分模型（上游量为输入），版次已配置。

    khbeta_external=True：K_Hβ 作为证据输入（只求 K_Hα/K_Fα，用于 K_Hβ 为外部给定的案例）。
    """
    fs = [KHBETA[0]] + KHALPHA if khbeta_external else LOAD_DISTRIBUTION
    extra = [_S("K_Hbeta", "1", "齿向载荷系数（外部给定）", ("K_Hbeta >= 1",))] if khbeta_external else []
    m = Model(fs, inputs=input_specs(fs, UPSTREAM_INPUTS + LD_INPUTS + extra), editions={"ISO 6336-1": "2019"})
    return set_ld_constants(m)


def pair_model_ld(editions=None, selectors=None):
    """K_V（方法B）、K_Hβ（方法C）、K_Hα/K_Fα（方法B）均由公式推出的齿轮副模型（经 rating.pair_model 选择器特化）。
    method.K_V、method.K_Hbeta、method.K_Halpha（B / C / B 为本模型的典型取值）、
    method.m_red、method.f_pb、method.root_shift 须由 selectors 显式给出，否则模型求值阻断（不设默认；v0.6 起移除内置默认）。"""
    from .rating import pair_model          # 延迟导入：rating 依赖本模块
    sel = dict(selectors or {})
    return pair_model(editions, selectors=sel, selector_sources={k: "pair_model_ld" for k in sel})
