"""ISO 6336-5:2016 material stress numbers for the TR30 1–4 subset.

Coefficients come from the supplied standard's explicit Table 1, not fits to
TR30 outputs or digitized curves. Formula (2), rows 25/31/42/47 and Figures
5/6/9/10 have been checked on rendered pages. Material class/quality selection
is explicit; no heat treatment qualification or hardness conversion is inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..kernel.expr import FormulaError
from ..kernel.graph import Formula, InputSpec

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "m33_material" / "iso6336-5-2016-subset.json"


def load_material_rows():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class MaterialLimits:
    formulas: tuple
    inputs: tuple
    constants: tuple
    selections: dict
    source_status: dict

    def set_constants(self, model):
        for name, value, unit, source in self.constants:
            model.set(name, value, unit, "standard_constant", source)
        return model


def select_material_limits(choices):
    """Select each gear's material branch without defaulting an omitted field.

    ``choices`` has exactly string keys '1' and '2', each containing:
      family: case_hardened_wrought | through_hardened_wrought_alloy
      quality: MQ
      hardness_scale: HV | HRC60
      core_branch: ge30_HRC | not_applicable

    HRC60 is supported only for the case-hardened branch and requires the
    actual surface-hardness input to equal 60. Other HRC values need a
    separately verified conversion or direct graphical implementation.
    ``material_surface_hardness_i`` and, for case hardened material,
    ``material_core_hardness_i`` remain mandatory model inputs.
    """
    if not isinstance(choices, dict) or set(choices) != {"1", "2"}:
        raise FormulaError("Material choices must explicitly specify string keys '1' and '2'")
    data = load_material_rows()
    rows = data["rows"]
    formulas, specs, selected = [], [], {}
    for i in ("1", "2"):
        choice = choices[i]
        required = {"family", "quality", "hardness_scale", "core_branch"}
        if not isinstance(choice, dict) or set(choice) != required:
            raise FormulaError(f"material {i}: explicit family/quality/hardness_scale/core_branch required")
        family, quality = choice["family"], choice["quality"]
        scale, core = choice["hardness_scale"], choice["core_branch"]
        if quality != "MQ":
            raise FormulaError(f"material {i}: only the image-verified MQ subset is implemented")
        if family == "through_hardened_wrought_alloy":
            if scale != "HV" or core != "not_applicable":
                raise FormulaError(f"material {i}: V alloy requires HV and explicit not_applicable core branch")
            pair = ("V_alloy_MQ_H", "V_alloy_MQ_F")
        elif family == "case_hardened_wrought":
            if scale not in {"HV", "HRC60"} or core != "ge30_HRC":
                raise FormulaError(f"material {i}: Eh requires HV/HRC60 and explicit ge30_HRC core branch")
            pair = ("Eh_MQ_H", "Eh_MQ_core30_F")
        else:
            raise FormulaError(f"material {i}: unsupported material family {family!r}")
        hardness = f"material_surface_hardness_{i}"
        if scale == "HRC60":
            hardness_domain = (f"{hardness} >= 60", f"{hardness} <= 60")
        else:
            hardness_domain = (f"{hardness} >= {rows[pair[0]]['hardness_min']}",
                               f"{hardness} <= {rows[pair[0]]['hardness_max']}")
        specs.append(InputSpec(hardness, "1", f"本轮表面硬度；显式选择的标尺为 {scale}", hardness_domain))
        if family == "case_hardened_wrought":
            specs.append(InputSpec(f"material_core_hardness_{i}", "1", "芯部硬度 HRC（图10的>=30分支）",
                                   (f"material_core_hardness_{i} >= 30",)))
        selected[i] = {**choice, "table_rows": [rows[key]["row"] for key in pair]}
        for stress, key in zip(("H", "F"), pair):
            row = rows[key]
            domain = list(hardness_domain)
            if stress == "F" and family == "case_hardened_wrought":
                domain.append(f"material_core_hardness_{i} >= {row['core_hardness_HRC_min']}")
            formulas.append(Formula(
                f"material.{key}.{scale}.{i}", f"sigma_{stress}lim_{i}", "MPa",
                f"({row['A']!r}*{hardness} + {row['B_MPa']!r})*material_stress_unit",
                f"ISO 6336-5:2016 5.5 式(2)，表1行{row['row']}，图{row['figure']}；{family}/{quality}/{scale}",
                tuple(domain),
                note=f"原图已核 PDF{row['pdf_page']}、图PDF{row['figure_pdf_page']}；源SHA256={data['source_sha256']}；"
                     "HRC60为图示范围内的窄点子集，无硬度换算；材料质量符合性另行判定" if scale == "HRC60" else
                     f"原图已核 PDF{row['pdf_page']}、图PDF{row['figure_pdf_page']}；源SHA256={data['source_sha256']}；材料质量符合性另行判定",
            ))
    specs.append(InputSpec("material_stress_unit", "MPa", "材料应力表达式的1MPa单位尺度",
                           ("material_stress_unit >= 1", "material_stress_unit <= 1")))
    return MaterialLimits(
        tuple(formulas), tuple(specs),
        (("material_stress_unit", 1.0, "MPa", "ISO 6336-5:2016 式(2)的应力单位尺度，不是材料极限输入"),),
        selected,
        {"status": "verified_equations_supported_subset", "source_sha256": data["source_sha256"],
         "source": data["source"], "pdf_pages": [12, 13, 14, 18, 19, 22, 23],
         "equation": "5.5 (2)", "table_rows": [25, 31, 42, 47],
         "material_qualification": "not_independently_assessed"},
    )
