"""v0.15 OPT3：齿顶缩短几何口径选择器（adapter.tip_shortening）对 KISSsoft P5 的外部回归。

口径来源（ISO 21771 原文不在本环境，未核原文；只按 KISSsoft 证据定义"等效口径"）：
  - P5-A（kFaktorFlag=true、kXmn=0，轴 88/8.8/44 mm 显式）↔ tip_shortening = none；
  - P5-B（只改几何/中心距，KISSsoft 自动 kXmn=−0.019 mm、轴自动 57.2/5.72/28.6 mm）↔ tip_shortening = kisssoft_auto_equivalent，
    k·m_n = a_w − a − (x_1 + x_2)·m_n = −0.019090 mm；KISSsoft 圆整到 0.001 mm（da 155.35/416.98），本库不圆整。
两例的设计输入（z 23/68、m_n 6、b 28.6、x_1 0.449、a 274.1839 mm）即 v0.14 OPT2 K01 系数重算版最优解
（output/m34/K01-spur.factors.opt-36f05481.math-source.json），逐字段对齐后比较。

私有证据只提取最小 JSON（data/kisssoft_v015/OPT3-P5-tip.json：字段、值、来源相对路径与 sha256），不复制原生文件。
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib

from ..kernel import units as U
from . import math_source as MS

ROOT = MS.ROOT
PRIVATE = pathlib.Path("/home/claude/private_ks15")
DATA = ROOT / "data" / "kisssoft_v015" / "OPT3-P5-tip.json"
SCHEMA = "gearbase.kisssoft_v015.opt3_p5_tip/1"
CASES = {"P5-A": ("cases/P5-A-tip-coefficient-input/run.json", "none"),
         "P5-B": ("cases/P5-B-auto/run.json", "kisssoft_auto_equivalent")}
OPT_DOC = ROOT / "output" / "m34" / "K01-spur.factors.opt-36f05481.math-source.json"
FIELDS = ("ZR[0].kXmn", "ZR[1].kXmn", "ZR[0].da.nul", "ZR[1].da.nul", "ZR[0].kFaktorFlag", "ZR[1].kFaktorFlag",
          "ZP[0].a", "ZP[0].Eps.a", "ZPP[0].Flanke.SH", "ZPP[1].Flanke.SH", "ZPP[0].Fuss.SFnorm", "ZPP[1].Fuss.SFnorm",
          "ZP[0].KHdat.l", "ZP[0].KHdat.S", "ZP[0].KHdat.dsh", "Zst.lsdFlag")
# 本库量 ↔ KISSsoft 字段（单位）
COMPARE = (("k_X_1", "ZR[0].kXmn", "mm"), ("k_X_2", "ZR[1].kXmn", "mm"), ("da_1", "ZR[0].da.nul", "mm"),
           ("da_2", "ZR[1].da.nul", "mm"), ("a_w", "ZP[0].a", "mm"), ("eps_alpha", "ZP[0].Eps.a", "1"),
           ("S_H_1", "ZPP[0].Flanke.SH", "1"), ("S_H_2", "ZPP[1].Flanke.SH", "1"),
           ("S_F_1", "ZPP[0].Fuss.SFnorm", "1"), ("S_F_2", "ZPP[1].Fuss.SFnorm", "1"))
# 门限：k·m_n、d_a 按 KISSsoft 0.001 mm 圆整半格；ε_α none 例逐位（同输入同式），auto 例含圆整影响；
# S_H/S_F 沿用 P2 归因（Z_V/Z_R 已知差异 ≤ 1.5e-5，见 docs/M34-系数对账-P2.md）
GATES = {"k_X_1": ("abs", 5e-4), "k_X_2": ("abs", 5e-4), "da_1": ("abs", 1e-3), "da_2": ("abs", 1e-3),
         "a_w": ("rel", 1e-12), "eps_alpha": ("rel", 3e-5), "S_H_1": ("rel", 1e-5), "S_H_2": ("rel", 1e-5),
         "S_F_1": ("rel", 3e-5), "S_F_2": ("rel", 3e-5)}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def extract(private_root=PRIVATE):
    """私有 run.json → 最小 JSON（只取 FIELDS 与编辑记录）。"""
    out = {"schema": SCHEMA, "note": "KISSsoft 2026（26.0.0.0）P5 运行记录的最小提取；私有资料，不外传。"
                                     "accepted=false：用户未改 gearbase 接受状态；只作齿顶缩短口径回归。",
           "cases": {}}
    for cid, (rel, tip) in CASES.items():
        p = pathlib.Path(private_root) / rel
        d = json.loads(p.read_text(encoding="utf-8"))
        out["cases"][cid] = {
            "source": rel, "sha256": _sha(p), "source_model_sha256": d["source_sha256"], "module": d["module"],
            "file_version": d["file_version"], "accepted": d["accepted"],
            "fresh_headless_module_ok": d["fresh_headless_module_ok"], "tip_shortening_equivalent": tip,
            "edits": [{"field": e["field"], "readback": e["readback"]} for e in d["edits"]],
            "values": {k: d["values"][k] for k in FIELDS}}
    return out


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def _shaft(case):
    v = case["values"]
    return {"l_sh": v["ZP[0].KHdat.l"], "s_sh": v["ZP[0].KHdat.S"], "d_sh": v["ZP[0].KHdat.dsh"]}


def alignment(doc, case):
    """KISSsoft 编辑（输入）与文档输入逐字段对齐。"""
    rb = {e["field"]: e["readback"] for e in case["edits"]}
    rows = []
    for name, field in (("z_1", "ZR[0].z"), ("z_2", "ZR[1].z"), ("m_n", "ZS.Geo.mn"), ("b", "ZR[0].b"), ("x_1", "ZR[0].x.nul")):
        row = doc["inputs"][name]
        mine = U.from_canonical(U.to_canonical(row["value"], row["unit"]), "mm") if row["unit"] == "mm" else row["value"]
        rows.append({"input": name, "gearbase": mine, "kisssoft_field": field, "kisssoft": rb[field],
                     "identical": abs(mine - rb[field]) <= 1e-12 * max(1.0, abs(mine))})
    return rows


def compare(doc=None, data=None):
    """每例：文档 + adapter.tip_shortening（按例的等效口径）+ 该例小轮轴输入 → 本库值 vs KISSsoft。"""
    from .source_optimize import build_family_model, with_tip_formulas
    doc = doc or json.loads(OPT_DOC.read_text(encoding="utf-8"))
    data = data or load()
    out = {}
    for cid, case in data["cases"].items():
        d = copy.deepcopy(doc)
        d["selectors"]["adapter.tip_shortening"] = {"value": case["tip_shortening_equivalent"],
                                                    "source": f"回归：KISSsoft {cid} 等效口径"}
        m = build_family_model(d, "kisssoft_chain", "K01-spur")
        for n, v in _shaft(case).items():
            m.set(n, v, "mm", "assumption", f"KISSsoft {cid} 小轮轴输入（对齐）")
        m = with_tip_formulas(m)
        r = m.evaluate([q for q, _, _ in COMPARE])
        rows = []
        for q, f, u in COMPARE:
            mine, ks = U.from_canonical(r.values[q], u), case["values"][f]
            kind, gate = GATES[q]
            diff = (mine - ks) if kind == "abs" else (mine / ks - 1.0)
            rows.append({"quantity": q, "unit": u, "gearbase": mine, "kisssoft": ks, "kisssoft_field": f,
                         "diff_kind": kind, "diff": diff, "gate": gate, "pass": abs(diff) <= gate})
        out[cid] = {"tip_shortening": case["tip_shortening_equivalent"], "alignment": alignment(doc, case), "rows": rows,
                    "shaft": _shaft(case)}
    return out
