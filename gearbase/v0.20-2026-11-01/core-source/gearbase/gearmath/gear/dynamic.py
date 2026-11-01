"""动载系数 K_V（ISO 6336-1:2019 方法B）公式库 + 模型装配变体。

替代原先从 M31 收据直接取用的证据输入 K_V。链路：
单齿刚度 c' → 啮合刚度 cγα → 诱导质量 m_red → 主共振转速 nE1 → 共振比 N → 区段判别
→ Bp/Bf/Bk（有效偏差、跑合量、单位齿宽载荷）→ K_V。

条款/式号只做引用，不复制标准原文。6.5.3/6.5.4/6.5.9（式(6)-(9)、(15)-(19)、(30)-(32)）已对照
ISO 6336-1:2019 扫描页核图（PDF 页 = 印刷页 + 8）；其余式号沿用 M31 python-gearbox@c005e4d 注释。
两处口径由选择器显式决定（无默认，见 gear/rating.py:SELECTOR_OPTIONS）：
  method.m_red ∈ {eq30, exact}：式(30) 近似（隐含 dm2/dm1 = u）/ 式(7)(8) 两轮各自折算；
  method.f_pb  ∈ {fpt, fpbT}：表2 允许以 fpt 代替 fpb / 基节公差 fpbT = fpT·cosαt。
下标 _1 = 小轮，_2 = 大轮。偏差类量单位 µm，内部规范单位仍为 mm。
"""
from __future__ import annotations

import math

from ..kernel.graph import Formula, InputSpec
from .formulas import _pair

F = Formula
R1 = "ISO 6336-1:2019"

STIFFNESS = [
    *_pair("dyn.zn_c", "zn_c_{i}", "1", "z_{i}/cos(beta)**3", f"{R1} 9.3 式(81) 刚度计算用当量齿数 z/cos³β"),
    F("dyn.q_s", "q_s", "1",
      "0.04723 + 0.15551/zn_c_1 + 0.25791/zn_c_2 - 0.00635*x_1 - 0.11654*x_1/zn_c_1"
      " - 0.00193*x_2 - 0.24188*x_2/zn_c_2 + 0.00529*x_1**2 + 0.00182*x_2**2",
      f"{R1} 9.3 式(84) 最小柔度 q'（数值以 mm·µm/N 计，量纲由 c_unit 承担）"),
    F("dyn.c_th", "c_th", "N/(mm*um)", "c_unit/q_s", f"{R1} 9.3 式(83) 理论单齿刚度 c'th = 1/q'"),
    F("dyn.C_B", "C_B", "1", "(1 + 0.5*(1.2 - hfP))*(1 - 0.02*(pi/9*rad - alpha_n)*180/(pi*rad))",
      f"{R1} 9.3 式(88)(89) 基本齿条系数 C_B（两轮同刀具，均值即本值）"),
    F("dyn.line_load", "line_load", "N/mm", "F_t*K_A*K_gamma/b", f"{R1} 6.5 单位齿宽载荷 F_t·K_A·K_γ/b"),
    F("dyn.c_s", "c_s", "N/(mm*um)",
      "c_th*0.8*C_R*C_B*cos(beta)*(E/E_St)*where(line_load < w_ref, (line_load/w_ref)**0.25, 1)",
      f"{R1} 9.3 式(82)(85)(90)-(92) 单齿刚度 c' = c'th·C_M·C_R·C_B·cosβ，C_M=0.8；"
      "同材料时 2E1E2/(E1+E2)=E；载荷 <100 N/mm 时乘 (载荷/100)^0.25"),
    F("dyn.c_gamma_alpha", "c_gamma_alpha", "N/(mm*um)", "c_s*(0.75*eps_alpha + 0.25)*where(eps_alpha < 1.2, 0.9, 1)",
      f"{R1} 9.3 式(93) 啮合刚度 cγα；εα<1.2 的直齿取下调 10%（9.3.3.1，与 python-gearbox 同口径）"),
    F("dyn.c_gamma_beta", "c_gamma_beta", "N/(mm*um)", "0.85*c_gamma_alpha", f"{R1} 9.3 式(94) cγβ（供 KHβ，K_V 不用）"),
]

