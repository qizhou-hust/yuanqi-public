"""Offline verification of source copies, supplied reports and TR30 page assembly."""
from pathlib import Path
import hashlib
import json
import fitz

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = []
    inventory = json.loads((ROOT / "verification/local-standards-inventory.json").read_text(encoding="utf-8"))
    for row in inventory:
        matches = [p for p in (ROOT / "standards").rglob(row["name"]) if p.is_file()]
        checks.append({"check": "source_copy_hash", "file": row["name"], "pass": len(matches) == 1 and sha(matches[0]) == row["sha256"]})
    prov = json.loads((ROOT / "verification/page-repair-provenance.json").read_text(encoding="utf-8"))
    original = fitz.open(ROOT / prov["source"])
    amended = fitz.open(ROOT / prov["output"])
    preview = fitz.open(ROOT / prov["preview"])
    preserved = []
    for i in range(len(original)):
        old = original[i].get_pixmap()
        new = amended[i if i < 7 else i + 1].get_pixmap()
        preserved.append(old.digest == new.digest)
    a = amended[7].get_pixmap()
    b = preview[7].get_pixmap()
    checks.append({"check": "TR30_page_repair", "pass": len(amended) == 70 and all(preserved) and a.digest == b.digest,
                   "original_pages_unchanged": sum(preserved), "total_original_pages": len(original), "inserted_page_identical": a.digest == b.digest})
    summary = json.loads((ROOT / "verification/kisssoft-run-summary.json").read_text(encoding="utf-8"))
    for case in summary["cases"]:
        stem = ROOT / "reports" / case["id"] / case["id"]
        pdf = fitz.open(stem.with_suffix(".pdf"))
        txt = "\n".join(p.get_text() for p in pdf)
        for p in pdf:
            p.get_pixmap(matrix=fitz.Matrix(.4, .4))
        checks.append({"check": "KISSsoft_report_and_native", "case": case["id"], "pages": len(pdf),
                       "pass": all([case["evidence_ready"], not case["get_errors"], not case["reload_errors"],
                                    sha(stem.with_suffix(".Z12")) == case["native_sha256"],
                                    "ISO 6336:2019" in txt, "Tooth root stress" in txt, "Contact stress" in txt,
                                    "End of report" in txt, "<EXECUTE=" not in txt])})
    standard_results = json.loads((ROOT / "verification/standards-validation.json").read_text(encoding="utf-8"))
    checks.append({"check": "six_core_standard_page_sequences", "pass": len(standard_results) == 6 and all(x["sequence_verified"] for x in standard_results)})
    manifest_path = ROOT / "SHA256SUMS.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bad = [name for name, expected in manifest.items() if not (ROOT / name).exists() or sha(ROOT / name) != expected]
        checks.append({"check": "manifest_hashes", "files": len(manifest), "pass": not bad, "mismatches": bad})
    status = {"status": "PASS" if all(x["pass"] for x in checks) else "FAIL", "checks": checks,
              "boundary": "Evidence-file readiness only; no claim of gearmath numerical agreement or product approval."}
    (ROOT / "verification/final-validation.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if status["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
