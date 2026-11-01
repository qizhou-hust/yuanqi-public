"""KISSsoft v0.15 外部证据（Release 2026 / 26.0.0.0）：P5 优化器外部闭环 + M39 补差（提取与对拍）。

数据：data/kisssoft_v015/P5-A.json、P5-B.json、M39-*.json（由 extract_* 从用户私有证据目录 /home/claude/private_ks15
提取的最小 JSON；每个值带来源文件相对路径、sha256 与字段定位；不含 PDF/Z12）。

P5（OPT2 新最优 z 23/68、m_n 6、b 28.6、x1 0.449、a=274.18390994938926 的复核）：
  A（完全对齐）：KISSsoft 显式小轮轴 88/8.8/44（lsdFlag）、齿顶缩短 kXmn=0（kFaktorFlag）——与优化写回文档同一输入；
  B（自动）：只改几何与中心距，KISSsoft 自动轴 57.2/5.72/28.6、kXmn=−0.019 mm。
比较两层：
  1. 公式层（compare_p5）：沿用 kisssoft_v014.compare_p2 的对齐模型（K01 K 链 + 显式系数契约，输入逐字段取 KISSsoft 实际值，
     kXmn 用 'additive_kXmn_mm' 适配）与 GATES/KNOWN_DIFFERENCES，不新设门；
  2. 闭环层（closed_loop_p5）：优化器写回文档（output/m34/K01-spur.factors.opt-36f05481）经统一校核同一装配
     （kisssoft_v014.predict_for_document）求值，只把 KISSsoft 运行的工况差异（A：无；B：kXmn、自动轴）按 KISSsoft 记录代入，
     逐系数、逐安全系数与 KISSsoft 比较，门同 GATES；再判 KISSsoft 值是否满足声明约束 S_H ≥ 1、S_F ≥ 1.4。
不调输入、系数或门限追平；KISSsoft 值来自文件。
"""
from __future__ import annotations

import hashlib
import json
import pathlib

from . import kisssoft_v014 as KV

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "kisssoft_v015"
PRIVATE15 = pathlib.Path("/home/claude/private_ks15")
P5_SCHEMA = "gearbase.kisssoft_v015.p5/1"
M39_SCHEMA = "gearbase.kisssoft_v015.m39/1"
P5_CASES = {"P5-A": "P5-A-tip-coefficient-input", "P5-B": "P5-B-auto"}
P5_COMMON_FILES = ("RESULTS.txt", "AI_START_HERE.md", "summary.json", "case-index.json")
OPT_DOC = ROOT / "output" / "m34" / "K01-spur.factors.opt-36f05481.math-source.json"
# OPT2（v0.14）在 KISSsoft 运行请求 v0.15 中登记的事前预测（写入数据仅作记录，不作参照）
P5_PREDICTIONS = {
    "P5-A": {"S_H_1": 1.001468, "S_H_2": 1.035327, "S_F_1": 1.515292, "S_F_2": 1.404448, "eps_alpha": 1.583724},
    "P5-B": {"S_H_1": 1.00053, "S_H_2": 1.03436, "S_F_1": 1.51224, "S_F_2": 1.40284, "eps_alpha": 1.57905},
}
P5_FLAGS = ("Zst.lsdFlag", "ZR[0].kFaktorFlag", "ZR[1].kFaktorFlag")
P5_RAW = ("ZPP[0].Flanke.SH", "ZPP[1].Flanke.SH", "ZPP[0].Fuss.SFnorm", "ZPP[1].Fuss.SFnorm", "ZP[0].Eps.a", "ZP[0].a",
          "ZR[0].kXmn", "ZR[1].kXmn")
