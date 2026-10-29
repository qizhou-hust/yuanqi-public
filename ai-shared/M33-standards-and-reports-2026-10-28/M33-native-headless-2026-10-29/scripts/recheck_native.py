"""Reload one saved variant through headless COM; never save over the model.

Usage: python recheck_native.py PATH_TO_VARIANT --output recheck.json
Requires licensed KISSsoft 2026 and pywin32 on Windows.
"""
import argparse
import json
import math
from pathlib import Path
import win32com.client


def check(folder):
    run = json.loads((folder / "run.json").read_text(encoding="utf8"))
    native = folder / (run["variant"] + ".Z12")
    kiss = win32com.client.Dispatch("KISSsoftCOM2026.KISSsoft")
    kiss.GetModule("Z012", False)
    kiss.SetSilentMode(True)
    try:
        kiss.LoadFile(str(native.resolve()))
        ok = bool(kiss.CalculateRetVal())
        differences = {}
        for field, expected in run["reload_values"].items():
            actual = kiss.GetVar(field)
            try:
                actual = float(actual)
            except (ValueError, TypeError):
                pass
            equal = (math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
                     if isinstance(actual, float) and isinstance(expected, (int, float))
                     else actual == expected)
            if not equal:
                differences[field] = {"saved": expected, "reloaded": actual}
        return {"variant": run["variant"], "calculate_return": ok,
                "messages": kiss.Message(), "checked_fields": len(run["reload_values"]),
                "differences": differences, "accepted": False,
                "native_file_modified": False, "interface_requested": False}
    finally:
        kiss.ReleaseModule()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = check(args.folder)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(result["variant"], "calculated", result["calculate_return"], "differences", len(result["differences"]))
    raise SystemExit(0 if result["calculate_return"] and not result["differences"] else 2)
