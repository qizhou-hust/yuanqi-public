"""Reference-stress lubricant, velocity and flank roughness factors.

ISO 6336-2:2019 equations have been checked against the supplied page images
(PDF 33..44, printed 25..36; source hash in SOURCE_SHA256).  Equation-image
verification and acceptance of the entire rating model remain separate.

The explicit reference material input avoids inferring hardness from the
allowable stress number.  The supported subset is mineral oil, 10..500
mm²/s at 40°C with the VI=95 viscosity basis, 1..100 m/s working pitch speed,
external gears, both lives at least their explicitly selected reference life.
"""
from __future__ import annotations

from dataclasses import replace

from ..kernel.graph import Formula, InputSpec, Model
from ..kernel.units import to_canonical
from .inputs import input_specs

F, S = Formula, InputSpec
REF = "ISO 6336-2:2019 12.3.2"
SOURCE_SHA256 = "5e7a4b83c2d91292f6ddce324ea2fee16699b1c385d80b76606fec6b459de5b0"
SOURCE_NOTE = ("ISO 原图已核，源SHA256=" + SOURCE_SHA256 + "；"
               "矿物油ν40/VI95 reference stress 子集，无有限寿命插值")
SOURCE_STATUS = {
    "iso_equation_images": "verified",
    "source_sha256": SOURCE_SHA256,
    "source_path": "standards/core/ISO 6336-2-2019.pdf",
    "pdf_pages": [19, 20, 21, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44],
    "equations": [42, 43, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56],
    "status": "verified_equations_supported_subset",
    "scope": "mineral oil, nu40/VI95, explicit material reference cycle; finite-life interpolation not implemented",
    "case_input_assumptions": ["K01 VI95 approximation", "K01 Eh no-pitting reference life"],
}

SURFACE_CONSTANTS = [
    ("sf_stress_unit", 1.0, "MPa", "单位尺度 1 MPa"),
    ("sf_length_unit", 1.0, "mm", "单位尺度 1 mm"),
    ("sf_roughness_unit", 1.0, "um", "单位尺度 1 µm"),
    ("sf_velocity_unit", 1.0, "m/s", "单位尺度 1 m/s"),
    ("sf_viscosity_unit", 1.0, "mm^2/s", "单位尺度 1 mm²/s"),
]

_REFERENCE_DOMAIN = (
    "surface_oil_mineral >= 1", "surface_oil_mineral <= 1",
    "surface_nu40_vi95 >= 1", "surface_nu40_vi95 <= 1",
    "N_L_1 >= N_Href_1", "N_L_2 >= N_Href_2",
    "nu_40 >= 10*sf_viscosity_unit", "nu_40 <= 500*sf_viscosity_unit",
    "surface_v_w >= sf_velocity_unit", "surface_v_w <= 100*sf_velocity_unit",
)

