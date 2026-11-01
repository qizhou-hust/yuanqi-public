"""Explicit K01 long-life curves, checked against ISO 6336:2019 page images.

Only the case-hardened, Normal/0.85-at-1e10 branch is supplied.  Selecting
this branch is a material/curve decision, not an implicit material default.
No finite-life interpolation, fatigue plateau, or extrapolation is inferred.
"""
from __future__ import annotations

from ..kernel.graph import Formula, InputSpec

F, S = Formula, InputSpec

SOURCE_STATUS = "iso_original_images_checked_selected_branch"
SOURCE_AUDIT = {
    "ISO 6336-2:2019": {
        "sha256": "5e7a4b83c2d91292f6ddce324ea2fee16699b1c385d80b76606fec6b459de5b0",
        "pdf_pages": [20, 21, 30, 31], "printed_pages": [12, 13, 22, 23],
        "references": ["5.4.4.3 and Figure 1", "11.3", "Figure 6 curve 2", "Table 5 and footnote a"],
    },
    "ISO 6336-3:2019": {
        "sha256": "f00fea96b736a1d0d34e71496afc3338982d4bc8613571a6c882aae2fe89cf04",
        "pdf_pages": [21, 22, 38, 39], "printed_pages": [13, 14, 30, 31],
        "references": ["5.4.4.3 and Figure 1", "12.3.3", "Figure 11 curve 2", "Table 3 and footnote a"],
    },
}
LIFE_METHOD = "case_hardened_085_long_life"

LIFE_INPUTS = [
    S(f"N_L_{i}", "1", f"Load cycles, gear {i}", (f"N_L_{i} > 0",))
    for i in (1, 2)
]

LIFE_FACTORS = [
    F(f"life.Z_NT.{i}", f"Z_NT_{i}", "1",
      f"exp(log(N_L_{i}/5e7)*log(0.85)/log(1e10/5e7))",
      "ISO 6336-2:2019 11.3 Figure 6 curve 2, Table 5 footnote a; PDF31/printed23 image checked",
      (f"N_L_{i} >= 5e7", f"N_L_{i} <= 1e10"),
      note="Case-hardened steel, no pitting permitted, 0.85 explicitly selected at 1e10; not a default or other-curve claim")
    for i in (1, 2)
] + [
    F(f"life.Y_NT.{i}", f"Y_NT_{i}", "1",
      f"exp(log(N_L_{i}/3e6)*log(0.85)/log(1e10/3e6))",
      "ISO 6336-3:2019 12.3.3 Figure 11 curve 2, Table 3 footnote a; PDF39/printed31 image checked",
      (f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10"),
      note="Case-hardened steel, 0.85 explicitly selected at 1e10; compatible with K01 2006 Normal option, not a default")
    for i in (1, 2)
]

LIFE_VARIANTS = {LIFE_METHOD: LIFE_FACTORS}

# Optional operating-condition calculation.  Curve-only models may instead
# declare N_L_i as an independently specified input.  They cannot do both.
CYCLE_INPUTS = [
    S("life_duration", "s", "Duration under the declared constant operating condition",
      ("life_duration > 0",)),
    *[S(f"cycles_per_rev_{i}", "1", f"Load applications per revolution, gear {i}",
        (f"cycles_per_rev_{i} > 0",)) for i in (1, 2)],
]
LIFE_CYCLES = [
    F("life.N_L.1", "N_L_1", "1", "n_1*life_duration*cycles_per_rev_1",
      "Operating-condition identity; rotational frequency is canonical 1/s"),
    F("life.N_L.2", "N_L_2", "1", "n_1/u*life_duration*cycles_per_rev_2",
      "Operating-condition identity; n2=n1/u, external constant-ratio pair"),
]
