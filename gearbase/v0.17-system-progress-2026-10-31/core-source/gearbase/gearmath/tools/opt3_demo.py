"""v0.15 OPT3 演示（生成 output/m34/opt3/）：
  1. 单目标闭环 + 统一报告：K01 局部精修（tip_shortening=none / kisssoft_auto_equivalent）、K02、K04（系数重算版）；
  2. 齿顶缩短口径对 KISSsoft P5-A/P5-B 回归；
  3. M39 多目标：K01 ε-约束（体积主目标，S_F 下限扫描），每点统一校核复核 + S_intS（ISO/TS 6336-21，P3 实际输入）；
  4. design_store 文件存储：父文档导入 → 优化修订（父哈希链），修订历史。
运行：python3 -I -c "import sys; sys.path.insert(0, '.'); from gearmath.tools.opt3_demo import main; main()" [all|k01|k02|k04|pareto|store]
"""
from __future__ import annotations

import json
import shutil
import sys

from ..gear import factor_recompute as FR
from ..gear import opt_report as OR
from ..gear import source_multiobj as MO
from ..gear import source_optimize as SO
from ..gear import tip_shortening_p5 as TP
from . import design_store as DS
from .declared_tool import _clean

OUT = SO.ROOT / "output" / "m34" / "opt3"
RUNS = {"k01": [("K01-spur-recompute-local", "K01-spur.factors"), ("K01-spur-recompute-local-kxauto", "K01-spur.factors")],
        "k02": [("K02-helical-min-volume-recompute", "K02-helical.factors")],
        "k04": [("K04-EV-stage1-min-volume-recompute", "K04-EV-stage1.factors")]}
PARETO_SCAN = {"quantities": ["S_F_1", "S_F_2"], "unit": "1", "sense": ">=", "levels": [1.40, 1.45, 1.50, 1.55, 1.60],
               "source": "代理提议（agent_proposed）：ε 列表 1.40（= 文档 S_Fmin）…1.60，步长 0.05，演示用", "tag": "epsSF",
               "front_quantity": "S_F_min"}