SURFACE_FACTORS = [
    F("surface.C_ZL", "C_ZL", "1",
      "where(sigma_Hlim_surface < 850*sf_stress_unit, 0.83, "
      "where(sigma_Hlim_surface > 1200*sf_stress_unit, 0.91, "
      "sigma_Hlim_surface/(4375*sf_stress_unit) + 0.6357))",
      REF + ".1.3 式(43)–(45) 润滑系数辅助常数（PDF34/印刷26）", note=SOURCE_NOTE),
    F("surface.C_ZV", "C_ZV", "1", "C_ZL + 0.02",
      REF + ".2.3 式(48) 速度系数辅助常数（PDF35/印刷27）", note=SOURCE_NOTE),
    F("surface.C_ZR", "C_ZR", "1",
      "where(sigma_Hlim_surface < 850*sf_stress_unit, 0.15, "
      "where(sigma_Hlim_surface > 1200*sf_stress_unit, 0.08, "
      "0.32 - 0.0002*sigma_Hlim_surface/sf_stress_unit))",
      REF + ".3.3 式(54)–(56) 粗糙度指数（PDF37/印刷29）", note=SOURCE_NOTE),
    F("surface.rho_red", "rho_red", "mm",
      "0.5*db_1*db_2*tan(alpha_wt)/(db_1 + db_2)",
      REF + ".3.1 式(51)(52) 节点相对曲率半径（外啮合，PDF37/印刷29）",
      ("db_1 > 0", "db_2 > 0", "alpha_wt > 0*rad", "alpha_wt < pi/2*rad"),
      note=SOURCE_NOTE),
    F("surface.Rz_H_mean", "Rz_H_mean", "um", "(Rz_H_1 + Rz_H_2)/2",
      REF + ".3.1 式(49) 两轮齿面粗糙度均值（PDF36/印刷28）", note=SOURCE_NOTE),
    F("surface.Rz_10", "Rz_10", "um",
      "Rz_H_mean*(10*sf_length_unit/rho_red)**(1/3)",
      REF + ".3.1 式(50) 曲率归一化粗糙度（PDF37/印刷29）", note=SOURCE_NOTE),
    F("surface.v_w", "surface_v_w", "m/s", "v*cos(alpha_t)/cos(alpha_wt)",
      REF + ".2 式(47) 工作节线速度（由基圆不变量换算；PDF35/印刷27）",
      ("alpha_t > 0*rad", "alpha_t < pi/2*rad", "alpha_wt > 0*rad", "alpha_wt < pi/2*rad"),
      note=SOURCE_NOTE),
    F("surface.Z_L", "Z_L", "1",
      "C_ZL + 4*(1 - C_ZL)/(1.2 + 134*sf_viscosity_unit/nu_40)**2",
      REF + ".1.3 式(42) 矿物油润滑剂系数（PDF34/印刷26）", _REFERENCE_DOMAIN, note=SOURCE_NOTE),
    F("surface.Z_V", "Z_V", "1",
      "C_ZV + 2*(1 - C_ZV)/sqrt(0.8 + 32*sf_velocity_unit/surface_v_ZV)",
      REF + ".2.3 式(47) 速度系数（PDF35/印刷27）；式中速度口径由 method.Z_V_velocity 显式选择",
      _REFERENCE_DOMAIN, note=SOURCE_NOTE),
    F("surface.Z_R", "Z_R", "1",
      "exp(C_ZR*log(3*sf_roughness_unit/Rz_10))",
      REF + ".3.3 式(53) 齿面粗糙度系数（PDF37/印刷29）", _REFERENCE_DOMAIN, note=SOURCE_NOTE),
]

# 式(47)的速度口径：ISO 6336-2:2019 原文为工作节线速度 vw；ISO/TR 6336-30:2022 附录A A.9.2
# 印作 32/v，并以分度圆线速度 v=2,664 20 m/s 得 ZV=0,969 11（若用 vw=2,670 35 则为 0,969 16）。
# 两种口径都有原文依据，故不设默认：缺选择器即阻断，契约须写明取值及页码出处。
ZV_VELOCITY_OPTIONS = {
    "v_w": "ISO 6336-2:2019 12.3.2.2.3 式(47)：工作节线速度 vw（PDF35/印刷27 原图已核）",
    "v_ref": "ISO/TR 6336-30:2022 附录A A.9.2 式(47) 印 32/v，用分度圆线速度 v（PDF59/印刷53；v 见 PDF52/印刷46，原图已核）",
}
ZV_VELOCITY_VARIANTS = {
    "v_w": F("surface.v_ZV.v_w", "surface_v_ZV", "m/s", "surface_v_w",
             REF + ".2.3 式(47) 速度口径 vw（PDF35/印刷27）", note=SOURCE_NOTE),
    "v_ref": F("surface.v_ZV.v_ref", "surface_v_ZV", "m/s", "v",
               REF + ".2.3 式(47) 速度取分度圆v，依据 ISO/TR 6336-30:2022 附录A A.9.2（PDF59/印刷53）",
               note="TR30原图已核：ZV=0,969 11 与 v=2,664 20 m/s（PDF52/印刷46）相符；适用域仍按 vw 检查"),
}
ZV_VELOCITY_AUDIT = {
    "iso_equation_images": "verified",
    "sources": {"v_w": "ISO 6336-2:2019 PDF35/印刷27 式(47)，源SHA256=" + SOURCE_SHA256,
                "v_ref": "ISO/TR 6336-30:2022 PDF59/印刷53 A.9.2 式(47) 与 PDF52/印刷46 v，"
                         "源SHA256=12834eabe980fd66da9a6e41881339ba0ddda0ff8222af6eec3bfc3401e7b2db"},
    "status": "explicit_selector_no_default",
}