RESONANCE = [
    *_pair("dyn.dm", "dm_{i}", "mm", "(da_{i} + df_{i})/2", f"{R1} 6.5.9 式(31) 平均直径 dm = (da+df)/2（PDF 45 页）"),
    F("dyn.n_E1", "n_E1", "rpm", "sqrt(c_gamma_alpha/m_red)/(2*pi*z_1)",
      f"{R1} 6.5.3 式(6) 小轮主共振转速 nE1（即 30000/(π z1)·√(cγα/m_red) 的规范单位写法；PDF 37 页）"),
    F("dyn.N_res", "N_res", "1", "n_1/n_E1", f"{R1} 6.5 共振比 N = n1/nE1"),
    F("dyn.N_S", "N_S", "1", "where(line_load < w_ref, 0.5 + 0.35*sqrt(line_load/w_ref), 0.85)",
      f"{R1} 6.5 式(11)(12) 亚临界区上界 N_S"),
    F("dyn.eps_gamma", "eps_gamma", "1", "eps_alpha + eps_beta", f"{R1} 总重合度 εγ", ("eps_gamma > 1",)),
]

# Cv1..Cv7：按总重合度 εγ 分段（ISO 6336-1:2019 6.5 系数表）
CV = [
    F("dyn.C_v1", "C_v1", "1", "0.32", f"{R1} 6.5 Cv1"),
    F("dyn.C_v2", "C_v2", "1", "where(eps_gamma <= 2, 0.34, 0.57/(eps_gamma - 0.3))", f"{R1} 6.5 Cv2"),
    F("dyn.C_v3", "C_v3", "1", "where(eps_gamma <= 2, 0.23, 0.096/(eps_gamma - 1.56))", f"{R1} 6.5 Cv3"),
    F("dyn.C_v4", "C_v4", "1", "where(eps_gamma <= 2, 0.9, (0.57 - 0.05*eps_gamma)/(eps_gamma - 1.44))", f"{R1} 6.5 Cv4"),
    F("dyn.C_v5", "C_v5", "1", "0.47", f"{R1} 6.5 Cv5"),
    F("dyn.C_v6", "C_v6", "1", "where(eps_gamma <= 2, 0.47, 0.12/(eps_gamma - 1.74))", f"{R1} 6.5 Cv6"),
    F("dyn.C_v7", "C_v7", "1",
      "where(eps_gamma <= 1.5, 0.75, where(eps_gamma <= 2.5, 0.125*sin(pi*(eps_gamma - 2)*rad) + 0.875, 1))",
      f"{R1} 6.5 Cv7"),
]

# 诱导质量（选择器 method.m_red）
M_RED_VARIANTS = {
    "eq30": [F("dyn.m_red", "m_red", "kg/mm",
               "pi/8*(dm_1/db_1)**2*dm_1**2/(1/(rho_1*(1 - q_1**4)) + 1/(rho_2*(1 - q_2**4)*u**2))",
               f"{R1} 6.5.9 式(30) 外啮合齿轮副单位齿宽诱导质量（标准称'足够精确的近似'，隐含 dm2/dm1 = u；"
               "齿坯按圆环，q = di/dm 式(32)，实心 q=0；PDF 45 页核图）")],
    "exact": [*_pair("dyn.mstar", "mstar_{i}", "kg/mm", "pi/8*rho_{i}*(1 - q_{i}**4)*dm_{i}**4/db_{i}**2",
                     f"{R1} 6.5.3 式(8) m* = J*/rb²，J* = π/32·ρ(1−q⁴)dm⁴（单位齿宽圆环，与式(30)-(32) 同一齿坯假设；PDF 37/45 页）"),
              F("dyn.m_red.exact", "m_red", "kg/mm", "mstar_1*mstar_2/(mstar_1 + mstar_2)",
                f"{R1} 6.5.3 式(7) m_red = m1*·m2*/(m1*+m2*)（两轮各自折算，不作 dm2/dm1 = u 的近似；PDF 37 页核图）")],
}

# 单轮基节偏差 fpb_i（选择器 method.f_pb；K_Hα 方法B 的 f_pb_a 也取这两个量）
F_PB_VARIANTS = {
    "fpt": _pair("dyn.f_pbT", "f_pbT_{i}", "um", "f_pt_{i}",
                 f"{R1} 表2 fpb 说明：按 ISO 1328-1:2013 公差计算时可用 fpt 代替 fpb（PDF 14 页核图）"),
    "fpbT": _pair("dyn.f_pbT.cos", "f_pbT_{i}", "um", "f_pt_{i}*cos(alpha_t)",
                  "基节公差 fpbT = fpT·cosαt（端面基节 = 端面齿距·cosαt 的几何关系；KISSsoft 公差表口径，"
                  "K01 报告 [fpbT]=10.34；TR30:2022正式版4.2.1式(1)支持且不圆整，PDF12原图已核；"
                  "ISO 21771-1:2024 4.5.5.1式(31)支持对应端面基节几何关系）"),
}

