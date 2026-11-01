"""ISO/TR 6336-30 examples 1--4: explicitly selected Eh/V material branches.

The originals were read as page images, not inferred from example outputs.
All contact curves here require no permissible pitting.  Root corrections
cover reference/long life (N_L >= 3e6); finite-life root interpolation is not
implemented.  No material identity or long-life endpoint is a library default.
"""
from __future__ import annotations

import re

from ..kernel.graph import Formula, InputSpec
from .root_factors import ROOT_FACTOR_INPUTS, set_root_constants

F, S = Formula, InputSpec
SOURCE_STATUS = "iso_original_images_checked_selected_branches"
SOURCE_AUDIT = {
    "ISO 6336-2:2019": {
        "sha256": "5e7a4b83c2d91292f6ddce324ea2fee16699b1c385d80b76606fec6b459de5b0",
        "pdf_pages": [20, 21, 31], "references": ["5.4.4.3", "11.3 Figure 6 curve 2/Table 5"],
    },
    "ISO 6336-3:2019": {
        "sha256": "f00fea96b736a1d0d34e71496afc3338982d4bc8613571a6c882aae2fe89cf04",
        "pdf_pages": [39, 41, 48, 49, 51],
        "references": ["12.3.3/Table 3", "13.3.2.1/Table 4", "14.3.2.1", "15.3.3.1/Table 5"],
    },
    "ISO/TR 6336-30:2022": {
        "sha256": "12834eabe980fd66da9a6e41881339ba0ddda0ff8222af6eec3bfc3401e7b2db",
        "pdf_pages": [13, 14], "references": ["4.2.4", "4.2.7"],
    },
}

TR30_MATERIAL_INPUTS = ROOT_FACTOR_INPUTS + [
    *[S(f"yield_strength_{i}", "MPa", f"Declared V steel yield/proof strength, gear {i}",
        (f"yield_strength_{i} > 0",)) for i in (1, 2)],
    S("root_MPa", "MPa", "Fixed stress unit, 1 MPa", ("root_MPa >= 1", "root_MPa <= 1")),
]


def _gear_formulas(material, i):
    if material not in {"Eh", "V"}:
        raise NotImplementedError(f"Unsupported TR30 material branch {material!r}")
    nl, qs = f"N_L_{i}", f"qs_{i}"
    life_dom = (f"{nl} >= 3e6", f"{nl} <= 1e10")
    fs = [
        F(f"trmat.Z_NT.{material}.{i}", f"Z_NT_{i}", "1",
          f"where({nl} < 5e7, exp(log(1.6)*log(5e7/{nl})/log(5e7/1e5)), "
          f"exp(log({nl}/5e7)*log(0.85)/log(1e10/5e7)))",
          "ISO 6336-2:2019 11.3 Figure 6 curve 2/Table 5, PDF31/printed23 checked",
          (f"{nl} >= 1e5", f"{nl} <= 1e10"),
          note="No pitting permissible; 0.85 endpoint explicitly selected; ZNT is distinct from combined ZN"),
        F(f"trmat.contact_weight.{i}", f"contact_reference_weight_{i}", "1",
          f"min(1, max(0, log({nl}/1e5)/log(5e7/1e5)))",
          "ISO/TR 6336-30:2022 4.2.4, PDF13/printed7 checked; factor endpoint decomposition",
          (f"{nl} >= 1e5", f"{nl} <= 1e10"),
          note="Exact log endpoint weight; do not equate bitwise with rounded 0.3705 combined-stress coefficient"),
        F(f"trmat.Y_NT.{material}.{i}", f"Y_NT_{i}", "1",
          f"exp(log({nl}/3e6)*log(0.85)/log(1e10/3e6))",
          "ISO 6336-3:2019 12.3.3 Figure 11/Table 3, PDF39/printed31 checked",
          life_dom, note="Eh and V share the selected long-life endpoints, not their finite-life curves"),
    ]
    if material == "Eh":
        fs += [F(f"trmat.slip.Eh.{i}", f"slip_layer_{i}", "mm", "0.003*root_mm",
                 "ISO 6336-3:2019 13.3.2.1 Table 4 item 10, PDF41/printed33 checked")]
        size = "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 25, 1.05-0.01*m_n/root_mm, 0.8))"
    else:
        y = f"yield_strength_{i}/root_MPa"
        slip = (f"where({y} <= 600, 0.0281+(0.0194-0.0281)*({y}-500)/100, "
                f"where({y} <= 800, 0.0194+(0.0064-0.0194)*({y}-600)/200, "
                f"0.0064+(0.0014-0.0064)*({y}-800)/200))*root_mm")
        fs += [F(f"trmat.slip.V.{i}", f"slip_layer_{i}", "mm", slip,
                 "ISO 6336-3:2019 13.3.2.1 Table 4 items 6-9/footnote a, PDF41/printed33 checked",
                 (f"{y} >= 500", f"{y} <= 1000"),
                 note="V steel only; tabulated knots and permitted within-category interpolation, no extrapolation")]
        size = "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 30, 1.03-0.006*m_n/root_mm, 0.85))"
    fs += [
        F(f"trmat.Y_drelT.{material}.{i}", f"Y_drelT_{i}", "1",
          f"(1+sqrt(slip_layer_{i}/root_mm*0.2*(1+2*{qs})))/(1+sqrt(slip_layer_{i}/root_mm*1.2))",
          "ISO 6336-3:2019 13.3.2.1 (75)-(77), PDF41/printed33 checked",
          (f"{qs} >= 1", f"{qs} < 8", *life_dom)),
        F(f"trmat.Y_RrelT.{material}.{i}", f"Y_RrelT_{i}", "1",
          f"where(Rz_F_{i}/root_um < 1, 1.12, 1.674-0.529*(Rz_F_{i}/root_um+1)**0.1)",
          "ISO 6336-3:2019 14.3.2.1 (84)(87), PDF48-49/printed40-41 checked",
          (f"Rz_F_{i} > 0", f"Rz_F_{i}/root_um <= 40", f"root_surface_intact_{i} >= 1",
           f"root_surface_intact_{i} <= 1", *life_dom)),
        F(f"trmat.Y_X.{material}.{i}", f"Y_X_{i}", "1", size,
          "ISO 6336-3:2019 15.3.3.1 Table 5, PDF51/printed43 checked", ("m_n > 0", *life_dom)),
    ]
    return fs


