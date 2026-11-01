"""M34 主线演示：真源 v2 → 声明 → 剪枝格搜索 + NLP → 回写 → 统一校核复核（C001、K01），以及 H2 旗舰最小回归。

用法（仓库根目录）：python3 -I -c "import sys; sys.path.insert(0, '.'); from gearmath.tools.m34_demo import main; main()" [C001|K01|C001R|K01R|H2 ...] [--out output/m34] [--leaf-subboxes 8]
输出：<out>/<新文档 id>.math-source.json（新真源修订）与 <out>/<声明 id>.run.json（运行报告，含 assurance 四项）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from ..gear import math_source as MS
from ..gear import source_optimize as SO
from ..kernel import gridprune as GP

CASES = {"C001": ("C001-G1-min-volume", lambda: MS.load_file()),
         "K01": ("K01-spur-min-volume", lambda: __import__("gearmath.gear.math_source_kisssoft",
                                                             fromlist=["load_doc"]).load_doc("K01-spur")),
         # v0.14 OPT2：系数随几何重算的修订文档 + 带 hold_rationale 的声明
         "K01R": ("K01-spur-min-volume-recompute", lambda: __import__("gearmath.gear.factor_recompute",
                                                                       fromlist=["load_doc"]).load_doc("K01-spur.factors")),
         "C001R": ("C001-G1-min-volume-recompute", lambda: __import__("gearmath.gear.factor_recompute",
                                                                       fromlist=["load_doc"]).load_doc("C001.factors"))}


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float):
        return o if o == o and abs(o) != float("inf") else None
    if o is None or isinstance(o, (bool, int, str)):
        return o
    return str(o)


def run_case(key, out, leaf_subboxes):
    name, load = CASES[key]
    doc, decl = load(), SO.load_declaration(name)
    rep = SO.optimize_source(doc, decl, leaf_subboxes=leaf_subboxes)
    new = rep.pop("new_document")
    if new is not None:
        (out / f"{new['id']}.math-source.json").write_text(json.dumps(new, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                                            encoding="utf-8")
        rep["new_document_id"] = new["id"]
    rep["leaf_subboxes"] = leaf_subboxes
    (out / f"{name}.run.json").write_text(json.dumps(_clean(rep), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return rep


def run_h2(out):
    from ..gear import h2_flagship as H
    from ..kernel import optimize as OPT
    decl = SO.load_declaration("H2-flagship-geometry")
    p, b, ev = H.compile_h2(decl)
    t0 = time.perf_counter()
    r = GP.pruned_lattice_search(p, b, keep_records=True)
    ties = [x["assignment"] for x in r["records"] if x["feasible"] and x["value"] == r["best"]["value"]]
    g = OPT._evaluate(p, H.GOLDEN)
    rep = {"declaration_id": decl["id"], "wall_time_s": time.perf_counter() - t0,
           "search": {k: r[k] for k in ("lattice_points_total", "points_pruned", "pruned_points_by_reason", "leaves_solved",
                                        "interval_bound_calls", "nodes_visited")},
           "best": {"x": r["best"]["assignment"], "ratio_error": r["best"]["value"], "beta_deg": H.beta_deg(r["best"]["assignment"], ev)},
           "zero_error_designs_found": len(ties), "golden": H.GOLDEN, "golden_in_optimal_set": H.GOLDEN in ties,
           "golden_feasible": g.feasible, "golden_ratio_error": g.objectives["ratio_error"],
           "golden_beta_deg": H.beta_deg(H.GOLDEN, ev), "assurance": r["assurance"], "solver": r["solver"]}
    (out / "H2-flagship-geometry.run.json").write_text(json.dumps(_clean(rep), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*", default=["C001", "K01", "H2"])
    ap.add_argument("--out", default=str(SO.ROOT / "output" / "m34"))
    ap.add_argument("--leaf-subboxes", type=int, default=8)
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for c in a.cases:
        t0 = time.perf_counter()
        rep = run_h2(out) if c == "H2" else run_case(c, out, a.leaf_subboxes)
        s = rep["search"]
        print(f"{c}: {rep.get('status', '')} 格点 {s['lattice_points_total']} 剪 {s['points_pruned']} 解 {s['leaves_solved']} "
              f"用时 {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
