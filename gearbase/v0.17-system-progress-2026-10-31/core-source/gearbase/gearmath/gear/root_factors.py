"""Case-hardened reference-life root factors, explicitly selected.

Equations were independently written and visually checked against the
ISO 6336-3:2019 original page images.  The selected case-hardened reference
branch is audited; this does not qualify other material or life branches.
No finite-life interpolation, scratches, or other material group is supplied.
"""
from __future__ import annotations

from ..kernel.graph import Formula, InputSpec

F, S = Formula, InputSpec
SOURCE_STATUS = "iso_original_images_checked_selected_branch"
SOURCE_AUDIT = {
    "standard": "ISO 6336-3:2019",
    "sha256": "f00fea96b736a1d0d34e71496afc3338982d4bc8613571a6c882aae2fe89cf04",
    "pdf_pages": [32, 35, 36, 37, 41, 46, 48, 49, 51],
    "printed_pages": [24, 27, 28, 29, 33, 38, 40, 41, 43],
    "references": ["7.2", "9.3.1 (68)(69)", "10.1/10.3 (72)-(74)",
                   "13.3.2.1 (75)-(77), Table 4 item 10", "14.1",
                   "14.3.2.1 (84)(87)", "15.3.3.1 Table 5"],
}
ROOT_METHOD = "case_hardened_reference"

ROOT_FACTOR_INPUTS = [
    *[S(f"N_L_{i}", "1", f"Load cycles, gear {i}", (f"N_L_{i} > 0",))
      for i in (1, 2)],
    *[S(f"Rz_F_{i}", "um", f"Root peak-to-valley roughness, gear {i}",
        (f"Rz_F_{i} > 0",)) for i in (1, 2)],
    *[S(f"root_surface_intact_{i}", "1",
        f"14.1 applicability: no root scratches deeper than 2Rz or detrimental oxidation/chemical effects, gear {i}",
        (f"root_surface_intact_{i} >= 1", f"root_surface_intact_{i} <= 1")) for i in (1, 2)],
    S("root_mm", "mm", "Fixed length unit, 1 mm", ("root_mm >= 1", "root_mm <= 1")),
    S("root_um", "um", "Fixed roughness unit, 1 um", ("root_um >= 0.001", "root_um <= 0.001")),
]

# ISO 6336-3:2019 15.1：YX 须对小轮、大轮分别确定；15.3.3.1 表5（PDF51/印刷43 原图已核）
# 按材料组给出 3×10⁶ 次参考寿命分支。键为材料组，逐轮显式选择，不从材料名或硬度推断。
YX_TABLE5 = {
    # St, V, GGG (perl., bai.), GTS (perl.)
    "structural_through_hardened": "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 30, 1.03 - 0.006*m_n/root_mm, 0.85))",
    # Eh, IF (root), NT, NV
    "surface_hardened": "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 25, 1.05 - 0.01*m_n/root_mm, 0.8))",
    # GG, GGG (ferr.)
    "grey_ferritic_cast": "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 25, 1.075 - 0.015*m_n/root_mm, 0.7))",
}
# 现行 sigma_FG 仍用共用 Y_X：仅当两轮逐轮值相同时给出，不同即 out_of_domain，不以一轮系数代替另一轮
YX_COMMON = F("rf.Y_X.common", "Y_X", "1", "Y_X_1",
              "ISO 6336-3:2019 15.1; common-factor API only when both per-gear values agree",
              ("abs(Y_X_1 - Y_X_2) <= 1e-12",),
              note="Unequal YX values are out_of_domain for the shared-factor rating path")


def size_factor_formulas(materials):
    """逐轮表5 YX：materials 形如 {1: "surface_hardened", 2: "structural_through_hardened"}，须两轮都给出。"""
    from ..kernel.expr import FormulaError
    if set(materials) != {1, 2} or any(v not in YX_TABLE5 for v in materials.values()):
        raise FormulaError(f"YX 须逐轮显式选择材料组；可选：{sorted(YX_TABLE5)}")
    return [F(f"rf.Y_X.{materials[i]}.{i}", f"Y_X_{i}", "1", YX_TABLE5[materials[i]],
              "ISO 6336-3:2019 15.1 per-gear, 15.3.3.1 Table 5; PDF49/51, printed41/43 images checked",
              ("m_n > 0",), note="Reference-life (3e6) branch; static and limited-life YX not implemented")
            for i in (1, 2)] + [YX_COMMON]


