"""Explicit optional factor methods, compiled into the existing pair graph.

The v0.4 API remains available for receipt replay. Passing factor_selectors,
including an empty dict, opts into this extension and requires all three
choices. No missing factor method is silently selected for evaluation.
The selected equations have an original-image audit; case assumptions and
whole-rating acceptance are separate from that audit.
"""
from __future__ import annotations

from ..kernel.expr import FormulaError
from ..kernel.select import external, specialize, variant


ZV_KEY = "method.Z_V_velocity"
ZBD_KEY = "method.Z_BD"
FACTOR_OPTIONS = {
    "method.Z_LVR": {
        "B_reference": "矿物油 reference-stress 子集；ISO 6336-2 原图已核",
        "external": "ZL/ZV/ZR 均作为有出处的 evidence 输入",
    },
    "method.life": {
        "case_hardened_085_long_life": "渗碳钢长寿命 0.85 曲线；ISO 原图已核",
        "external": "ZNT/YNT 均作为有出处的 evidence 输入",
    },
    "method.root_factors": {
        "case_hardened_reference": "渗碳钢 reference Yδ/YR/YX；ISO 6336-3 原图已核",
        "external": "Yδ/YR/YX 均作为有出处的 evidence 输入",
    },
}
BASE_FACTOR_KEYS = tuple(FACTOR_OPTIONS)
FACTOR_OPTIONS.update({
    "method.contact_aux": {"both_case_hardened": "两轮均渗碳钢中性ZW及ZX公式", "external": "ZW/ZX evidence输入"},
    "method.root_aux": {"external_annular": "外齿环状/实心轮坯YB、显式精度/修形YDT", "external": "YB/YDT evidence输入"},
    # 式(47)速度口径：method.Z_LVR 非 external 时必须显式选择；external 时只能取 external（不参与计算）
    ZV_KEY: {"v_w": "ISO 6336-2:2019 式(47) 工作节线速度 vw（PDF35/印刷27）",
             "v_ref": "ISO/TR 6336-30:2022 A.9.2 式(47) 分度圆线速度 v（PDF59/印刷53）",
             "external": "method.Z_LVR=external：ZV 为证据输入，速度口径不参与计算"},
    # 可选组：给出时以 ISO 6336-2:2019 6.3 显式表3方法（含 fZCa）替换主图 pit.Z_B/Z_D
    ZBD_KEY: {"spur": "直齿 6.3a，fZCa 不出现", "helical_3d": "斜齿表3 fZCa=1.0（3D载荷分布计算）",
              "helical_manufacturer": "斜齿表3 fZCa=1.07（制造商经验修形）",
              "helical_unmodified": "斜齿表3 fZCa=1.2（未修形）"},
})

FACTOR_OUTPUTS = {
    "method.Z_LVR": ("Z_L", "Z_V", "Z_R"),
    "method.life": ("Z_NT_1", "Z_NT_2", "Y_NT_1", "Y_NT_2"),
    "method.root_factors": ("Y_drelT_1", "Y_drelT_2", "Y_RrelT_1", "Y_RrelT_2", "Y_X"),
    "method.contact_aux": ("Z_W", "Z_X"),
    "method.root_aux": ("Y_B", "Y_DT"),
}

K01_FACTOR_SELECTORS = {
    "method.Z_LVR": "B_reference",
    ZV_KEY: "v_ref",
    "method.life": "case_hardened_085_long_life",
    "method.root_factors": "case_hardened_reference",
}
# K01 契约选择器的专门来源（未列出的用通用"显式系数契约"说明）
K01_FACTOR_SELECTOR_SOURCES = {
    ZV_KEY: ("KISSsoft口径：K03/K04/K05 COM ZPP.Flanke.ZV 与分度圆v复算相差≤1e-6，与vw相差2.8e-4–4.0e-4；"
             "K01 x1+x2=0 时 v=vw，两口径数值相同（见 docs/M33-TR30验收契约.md）"),
}
K01_FULL_FACTOR_SELECTORS = {**K01_FACTOR_SELECTORS,
                             "method.contact_aux": "both_case_hardened",
                             "method.root_aux": "external_annular"}


