"""TR30 例7、例8 三方对拍：gearbase（当前代码）↔ KISSsoft 2026 复算 ↔ TR30 印刷值。

证据：data/kisssoft/tr30-7-8/（用户本地 KISSsoft 2026 复算，私有、不得再分发；文件与上传原件逐字节相同，
加载时按 SOURCE_SHA256 核对）。KISSsoft 值是外部证据（provenance=evidence），只在建图之后用于比较；
从不读取 comparison.csv 的 gearmath 列（v0.8 旧值）建图。

两种判据分列，互不替代：
- gearbase ↔ KISSsoft：严格双门 |Δ| ≤ 0.01 且 |Δ| ≤ 0.5 %·|KISSsoft|（TR30 4.2.15，PDF14–15 原文双门；两侧均为未舍入值）；
- KISSsoft/gearbase ↔ TR30 印刷：显示量子判据 |Δ| ≤ q/2 + min(0.01, 0.005|r|)（tr30_full58.quantum_tolerance）。

硬度换算（例7）：正式口径 hardness_conversion='ISO18265_A1_linear'（不变）。'HV_external_readback' 是显式变体：把 KISSsoft
齿轮模块读回的 HV 作为 provenance=evidence 的输入，只用于证明"相同 HV 下两实现逐行一致"。两者都须显式选择，不设默认。

本模块从不授予验收：accepted=false；M33 是否验收由用户决定（用户结论：M33 仍未验收）。
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

from .tr30_full58 import compare_full, build_model, quantum_tolerance, _rows, _num
from .protuberance import protuberance_dff_converged

DATA = Path(__file__).resolve().parents[2] / "data/kisssoft/tr30-7-8"
UPLOAD = "M33:TR30-7-8-2026-10-29（用户上传 ai-shared/M33-standards-and-reports-2026-10-28/TR30-7-8-2026-10-29）"
ABS_TOL, REL_TOL = 0.01, 0.005

# 上传包 SHA256SUMS 中的值（本地已核）；入库文件与之逐字节相同
SOURCE_SHA256 = {
    "example-7/comparison.csv": "1f9ddf21d07f222ca28ca73ca704a0be463dc6af81ceb360bc6a33c955d46e72",
    "example-7/high-precision-values.csv": "862560a9e559ec996095750fc9a65d78dcef15a41685bc7f6675f1a99c65c418",
    "example-7/input-audit.csv": "7fc73e1857c4a219b00f827f17f2bd32bcb6db02a5d595405de9ec0892bca6b1",
    "example-7/relief-length-sensitivity.json": "505c4e9581ff62a172e41a0cc13fbd2a438234e0ee2446d2eefe5ff746164f27",
    "example-8/comparison.csv": "979f5d04790c794e61265052d916fedc6a17de1da40c4d96bebc9ca7396014b2",
    "example-8/high-precision-values.csv": "384c72f52f789111ad4b1a3fb9c4d433ed764141f0e70cc60c8751007e8b474a",
    "example-8/input-audit.csv": "52d750aab77b5e8b10ad795bba58cc90e2ebc762683e6b749c41862e55bcdfe1",
    "example-8/relief-length-sensitivity.json": "4c20febe0f3569c421bd0195203a550737cee87f90263302c740538dda1f6007",
}
NATIVE_Z12_SHA256 = {7: "ba9205dda2b8fcd9f7a6bb5eb40ed7c66924782b886a455fa4b1b95839787f8e",
                     8: "f43d54fc0667da8a412aee29348e5b17710512841dc985ea5d31263f207d3ed0"}

# KISSsoft 对齿轮 i 读回的 HV 字段（例7 原表硬度为 HB；KISSsoft 界面 HBW 输入）
HV_READBACK_FIELDS = {1: "ZR[0].HardnessHV", 2: "ZR[1].HardnessHV"}
HARDNESS_CONVERSIONS = ("ISO18265_A1_linear", "HV_external_readback")

# 剩余差异性质（docs/M33-验收报告.md "KISSsoft 复算"一节）
NATURE = {
    (7, "gb_ks", "material"): "来源冲突（HB→HV 换算口径：ISO 18265 表A.1 插值 vs KISSsoft 读回≈HB/0.9505）",
    (7, "tr30", "material"): "来源冲突（硬度换算口径：TR30 原表数值更接近 HB/0.95；ISO 18265 与 KISSsoft 均不同）",
    (8, "tr30", "root_stress"): "原表印刷（候选）：gearbase 与 KISSsoft 两个实现相差 <0.003 MPa，同时高于印刷值；"
                                "不能据此断言原表错误",
}
MATERIAL_ROWS = ("sigma_Hlim", "sigma_Flim", "sigma_HP", "sigma_FP")


def _verify(rel):
    path = DATA / rel
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256[rel]:
        raise ValueError(f"{rel} 与上传原件 sha256 不符：{digest}")
    return path


def load_comparison(number):
    with open(_verify(f"example-{number}/comparison.csv"), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_high_precision(number):
    with open(_verify(f"example-{number}/high-precision-values.csv"), encoding="utf-8-sig", newline="") as fh:
        return {row["variable"]: row["value"] for row in csv.DictReader(fh)}


def load_input_audit(number):
    with open(_verify(f"example-{number}/input-audit.csv"), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_relief_sensitivity(number):
    return json.loads(_verify(f"example-{number}/relief-length-sensitivity.json").read_text(encoding="utf-8"))


def hv_readback_inputs(number):
    """KISSsoft 读回 HV → mat_hv_ext_i（provenance=evidence，带字段名与文件 sha256）。"""
    hp = load_high_precision(number)
    rel = f"example-{number}/high-precision-values.csv"
    return {f"mat_hv_ext_{i}": (float(hp[f]), "1", "evidence",
                                f"KISSsoft 2026 齿轮模块读回 {f}（输入 {hp[f.replace('HardnessHV', 'HardnessHB')]} HBW）；"
                                f"{UPLOAD}/{rel} sha256 {SOURCE_SHA256[rel]}")
            for i, f in HV_READBACK_FIELDS.items()}


def strict_gate(actual, reference):
    d = actual - reference
    return abs(d) <= ABS_TOL + 1e-12 and abs(d) <= REL_TOL * abs(reference) + 1e-12


def protuberance_dff_example8(model=None):
    """例8 凸台刀预加工 + 磨削后的有效 dFf（数值包络，见 protuberance.protuberance_dff）。输入全部取原表行与模型
    中由跨齿距求得的 xE/xEV；KISSsoft 的 hprP 不作输入，只作旁证。"""
    case = 8
    from .tr30_examples58 import load
    raw = _rows(load(case))
    model = model or build_model(case, zv_velocity="v_ref", rz_source="printed_rz")
    out = {}
    for i in (1, 2):
        v = model.evaluate([f"xE_{i}", f"xEV_{i}"]).values
        p = {"z": _num(raw, "z", i-1), "m_n": _num(raw, "m_n"), "alpha_n": math.radians(_num(raw, "alpha_n")),
             "beta": math.radians(_num(raw, "beta")), "hfP_cut": _num(raw, "h_fP_pre", i-1),
             "rhofP": _num(raw, "rho_fP", i-1), "pr_cut": _num(raw, "pr", i-1),
             "alpha_pr": math.radians(_num(raw, "tool_pr_angle", i-1)), "x_cut": v[f"xEV_{i}"], "x_fin": v[f"xE_{i}"]}
        if abs((p["x_cut"] - p["x_fin"]) * p["m_n"] * math.sin(p["alpha_n"]) - _num(raw, "q", i-1)) > 1e-9:
            raise ValueError("xEV−xE 与原表 q 不一致")
        result, detail = protuberance_dff_converged(p)
        out[f"d_Ff_{i}"] = {"value": result.value, "unit": "mm", "convergence": result.convergence,
                            "inputs": {k: p[k] for k in sorted(p)}, **detail}
    return out


def three_way(number, *, zv_velocity, hardness_conversion=None, rz_source=None, with_protuberance_dff=False):
    """逐行三方对拍。全部选择器显式：例7 须给 hardness_conversion，例8 须给 rz_source（KISSsoft 用印刷 Rz=2.3，同输入为
    'printed_rz'）。with_protuberance_dff=True 时，例8 的 d_Ff 行用 protuberance_dff_example8 的数值方法结果。"""
    if number not in (7, 8):
        raise ValueError("只有例7、例8 有 KISSsoft 复算")
    kw = {"zv_velocity": zv_velocity}
    extra = None
    if number == 7:
        if hardness_conversion not in HARDNESS_CONVERSIONS:
            raise ValueError(f"例7 须显式选择 hardness_conversion ∈ {HARDNESS_CONVERSIONS}（正式口径 ISO18265_A1_linear）")
        kw["hardness_conversion"] = hardness_conversion
        if hardness_conversion == "HV_external_readback":
            extra = hv_readback_inputs(7)
    else:
        if hardness_conversion is not None:
            raise ValueError("例8 为 HRC 标尺，不做硬度换算")
        if rz_source is None:
            raise ValueError("例8 须显式选择 rz_source（KISSsoft 同输入为 printed_rz）")
        kw["rz_source"] = rz_source
    report = compare_full(number, **kw, extra_inputs=extra)
    if report["status"] != "full_rating_diagnostic":
        raise ValueError(f"例{number} 建图阻断：{report.get('errors')}")
    gb = {r["quantity"]: r for r in report["rows"]}
    dff = protuberance_dff_example8() if (number == 8 and with_protuberance_dff) else {}
    rows = []
    for k in load_comparison(number):
        q = k["quantity"]
        row = {"quantity": q, "unit": k["unit"], "kisssoft_mapping": k["kisssoft_mapping"],
               "tr30_printed": float(k["tr30_printed"]) if k["tr30_printed"] else None,
               "kisssoft": float(k["kisssoft"]) if k["kisssoft"] else None}
        g = gb.get(q, {})
        row["display"] = g.get("display")
        if q in dff:
            row["gearbase"], row["gearbase_status"] = dff[q]["value"], "numerical_method_outside_graph"
        elif "actual" in g:
            row["gearbase"], row["gearbase_status"] = g["actual"], g["status"]
        else:
            row["gearbase"], row["gearbase_status"] = None, g.get("status", "absent")
        ks, gv, tr = row["kisssoft"], row["gearbase"], row["tr30_printed"]
        if ks is not None and gv is not None:
            row["gb_minus_ks"] = gv - ks
            row["gb_ks_strict"] = strict_gate(gv, ks)
        if tr is not None and row["display"] is not None:
            tol = quantum_tolerance(row["display"], tr)
            row["quantum_tolerance"] = tol
            if ks is not None:
                row["ks_tr30_quantum"] = abs(ks - tr) <= tol + 1e-12
            if gv is not None:
                row["gb_tr30_quantum"] = abs(gv - tr) <= tol + 1e-12
        rows.append(row)
    both = [r for r in rows if "gb_ks_strict" in r]
    summary = {
        "rows_total": len(rows),
        "kisssoft_rows": sum(r["kisssoft"] is not None for r in rows),
        "gb_ks_compared": len(both),
        "gb_ks_strict_pass": sum(r["gb_ks_strict"] for r in both),
        "gb_ks_strict_fail": sorted(r["quantity"] for r in both if not r["gb_ks_strict"]),
        "no_kisssoft_value": sorted(r["quantity"] for r in rows if r["kisssoft"] is None),
        "no_gearbase_value": sorted(r["quantity"] for r in rows if r["kisssoft"] is not None and r["gearbase"] is None),
        "ks_tr30_quantum_fail": sorted(r["quantity"] for r in rows if r.get("ks_tr30_quantum") is False),
        "gb_tr30_quantum_fail": sorted(r["quantity"] for r in rows if r.get("gb_tr30_quantum") is False),
        "max_abs_gb_minus_ks": max((abs(r["gb_minus_ks"]) for r in both), default=None),
    }
    return {"schema": "gearmath.tr30_kisssoft78/v1", "example_number": number, "accepted": False,
            "selectors": {**report["selectors"], **({"hardness_conversion": hardness_conversion} if number == 7 else {})},
            "formal_hardness_conversion": "ISO18265_A1_linear" if number == 7 else None,
            "evidence_inputs": {n: {"value": v[0], "source": v[3]} for n, v in (extra or {}).items()},
            "model_sha256": report["model_sha256"], "summary": summary, "rows": rows,
            "protuberance_dff": dff or None}


def classify(number, result):
    """把剩余差异按性质归类（只读结果，不改判据）。"""
    out = []
    s = result["summary"]
    for q in s["gb_ks_strict_fail"]:
        base = q.rsplit("_", 1)[0]
        nature = NATURE[(number, "gb_ks", "material")] if (number == 7 and base in MATERIAL_ROWS) else "未知（未登记）"
        out.append({"pair": "gearbase↔KISSsoft", "quantity": q, "nature": nature})
    tr_fail = sorted(set(s["ks_tr30_quantum_fail"]) | set(s["gb_tr30_quantum_fail"]))
    for q in tr_fail:
        base = q.rsplit("_", 1)[0]
        if number == 7 and base in MATERIAL_ROWS:
            nature = NATURE[(7, "tr30", "material")]
        elif number == 8 and q in ("sigma_F0_1", "sigma_F_2"):
            nature = NATURE[(8, "tr30", "root_stress")]
        else:
            nature = "未知（未登记）"
        out.append({"pair": "KISSsoft/gearbase↔TR30", "quantity": q, "nature": nature,
                    "kisssoft_fails": q in s["ks_tr30_quantum_fail"], "gearbase_fails": q in s["gb_tr30_quantum_fail"]})
    return out


def relief_sensitivity_summary(number):
    d = load_relief_sensitivity(number)
    rows = d["rows"]
    return {"baseline": d["baseline"], "sensitivity": d["sensitivity"],
            "mapped_rows": sum(r["unchanged"] is not None for r in rows),
            "unchanged": sum(r["unchanged"] is True for r in rows),
            "changed": sorted(r["quantity"] for r in rows if r["unchanged"] is False),
            "not_mapped": sorted(r["quantity"] for r in rows if r["unchanged"] is None),
            "input_missing_from_TR30": d["input_missing_from_TR30"],
            "strict_input_closure": False,
            "meaning": "两点（线性修缘 LCa=0.5·mn 与 1·mn）下可映射输出全部不变：附属假设对已对拍的输出无数值影响；"
                       "但 TR30 未给修缘长度/形状，原生文件仍含原表以外的输入，形式上的严格同输入不闭合"}


def evidence_summary():
    """供 m33_acceptance 门使用的紧凑结论（正式口径 + 外部 HV 变体 + 凸台 dFf + 修缘敏感性）。"""
    r7 = three_way(7, zv_velocity="v_ref", hardness_conversion="ISO18265_A1_linear")
    r7x = three_way(7, zv_velocity="v_ref", hardness_conversion="HV_external_readback")
    r8 = three_way(8, zv_velocity="v_ref", rz_source="printed_rz", with_protuberance_dff=True)
    dff = r8["protuberance_dff"]
    rows8 = {r["quantity"]: r for r in r8["rows"]}
    # ISO 6336-2:2019 6.3 前提（有效啮合线不被缩短）的主图外数值核查：|dNf| ≥ |dFf|（主图仍按显式假设处理）
    contact_path = {f"gear_{i}": {"d_Nf": rows8[f"d_Nf_{i}"]["gearbase"], "d_Ff": dff[f"d_Ff_{i}"]["value"],
                                  "margin_mm": rows8[f"d_Nf_{i}"]["gearbase"] - dff[f"d_Ff_{i}"]["value"]} for i in (1, 2)}
    return {
        "source": UPLOAD, "native_z12_sha256": NATIVE_Z12_SHA256, "accepted": False,
        "user_conclusion": "M33 仍未验收（用户）",
        "TR30-7": {"formal_ISO18265_A1_linear": r7["summary"], "HV_external_readback": r7x["summary"],
                   "residual_natures": classify(7, r7), "relief_length": relief_sensitivity_summary(7),
                   "material_limits_not_independent": "KISSsoft σHlim/σFlim 由构建脚本按 ISO 6336-5 V/ML 式(2) 以读回 HV 填入，"
                                                      "不是 KISSsoft 材料库独立取得"},
        "TR30-8": {"printed_rz": r8["summary"], "residual_natures": classify(8, r8), "relief_length": relief_sensitivity_summary(8),
                   "protuberance_dFf": {k: {"value": v["value"], "branch": v["branch"], "h_prP0_derived": v["h_prP0_derived"],
                                            "convergence_status": v["convergence"]["status"],
                                            "evidence_nature": v["evidence_nature"]} for k, v in dff.items()},
                   "contact_path_numeric_check": {**contact_path,
                                                  "holds": all(v["margin_mm"] > 0 for v in contact_path.values()),
                                                  "note": "主图外数值核查；主图 contact_path_not_shortened 仍为显式假设（dFf 未接入）"}},
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = json.dumps(evidence_summary(), ensure_ascii=False, indent=2, allow_nan=False, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    raise SystemExit(2)