S_MIN = {"S_H": 1.0, "S_F": 1.4}      # 声明约束（data/optimize/K01-spur-min-volume-recompute.decl.json）


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- P5 提取
def extract_p5(private_root, key):
    """P5-A / P5-B 最小 JSON（字段名与 P2 提取同一套 COM_FIELDS/TXT_FIELDS，可直接用 kisssoft_v014 对齐模型）。"""
    pr = pathlib.Path(private_root)
    case = P5_CASES[key]
    run_rel, txt_rel = f"cases/{case}/run.json", f"cases/{case}/{case}.txt"
    run = json.loads((pr / run_rel).read_text(encoding="utf-8"))
    vals, raw = run["values"], run["raw_values"]
    lines = (pr / txt_rel).read_text(encoding="utf-8").splitlines()
    fields = {}
    for name, k, unit in KV.COM_FIELDS:
        fields[name] = {"value": vals[k], "unit": unit, "source": run_rel, "locator": f"values[\"{k}\"]"}
    for name, k, sec, unit, which in KV.TXT_FIELDS:
        v, line, dec = KV._txt_value(lines, k, sec, which)
        if unit == "1e6":
            v, unit, dec = float(round(v * 1e6)), "1", dec - 6
        fields[name] = {"value": v, "unit": unit, "source": txt_rel, "locator": f"{k}（第 {line} 行，§{sec}）", "decimals": dec}
    files = {f: {"sha256": _sha(pr / f)} for f in (run_rel, txt_rel) + P5_COMMON_FILES if (pr / f).is_file()}
    return {
        "schema": P5_SCHEMA, "id": key, "case": case,
        "description": ("KISSsoft Release 2026（26.0.0.0）对 OPT2 K01 新最优的复算：" +
                        ("A 完全对齐（显式轴 88/8.8/44、kXmn=0）" if key == "P5-A" else "B 自动（KISSsoft 自动轴与齿顶缩短）")),
        "status": "external_evidence：计算成功、原生重载无差异、全新无头实例重算一致；用户阈值 SH≥1、SF≥1.4 通过；"
                  "accepted=false（不等于设计认证）",
        "software": {"name": "KISSsoft", "release": run.get("version"), "file_version": run.get("file_version"),
                     "module": run.get("module"), "calculate_return": run.get("calculate_return")},
        "native_baseline": {"file": "K01-spur.Z12（原机路径见 run.json source）", "sha256": run["source_sha256"]},
        "run_checks": {"reload_differences": run["reload_differences"], "source_unchanged": run["source_unchanged"],
                       "fresh_headless_module_ok": run["fresh_headless_module_ok"],
                       "external_user_numeric_gate_pass": run["external_user_numeric_gate_pass"], "accepted": run["accepted"]},
        "edits": [{k: e[k] for k in ("field", "before", "requested", "readback")} for e in run["edits"]],
        "flags": {k: vals[k] for k in P5_FLAGS},
        "raw_strings": {k: raw[k] for k in P5_RAW},
        "files": files, "fields": fields,
        "gearbase_prediction_v015_request": P5_PREDICTIONS[key],
    }