def compile_factors(selectors):
    """Return specialized formulas, input declarations and unresolved choices."""
    from .life_factors import CYCLE_INPUTS, LIFE_CYCLES, LIFE_FACTORS, LIFE_INPUTS
    from .root_factors import ROOT_FACTOR_INPUTS, ROOT_FACTORS, ROOT_AUX_FACTORS, ROOT_AUX_INPUTS
    from .surface_factors import SURFACE_FACTORS, SURFACE_INPUTS, CONTACT_AUX_FACTORS, CONTACT_AUX_INPUTS
    sel = {str(k): str(v) for k, v in selectors.items()}
    bad = [f"{k}={v!r}" for k, v in sel.items()
           if k not in FACTOR_OPTIONS or v not in FACTOR_OPTIONS[k]]
    if bad:
        raise FormulaError(f"系数选择器取值无效：{bad}；可选：{FACTOR_OPTIONS}")
    missing = [k for k in BASE_FACTOR_KEYS if k not in sel]
    zlvr, zv = sel.get("method.Z_LVR"), sel.get(ZV_KEY)
    if (zlvr == "external" and zv not in (None, "external")) or (zlvr not in (None, "external") and zv == "external"):
        raise FormulaError(f"{ZV_KEY}={zv!r} 与 method.Z_LVR={zlvr!r} 不相容；公式路径须选 v_w 或 v_ref")
    if zv is None and zlvr != "external":
        missing.append(ZV_KEY)
    # Placeholder compilation only. unresolved prevents every evaluation.
    full = {**{k: "external" for k in missing}, **sel}
    if ZV_KEY in missing or ZV_KEY not in full:
        full[ZV_KEY] = "v_w" if full["method.Z_LVR"] != "external" else "external"
    groups = {"method.Z_LVR": SURFACE_FACTORS, "method.life": LIFE_FACTORS,
              "method.root_factors": ROOT_FACTORS}
    if "method.contact_aux" in full:
        groups["method.contact_aux"] = CONTACT_AUX_FACTORS
    if "method.root_aux" in full:
        groups["method.root_aux"] = ROOT_AUX_FACTORS
    variants = []
    for key, formulas in groups.items():
        method = next(v for v in FACTOR_OPTIONS[key] if v != "external")
        variants += [variant(f, {key: method}) for f in formulas]
        variants += [external(q, "1", {key: "external"}, ref=f"{key} external evidence")
                     for q in FACTOR_OUTPUTS[key]]
    from .surface_factors import ZV_VELOCITY_VARIANTS
    variants += [variant(f, {ZV_KEY: k}) for k, f in ZV_VELOCITY_VARIANTS.items()]
    table_extra = []
    if ZBD_KEY in full:
        from .contact_factors import ZBD_INPUTS, ZBD_VARIANTS
        variants += [variant(f, {ZBD_KEY: k}) for k, fs in ZBD_VARIANTS.items() for f in fs]
        table_extra = [s for s in ZBD_INPUTS if s.name in ("contact_path_not_shortened", "zCa_method_supported")]
    spec = specialize(variants, full, prune=True)
    if any(full[k] != "external" for k in BASE_FACTOR_KEYS):
        spec.extend(LIFE_CYCLES)
    table = SURFACE_INPUTS + LIFE_INPUTS + CYCLE_INPUTS + ROOT_FACTOR_INPUTS + CONTACT_AUX_INPUTS + ROOT_AUX_INPUTS + table_extra
    unresolved = [{"name": k, "code": "missing_selector",
                   "message": f"未选择系数方法：{k}；可选：{FACTOR_OPTIONS[k]}"} for k in missing]
    return spec, table, unresolved


def validation_status(selectors):
    from . import contact_factors, life_factors, root_factors, surface_factors
    audit = {"method.Z_LVR": surface_factors.SOURCE_STATUS,
             ZV_KEY: surface_factors.ZV_VELOCITY_AUDIT,
             ZBD_KEY: contact_factors.SOURCE_STATUS,
             "method.contact_aux": surface_factors.SOURCE_STATUS,
             "method.life": life_factors.SOURCE_AUDIT,
             "method.root_factors": root_factors.SOURCE_AUDIT,
             "method.root_aux": root_factors.SOURCE_AUDIT}
    return {k: {"method": v, "iso_equation_images": "not_applicable" if v == "external" else "verified",
                "status": "external_evidence" if v == "external" else "verified_equations_supported_subset",
                "source_audit": audit[k] if v != "external" else {}}
            for k, v in selectors.items()}