SURFACE_INPUTS = [
    S("sigma_Hlim_surface", "MPa", "显式指定参考材料的接触疲劳极限，不从硬度或 min 推断",
      ("sigma_Hlim_surface > 0",)),
    S("nu_40", "mm^2/s", "矿物油在 40°C 的运动黏度", ("nu_40 > 0",)),
    S("surface_v_ZV", "m/s", "式(47)所用速度；正常由 method.Z_V_velocity 所选公式给出，未编译该公式时须显式输入",
      ("surface_v_ZV > 0",)),
    S("Rz_H_1", "um", "小轮跑合后/制造齿面 Rz；不得隐式由 Ra 换算", ("Rz_H_1 > 0",)),
    S("Rz_H_2", "um", "大轮跑合后/制造齿面 Rz；不得隐式由 Ra 换算", ("Rz_H_2 > 0",)),
    S("surface_oil_mineral", "1", "矿物油适用性明确声明（1=矿物油，其他未实现）",
      ("surface_oil_mineral >= 1", "surface_oil_mineral <= 1")),
    S("surface_nu40_vi95", "1", "ν40式(42)的VI95基准声明（1=确认/显式接受该近似）",
      ("surface_nu40_vi95 >= 1", "surface_nu40_vi95 <= 1")),
    S("N_L_1", "1", "小轮载荷循环次数", ("N_L_1 > 0",)),
    S("N_L_2", "1", "大轮载荷循环次数", ("N_L_2 > 0",)),
    S("N_Href_1", "1", "小轮所选材料/点蚀曲线的reference循环数，须显式声明", ("N_Href_1 > 0",)),
    S("N_Href_2", "1", "大轮所选材料/点蚀曲线的reference循环数，须显式声明", ("N_Href_2 > 0",)),
    *[S(name, unit, description,
        (f"{name} >= {to_canonical(value, unit)!r}",
         f"{name} <= {to_canonical(value, unit)!r}"))
      for name, value, unit, description in SURFACE_CONSTANTS],
]

# Endpoint and per-gear exports for the TR30 4.2.4 decomposition.  The reference
# endpoint has the same oil/velocity validity checks but no actual-life gate;
# actual life is represented by an explicitly supplied/derived log weight.
# 单一真源：端点公式由 SURFACE_FACTORS 经 dataclasses.replace 派生，只改 id、输出名（Z_*→Z_*_ref）与去掉寿命门；
# 表达式字符串不另写一份，改基础式即同步（tests 钉住 expr 逐字相同）。
_REF_NAMES = {"Z_L": "Z_L_ref", "Z_V": "Z_V_ref", "Z_R": "Z_R_ref"}
SURFACE_REFERENCE_ENDPOINTS = [
    replace(f, id=f.id + ".endpoint", output=_REF_NAMES.get(f.output, f.output),
            domain=tuple(d for d in f.domain if not d.startswith("N_L_")))
    for f in SURFACE_FACTORS
]
SURFACE_PER_GEAR_FACTORS = []
for _i in (1, 2):
    for _q in ("Z_L", "Z_V", "Z_R"):
        SURFACE_PER_GEAR_FACTORS.append(F(
            f"surface.{_q}.life.{_i}", f"{_q}_{_i}", "1",
            f"exp(contact_reference_weight_{_i}*log({_q}_ref))",
            "ISO/TR 6336-30:2022 4.2.4 reference/static因子对数插值；static端式57均1",
            (f"contact_reference_weight_{_i} >= 0", f"contact_reference_weight_{_i} <= 1"),
            note="TR30逐因子分解接口；权重必须由材料分支/循环数派生，不能从目标结果反推"))
    SURFACE_PER_GEAR_FACTORS.append(F(
        f"surface.Z_W.life.{_i}", f"Z_W_{_i}", "1",
        f"exp((1 - contact_reference_weight_{_i})*log(Z_W_static_{_i}) + contact_reference_weight_{_i}*log(Z_W_ref_{_i}))",
        "ISO/TR 6336-30:2022 4.2.4 工作硬化reference/static因子对数插值",
        (f"contact_reference_weight_{_i} >= 0", f"contact_reference_weight_{_i} <= 1"),
        note="静态和reference端必须按ISO6336-2:2019第13条对应材料方法独立给出"))
    SURFACE_PER_GEAR_FACTORS.append(F(
        f"surface.Z_X.life.{_i}", f"Z_X_{_i}", "1", "1",
        "ISO 6336-2:2019 14 尺寸系数（PDF44/印刷36）", note="ISO 原图已核"))

