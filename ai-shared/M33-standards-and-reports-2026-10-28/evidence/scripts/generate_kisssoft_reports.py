"""Generate original KISSsoft ISO 6336:2019 reports from installed vendor examples.

Run with Python + pywin32 + PyMuPDF; requires KISSsoft 2026 and Microsoft Word.
No project engine, legacy code or manually supplied rating factors are used.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import shutil

import fitz
import win32api
import win32com.client

ROOT = Path(__file__).resolve().parents[1]
INSTALL = Path(r"D:\Program Files\KISSsoft AG\KISSsoft 2026")
CASES = [
    ("K01-spur", "01 Spur (ISO 6336).Z12"),
    ("K02-helical", "06 Helical (DIN 3990).Z12"),
    ("K03-premachining", "09 Spur With Premachining (Grinding).Z12"),
    ("K04-EV-stage1", "19 Helical (EV S1).Z12"),
    ("K05-EV-stage2", "20 Helical (EV S2).Z12"),
]
GLOBAL = [
    "RechSt.RechenMethID", "RechSt.RechenMeth", "RechSt.GeometrieMeth",
    "ZS.Geo.mn", "ZS.Geo.alfn", "ZS.Geo.beta", "ZS.KA", "ZS.H", "ZS.Pnominal",
    "Zst.KVFlag", "Zst.KHaFlag", "Zst.KHbVariant", "Zst.KwbVariant",
    "ZP[0].a", "ZP[0].alfwt", "ZP[0].Ft", "ZP[0].Eps.a", "ZP[0].Eps.b",
    "ZP[0].Eps.G", "ZP[0].KV.KV", "ZP[0].KHa", "ZP[0].KFa",
    "ZP[0].KHb", "ZP[0].KFb", "ZP[0].Flanke.ZH", "ZP[0].Flanke.Zeps",
    "ZP[0].Flanke.Zbet", "ZP[0].Flanke.sigH0", "ZP[0].Flanke.sigH",
    "ZP[0].Fuss.Ybet", "ZP[0].Fuss.YDT", "ZS.Yst",
]
GEAR = [
    "z", "x.nul", "b", "d", "da.nul", "df.nul", "nnominal", "Tnominal", "Qpre",
    "kFlag", "kFaktorFlag", "kXmn", "Ca", "Cf", "crowning", "mat.E", "mat.ny",
    "mat.limh", "mat.limf", "Tool.type", "Tool.RefProfile.DBID",
    "Tool.RefProfile.haP", "Tool.RefProfile.hfP", "Tool.RefProfile.rhofP",
    "Fuss.YB", "Fuss.YNT", "Fuss.Kwb", "Fuss.YR", "Fuss.YX", "Flanke.ZNT", "Flanke.ZX",
]
MEMBER = [
    "Fuss.YF", "Fuss.YS", "Fuss.hF", "Fuss.sFn", "Fuss.roF", "Fuss.Ydrel",
    "Fuss.sigF0", "Fuss.sigF", "Fuss.sigFP", "Fuss.SFnorm",
    "Flanke.ZBD", "Flanke.ZL", "Flanke.ZV", "Flanke.ZR", "Flanke.ZW",
    "Flanke.sigHBD", "Flanke.sigHP", "Flanke.SH", "Flanke.SHw",
]
FIELDS = GLOBAL + [f"ZR[{i}].{v}" for i in (0, 1) for v in GEAR] + [f"ZPP[{i}].{v}" for i in (0, 1) for v in MEMBER]
REQUIRED = ["ZP[0].Flanke.sigH"] + [f"ZPP[{i}].{v}" for i in (0, 1) for v in ("Fuss.sigF", "Fuss.SFnorm", "Flanke.SH")]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def values(k):
    result, errors = {}, {}
    for name in FIELDS:
        try:
            raw = k.GetVar(name)
            try:
                result[name] = float(raw)
            except (ValueError, TypeError):
                result[name] = raw
        except Exception as exc:
            errors[name] = str(exc)
    return result, errors


def messages(k):
    strings, types, count = k.Message()
    return {"strings": list(strings), "types": list(types), "count": count}


def main():
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    software = {"progid": "KISSsoftCOM2026.KISSsoft", "module": "Z012", "report_template": "Z012Le0.RPT",
                "report_template_sha256": sha(INSTALL / "rpt" / "Z012Le0.RPT"),
                "standard": "ISO 6336:2019", "geometry_edition": "Preserved from each vendor example; see report and RechSt.GeometrieMeth",
                "units": {"length": "mm", "angle_COM": "rad", "angle_report": "deg", "torque": "Nm", "speed": "rpm", "stress": "N/mm2", "life": "h"}}
    vi = win32api.GetFileVersionInfo(str(INSTALL / "bin" / "KISSsoft.exe"), "\\")
    software["file_version"] = ".".join(str(x) for x in (vi["FileVersionMS"] >> 16, vi["FileVersionMS"] & 65535, vi["FileVersionLS"] >> 16, vi["FileVersionLS"] & 65535))
    records = []
    k = win32com.client.Dispatch(software["progid"])
    try:
        k.GetModule("Z012", False)
        k.SetSilentMode(True)
        k.SetLanguage(1)
        software["runtime_version"] = k.GetKsoftVersion()
        software["module_license_check"] = bool(k.CheckLicense("Z012"))
        for case_id, filename in CASES:
            folder = reports / case_id
            folder.mkdir(exist_ok=True)
            source = INSTALL / "example" / filename
            shutil.copy2(source, folder / "source-example.Z12")
            k.LoadFile(str(source))
            before = k.GetVar("RechSt.RechenMethID")
            edits = []
            if before != "10029":
                k.SetVar("RechSt.RechenMethID", "10029")
                edits.append({"variable": "RechSt.RechenMethID", "before": before, "after": "10029", "reason": "Align strength calculation with the M33 ISO 6336:2019 contract"})
            ok = bool(k.CalculateRetVal())
            msg = messages(k)
            output, get_errors = values(k)
            native = folder / (case_id + ".Z12")
            k.SaveFile(str(native))
            # Type 0 expands report directives. Types 1/10/20 retain raw directives
            # for this template in KISSsoft 2026 and must not be used as full reports.
            k.ReportWithParameters("Z012Le0.RPT", str(folder / (case_id + ".rtf")), 0, 0)
            k.ReportWithParameters("Z012Le0.RPT", str(folder / (case_id + ".html")), 0, 2)
            k.LoadFile(str(native))
            reload_ok = bool(k.CalculateRetVal())
            reload_msg = messages(k)
            readback, reload_errors = values(k)
            differences = {}
            for name, value in output.items():
                other = readback.get(name)
                same = math.isclose(value, other, rel_tol=1e-9, abs_tol=1e-10) if isinstance(value, float) and isinstance(other, float) else value == other
                if not same:
                    differences[name] = {"before_save": value, "after_reload": other}
            record = {"id": case_id, "generated_utc": datetime.now(timezone.utc).isoformat(), "source": str(source),
                      "source_sha256": sha(source), "native_sha256": sha(native), "edits": edits,
                      "software": software, "calculate_return": ok, "messages": msg,
                      "values": output, "get_errors": get_errors, "reload_calculate_return": reload_ok,
                      "reload_messages": reload_msg, "reload_errors": reload_errors, "reload_differences": differences,
                      "required_results_positive_finite": all(isinstance(output.get(n), float) and math.isfinite(output[n]) and output[n] > 0 for n in REQUIRED),
                      "scope": "Installed vendor example rerun locally; not an ISO/TR 6336-30 worked example, not a product approval, not a gearmath comparison"}
            dump(folder / (case_id + ".json"), record)
            records.append(record)
            print(json.dumps({"id": case_id, "calculate_ok": ok, "warnings": msg, "reload_ok": reload_ok, "differences": differences, "read_errors": get_errors}), flush=True)
    finally:
        k.ReleaseModule()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        for record in records:
            stem = reports / record["id"] / record["id"]
            doc = word.Documents.Open(str(stem.with_suffix(".rtf")), ReadOnly=True, AddToRecentFiles=False)
            try:
                doc.ExportAsFixedFormat(str(stem.with_suffix(".pdf")), 17)
            finally:
                doc.Close(False)
            pdf = fitz.open(stem.with_suffix(".pdf"))
            text = "\n".join(p.get_text() for p in pdf)
            stem.with_suffix(".extracted.txt").write_text(text, encoding="utf-8")
            record["report_validation"] = {"pages": len(pdf), "text_characters": len(text),
                "contains_ISO_2019": "ISO 6336:2019" in text,
                "contains_root_stress": "Tooth root stress" in text,
                "contains_contact_stress": "Contact stress" in text,
                "contains_safety_factors": "Safety factors" in text,
                "contains_end_of_report": "End of report" in text,
                "unexpanded_template_directives": "<EXECUTE=" in text or "1IF (" in text}
            record["evidence_ready"] = all([record["calculate_return"], record["reload_calculate_return"], record["required_results_positive_finite"], not record["reload_differences"], record["values"]["RechSt.RechenMethID"] == 10029, all(record["report_validation"][key] for key in ("contains_ISO_2019", "contains_root_stress", "contains_contact_stress", "contains_safety_factors", "contains_end_of_report")), not record["report_validation"]["unexpanded_template_directives"]])
            dump(stem.with_suffix(".json"), record)
            print(json.dumps({"id": record["id"], "evidence_ready": record["evidence_ready"], "report_validation": record["report_validation"]}), flush=True)
    finally:
        word.Quit()
    dump(ROOT / "verification" / "kisssoft-run-summary.json", {"software": software, "cases": records, "all_five_ready": len(records) == 5 and all(x["evidence_ready"] for x in records)})


if __name__ == "__main__":
    main()
