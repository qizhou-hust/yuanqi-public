"""v0.15 OPT3：优化结果统一报告（单目标闭环与多目标每个点共用）。

输入：source_optimize.optimize_source 的报告（含 new_document 与独立复核 verification）、声明、父文档。输出（JSON 可序列化）：
  optimum        写回（回圆后）设计点、目标值、统一校核各项（来自独立复核，不复用优化器缓存）；
  active_set     活跃约束：(a) 连续最优点 KKT 乘子 > 0 的约束/变量界；(b) 回圆点相对裕度 ≤ ACTIVE_REL_TOL 的约束；变量落在界上；
  kkt            一阶 KKT 状态、残差、梯度自检；convergence 数值终止原因；search 搜索覆盖声明（四项分开，不合并成"最优"）；
  evidence       优化器不提升证据等级；列出外部复核状态（KISSsoft 对拍是否覆盖本设计点）；
  hold           未随几何更新的量（含理由）+ 几何口径/适配选择器 + 代理提议/假设类输入；
  kisssoft_request  自动生成的 KISSsoft 复核请求片段（K 链案例：Z012 字段名、全部改动输入、要读的输出与本库预测值）。
"""
from __future__ import annotations

import math

from ..kernel import units as U

ACTIVE_REL_TOL = 2e-3       # 回圆点：|q/limit − 1| ≤ 0.2 % 记为活跃（回圆分辨率导致的离开量级）


def _external_review(new_doc, decl):
    """若写回设计点与 KISSsoft P5 编辑逐字段一致，给出 P5 对拍结果（只读私有提取 JSON）；否则 pending。"""
    try:
        from . import tip_shortening_p5 as T
        data = T.load()
    except (OSError, ValueError, ImportError):
        return {"status": "pending", "note": "无外部复核数据"}
    tip = new_doc.get("selectors", {}).get("adapter.tip_shortening", {}).get("value")
    out = []
    for cid, case in data["cases"].items():
        try:
            al = T.alignment(new_doc, case)
        except KeyError:
            continue
        if all(r["identical"] for r in al):
            out.append({"case": cid, "kisssoft_tip_equivalent": case["tip_shortening_equivalent"],
                        "same_tip_basis": case["tip_shortening_equivalent"] == tip,
                        "kisssoft": {k: case["values"][k] for k in ("ZPP[0].Flanke.SH", "ZPP[1].Flanke.SH",
                                                                    "ZPP[0].Fuss.SFnorm", "ZPP[1].Fuss.SFnorm", "ZP[0].Eps.a")}})
    if not out:
        return {"status": "pending", "note": "本设计点尚无 KISSsoft 外部复核；见 kisssoft_request"}
    return {"status": "kisssoft_reviewed_same_design" if any(o["same_tip_basis"] for o in out) else "kisssoft_reviewed_other_tip_basis",
            "runs": out, "note": "KISSsoft 2026 P5 外部复核（accepted=false：未改 gearbase 接受状态）；比对见 tip_shortening_p5.compare"}


def _active(rep, decl):
    opt = (rep.get("assurance") or {}).get("optimality") or [{}]
    mult = opt[0].get("multipliers") or {}
    kkt_active = sorted(k for k, v in mult.items() if isinstance(v, (int, float)) and v > 0.0)
    rows = []
    for c in (rep.get("verification") or {}).get("declared_constraints", []):
        lim = c["limit"]
        rel = (c["value"] / lim - 1.0) if lim else c["value"]
        margin = rel if c["sense"] == ">=" else -rel
        rows.append({"id": c["id"], "quantity": c["quantity"], "value": c["value"], "limit": lim, "sense": c["sense"],
                     "rel_margin": margin, "active_at_written_point": abs(margin) <= ACTIVE_REL_TOL})
    x = (rep.get("snap") or {}).get("x") or {}
    at_bound = []
    for v in decl["variables"]:
        if v["name"] not in x:
            continue
        val = x[v["name"]]
        if v["kind"] in ("integer", "continuous"):
            if val <= v["lo"]:
                at_bound.append({"name": v["name"], "bound": "lo", "value": val})
            elif val >= v["hi"]:
                at_bound.append({"name": v["name"], "bound": "hi", "value": val})
        else:
            vals = sorted(v["values"])
            if len(vals) > 1 and val in (vals[0], vals[-1]):
                at_bound.append({"name": v["name"], "bound": "lo" if val == vals[0] else "hi", "value": val})
    return {"kkt_multiplier_positive": kkt_active, "constraints": rows,
            "active_at_written_point": [r["id"] for r in rows if r["active_at_written_point"]],
            "variables_at_bound": at_bound, "rel_tol": ACTIVE_REL_TOL,
            "note": "KKT 乘子来自连续最优点（回圆前、该离散组合）；回圆点活跃按相对裕度判定"}