def write_p5(private_root=PRIVATE15):
    out = {}
    DATA.mkdir(parents=True, exist_ok=True)
    for key in P5_CASES:
        d = extract_p5(private_root, key)
        (DATA / f"{key}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        out[key] = d
    return out


def load_p5(key):
    return json.loads((DATA / f"{key}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- P5 公式层
def compare_p5(key):
    """kisssoft_v014 对齐模型（输入逐字段取 KISSsoft P5 实际值；B 的 kXmn 与自动轴亦取记录）vs KISSsoft P5。"""
    return KV.compare_p2(load_p5(key))


# ---------------------------------------------------------------- P5 闭环层
CLOSED_LOOP = [("geometry", "eps_alpha"), ("geometry", "da_1"), ("geometry", "da_2"), ("geometry", "alpha_wt"),
               ("factor", "K_V"), ("factor", "K_Hbeta"), ("factor", "K_Fbeta"), ("factor", "K_Halpha"), ("factor", "K_Falpha"),
               ("factor", "Z_H"), ("factor", "Z_E"), ("factor", "Z_eps"), ("factor", "Z_NT_1"), ("factor", "Z_NT_2"),
               ("factor", "Z_L"), ("factor", "Z_V"), ("factor", "Z_R"),
               ("factor", "Y_F_1"), ("factor", "Y_F_2"), ("factor", "Y_S_1"), ("factor", "Y_S_2"),
               ("factor", "Y_NT_1"), ("factor", "Y_NT_2"), ("factor", "Y_X"), ("factor", "Y_drelT_1"), ("factor", "Y_drelT_2"),
               ("factor", "Y_RrelT_1"), ("factor", "Y_RrelT_2"), ("factor", "Y_B"), ("factor", "Y_DT"),
               ("safety", "S_H_1"), ("safety", "S_H_2"), ("safety", "S_F_1"), ("safety", "S_F_2")]
CLOSED_LOOP_UNITS = {"da_1": "mm", "da_2": "mm", "alpha_wt": "rad"}
# 写回文档 vs KISSsoft 记录的输入（逐字段）：A 应全部一致（d_inner 仅 KISSsoft 显示两位小数）
LOOP_INPUTS = [("z_1", "1"), ("z_2", "1"), ("m_n", "mm"), ("b", "mm"), ("x_1", "1"), ("x_2", "1"),
               ("l_sh", "mm"), ("s_sh", "mm"), ("d_sh", "mm"), ("d_inner_1", "mm"), ("d_inner_2", "mm"),
               ("f_Hbeta5", "um"), ("f_Hbeta_1", "um"), ("f_Hbeta_2", "um"), ("f_pt_1", "um"), ("f_falpha_1", "um")]


def load_opt_doc():
    return json.loads(OPT_DOC.read_text(encoding="utf-8"))


def closed_loop_p5(key, doc=None):
    """优化写回文档（统一校核同一装配）在 KISSsoft P5 工况下的值 vs KISSsoft。
    A：不代入任何 KISSsoft 值（k_X=0、轴为文档值）——纯预测；B：代入 KISSsoft 记录的 kXmn 与自动轴（工况差异，非系数）。"""
    from .source_optimize import build_family_model
    from ..kernel import units as U
    p5 = load_p5(key)
    doc = doc or load_opt_doc()
    kx = KV.ks(p5, "k_X_1", "mm")
    if kx != KV.ks(p5, "k_X_2", "mm"):
        raise NotImplementedError("两轮 kXmn 不同")
    shaft = None if key == "P5-A" else {n: KV.ks(p5, n, "mm") for n in ("l_sh", "s_sh", "d_sh")}
    m0 = build_family_model(doc, "kisssoft_chain", "K01-spur")
    inv = {}
    for n, u in LOOP_INPUTS:
        g = KV.model_values(m0, [(n, u)])[n]
        k = KV.ks(p5, "b_1" if n == "b" else n, u)
        inv[n] = {"unit": u, "writeback_doc": g, "kisssoft": k, "abs_diff": g - k}
    pred = KV.predict_for_document(doc, "kisssoft_chain", "K01-spur", k_X_mm=kx, shaft=shaft)
    m = KV._with_tip_alteration(build_family_model(doc, "kisssoft_chain", "K01-spur"))
    for i in ("1", "2"):
        m.set(f"k_X_{i}", kx, "mm", "assumption", "P5 工况")
    for n, v in (shaft or {}).items():
        m.set(n, v, "mm", "assumption", "P5-B KISSsoft 自动轴")
    vals = KV.model_values(m, [(q, CLOSED_LOOP_UNITS.get(q, "1")) for _, q in CLOSED_LOOP])
    rows = []
    for cat, q in CLOSED_LOOP:
        g, k = vals[q], KV.ks(p5, q, CLOSED_LOOP_UNITS.get(q, "1"))
        rel = g / k - 1
        known = KV.KNOWN_DIFFERENCES.get(q)
        rows.append({"category": cat, "quantity": q, "gearbase": g, "kisssoft": k, "rel_diff": rel,
                     "gate": None if known else KV.GATES[cat],
                     "status": "known_difference" if known else ("pass" if abs(rel) <= KV.GATES[cat] else "FAIL")})
    cons = {q: {"kisssoft": KV.ks(p5, q), "limit": S_MIN[q[:3]], "margin": KV.ks(p5, q) - S_MIN[q[:3]],
                "satisfied": KV.ks(p5, q) >= S_MIN[q[:3]]} for q in ("S_H_1", "S_H_2", "S_F_1", "S_F_2")}
    k_pred = KV.iso21771_tip_alteration_mm(m0)
    return {"case": key, "k_X_mm": kx, "shaft": shaft, "inputs": inv, "rows": rows, "constraints": cons,
            "prediction_check": {q: pred[q] for q in ("S_H_1", "S_H_2", "S_F_1", "S_F_2", "eps_alpha")},
            "k_X_iso21771_mm": k_pred, "registered_prediction": p5["gearbase_prediction_v015_request"],
            "all_gated_pass": all(r["status"] != "FAIL" for r in rows),
            "all_constraints_satisfied": all(c["satisfied"] for c in cons.values())}


def closed_loop_verdict():
    """闭环判定：A 逐系数/逐安全系数在 GATES 内且 KISSsoft 满足约束；B 在对齐模型下同样在门内且满足约束。"""
    a, b = closed_loop_p5("P5-A"), closed_loop_p5("P5-B")
    ok = a["all_gated_pass"] and a["all_constraints_satisfied"] and b["all_gated_pass"] and b["all_constraints_satisfied"]
    return {"pass": ok, "A": a, "B": b,
            "scope": "优化器写回 → 外部商业软件复核 数值闭环；不是工程验收（证据保持项 Y_ST、轴、未建模齿顶缩短仍随结果一起读）"}


# ---------------------------------------------------------------- M39 补差（v0.15 回传）提取
M39_CASES = ("M39-K01-runin0", "M39-K02-helical-Ca-not-optimal", "M39-K04-EV-stage1-Ca-not-optimal",
             "M39-K05-EV-stage2-Ca-not-optimal", "M39-baseline-K01-spur", "M39-baseline-K03-premachining")
# 对应的 v0.14 P3 输入案例（M39 运行只改 edits 所列字段；其余输入同 P3 原生文件）
M39_P3 = {"M39-K01-runin0": "P3-K01-spur", "M39-K02-helical-Ca-not-optimal": "P3-K02-helical",
          "M39-K04-EV-stage1-Ca-not-optimal": "P3-K04-EV-stage1", "M39-K05-EV-stage2-Ca-not-optimal": "P3-K05-EV-stage2",
          "M39-baseline-K01-spur": "P3-K01-spur", "M39-baseline-K03-premachining": "P3-K03-premachining"}
M39_KEYS = ("RechSt.Scoring_RunIn", "ZP[0].Ceff", "ZPP[0].Ceq", "ZPP[1].Ceq", "ZPP[0].CaValid", "ZPP[1].CaValid",
            "ZPP[0].eps.nul", "ZPP[1].eps.nul", "ZR[0].Cf", "ZR[1].Cf", "ZR[0].RAH", "ZR[1].RAH",
            "ZP[0].FIT.XCa", "ZP[0].FIT.mym", "ZP[0].FIT.SSint", "ZP[0].FIT.SSL", "ZP[0].FIT.theflaint", "ZP[0].FIT.theMC",
            "ZP[0].FIT.theint", "ZP[0].FIT.XE", "ZP[0].FBT.mymy", "ZP[0].FBT.XLforPart1", "ZP[0].Scoring_wBT",
            "ZP[0].Scoring_XE", "ZP[0].Scoring_Theflm", "ZP[0].FBT.theflamax", "ZP[0].FBT.them", "ZP[0].FBT.theB",
            "ZP[0].FBT.SB")
M39_SUMMARY = "evidence/M39-return-summary.txt"


def extract_m39(private_root, case):
    pr = pathlib.Path(private_root)
    run_rel = f"cases/{case}/run.json"
    run = json.loads((pr / run_rel).read_text(encoding="utf-8"))
    vals, raw = run["values"], run["raw_values"]
    fields = {k: {"value": vals[k], "raw": raw.get(k), "source": run_rel, "locator": f"values[\"{k}\"]"}
              for k in M39_KEYS if k in vals}
    files = {f: {"sha256": _sha(pr / f)} for f in (run_rel, M39_SUMMARY, "RESULTS.txt", "case-index.json") if (pr / f).is_file()}
    return {"schema": M39_SCHEMA, "id": case, "p3_input_case": M39_P3[case], "private": True,
            "software": {"name": "KISSsoft", "release": run.get("version"), "file_version": run.get("file_version"),
                         "module": run.get("module")},
            "native": {"source_sha256": run["source_sha256"], "native_sha256": run["native_sha256"],
                       "calculate_return": run["calculate_return"], "reload_calculate_return": run["reload_calculate_return"],
                       "reload_differences": run["reload_differences"], "source_unchanged": run["source_unchanged"],
                       "edits": [{k: e[k] for k in ("field", "before", "requested", "readback")} for e in run["edits"]]},
            "files": files, "fields": fields}


def write_m39(private_root=PRIVATE15):
    DATA.mkdir(parents=True, exist_ok=True)
    out = {}
    for c in M39_CASES:
        d = extract_m39(private_root, c)
        (DATA / f"{c}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        out[c] = d
    return out


def load_m39(case):
    if case not in M39_CASES:
        raise ValueError(f"未知 M39 案例 {case!r}")
    return json.loads((DATA / f"{case}.json").read_text(encoding="utf-8"))


def m39v(case, key):
    return load_m39(case)["fields"][key]["value"]