DEVIATION = [
    F("dyn.f_falpha", "f_falpha", "um", "max(f_falpha_1, f_falpha_2)",
      f"{R1} 6.5.4 式(19) 取两轮较大（通常为大轮）的齿廓形状偏差 ffα（PDF 42 页核图）"),
    F("dyn.f_pb", "f_pb", "um", "max(f_pbT_1, f_pbT_2)",
      f"{R1} 6.5.4 式(18) 取两轮较大（通常为大轮）的基节偏差 fpb（PDF 42 页核图）；"
      "不以 ffα 代替——'ffα 更大时代替'是 8.3.2 注，只用于 K_Hα（PDF 74 页）"),
    F("dyn.y_p", "y_p", "um", "min(0.075*f_pb, y_alpha_max)",
      f"{R1} 8.3 式(77)-(79) 跑合量 yp = yα（表面硬化/渗氮类钢：0.075·fpb，上限 3 µm）"),
    F("dyn.y_f", "y_f", "um", "min(0.075*f_falpha, y_alpha_max)", f"{R1} 8.3 式(77)-(79) 跑合量 yf（同上，以 ffα 代入）"),
    F("dyn.f_pb_eff", "f_pb_eff", "um", "f_pb - y_p", f"{R1} 6.5 式(18) 有效基节偏差"),
    F("dyn.f_f_eff", "f_f_eff", "um", "f_falpha - y_f", f"{R1} 6.5 式(19) 有效齿廓形状偏差"),
    F("dyn.C_a", "C_a", "um",
      "(((sigma_Hlim_1/Cay_s - 18.45)**2 + (sigma_Hlim_2/Cay_s - 18.45)**2)/36 + 1.5)*Cay_u",
      f"{R1} 6.5 表注 无齿顶修缘时 Ca 取跑合修缘量 Cay（两轮均值）"),
    F("dyn.B_p", "B_p", "1", "c_s*f_pb_eff/line_load", f"{R1} 6.5 式(15) Bp"),
    F("dyn.B_f", "B_f", "1", "c_s*f_f_eff/line_load", f"{R1} 6.5 式(16) Bf"),
    F("dyn.B_k", "B_k", "1", "where(Q_grade >= 6, 1, abs(1 - c_s*min(C_a + C_f_2, C_a + C_f_1)/line_load))",
      f"{R1} 6.5.4 式(17) Bk = |1 − c'·min(Ca1+Cf2, Ca2+Cf1)/(KA·Kγ·Ft/b)|；无规定齿廓修形时 Ca 以跑合量 Cay 代入"
      "（两轮同值）；脚注4：式(17) 只用于 ISO 1328-1:2013 精度等级 1–5，等级 6–11 取 Bk=1.0（PDF 41/42 页核图）"),
]

KV = [
    F("dyn.K_V_sub", "K_V_sub", "1", "N_res*(C_v1*B_p + C_v2*B_f + C_v3*B_k) + 1", f"{R1} 6.5 亚临界区 K_V"),
    F("dyn.K_V_res", "K_V_res", "1", "C_v1*B_p + C_v2*B_f + C_v4*B_k + 1", f"{R1} 6.5 主共振区 K_V"),
    F("dyn.K_V_sup", "K_V_sup", "1", "C_v5*B_p + C_v6*B_f + C_v7", f"{R1} 6.5 超临界区 K_V"),
    F("dyn.K_V_int", "K_V_int", "1", "K_V_sup + (K_V_res - K_V_sup)/0.35*(1.5 - N_res)", f"{R1} 6.5 中间区线性插值"),
    F("dyn.K_V_raw", "K_V_raw", "1",
      "where(N_res <= N_S, K_V_sub, where(N_res <= 1.15, K_V_res, where(N_res >= 1.5, K_V_sup, K_V_int)))",
      f"{R1} 6.5 按区段取值"),
    F("dyn.K_V", "K_V", "1",
      "where(N_res > N_S and N_res < 1.5, max(K_V_raw, 1), min(max(K_V_raw, 1), 2))",
      f"{R1} 6.2/6.3 K_V 不小于 1；共振区外不大于 2"),
    F("dyn.KV_regime", "KV_regime", "1",
      "where(N_res <= N_S, 1, where(N_res <= 1.15, 2, where(N_res < 1.5, 3, 4)))",
      f"{R1} 6.5 区段编码：1 亚临界 / 2 主共振 / 3 中间 / 4 超临界"),
]

# 与口径选择无关的方法B 公式（m_red、f_pbT_i 另见 M_RED_VARIANTS / F_PB_VARIANTS）
DYNAMIC_B = STIFFNESS + RESONANCE + CV + DEVIATION + KV