ROOT_FACTORS = [
    F(f"rf.Y_drelT.{i}", f"Y_drelT_{i}", "1",
      f"(1 + sqrt(0.003*0.2*(1 + 2*qs_{i})))/(1 + sqrt(0.003*1.2))",
      "ISO 6336-3:2019 13.3.2.1 (75)-(77), Table 4 item 10; PDF41/printed33 image checked",
      (f"qs_{i} >= 1", f"qs_{i} < 8", f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10"),
      note="Selected case-hardened branch: slip-layer parameter 0.003 mm; reference life")
    for i in (1, 2)
] + [
    F(f"rf.Y_RrelT.{i}", f"Y_RrelT_{i}", "1",
      f"where(Rz_F_{i}/root_um < 1, 1.12, 1.674 - 0.529*(Rz_F_{i}/root_um + 1)**0.1)",
      "ISO 6336-3:2019 14.3.2.1 (84)(87); PDF48-49/printed40-41 images checked",
      (f"Rz_F_{i} > 0", f"Rz_F_{i}/root_um <= 40", f"root_surface_intact_{i} >= 1", f"root_surface_intact_{i} <= 1",
       f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10"),
      note="Case-hardened branch; reference life and 14.1 surface applicability must be declared")
    for i in (1, 2)
] + [
    *[F(f"rf.Y_X.{i}", f"Y_X_{i}", "1", YX_TABLE5["surface_hardened"],
        "ISO 6336-3:2019 15.1 per-gear, 15.3.3.1 Table 5; PDF49/51, printed41/43 images checked",
        ("m_n > 0", f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10"),
        note="Case-hardened reference-life branch for this gear; no finite-life interpolation") for i in (1, 2)],
    YX_COMMON,
]

ROOT_VARIANTS = {ROOT_METHOD: ROOT_FACTORS}

# The current rating graph uses a common Y_B.  Keep both per-gear calculations
# and reject unlike factors rather than silently applying one gear's factor.
ROOT_AUX_INPUTS = [
    *[S(f"d_inner_{i}", "mm", f"Bore diameter of annular supporting rim, gear {i}",
        (f"d_inner_{i} >= 0",)) for i in (1, 2)],
    *[S(f"DT_grade_{i}", "1", f"ISO tolerance class used for YDT, gear {i}",
        (f"DT_grade_{i} >= 1", f"DT_grade_{i} <= 12")) for i in (1, 2)],
    S("DT_profile_modified", "1", "Actual modification giving trapezoidal load distribution (10.1), 0 or 1",
      ("DT_profile_modified >= 0", "DT_profile_modified <= 1",
       "DT_profile_modified*(1-DT_profile_modified) <= 0")),
]
ROOT_AUX_FACTORS = [
    *[F(f"rf.rim_thickness.{i}", f"rim_thickness_{i}", "mm", f"(df_{i}-d_inner_{i})/2",
        "Annular blank geometry, supporting rim thickness measured from root circle to concentric bore",
        (f"df_{i} > 0", f"d_inner_{i} >= 0", f"df_{i} > d_inner_{i}"),
        note="Selected external annular blank only; not valid for spokes, pockets or arbitrary sections")
      for i in (1, 2)],
    *[F(f"rf.Y_B.{i}", f"Y_B_{i}", "1",
        f"where(rim_thickness_{i}/h_{i} >= 1.2, 1, 1.6*log(2.242*h_{i}/rim_thickness_{i}))",
        "ISO 6336-3:2019 9.3.1 (68)(69); PDF35/printed27 image checked",
        (f"h_{i} > 0", f"rim_thickness_{i}/h_{i} > 0.5"),
        note="External gear only; minimum rim thickness, not arbitrary bore radius") for i in (1, 2)],
    F("rf.Y_B.common", "Y_B", "1", "Y_B_1",
      "ISO 6336-3:2019 9.3.1; common-factor API only when both per-gear values agree",
      ("abs(Y_B_1-Y_B_2) <= 1e-12",),
      note="Unequal YB values are out_of_domain until rating supports per-gear factors"),
    F("rf.Y_DT", "Y_DT", "1",
      "where(max(DT_grade_1, DT_grade_2) > 4, 1, "
      "where(eps_alphan <= 2.05, 1, where(DT_profile_modified > 0, "
      "where(eps_alphan <= 2.5, 2.366-0.666*eps_alphan, 0.7), 1)))",
      "ISO 6336-3:2019 10.1/10.3 (72)-(74); PDF36-37/printed28-29 images checked",
      ("eps_alphan > 0",),
      note="Worse tolerance class governs; reduced stress only with actual 10.1 modification declared"),
]


def set_root_constants(model):
    """Set fixed unit conversions only if the selected model requires them."""
    for name, unit in (("root_mm", "mm"), ("root_um", "um")):
        if name in model.specs:
            model.set(name, 1, unit, "standard_constant", "Definition of metric length unit")
    return model
