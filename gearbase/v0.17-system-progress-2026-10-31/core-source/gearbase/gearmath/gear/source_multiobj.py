"""M39 多目标骨架（v0.15 OPT3）：ε-约束法，体积主目标 + 对安全系数下限扫描 → Pareto 前沿；每点走 M34 单目标闭环
（剪枝格搜索 + NLP → 回圆 → 写回候选文档 → 从文档独立统一校核复核），再做非支配筛选。

扫描规格（全部显式，无默认）：
  {"quantities": ["S_F_1", "S_F_2"], "unit": "1", "sense": ">=", "levels": [...], "source": "...", "tag": "epsSF",
   "front_quantity": "S_F_min"}     # 前沿坐标 = 各 quantities 的最小值（>=）或最大值（<=），取自独立复核
S_intS（ISO/TS 6336-21 积分温度法，gear/scuffing_integral.py）：
  - 不在公式图中（逐点 Python 求值，无精确导数/区间界）→ 不能作为 ε 约束进入 NLP：scan quantities 含 S_intS 即阻断（TODO）；
  - 作为前沿每点的附加坐标：sints={"inputs": {键: {"value", "source"}}} 显式给出非几何输入（润滑、材料、试验、修缘、主动轮…），
    几何/载荷量由该点写回文档装配的模型给出；任一必需输入缺失 → 整列阻断（status=blocked_missing_inputs，列出缺项），不补默认。
"""
from __future__ import annotations

import time

from ..kernel import epsilon as EP
from ..kernel import units as U
from . import opt_report as OR
from . import scuffing_integral as SI
from . import source_optimize as SO

SINTS = "S_intS"
# scuffing_integral 几何/载荷键 ← 模型量（单位）
SINTS_FROM_MODEL = {"z1": ("z_1", "1"), "z2": ("z_2", "1"), "a": ("a_w", "mm"), "alpha_n": ("alpha_n", "rad"),
                    "alpha_t": ("alpha_t", "rad"), "alpha_wt": ("alpha_wt", "rad"), "beta": ("beta", "rad"),
                    "beta_b": ("beta_b", "rad"), "d_a1": ("da_1", "mm"), "d_a2": ("da_2", "mm"), "d_b1": ("db_1", "mm"),
                    "d_b2": ("db_2", "mm"), "eps_beta": ("eps_beta", "1"), "b": ("b", "mm"), "F_t": ("F_t", "N"),
                    "v": ("v", "m/s"), "K_A": ("K_A", "1"), "K_v": ("K_V", "1"), "K_Hbeta": ("K_Hbeta", "1"),
                    "K_Halpha": ("K_Halpha", "1")}
SINTS_STIFFNESS = {"spur": ("c_s", "N/(mm*um)"), "helical": ("c_gamma_alpha", "N/(mm*um)")}


def _scan_errors(scan):
    errs = []
    for k in ("quantities", "unit", "sense", "levels", "source", "tag", "front_quantity"):
        if k not in scan:
            errs.append({"path": f"$.scan.{k}", "code": "missing", "message": f"扫描规格缺 {k}（无默认）"})
    if SINTS in (scan.get("quantities") or []):
        errs.append({"path": "$.scan.quantities", "code": "not_in_formula_graph",
                     "message": "S_intS 由 scuffing_integral 逐点求值（无公式图精确导数与区间界），不能作 ε 约束进入 NLP；"
                                "可作为前沿附加坐标（sints）。TODO：-21 积分温度法入公式图"})
    return errs


def sints_inputs(new_doc, decl, spec):
    """该点 S_intS 的输入：几何/载荷取自写回文档装配的模型；其余取 spec["inputs"]（显式，带来源）。返回 (inputs, sources, missing)。"""
    fam, case = SO._family(decl)
    m = SO.with_tip_formulas(SO.build_family_model(new_doc, fam, case))
    helical = m.inputs["beta"].value != 0.0 if "beta" in m.inputs else False
    names = dict(SINTS_FROM_MODEL)
    names["mesh_stiffness"] = SINTS_STIFFNESS["helical" if helical else "spur"]
    r = m.evaluate([q for q, _ in names.values() if q in m.formulas])
    inp, src = {}, {}
    for k, (q, u) in names.items():
        v = r.values.get(q) if q in m.formulas else (m.inputs[q].value if q in m.inputs else None)
        if v is not None:
            inp[k] = U.from_canonical(v, u)
            src[k] = f"写回文档 {new_doc['id']} 装配模型输出 {q}"
    for k, row in (spec.get("inputs") or {}).items():
        if k in inp:
            continue
        if isinstance(row, dict) and "value" in row and isinstance(row.get("source"), str) and row["source"].strip():
            inp[k] = row["value"]
            src[k] = row["source"]
    missing = [k for k in SI.required_inputs(inp) if inp.get(k) is None]
    return inp, src, missing


def sints_at(new_doc, decl, spec):
    inp, src, missing = sints_inputs(new_doc, decl, spec)
    if missing:
        return {"status": "blocked_missing_inputs", "missing": missing}
    r = SI.rate(inp)
    if r.get("status") != "ok":
        return {"status": "blocked", "missing": r.get("missing", []), "unconfirmed": r.get("unconfirmed", [])}
    return {"status": "ok", "S_intS": r["S_intS"], "theta_int": r.get("theta_int"), "theta_intS": r.get("theta_intS"),
            "sources": src}