def _hold(rep, new_doc):
    sel = new_doc.get("selectors", {})
    adapters = {k: r["value"] for k, r in sel.items() if k.startswith("adapter.")}
    proposed = sorted(n for n, r in new_doc.get("inputs", {}).items() if r.get("provenance") in ("agent_proposed", "assumption"))
    lims = sorted(n for n, r in new_doc.get("constraints", {}).items() if r.get("provenance") in ("agent_proposed", "assumption"))
    return {"held_not_updated": rep.get("held_not_updated") or [], "geometry_and_adapter_selectors": adapters,
            "agent_proposed_or_assumption_inputs": proposed, "agent_proposed_limits": lims,
            "note": "held 项在设计变量变化时未重新取证：安全系数只在这些量不变的前提下成立"}


# ---------------------------------------------------------------- KISSsoft 复核请求片段
_KS_INPUTS = (("z_1", "ZR[0].z", "1"), ("z_2", "ZR[1].z", "1"), ("m_n", "ZS.Geo.mn", "mm"), ("b_1", "ZR[0].b", "mm"),
              ("b_2", "ZR[1].b", "mm"), ("x_1", "ZR[0].x.nul", "1"), ("x_2", "ZR[1].x.nul", "1"), ("a_w", "ZP[0].a", "mm"))
_KS_OUTPUTS = (("S_H_1", "ZPP[0].Flanke.SH", "1"), ("S_H_2", "ZPP[1].Flanke.SH", "1"), ("S_F_1", "ZPP[0].Fuss.SFnorm", "1"),
               ("S_F_2", "ZPP[1].Fuss.SFnorm", "1"), ("eps_alpha", "ZP[0].Eps.a", "1"), ("k_X_1", "ZR[0].kXmn", "mm"),
               ("k_X_2", "ZR[1].kXmn", "mm"), ("da_1", "ZR[0].da.nul", "mm"), ("da_2", "ZR[1].da.nul", "mm"),
               ("d_inner_1", "ZR[0].di", "mm"), ("d_inner_2", "ZR[1].di", "mm"), ("K_V", "ZP[0].KV.KV", "1"),
               ("Z_V", "ZPP[0].Flanke.ZV", "1"), ("Z_R", "ZPP[0].Flanke.ZR", "1"))


def _model_values(new_doc, decl, names):
    from .source_optimize import _family, build_family_model, with_tip_formulas
    fam, case = _family(decl)
    m = with_tip_formulas(build_family_model(new_doc, fam, case))
    want = [(n, u) for n, u in names if n in m.formulas or n in m.inputs]
    r = m.evaluate([n for n, _ in want if n in m.formulas])
    out = {}
    for n, u in want:
        v = r.values.get(n) if n in m.formulas else m.inputs[n].value
        out[n] = None if v is None else U.from_canonical(v, u)
    return out, case