def set_k01_factor_inputs(model, case):
    """Input-only mapping: never read a commercial factor to compute itself."""
    from .surface_factors import set_k01_surface_inputs
    from .root_factors import set_root_constants
    if case.get("id") != "K01-spur":
        raise NotImplementedError("系数公式输入契约只支持 K01-spur")
    if "life_duration" in model.specs:
        model.set("life_duration", case["com"]["ZS.H"] * 3600, "s", "user",
                  "KISSsoft K01 COM ZS.H，小时换算为秒")
        for i in (1, 2):
            model.set(f"cycles_per_rev_{i}", 1, "1", "assumption",
                      "K01 单向单啮合，每转受载一次；显式工况假设，NL报告值仅用作独立对照")
    if model.selectors.get("method.Z_LVR") == "B_reference":
        set_k01_surface_inputs(model, case)
    if model.selectors.get("method.root_factors") == "case_hardened_reference":
        row = case["report"]["Rz_F"]
        for i in (1, 2):
            model.set(f"Rz_F_{i}", row["value"], row["unit"], "user",
                      f"K01 两轮共同齿根 Rz；报告第 {row['line']} 行 {row['label']}")
            model.set(f"root_surface_intact_{i}", 1, "1", "assumption",
                      "按粗糙度模型假设齿根无深划痕；原始报告未提供实测表面完整性证据")
        set_root_constants(model)
    if model.selectors.get("method.contact_aux") == "both_case_hardened":
        model.set("aux_both_case_hardened", 1, "1", "user",
                  f"K01 两轮均渗碳钢；报告第{case['report_text']['material']['line']}行")
    if model.selectors.get("method.root_aux") == "external_annular":
        for i in (1, 2):
            row = case["report"][f"d_inner_{i}"]
            model.set(f"d_inner_{i}", row["value"], row["unit"], "user", f"K01轮坯内径，报告第{row['line']}行")
            grade = case["report"][f"Q_grade_{i}"]
            model.set(f"DT_grade_{i}", grade["value"], "1", "user", f"K01精度，报告第{grade['line']}行")
        row = case["report_text"]["profile_modification"]
        if row["text"] != "none (only running-in)":
            raise NotImplementedError("K01 YDT修形映射仅支持原报告none配置")
        model.set("DT_profile_modified", 0, "1", "user", f"K01无实际修形，报告第{row['line']}行")
    return model


def factor_variants():
    """系数方法组的全部变体（含 external），不经选择；供公式注册表导出。
    与 compile_factors 内部装配的是同一批公式对象（测试核对）。"""
    from .contact_factors import ZBD_VARIANTS
    from .root_factors import ROOT_AUX_FACTORS, ROOT_FACTORS
    from .surface_factors import CONTACT_AUX_FACTORS, SURFACE_FACTORS, ZV_VELOCITY_VARIANTS
    from .life_factors import LIFE_FACTORS
    groups = {"method.Z_LVR": SURFACE_FACTORS, "method.life": LIFE_FACTORS, "method.root_factors": ROOT_FACTORS,
              "method.contact_aux": CONTACT_AUX_FACTORS, "method.root_aux": ROOT_AUX_FACTORS}
    out = []
    for key, formulas in groups.items():
        method = next(v for v in FACTOR_OPTIONS[key] if v != "external")
        out += [variant(f, {key: method}) for f in formulas]
        out += [external(q, "1", {key: "external"}, ref=f"{key} external evidence") for q in FACTOR_OUTPUTS[key]]
    out += [variant(f, {ZV_KEY: k}) for k, f in ZV_VELOCITY_VARIANTS.items()]
    out += [variant(f, {ZBD_KEY: k}) for k, fs in ZBD_VARIANTS.items() for f in fs]
    return out