PER_GEAR_SURFACE_INPUTS = [
    *[S(q, "1", "独立计算的reference端系数", (f"{q} > 0",)) for q in _REF_NAMES.values()],
    *[S(f"contact_reference_weight_{i}", "1", "由材料分支与循环数派生的reference权重",
        (f"contact_reference_weight_{i} >= 0", f"contact_reference_weight_{i} <= 1")) for i in (1, 2)],
    *[S(f"Z_W_{end}_{i}", "1", f"工作硬化{end}端点，需对应材料公式来源",
        (f"Z_W_{end}_{i} > 0",)) for i in (1, 2) for end in ("static", "ref")],
]

# Independent whole-stress check for ISO 6336-2:2019 5.4.4.3b, Eq(11)/(8).
# This preserves the published 0.3705 coefficient instead of silently replacing
# it with exact log interpolation.  It is a separate check from the TR30
# permitted per-factor decomposition above.
CONTACT_STRESS_NO_PITTING = []
for _i in (1, 2):
    CONTACT_STRESS_NO_PITTING += [
        F(f"surface.H_life_exp.{_i}", f"contact_life_exponent_{_i}", "1",
          f"0.3705*log(sigma_HG_static_{_i}/sigma_HG_ref_{_i})/log(10)",
          "ISO 6336-2:2019 5.4.4.3 式(8)（PDF20/印刷12）", note="ISO 原图已核；保留发布系数0.3705"),
        F(f"surface.sigma_HG_life.{_i}", f"sigma_HG_life_{_i}", "MPa",
          f"where(N_L_{_i} <= 1e5, sigma_HG_static_{_i}, "
          f"where(N_L_{_i} <= 5e7, sigma_HG_ref_{_i}*exp(contact_life_exponent_{_i}*log(5e7/N_L_{_i})), "
          f"sigma_HG_ref_{_i}*Z_NT_long_{_i}))",
          "ISO 6336-2:2019 5.4.4.3b 式(11)/(8)、表5禁点蚀钢曲线（PDF20–21/31，印刷12–13/23）",
          ("contact_no_pitting_steel >= 1", "contact_no_pitting_steel <= 1"),
          note="ISO 原图已核；仅St/V/Eh/IF禁点蚀材料，1e5–5e7有限寿命；long端需独立寿命系数"),
    ]
CONTACT_STRESS_INPUTS = [
    S("contact_no_pitting_steel", "1", "明确选择St/V/Eh/IF禁点蚀材料曲线",
      ("contact_no_pitting_steel >= 1", "contact_no_pitting_steel <= 1")),
    *[S(f"sigma_HG_{end}_{i}", "MPa", f"独立公式计算的{end}接触强度端点，不是对拍目标",
        (f"sigma_HG_{end}_{i} > 0",)) for i in (1, 2) for end in ("ref", "static")],
    *[S(f"Z_NT_long_{i}", "1", "由独立寿命材料曲线计算的long-life系数",
        (f"Z_NT_long_{i} > 0", f"Z_NT_long_{i} <= 1")) for i in (1, 2)],
]