def kisssoft_request(new_doc, decl):
    """K 链案例：生成可直接执行的 KISSsoft 复核请求（Z012 字段、输入、输出、预测值、用途）。其它族：说明需新建模型。"""
    from .source_optimize import _family
    fam, case = _family(decl)
    if fam != "kisssoft_chain":
        return {"applicable": False, "text": f"{decl['id']}：模型族 {fam} 无 KISSsoft 原始文件，需用户新建 Z012 模型后按本报告输入复核。"}
    vals, _ = _model_values(new_doc, decl, [(n, u) for n, _, u in _KS_INPUTS + _KS_OUTPUTS] + [("b", "mm")])
    for n in ("b_1", "b_2"):
        if vals.get(n) is None:
            vals[n] = vals.get("b")
    tip = new_doc.get("selectors", {}).get("adapter.tip_shortening", {}).get("value")
    ins = [{"field": f, "value": vals[n], "unit": u, "gearbase": n} for n, f, u in _KS_INPUTS if vals.get(n) is not None]
    if tip == "none":
        ins += [{"field": f"ZR[{i}].kFaktorFlag", "value": "true", "unit": "", "gearbase": "tip_shortening=none"} for i in (0, 1)]
        ins += [{"field": f"ZR[{i}].kXmn", "value": 0.0, "unit": "mm", "gearbase": "tip_shortening=none"} for i in (0, 1)]
    elif tip == "kisssoft_auto_equivalent":
        ins += [{"field": f"ZR[{i}].kFaktorFlag", "value": "false（自动）", "unit": "", "gearbase": "tip_shortening=kisssoft_auto_equivalent"}
                for i in (0, 1)]
    held = {n: new_doc["inputs"][n] for n in ("l_sh", "s_sh", "d_sh") if n in new_doc.get("inputs", {})}
    if held:
        ins.append({"field": "Zst.lsdFlag", "value": "true", "unit": "", "gearbase": "小轮轴按文档显式输入（不随齿宽自动缩放）"})
        for n, f in (("l_sh", "ZP[0].KHdat.l"), ("s_sh", "ZP[0].KHdat.S"), ("d_sh", "ZP[0].KHdat.dsh")):
            if n in held:
                ins.append({"field": f, "value": held[n]["value"], "unit": held[n]["unit"], "gearbase": n})
    outs = [{"field": f, "gearbase": n, "unit": u, "predicted": vals.get(n)} for n, f, u in _KS_OUTPUTS if vals.get(n) is not None]
    lines = [f"### KISSsoft 运行请求：{new_doc['id']}",
             f"- 模块/计算：KISSsoft 圆柱齿轮副 Z012，ISO 6336:2019 方法 B（RechenMethID 10029，与原 {case}.Z12 相同）；"
             f"以原始 {case}.Z12 为底，只改下列输入，其余不动。",
             f"- 齿顶缩短口径：tip_shortening = {tip or '未声明（旧路径，不含齿顶缩短）'}。",
             "- 输入（单位）："]
    lines += [f"  - `{r['field']}` = {_fmt(r['value'])} {r['unit']}（本库 {r['gearbase']}）" for r in ins]
    lines += ["- 读取输出（报告位置：GetVar 字段；PDF 第 3 节几何、第 4–6 节强度、第 13 节公差），本库预测值："]
    lines += [f"  - `{r['field']}`（{r['gearbase']}）预测 {_fmt(r['predicted'])} {r['unit']}" for r in outs]
    from ..kernel.declared import declaration_sha256
    lines += [f"- 用途：外部复核优化写回设计（声明 {decl['id']}，sha256 {declaration_sha256(decl)[:16]}…）；"
              "差异逐项归因（先对齐输入）；held 清单中的量若 KISSsoft 自动重算，请一并读出。"]
    return {"applicable": True, "case": case, "inputs": ins, "outputs": outs, "text": "\n".join(lines)}


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.10g}" if math.isfinite(v) else str(v)
    return str(v)


