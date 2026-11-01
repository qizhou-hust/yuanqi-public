"""Explicit geometry scopes used by ISO/TR 6336-30:2022 Annex A.

This is an opt-in formula-set patch, not a global change to pair_model. The
TR's main geometry uses generating shift, while Annex A uses nominal root
diameters for reduced mass and explicitly for K_Fbeta tooth height. The
apparent conflict with the broad wording in 4.2.12 is recorded in the audit.

Currently limited to external gears with rack-generated roots. Shaper cutter,
undercut, protuberance and double-helical width selection remain separate
assembly requirements. Inputs and methods have no inferred defaults.
"""
from __future__ import annotations

from ..kernel.expr import FormulaError
from ..kernel.graph import Formula, InputSpec
from .formulas import ROOT_GENERATING, _pair

R = "ISO/TR 6336-30:2022"

SPAN_SHIFT = _pair(
    "tr30.xE.span", "xE_{i}", "1",
    "(W_k_{i} - m_n*cos(alpha_n)*(pi*(k_span_{i} - 0.5) + z_{i}*inv(alpha_t)/rad))"
    "/(2*m_n*sin(alpha_n))",
    f"{R} Annex A.6 印刷45页：法向跨齿厚 Wk 求产形变位；alpha_t 为端面压力角",
    ("m_n > 0", "alpha_n > 0*rad", "alpha_n < pi/2*rad", "z_{i} > 0"),
)

GENERATED_ROOT_DIAMETER = _pair(
    "tr30.df.generated", "df_{i}", "mm", "d_{i} - 2*m_n*(hfP_{i} - xE_{i})",
    f"{R} 4.2.12 / Annex A.6 印刷45页：主几何齿根圆用产形变位（外齿、齿条刀）",
    ("d_{i} > 0", "df_{i} > 0"),
)

NOMINAL_ROOT_DIAMETER = _pair(
    "tr30.df.nominal", "df_nominal_{i}", "mm", "d_{i} - 2*m_n*(hfP_{i} - x_{i})",
    f"{R} Annex A.8.1 印刷48页数值口径 / A.8.2 印刷51页注：分用途保留名义齿根圆",
    ("d_{i} > 0", "df_nominal_{i} > 0"),
)

NOMINAL_MASS_DIAMETER = _pair(
    "tr30.dm.nominal", "dm_{i}", "mm", "(da_{i} + df_nominal_{i})/2",
    f"{R} Annex A.8.1 印刷48页式(31)数值口径：dm 的 df 采用名义值；据附录数值判定",
)

NOMINAL_TOOTH_HEIGHT = _pair(
    "tr30.h.nominal", "h_{i}", "mm", "(da_{i} - df_nominal_{i})/2",
    f"{R} Annex A.8.2 印刷51页式(72)前注：KFbeta 齿高中的 df 用名义值",
    ("h_{i} > 0",),
)

EXACT_STIFFNESS_TEETH = _pair(
    "tr30.zn.stiffness", "zn_c_{i}", "1", "z_{i}/(cos(beta_b)**2*cos(beta))",
    f"{R} 4.2.3 / Annex A.8.1 印刷47页：刚度当量齿数按 ISO 6336-3:2019 式(16)",
    ("z_{i} > 0", "cos(beta) > 0"),
)

TR30_GEOMETRY_INPUTS = [
    *[InputSpec(f"W_k_{i}", "mm", "法向跨齿厚；输入量，不是附录生成变位输出", (f"W_k_{i} > 0",)) for i in (1, 2)],
    *[InputSpec(f"k_span_{i}", "1", "跨测齿数；案例装配需额外核对为整数", (f"k_span_{i} >= 1",)) for i in (1, 2)],
    *[InputSpec(f"hfP_{i}", "1", "本轮名义基本齿条齿根高系数", (f"hfP_{i} > 0",)) for i in (1, 2)],
]


def patch_tr30_geometry(formulas, *, shift_source, mass_root, kfbeta_root):
    """Return a new formula list with explicit TR30 geometry scopes.

    Required choices:
      shift_source = 'span' | 'normal_thickness_deviation'
      mass_root = kfbeta_root = 'nominal_annex_a'

    Pass the specialized generating-root model's formulas. Core inputs x_1/x_2
    remain nominal in stiffness; only xE comes from the chosen measurement.
    The caller must add TR30_GEOMETRY_INPUTS to its input declarations and
    explicitly declare the ISO/TR 6336-30 edition. This helper sets no inputs,
    editions, method defaults or evidence values.
    """
    if shift_source not in {"span", "normal_thickness_deviation"}:
        raise FormulaError("TR30 shift_source must be explicit: span | normal_thickness_deviation")
    if mass_root != "nominal_annex_a" or kfbeta_root != "nominal_annex_a":
        raise FormulaError("TR30 Annex A mass_root and kfbeta_root must explicitly select nominal_annex_a")
    original = list(formulas)
    by_output = {f.output: f for f in original}
    if len(by_output) != len(original):
        raise FormulaError("TR30 geometry patch requires one formula per output")
    replaced = {f.output for f in GENERATED_ROOT_DIAMETER + NOMINAL_MASS_DIAMETER +
                NOMINAL_TOOTH_HEIGHT + EXACT_STIFFNESS_TEETH}
    missing = replaced - by_output.keys()
    if missing:
        raise FormulaError(f"TR30 geometry patch missing base outputs: {sorted(missing)}")
    for i in (1, 2):
        for name in (f"G_{i}", f"gamma_e_{i}"):
            if name in by_output and f"xE_{i}" not in by_output[name].compiled().names:
                raise FormulaError("TR30 geometry patch requires explicitly selected generating root shift")
    if any(f.output.startswith("df_nominal_") for f in original):
        raise FormulaError("TR30 nominal root diameter already defined")
    shift = SPAN_SHIFT if shift_source == "span" else [f for f in ROOT_GENERATING if f.output.startswith("xE_")]
    replaced.update(f.output for f in shift)
    patched = [f for f in original if f.output not in replaced]
    patched += shift + NOMINAL_ROOT_DIAMETER + GENERATED_ROOT_DIAMETER + NOMINAL_MASS_DIAMETER
    patched += NOMINAL_TOOTH_HEIGHT + EXACT_STIFFNESS_TEETH
    return patched