# Contact auxiliaries deliberately kept separate from ZL/ZV/ZR.  A common ZW
# is valid for the neutral branch only; non-neutral methods below return a
# factor for each gear so that a wheel benefit cannot inflate pinion strength.
_AUX_MAT_DOMAIN = ("aux_both_case_hardened >= 1", "aux_both_case_hardened <= 1")
CONTACT_AUX_FACTORS = [
    F("surface.Z_W.neutral", "Z_W", "1", "1",
      "ISO 6336-2:2019 13.1/13.3 工作硬化增强只针对软轮；两轮均渗碳钢排除该增强（PDF38–43/印刷30–35）",
      _AUX_MAT_DOMAIN,
      note="ISO 原图已核；由13.1适用范围排除增强，不是将式(59)套用于两轮均表面硬化；材料须显式声明"),
    F("surface.Z_X", "Z_X", "1", "1",
      "ISO 6336-2:2019 14 尺寸系数明确取1（PDF44/印刷36）", note="ISO 原图已核；分册规定的常数，不是猜默认值"),
]
CONTACT_AUX_INPUTS = [
    S("aux_both_case_hardened", "1", "两轮均为渗碳硬化钢；不属于13.3软轮工作硬化增强组合",
      _AUX_MAT_DOMAIN),
]


def set_k01_contact_aux_inputs(model, case):
    """Declare the neutral work-hardening branch from input material text."""
    material = case.get("report_text", {}).get("material", {})
    if case.get("id") != "K01-spur" or "case-hardened" not in material.get("text", ""):
        raise NotImplementedError("contact_aux中性映射仅支持K01两轮渗碳钢；其他材料须明确选择分轮方法")
    if "aux_both_case_hardened" in model.specs:
        model.set("aux_both_case_hardened", 1, "1", "evidence",
                  f"K01两轮共同材料；报告行{material['line']} {material['text']}")
    return model


_WH_COMMON_DOMAIN = ("N_L_1 >= N_Href_1", "N_L_2 >= N_Href_2")


def _material_domain(pinion, wheel):
    return (f"wh_mat_1 >= {pinion}", f"wh_mat_1 <= {pinion}",
            f"wh_mat_2 >= {wheel}", f"wh_mat_2 <= {wheel}", *_WH_COMMON_DOMAIN)


_WH_SCOPE = {
    "surface_pinion_through_wheel_reference": _material_domain(1, 2),
    "through_hardened_pair_reference": _material_domain(2, 2),
    "surface_pinion_ductile_wheel_reference": _material_domain(1, 3),
}

_WH_SHARED = [f for f in SURFACE_FACTORS if f.output in ("rho_red", "surface_v_w")]
_WH_SURFACE_THROUGH = [
    *_WH_SHARED,
    F("surface.wh.RzH.raw", "wh_RzH_raw", "um",
      "Rz_pre_1*(10*sf_length_unit/rho_red)**0.33*(Rz_pre_1/Rz_pre_2)**0.66/"
      "((nu_40/sf_viscosity_unit)*(surface_v_w/sf_velocity_unit)/1500)**0.33",
      "ISO 6336-2:2019 13.3.1.1 式(58) 跑合前等效粗糙度（PDF39/印刷31）", note="ISO 原图已核"),
    F("surface.wh.RzH", "wh_RzH", "um",
      "min(16*sf_roughness_unit, max(3*sf_roughness_unit, wh_RzH_raw))",
      "ISO 6336-2:2019 13.3.1.1 式(58)下限幅3–16µm（PDF39/印刷31）", note="ISO 原图已核"),
    F("surface.wh.ZW.raw", "wh_ZW_raw", "1",
      "(1.2 - (min(470, max(130, HB_2)) - 130)/1700)*exp(0.15*log(3*sf_roughness_unit/wh_RzH))",
      "ISO 6336-2:2019 13.3.1.3 式(59)–(61) 软钢轮工作硬化（PDF40–41/印刷32–33）", note="ISO 原图已核"),
    F("surface.wh.ZW.wheel", "Z_W_2", "1", "max(1, wh_ZW_raw)",
      "ISO 6336-2:2019 13.3.1.1 计算值小于1时取1（PDF39/印刷31）",
      _WH_SCOPE["surface_pinion_through_wheel_reference"], note="ISO 原图已核；reference/long life，有限寿命未实现"),
]