def dynamic_b(m_red, f_pb):
    """按显式口径取方法B 全部公式（无默认值）：m_red ∈ M_RED_VARIANTS，f_pb ∈ F_PB_VARIANTS。"""
    if m_red not in M_RED_VARIANTS or f_pb not in F_PB_VARIANTS:
        raise ValueError(f"未知口径 m_red={m_red!r}、f_pb={f_pb!r}；可选 {sorted(M_RED_VARIANTS)} / {sorted(F_PB_VARIANTS)}")
    return DYNAMIC_B + M_RED_VARIANTS[m_red] + F_PB_VARIANTS[f_pb]
REGIMES = {1: "subcritical", 2: "main_resonance", 3: "intermediate", 4: "supercritical"}

# 方法B 中的单位约定与标准常数（标准常数，不是用户可调参数）
CONSTANTS = [
    ("c_unit", 1.0, "N/(mm*um)", f"{R1} 9.3 q' 多项式的单位约定 mm·µm/N"),
    ("E_St", 206000.0, "MPa", f"{R1} 9.3 式(90) 参考钢弹性模量"),
    ("w_ref", 100.0, "N/mm", f"{R1} 9.3 式(92)/6.5 式(11)(12) 参考单位齿宽载荷"),
    ("y_alpha_max", 3.0, "um", f"{R1} 8.3 表面硬化/渗氮类钢跑合量上限"),
    ("Cay_s", 97.0, "MPa", f"{R1} 6.5 表注 Cay 经验式中 σHlim 的除数"),
    ("Cay_u", 1.0, "um", f"{R1} 6.5 表注 Cay 经验式结果单位"),
]

# 跑合量式(77)-(79)按材料组分支；本模块只实现"表面硬化/渗氮类钢"组（M31 C001 为氮碳共渗钢）
SURFACE_HARDENED = {"CASE_HARDENED_STEEL", "FLAME_OR_INDUCTION_HARDENED_STEEL", "NITRIDED_STEEL",
                    "THROUGH_HARDENED_NITRIDED_STEEL", "NITROCARBURIZED_STEEL"}


_S = InputSpec
# 方法B 新增输入的声明（期望单位、含义、取值域）；与 gear/inputs.py 同一规则：未声明的自由变量装配时报错
DYNAMIC_INPUTS = [
    _S("K_gamma", "1", "行星/多路功率分流的啮合载荷系数 Kγ", ("K_gamma >= 1",)),
    *[_S(f"rho_{i}", "kg/mm^3", f"材料密度（{w}）", (f"rho_{i} > 0",)) for i, w in (("1", "小轮"), ("2", "大轮"))],
    *[_S(f"q_{i}", "1", f"轮缘/腹板减重比（{w}），实心齿坯为 0", (f"q_{i} >= 0", f"q_{i} < 1")) for i, w in (("1", "小轮"), ("2", "大轮"))],
    _S("C_R", "1", "齿坯结构系数 C_R", ("C_R > 0", "C_R <= 1")),
    _S("Q_grade", "1", "ISO 1328-1 精度等级（取小轮）", ("Q_grade >= 1", "Q_grade <= 11")),
    *[_S(f"f_pt_{i}", "um", f"单个齿距公差 fpT（{w}）", (f"f_pt_{i} > 0",)) for i, w in (("1", "小轮"), ("2", "大轮"))],
    *[_S(f"f_falpha_{i}", "um", f"齿廓形状公差 ffαT（{w}）", (f"f_falpha_{i} > 0",)) for i, w in (("1", "小轮"), ("2", "大轮"))],
    *[_S(f"C_f_{i}", "um", f"齿根修缘量 Cf（{w}），式(17)；无齿根修缘为 0", (f"C_f_{i} >= 0",)) for i, w in (("1", "小轮"), ("2", "大轮"))],
    *[_S(name, unit, f"标准常数：{ref}") for name, _, unit, ref in CONSTANTS],
]


def pair_model_kvb(editions=None):
    """兼容包装：等价于 rating.pair_model(editions, selectors={"method.K_V": "B"})。K_V 由方法B 公式推出。
    统一入口见 gear/rating.py:pair_model；方法B 另需 method.m_red、method.f_pb 等选择器，未选时模型求值阻断。"""
    from .rating import pair_model
    return pair_model(editions, selectors={"method.K_V": "B"},
                      selector_sources={"method.K_V": "pair_model_kvb 兼容包装"})


def _round_iso1328(v):
    """ISO 1328-1:2013 5.2.3 公差圆整：>10 µm 取整，5~10 µm 取 0.5，<5 µm 取 0.1（与 python-gearbox 相同用 round）。"""
    if v > 10:
        return float(round(v))
    if v >= 5:
        return round(v * 2) / 2
    return round(v, 1)


