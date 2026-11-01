"""Reproduce the bounded M39 front/scenario evidence and original-gate blockers.

Run: python -m gearmath.tools.m39_frontier --out <directory>
The finite axes/tolerances are authored software probes of the existing K01
problem; they are not supplier tolerance data or an approved production design.
"""
from __future__ import annotations

import argparse
import json
import pathlib

from ..gear import factor_recompute as FR
from ..gear import source_frontier as SF
from ..gear import source_optimize as SO
from ..product import design_check as DC


def authored_spec():
    zeros = {"z_1": 0, "z_2": 0, "m_n": 0, "b": 0, "x_1": 0}
    return {
        "source": "authored software capability probe: finite subset of existing "
                  "K01-spur-recompute-local-kxauto axes; existing agent_proposed ranges/constraints retained; "
                  "no production authorization or measured tolerance claimed",
        "axes": {"z_1": [23, 24], "z_2": [68, 72], "m_n": [6.0], "b": [36.0, 44.0, 52.0], "x_1": [0.25]},
        "tolerance_scenarios": [
            {"id": "nominal", "source": "explicit nominal scenario", "offsets": zeros},
            {"id": "lower", "source": "authored capability scenario: b -0.1 mm, x1 -0.001; not measured tolerance",
             "offsets": {**zeros, "b": -0.1, "x_1": -0.001}},
            {"id": "upper", "source": "authored capability scenario: b +0.1 mm, x1 +0.001; not measured tolerance",
             "offsets": {**zeros, "b": 0.1, "x_1": 0.001}}]}


def baseline():
    out = {}
    for case in ("C001", "K01-spur"):
        r = DC.check_files(case, case, "all")
        out[case] = {"source": f"data/source/{case}.math-source.json",
                     "system_input": f"data/system/{case}.system-input.json",
                     "result": r}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=pathlib.Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    doc = FR.load_doc("K01-spur.factors")
    decl = SO.load_declaration("K01-spur-recompute-local-kxauto")
    spec = authored_spec()
    report = SF.finite_frontier(doc, decl, spec)
    for name, value in (("frontier.json", report), ("source.json", doc), ("declaration.json", decl),
                        ("spec.json", spec), ("baseline.json", baseline())):
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "coverage": report["coverage"], "front": report["front"],
                      "frontier_current": SF.is_current(report, doc, decl, spec)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