WORK_HARDENING_VARIANTS = {
    "surface_pinion_through_wheel_reference": _WH_SURFACE_THROUGH,
    "through_hardened_pair_reference": [
        F("surface.wh.hardness_ratio", "wh_HB_ratio", "1", "HB_1/HB_2",
          "ISO 6336-2:2019 13.3.2.3 硬度比（PDF41/印刷33）", note="ISO 原图已核"),
        F("surface.wh.A", "wh_A", "1",
          "where(wh_HB_ratio < 1.2, 0, where(wh_HB_ratio > 1.7, 0.00698, 0.00898*wh_HB_ratio - 0.00829))",
          "ISO 6336-2:2019 13.3.2.3 式(66)–(68)（PDF41–42/印刷33–34）", note="ISO 原图已核"),
        F("surface.wh.ZW.through", "Z_W_2", "1", "max(1, 1 + wh_A*(min(u, 20) - 1))",
          "ISO 6336-2:2019 13.3.2.3 式(65)(67)(68)，u上限20（PDF41–42/印刷33–34）",
          _WH_SCOPE["through_hardened_pair_reference"], note="ISO 原图已核；只增强大轮，有限寿命未实现"),
    ],
    "surface_pinion_ductile_wheel_reference": [
        F("surface.wh.ZW.ductile", "Z_W_2", "1",
          "where(HB_2 < 162, 1.2, where(HB_2 > 344, 1, 1.2 - (1.87*HB_2 - 303.6)/1700))",
          "ISO 6336-2:2019 13.3.3.3 式(69)–(71)（PDF43/印刷35）",
          _WH_SCOPE["surface_pinion_ductile_wheel_reference"], note="ISO 原图已核；只增强大轮，有限寿命未实现"),
    ],
}
for _key, _rows in WORK_HARDENING_VARIANTS.items():
    _rows.append(F("surface.wh.ZW.pinion." + _key, "Z_W_1", "1", "1",
                   "ISO 6336-2:2019 13.1/13.3 工作硬化只增强软大轮，不增强小轮（PDF38–43）",
                   _WH_SCOPE[_key], note="ISO 原图已核；明确不把大轮系数复制给小轮"))

WORK_HARDENING_INPUTS = [
    S("wh_mat_1", "1", "小轮材料声明：1表面硬化钢，2调质钢，3球墨铸铁", ("wh_mat_1 >= 1", "wh_mat_1 <= 3")),
    S("wh_mat_2", "1", "大轮材料声明：1表面硬化钢，2调质钢，3球墨铸铁", ("wh_mat_2 >= 1", "wh_mat_2 <= 3")),
    S("HB_1", "1", "小轮Brinell硬度，不从其他硬度制静默换算", ("HB_1 > 0",)),
    S("HB_2", "1", "大轮Brinell硬度，不从其他硬度制静默换算", ("HB_2 > 0",)),
    S("Rz_pre_1", "um", "小轮跑合前齿面Rz，式58专用", ("Rz_pre_1 > 0",)),
    S("Rz_pre_2", "um", "大轮跑合前齿面Rz，式58专用", ("Rz_pre_2 > 0",)),
    S("u", "1", "外啮合齿数比", ("u >= 1",)),
]

_UPSTREAM = [
    S("db_1", "mm", "小轮基圆直径", ("db_1 > 0",)),
    S("db_2", "mm", "大轮基圆直径", ("db_2 > 0",)),
    S("alpha_wt", "rad", "工作端面压力角", ("alpha_wt > 0", "alpha_wt < pi/2")),
    S("alpha_t", "rad", "分度圆端面压力角", ("alpha_t > 0", "alpha_t < pi/2")),
    S("v", "m/s", "分度圆线速度", ("v > 0",)),
]


def set_surface_constants(model):
    """Set unit constants only if selected formulas actually require them."""
    for name, value, unit, source in SURFACE_CONSTANTS:
        if name in model.specs:
            model.set(name, value, unit, "standard_constant", source)
    return model


def standalone_model(z_v_velocity=None):
    """Formula-level model; upstream geometry remains explicit evidence inputs.

    z_v_velocity 必须显式取 ZV_VELOCITY_OPTIONS 之一；缺省时模型仍可设输入，但求值阻断
    （blocked_missing_selectors），不替调用方选择 vw 或 v。"""
    from ..kernel.expr import FormulaError
    if z_v_velocity is not None and z_v_velocity not in ZV_VELOCITY_VARIANTS:
        raise FormulaError(f"未实现的ZV速度口径 {z_v_velocity!r}；可选：{sorted(ZV_VELOCITY_OPTIONS)}")
    # 缺选择器时仅为装配占位（求值阻断），不是默认口径
    fs = SURFACE_FACTORS + [ZV_VELOCITY_VARIANTS[z_v_velocity or "v_w"]]
    model = Model(fs, inputs=input_specs(fs, SURFACE_INPUTS + _UPSTREAM),
                  editions={"ISO 6336-2": "2019"})
    if z_v_velocity is None:
        model.unresolved = [{"name": "method.Z_V_velocity", "code": "missing_selector",
                             "message": f"未选择ZV速度口径；可选：{ZV_VELOCITY_OPTIONS}"}]
    else:
        model.selectors = {"method.Z_V_velocity": z_v_velocity}
    return set_surface_constants(model)