def iso1328_tolerances(m_n, d, grade):
    """ISO 1328-1:2013 式(5)(8)：单个齿距公差 fpT、齿廓形状公差 ffαT（µm，已圆整）。

    圆整是阶跃函数，不进入可微公式图，故作为证据输入的预处理；对 b、n_1 的导数恒为 0。
    """
    if not (0.5 <= m_n <= 70 and 5 <= d <= 15000):
        raise ValueError(f"ISO 1328-1:2013 适用范围外：m_n={m_n}, d={d}")
    step = math.sqrt(2) ** (grade - 5)
    return _round_iso1328((0.001 * d + 0.4 * m_n + 5) * step), _round_iso1328((0.55 * m_n + 5) * step)


def set_dynamic_inputs(m, case, stage_index, case_rel):
    """从 M31 案例 engineering 段写入方法B 所需输入（每个都带来源）。"""
    st = case["stages"][stage_index]
    eng = case["engineering"]
    op, mat = eng["operating"], eng["material"]
    if op["dynamic_factor_method"] != "METHOD_B" or op["measured_dynamic_factor"] is not None:
        raise NotImplementedError(f"案例要求的 K_V 方法为 {op['dynamic_factor_method']}，本模块只实现方法B")
    if mat["material_type"] not in SURFACE_HARDENED:
        raise NotImplementedError(f"跑合量式只实现表面硬化/渗氮类钢，收到 {mat['material_type']}")
    sup = eng["stages"][st["id"]]
    base = f"M31 {case_rel if isinstance(case_rel, str) else '案例'} engineering"
    m.set("K_gamma", op["mesh_load_factor"], "1", "user", f"{base}.operating.mesh_load_factor")
    for i in (1, 2):
        m.set(f"rho_{i}", mat["density_kg_per_mm3"], "kg/mm^3", "evidence", f"{base}.material.density_kg_per_mm3")
        m.set(f"q_{i}", 0.0, "1", "assumption",
              "实心齿坯（legacy/m31/L4/gears/benchmark/rating_adapter.py 传 rim_thickness=None）")
    m.set("C_R", 1.0, "1", "assumption", "实心齿坯 C_R=1（同上：rim_thickness=None，web_thickness=b）")
    if op.get("flank_modification") != "NONE":
        raise NotImplementedError(f"齿廓修形 {op.get('flank_modification')} 的 Ca/Cf 映射未实现")
    for i in (1, 2):
        m.set(f"C_f_{i}", 0.0, "um", "user", f"{base}.operating.flank_modification = NONE（无齿根修缘，式(17) Cf=0）")
    m.set("Q_grade", sup["pinion"]["quality_grade"], "1", "user", f"{base}.stages.{st['id']}.pinion.quality_grade")
    if "helix_angle_deg" in st:
        helix_deg = st["helix_angle_deg"]
    elif st.get("kind") == "spur":
        helix_deg = 0.0                      # 直齿级：螺旋角按定义为 0（kind 为显式案例数据，不是缺省）
    else:
        raise ValueError(f"级 {st.get('id')}（kind={st.get('kind')}）缺 helix_angle_deg：非直齿级须显式给出螺旋角，不作 0 缺省")
    beta = math.radians(helix_deg)
    for i, (role, z) in enumerate((("pinion", st["driver_teeth"]), ("wheel", st["driven_teeth"])), start=1):
        grade = sup[role]["quality_grade"]
        d = z * st["module_mm"] / math.cos(beta)
        fpt, ffa = iso1328_tolerances(st["module_mm"], d, grade)
        src = (f"ISO 1328-1:2013 式(5)/(8)+5.2.3 圆整，精度等级 {grade}（{base}.stages.{st['id']}.{role}.quality_grade），"
               "gear/dynamic.py:iso1328_tolerances 计算，口径同 python-gearbox GearTolerances")
        m.set(f"f_pt_{i}", fpt, "um", "evidence", src)
        m.set(f"f_falpha_{i}", ffa, "um", "evidence", src)
    for name, v, unit, ref in CONSTANTS:
        m.set(name, v, unit, "standard_constant", ref)
    return m


def stage_model_kvb(case="golden/C001/derived-candidate.json", receipt="golden/C001/gear-rating.json", stage=0):
    """兼容包装：等价于 m31_case.stage_model(..., selectors={"method.K_V": "B"})（K_V 不再读收据的 dynamic_factor）。"""
    from .m31_case import stage_model
    return stage_model(case, receipt, stage, selectors={"method.K_V": "B"})