def pareto_epsilon(doc, decl, scan, *, sints=None, leaf_subboxes=8):
    """ε-约束扫描。返回 {"status", "points": [...], "front": [下标], "front_points": [...], ...}。"""
    t0 = time.perf_counter()
    SO.require_tip_shortening(decl)
    errs = _scan_errors(scan)
    if errs:
        return {"status": "blocked_invalid_scan", "errors": errs}
    if sints is not None:
        _, _, missing = sints_inputs(doc, decl, sints)          # 先在父文档几何上检查非几何输入是否齐全（缺即整列阻断）
        if missing:
            return {"status": "blocked_missing_inputs", "errors": [{"path": "$.sints.inputs", "code": "missing",
                                                                    "message": f"S_intS 必需输入缺失：{missing}"}],
                    "missing": missing}
    decls = EP.epsilon_declarations(decl, quantities=scan["quantities"], unit=scan["unit"], sense=scan["sense"],
                                    levels=scan["levels"], source=scan["source"], tag=scan["tag"])
    obj = decl["objective"]
    points = []
    for eps, d in decls:
        rep = SO.optimize_source(doc, d, leaf_subboxes=leaf_subboxes)
        ver = rep.get("verification") or {}
        row = {"epsilon": eps, "declaration_id": d["id"], "status": rep["status"], "confirmed": bool(ver.get("all_confirmed")),
               "x": (rep.get("snap") or {}).get("x"), "objective": None, scan["front_quantity"]: None,
               "new_document_id": rep["new_document"]["id"] if rep.get("new_document") else None,
               "new_sha256": rep.get("new_sha256"), "wall_time_s": rep.get("wall_time_s")}
        if rep.get("new_document") is not None:
            row["objective"] = ver["objective"]["value"]
            got = [c["value"] for c in ver["declared_constraints"] if c["quantity"] in scan["quantities"]]
            row[scan["front_quantity"]] = min(got) if scan["sense"] == ">=" else max(got)
            row["unified_checks"] = {c["id"]: c["value"] for c in ver["unified_checks"]}
            row["report"] = OR.unified_report(rep, d, doc)
            row["kkt_status"] = row["report"]["kkt"]["status"]
            row["kkt_independent_check"] = row["report"]["kkt"]["independent_check"]
            row["convergence"] = row["report"]["convergence"]["termination"]
            row["new_document"] = rep["new_document"]
            if sints is not None:
                row["sints"] = sints_at(rep["new_document"], d, sints)
        points.append(row)
    ok = [p for p in points if p["confirmed"]]
    senses = {"objective": obj["sense"], scan["front_quantity"]: "max" if scan["sense"] == ">=" else "min"}
    idx = EP.nondominated(ok, senses)
    front = [ok[i] for i in idx]
    return {"status": "ok" if front else "no_confirmed_point", "objective": {"quantity": obj["quantity"], "unit": obj["unit"],
                                                                              "sense": obj["sense"]},
            "scan": dict(scan), "points": points, "front_epsilons": [p["epsilon"] for p in front],
            "dominated_or_unconfirmed": [p["epsilon"] for p in points if p not in front],
            "kkt_caveats": [{"epsilon": p["epsilon"], "kkt_status": p.get("kkt_status"),
                             "independent_check": p.get("kkt_independent_check"), "termination": p.get("convergence")}
                            for p in points if p.get("kkt_status") not in (None, "kkt_satisfied")],
            "method": "ε-约束法：主目标不变，次目标改写为约束并按显式 ε 列表逐点求解；每点独立统一校核复核；非支配筛选。"
                      "每点为叶子 NLP 局部解（与 M34 单目标同一覆盖声明），前沿不是全局 Pareto 证明。",
            "wall_time_s": time.perf_counter() - t0}


def sints_spec_from_kisssoft_p3(case="P3-K01-spur"):
    """S_intS 非几何输入取自 KISSsoft 2026 P3 实际输入（data/kisssoft_v014，m39_demo.p3_integral_inputs，FZG 图7 标注值、
    实际修缘量 Ca）。K01 油品为 FZG A 载荷级 14：图7 只标注 3..12（scuffing_integral 阻断），故取式(50) 近似（eq50）。几何/载荷键与啮合刚度不取（由每个前沿点的写回文档模型给出）。修缘量 Ca 为制造输入，按原设计保持（hold）。"""
    from . import m39_demo as M39
    inp, notes = M39.p3_integral_inputs(case, t1t="eq50", ca_route="standard")
    skip = set(SINTS_FROM_MODEL) | {"mesh_stiffness"}
    rel = f"data/kisssoft_v014/{case}.json"
    out = {}
    for k, v in inp.items():
        if k in skip or v is None:
            continue
        why = notes.get(k) or notes.get("C_a" if k in ("C_a1", "C_a2") else k, "")
        out[k] = {"value": v, "source": f"{rel}（KISSsoft 2026 P3 实际输入，m39_demo.p3_integral_inputs，T1T 式(50)）{('：' + why) if why else ''}"}
    return {"inputs": out, "held_note": "C_a1/C_a2（实际修缘量）、油品/材料/试验输入按原设计保持；几何/载荷按每点写回文档重算"}