def _dump(path, obj):
    path.write_text(json.dumps(_clean(obj), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def single(decl_id, doc_id):
    doc, decl = FR.load_doc(doc_id), SO.load_declaration(decl_id)
    rep = SO.optimize_source(doc, decl)
    ur = OR.unified_report(rep, decl, doc)
    new = rep.pop("new_document", None)
    rep["new_document_id"] = new["id"] if new else None
    _dump(OUT / f"{decl_id}.run.json", rep)
    _dump(OUT / f"{decl_id}.report.json", ur)
    (OUT / f"{decl_id}.report.md").write_text(OR.render_markdown(ur) + "\n", encoding="utf-8")
    if new:
        _dump(OUT / f"{new['id']}.math-source.json", new)
    print(decl_id, rep["status"], rep.get("snap", {}).get("x"), f"{rep['wall_time_s']:.1f}s")
    return rep, new, decl, doc


def pareto():
    doc, decl = FR.load_doc("K01-spur.factors"), SO.load_declaration("K01-spur-recompute-local")
    res = MO.pareto_epsilon(doc, decl, PARETO_SCAN, sints=MO.sints_spec_from_kisssoft_p3("P3-K01-spur"))
    for p in res["points"]:
        new = p.pop("new_document", None)
        if new:
            _dump(OUT / f"{new['id']}.math-source.json", new)
    _dump(OUT / "K01-pareto-epsSF.json", res)
    L = ["## K01 ε-约束 Pareto（体积 min，S_F,min 下限扫描）", "",
         "| ε | 状态 | z1/z2 | m_n | b | x1 | V_blank (mm³) | S_F,min | S_H1 | S_intS | KKT | 前沿 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in res["points"]:
        x = p.get("x") or {}
        si = (p.get("sints") or {}).get("S_intS")
        L.append(f"| {p['epsilon']:.2f} | {p['status']} | {x.get('z_1')}/{x.get('z_2')} | {x.get('m_n')} | {x.get('b')} | {x.get('x_1')} | "
                 f"{(p['objective'] or float('nan')):.6g} | {(p['S_F_min'] or float('nan')):.5f} | "
                 f"{(p.get('unified_checks') or {}).get('pitting.pinion', float('nan')):.5f} | "
                 f"{'' if si is None else f'{si:.4f}'} | {p.get('kkt_status')} | {'是' if p['epsilon'] in res['front_epsilons'] else '否'} |")
    L += ["", res["method"]]
    for c in res["kkt_caveats"]:
        L.append(f"- ε={c['epsilon']:.2f}：KKT {c['kkt_status']}（求解器终止 {c['termination']}；独立 NNLS 乘子复核 {c['independent_check']}）。"
                 "该点可行且独立统一校核通过，但一阶最优性未由求解器达标：活跃约束数（S_H1 与两条 ε）多于连续变量数（b、x_1），"
                 "约束规范（LICQ）不成立属退化点。")
    (OUT / "K01-pareto-epsSF.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("pareto", res["status"], res["front_epsilons"], f"{res['wall_time_s']:.1f}s")
    return res


def tip():
    c = TP.compare()
    _dump(OUT / "tip-shortening-P5.json", c)
    print("tip", {k: all(r["pass"] for r in v["rows"]) for k, v in c.items()})


def store():
    """文件存储演示：K01 父文档导入 → 局部精修修订（none）。"""
    sd = OUT / "store"
    if sd.exists():
        shutil.rmtree(sd)
    st = DS.FileStore(sd)
    doc, decl = FR.load_doc("K01-spur.factors"), SO.load_declaration("K01-spur-recompute-local")
    rep = json.loads((OUT / "K01-spur-recompute-local.run.json").read_text(encoding="utf-8"))
    new = json.loads((OUT / f"{rep['new_document_id']}.math-source.json").read_text(encoding="utf-8"))
    DS.commit_source(st, "K01", doc, "演示：导入父文档 K01-spur.factors")
    DS.commit_optimization(st, "K01", new, decl, SO.provenance(rep, decl))
    _dump(OUT / "store-history.json", DS.revision_history(st, "K01"))
    print("store", [(r["version"], r["kind"]) for r in DS.revision_history(st, "K01")])


def reports():
    """不重新求解：由存档 run.json + 写回文档重建统一报告（报告格式更新后用）；Pareto 点只重建 KISSsoft 请求片段。"""
    from ..kernel import epsilon as EP
    for k in ("k01", "k02", "k04"):
        for decl_id, doc_id in RUNS[k]:
            f = OUT / f"{decl_id}.run.json"
            if not f.is_file():
                continue
            rep = json.loads(f.read_text(encoding="utf-8"))
            decl = SO.load_declaration(decl_id)
            rep["new_document"] = json.loads((OUT / f"{rep['new_document_id']}.math-source.json").read_text(encoding="utf-8"))
            ur = OR.unified_report(rep, decl, FR.load_doc(doc_id))
            _dump(OUT / f"{decl_id}.report.json", ur)
            (OUT / f"{decl_id}.report.md").write_text(OR.render_markdown(ur) + "\n", encoding="utf-8")
    f = OUT / "K01-pareto-epsSF.json"
    if f.is_file():
        res = json.loads(f.read_text(encoding="utf-8"))
        decl = SO.load_declaration("K01-spur-recompute-local")
        decls = {d["id"]: d for _, d in EP.epsilon_declarations(decl, **{k: res["scan"][k] for k in
                                                                        ("quantities", "unit", "sense", "levels", "source", "tag")})}
        for p in res["points"]:
            if p.get("new_document_id"):
                new = json.loads((OUT / f"{p['new_document_id']}.math-source.json").read_text(encoding="utf-8"))
                p["report"]["kisssoft_request"] = OR.kisssoft_request(new, decls[p["declaration_id"]])
        _dump(f, res)
    print("reports regenerated")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv) or ["all"]
    OUT.mkdir(parents=True, exist_ok=True)
    what = set(argv)
    for k in ("k01", "k02", "k04"):
        if what & {"all", k}:
            for decl_id, doc_id in RUNS[k]:
                single(decl_id, doc_id)
    if what & {"all", "tip"}:
        tip()
    if what & {"all", "store"}:
        store()
    if what & {"all", "pareto"}:
        pareto()
    if "reports" in what:
        reports()


if __name__ == "__main__":
    main()