def unified_report(rep, decl, parent_doc=None):
    new = rep.get("new_document")
    ver = rep.get("verification") or {}
    out = {"schema": "gearbase.opt_unified_report/1", "declaration_id": decl["id"], "declaration_sha256": rep.get("declaration_sha256"),
           "parent_id": rep.get("parent_id"), "parent_sha256": rep.get("parent_sha256"), "status": rep.get("status"),
           "new_document_id": new["id"] if new else None, "new_sha256": rep.get("new_sha256"),
           "tip_shortening": (decl.get("parameters") or {}).get("tip_shortening")}
    if new is None:
        out["note"] = "未写回（无可行点或回圆不可行）"
        out["search"] = (rep.get("assurance") or {}).get("search_claim")
        return out
    out["optimum"] = {"x_written": rep["snap"]["x"], "x_continuous": (rep.get("optimum") or {}).get("x"),
                      "rounding_shift": rep["snap"]["shift"], "objective": ver.get("objective"),
                      "unified_checks": ver.get("unified_checks"), "unified_check_status": ver.get("unified_check_status"),
                      "independently_confirmed": ver.get("all_confirmed")}
    out["active_set"] = _active(rep, decl)
    a = rep.get("assurance") or {}
    opt = (a.get("optimality") or [{}])[0]
    out["kkt"] = {"status": opt.get("status"), "residuals": opt.get("residuals"), "tolerances": opt.get("tolerances"),
                  "gradient_self_check": opt.get("gradient_self_check"), "fixed_variables": opt.get("fixed_variables"),
                  "independent_check": (opt.get("independent_check") or {}).get("status"), "meaning": opt.get("meaning")}
    out["convergence"] = {k: (a.get("solver_convergence") or {}).get(k) for k in ("status", "termination", "outer_iterations",
                                                                                  "inner_iterations", "final_resolve_identical_to_leaf")}
    sc = a.get("search_claim") or {}
    out["search"] = {"coverage": sc.get("coverage"), "claim_scope": sc.get("claim_scope"), "statement": sc.get("statement"),
                     "lattice": {k: (sc.get("lattice") or {}).get(k) for k in ("points_total", "points_pruned", "points_solved")},
                     "wall_time_s": rep.get("wall_time_s")}
    out["evidence"] = {"optimizer_evidence_level": a.get("evidence_level"), "external_review": _external_review(new, decl),
                       "note": "优化器不计算、不提升证据等级；外部复核通过也不改 accepted 标记"}
    out["hold"] = _hold(rep, new)
    out["kisssoft_request"] = kisssoft_request(new, decl)
    return out


def render_markdown(r):
    """统一报告 → 中文 Markdown（人读）。"""
    L = [f"## 优化结果：{r['declaration_id']}", f"- 状态：{r['status']}；父文档 {r['parent_id']}（{(r['parent_sha256'] or '')[:12]}…）"
         f" → 新修订 {r.get('new_document_id')}（{(r.get('new_sha256') or '')[:12]}…）；齿顶缩短口径 {r.get('tip_shortening')}"]
    if "optimum" not in r:
        return "\n".join(L + [f"- {r.get('note')}"])
    o = r["optimum"]
    L.append(f"- 写回设计点：{o['x_written']}；目标 {o['objective']['quantity']} = {o['objective']['value']:.6g} {o['objective']['unit']}"
             f"；独立复核 {o['independently_confirmed']}")
    L.append("- 统一校核：" + "，".join(f"{c['id']} {c['value']:.6f}（限 {c['limit']}）" for c in o["unified_checks"]))
    act = r["active_set"]
    L.append(f"- 活跃集：KKT 乘子>0 {act['kkt_multiplier_positive']}；回圆点活跃 {act['active_at_written_point']}；"
             f"变量在界 {[(b['name'], b['bound']) for b in act['variables_at_bound']]}")
    k = r["kkt"]
    res = k.get("residuals") or {}
    L.append(f"- KKT：{k['status']}（stationarity {res.get('stationarity', float('nan')):.2e}，primal {res.get('primal_feasibility', float('nan')):.2e}，"
             f"complementarity {res.get('complementarity', float('nan')):.2e}；梯度自检 {(k.get('gradient_self_check') or {}).get('max_rel_diff')}）；"
             f"收敛 {r['convergence']['status']}/{r['convergence']['termination']}")
    s = r["search"]
    L.append(f"- 搜索：{s['coverage']}（{s['claim_scope']}）；格点 {s['lattice']}；耗时 {s['wall_time_s']:.1f} s")
    e = r["evidence"]
    L.append(f"- 证据：优化器 {e['optimizer_evidence_level'].get('value') if e['optimizer_evidence_level'] else None}；外部复核 {e['external_review']['status']}")
    h = r["hold"]
    L.append("- hold 清单（未随几何更新）：" + ("；".join(f"{x['name']}（{x.get('reason', '')[:40]}）" for x in h["held_not_updated"]) or "无"))
    L.append(f"- 几何口径/适配：{h['geometry_and_adapter_selectors']}；代理提议/假设输入 {h['agent_proposed_or_assumption_inputs']}；"
             f"代理提议限值 {h['agent_proposed_limits']}")
    L.append("")
    L.append(r["kisssoft_request"]["text"])
    return "\n".join(L)
