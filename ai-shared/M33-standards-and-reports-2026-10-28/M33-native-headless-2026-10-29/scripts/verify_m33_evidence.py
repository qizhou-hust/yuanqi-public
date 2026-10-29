"""Verify saved KISSsoft evidence without changing models or using the UI."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    import fitz
    names = ["ex7-base-native", "ex7-diag-lim", "ex8-Rz2.3"] + [
        f"ex7-life-g{g}-N{n}" for g in (1, 2)
        for n in (100000, 600000, 10000000, 1000000000, 10000000000)
    ]
    checked = []
    for name in names:
        folder = root / name
        run = json.loads((folder / "run.json").read_text(encoding="utf8"))
        assert run["variant"] == name
        assert run["acceptance"] == "NOT_ACCEPTED"
        assert run["calculate_return"] is True
        assert run["reload_calculate_return"] is True
        assert not run["reload_differences"]
        values = run["reload_values"]
        assert len(values) == 1196
        assert values["RechSt.RechenMethID"] == 10029
        source = Path(run["source"])
        source_checked = source.is_file()
        if source_checked:
            assert sha256(source) == run["source_sha256"]
        with (folder / "high-precision-values.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(values)
        assert len({r["variable"] for r in rows}) == len(values)
        for row in rows:
            value = values[row["variable"]]
            if isinstance(value, (int, float)):
                assert math.isfinite(value) and float(row["value"]) == value
            else:
                assert row["value"] == value
        for suffix in (".Z12", ".rtf", ".pdf"):
            assert (folder / (name + suffix)).stat().st_size > 1000
        pdf = fitz.open(folder / (name + ".pdf"))
        text = "\n".join(p.get_text() for p in pdf)
        assert "End of report" in text
        assert "6336:2019" in text
        assert "{ZR[" not in text and "{ZPP[" not in text
        assert "Nominal stress at tooth root" in text
        stress_checks = []
        for g in (0, 1):
            stress = values[f"ZPP[{g}].Fuss.sigF"]
            reconstructed = (values[f"ZPP[{g}].Fuss.sigF0"] * values["ZS.KA"] *
                             values["ZP[0].KV.KV"] * values["ZP[0].KFb"] * values["ZP[0].KFa"])
            relative = abs(reconstructed / stress - 1)
            assert relative < 1e-12
            stress_checks.append({"gear": g + 1, "reported_MPa": stress,
                                  "reconstructed_MPa": reconstructed, "relative_error": relative})
        if name == "ex8-Rz2.3":
            assert "Protuberance" in text
            for g in (0, 1):
                assert values[f"ZR[{g}].RZH"] == 2.3
                assert values[f"ZR[{g}].RZF"] == 18
                assert values[f"ZPP[{g}].Fuss.YF"] > 0
                assert values[f"ZPP[{g}].Fuss.YS"] > 0
        checked.append({"variant": name, "fields": len(values), "pages": len(pdf),
                        "source_hash_checked_locally": source_checked,
                        "root_stress_reconstruction": stress_checks,
                        "native_sha256": sha256(folder / (name + ".Z12")),
                        "run_sha256": sha256(folder / "run.json")})
        pdf.close()
    life = json.loads((root / "life-curve.json").read_text(encoding="utf8"))
    assert len(life) == 10
    for row in life:
        assert math.isclose(row["actual_cycles"], row["target_cycles"], rel_tol=1e-10)
    return {"schema": "m33.saved_evidence_verification.v1", "evidence_integrity_pass": True,
            "accepted": False, "formal_gate": "BLOCKED_INPUT_IDENTITY",
            "valid_variants": len(checked), "total_pdf_pages": sum(r["pages"] for r in checked),
            "life_points": len(life), "checks": checked,
            "limit": "Checks saved artifacts and stress reconstruction. Does not certify original-table input identity or source settings."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.root)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}, ensure_ascii=False))
