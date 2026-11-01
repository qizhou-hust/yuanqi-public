"""ISO 6336:2019 nitrided (NT, NV nitr.) reference/long-life subset.

No nitrocarburized branch or finite-life figure digitization is implied.
"""
from ..kernel.graph import Formula

LIFE = [Formula(f"nitrided.Z_NT.{i}", f"Z_NT_{i}", "1",
    f"exp(log(N_L_{i}/2e6)*log(0.85)/log(1e10/2e6))",
    "ISO 6336-2:2019 Table 5, Figure 6 curve 3, PDF31; 0.85 endpoint selected",
    (f"N_L_{i} >= 2e6", f"N_L_{i} <= 1e10")) for i in (1, 2)] + [
    Formula(f"nitrided.Y_NT.{i}", f"Y_NT_{i}", "1",
    f"exp(log(N_L_{i}/3e6)*log(0.85)/log(1e10/3e6))",
    "ISO 6336-3:2019 Table 3, Figure 11 curve 3, PDF39-40; 0.85 endpoint selected",
    (f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10")) for i in (1, 2)]

NOTCH = [Formula(f"nitrided.Y_drelT.{i}", f"Y_drelT_{i}", "1",
    f"(1 + sqrt(0.1005*0.2*(1 + 2*qs_{i})))/(1 + sqrt(0.1005*1.2))",
    "ISO 6336-3:2019 (75)-(77), Table 4 item 3, PDF41",
    (f"qs_{i} >= 1", f"qs_{i} < 8", f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10")) for i in (1, 2)]

ROUGHNESS = [Formula(f"nitrided.Y_RrelT.{i}", f"Y_RrelT_{i}", "1",
    f"where(Rz_F_{i}/root_um < 1, 1.025, 4.299 - 3.259*(Rz_F_{i}/root_um + 1)**0.005)",
    "ISO 6336-3:2019 (86)(89), PDF48-49",
    (f"Rz_F_{i} > 0", f"Rz_F_{i}/root_um <= 40", f"root_surface_intact_{i} >= 1", f"root_surface_intact_{i} <= 1", f"N_L_{i} >= 3e6", f"N_L_{i} <= 1e10")) for i in (1, 2)]

# Separate IDs preserve one selector condition per registry record.
from dataclasses import replace
from .root_factors import ROOT_FACTORS
SIZE = [replace(f, id="nitrided." + f.id,
                note=f.note.replace("Case-hardened", "NT/NV nitrided") + "; NT/NV nitrided reference branch")
        for f in ROOT_FACTORS if f.output.startswith("Y_X")]