TR30_MATERIAL_FACTORS = {material: [f for i in (1, 2) for f in _gear_formulas(material, i)]
                         for material in ("Eh", "V")}


def _raw(case, key):
    rows = [r for r in case.get("raw_inputs", ()) if r.get("key") == key]
    if len(rows) != 1:
        raise ValueError(f"TR30 requires one raw input row {key!r}")
    return rows[0]


def _material(value):
    if value == "Eh":
        return "Eh"
    if value == "V (alloy steel)":
        return "V"
    raise NotImplementedError(f"Unsupported material {value!r}")


def material_formulas(case):
    """Select each gear from declared raw inputs, never from factor outputs."""
    materials = _raw(case, "material")["values"]
    pitting = _raw(case, "limited_pitting")["values"]
    if len(materials) != 2 or pitting != ["No", "No"]:
        raise NotImplementedError("TR30 subset requires two declared materials and no permissible pitting")
    for key in ("Z_NT_1e10", "Y_NT_1e10"):
        if _raw(case, key)["values"] != [0.85, 0.85]:
            raise NotImplementedError("TR30 material subset requires the explicitly declared 0.85 long-life endpoints")
    return [f for i, material in enumerate(materials, 1) for f in _gear_formulas(_material(material), i)]


def set_tr30_material_inputs(model, case):
    """Only raw input mapping and visible applicability assumptions."""
    materials = _raw(case, "material")["values"]
    roughness = _raw(case, "roughness_fillet")
    for i, material in enumerate(materials, 1):
        mat = _material(material)
        rz_name = f"Rz_F_{i}"
        if rz_name in model.specs:
            # TR30 input table is Ra (Rz). Use explicitly printed Rz when
            # present, with an independent check of the 4.2.7 conversion.
            text = str(roughness["values"][i-1])
            match = re.match(r"^\s*([+-]?\d+(?:[,.]\d+)?)\s*(?:\(|$)", text)
            if not match:
                raise ValueError(f"Cannot parse declared root Ra from {text!r}")
            ra = float(match.group(1).replace(",", "."))
            bracket = re.search(r"\(\s*([+-]?\d+(?:[,.]\d+)?)\s*\)", text)
            if bracket:
                rz = float(bracket.group(1).replace(",", "."))
                if abs(rz-6*ra) > 1e-10:
                    raise ValueError(f"TR30 printed Ra/Rz inconsistent with 4.2.7: {text!r}")
                model.set(rz_name, rz, "um", "derived",
                          "TR30 printed parenthesized root Rz; independently checked against 4.2.7 Rz=6Ra")
            else:
                model.set(rz_name, 6*ra, "um", "derived", "TR30 raw root Ra; 4.2.7 Rz=6Ra")
        flag = f"root_surface_intact_{i}"
        if flag in model.specs:
            model.set(flag, 1, "1", "assumption",
                      "ISO 6336-3 14.1 model applicability: no >2Rz scratches or detrimental chemical/oxidation effects")
        ys = f"yield_strength_{i}"
        if mat == "V" and ys in model.specs:
            row = _raw(case, "yield_strength")
            value = row["values"][i-1]
            if value is None:
                raise ValueError(f"Missing declared {ys}")
            model.set(ys, value, row["unit"], "user", f"TR30 raw yield strength {row['citation']}")
    set_root_constants(model)
    if "root_MPa" in model.specs:
        model.set("root_MPa", 1, "MPa", "standard_constant", "Definition of MPa unit")
    return model