def work_hardening_model(method):
    """Separate per-gear factors; method has no default or inferred material."""
    from ..kernel.expr import FormulaError
    if method not in WORK_HARDENING_VARIANTS:
        raise FormulaError(f"未实现的工作硬化方法 {method!r}；可选：{sorted(WORK_HARDENING_VARIANTS)}")
    fs = WORK_HARDENING_VARIANTS[method]
    table = SURFACE_INPUTS + WORK_HARDENING_INPUTS + _UPSTREAM
    m = Model(fs, inputs=input_specs(fs, table), editions={"ISO 6336-2": "2019"})
    m.selectors = {"method.Z_W": method}
    return set_surface_constants(m)


def contact_stress_life_model(method):
    """Published whole-stress finite-life equation, not a guessed material."""
    from ..kernel.expr import FormulaError
    if method != "no_pitting_steel":
        raise FormulaError("整体接触强度有限寿命仅实现显式no_pitting_steel方法")
    fs = CONTACT_STRESS_NO_PITTING
    m = Model(fs, inputs=input_specs(fs, CONTACT_STRESS_INPUTS + SURFACE_INPUTS),
              editions={"ISO 6336-2": "2019"})
    m.selectors = {"method.contact_stress_life": method}
    return m


def set_k01_surface_inputs(model, case):
    """Map existing K01 input evidence; never read reference factor outputs.

    This helper does not set upstream geometry.  The pair model derives it;
    formula-level callers must provide it explicitly.  Both K01 materials
    are equal, so selecting the reference material is unambiguous here.
    """
    if case.get("id") != "K01-spur":
        raise NotImplementedError("表面系数案例映射仅支持 K01-spur")
    c, report, text = case["com"], case["report"], case["report_text"]
    if "mineral-oil" not in text["lubrication"]["text"]:
        raise NotImplementedError("该路径仅支持明确声明的矿物油")
    s1, s2 = c["ZR[0].mat.limh"], c["ZR[1].mat.limh"]
    if s1 != s2:
        raise NotImplementedError("材料不同时须显式指定参考材料，不能按 sigma_Hlim 自动猜硬度")
    rows = [
        ("sigma_Hlim_surface", s1, "MPa", "K01 COM ZR[0/1].mat.limh（两轮相同）"),
        ("surface_oil_mineral", 1, "1", f"K01 报告行 {text['lubrication']['line']}：矿物油"),
    ]
    for name in ("nu_40", "N_L_1", "N_L_2"):
        row = report[name]
        rows.append((name, row["value"], row["unit"], f"K01 报告行 {row['line']} {row['label']}"))
    row = report["Rz_H"]
    for i in (1, 2):
        rows.append((f"Rz_H_{i}", row["value"], row["unit"],
                     f"K01 两轮共同齿面 Rz，报告行 {row['line']} {row['label']}"))
    for name, value, unit, source in rows:
        if name in model.specs and name not in model.formulas:
            model.set(name, value, unit, "evidence", source)
    if "surface_nu40_vi95" in model.specs:
        model.set("surface_nu40_vi95", 1, "1", "assumption",
                  "K01报告未提供VI；按ISO 6336-2:2019 12.3.2.1.1 ν40/VI95基准显式接受近似")
    for i in (1, 2):
        if f"N_Href_{i}" in model.specs:
            model.set(f"N_Href_{i}", 5e7, "1", "assumption",
                      "K01渗碳钢Eh按禁点蚀曲线2；ISO 6336-2:2019 表5 PDF31/印刷23；显式案例契约")
    return set_surface_constants(model)
