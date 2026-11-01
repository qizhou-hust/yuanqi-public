"""Reproduce M33 comparisons; source identity and full acceptance are separate.

TR30 验收判据（ISO/TR 6336-30:2022 4.2.14/4.2.15，PDF14–15/印刷8–9 原图已核）：
4.2.14 写明计算用未舍入值、表中数值为舍入值；4.2.15 规定程序间偏差范围为绝对 0,01
与相对 0,5 %，且"计算值同时处于绝对与相对范围内"。据此按参考值的显示量子 q 分两档：

* A 档（实质未舍入参考，如附录A 3–5位小数）：q/2 ≤ 0.1·min(0.01, 0.005|r|)，
  判据 |Δ| ≤ 0.01 且 |Δ| ≤ 0.005|r|，即 4.2.15 原文双门；
* B 档（只有舍入表值）：|Δ| ≤ q/2 + min(0.01, 0.005|r|)。q/2 是 4.2.14 舍入本身
  带来的、与计算无关的不确定度；在其外再给 4.2.15 双门，即"任何与 TR 未舍入值
  在 4.2.15 范围内一致的计算都不会被误判"的最紧界。不用 max(0.01, 0.5%) 的或读法。

旧的"直接拿舍入表值套双门"一列（strict_match）照旧输出，仅作透明诊断。
方法差异（如 ZV 的 v/vw）只能用显式选择器加出处解决，不得用容差吸收。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .factor_methods import K01_FULL_FACTOR_SELECTORS
from .kisssoft_case import EVIDENCE_MAP, compare
from .tr30_case import run_suite


ABS_TOL, REL_TOL = 0.01, 0.005
TIER_A_FRACTION = 0.1      # 舍入误差不超过双门带宽的 10 % 才视为"未舍入"参考
ANNEX_DATA = {1: Path(__file__).resolve().parents[2] / "data/tr30/annex-a-example1.json"}


def display_quantum(display):
    """原表显示量子 q（如 "1 338" → 1，"0,97" → 0.01）；无法解析的显示返回 None。"""
    text = str(display).replace(" ", "").replace("\u00a0", "").replace(",", ".").lstrip("+-")
    if not text or any(c not in "0123456789." for c in text) or text.count(".") > 1:
        return None
    return 10.0 ** -len(text.split(".")[1]) if "." in text else 1.0


def tier_verdict(actual, reference, quantum):
    """单行判定：返回 tier、bound、verdict（pass_A / pass_B / fail）。"""
    band = min(ABS_TOL, REL_TOL * abs(reference))
    delta = actual - reference
    if quantum / 2 <= TIER_A_FRACTION * band:
        tier, bound = "A", band
        ok = abs(delta) <= ABS_TOL + 1e-12 and abs(delta) <= REL_TOL * abs(reference) + 1e-12
    else:
        tier, bound = "B", quantum / 2 + band
        ok = abs(delta) <= bound + 1e-12
    return {"tier": tier, "display_quantum": quantum, "acceptance_bound": bound,
            "difference": delta, "acceptance_verdict": f"pass_{tier}" if ok else "fail"}


def _annex_rows(case):
    """附录A 未舍入中间值（只含数值与页码）逐项对拍；模型只由输入构建。"""
    path = ANNEX_DATA.get(case.get("example_number"))
    if path is None:
        return []
    from ..kernel import units as U
    from .tr30_rating import build_model
    annex = json.loads(path.read_text(encoding="utf-8"))
    model = build_model(case)
    rows = []
    for ref in annex["rows"]:
        row = {"quantity": ref["quantity"], "symbol": ref["symbol"], "reference": ref["value"],
               "unit": ref["unit"], "display": ref["display"], "citation": ref["citation"], "source_kind": "annex_A"}
        q = ref["quantity"]
        if q is None or (q not in model.formulas and q not in model.inputs):
            rows.append({**row, "status": "not_implemented"})
            continue
        if q in model.inputs:
            rows.append({**row, "status": "input_not_formula"})
            continue
        result = model.evaluate([q])
        if result.status != "ok":
            rows.append({**row, "status": result.status})
            continue
        actual = U.from_canonical(result.values[q], ref["unit"])
        rows.append({**row, "status": "computed", "actual": actual,
                     **tier_verdict(actual, ref["value"], ref["display_quantum"])})
    return rows


def _mandated_names(required, names):
    """契约最低覆盖量 → 实际行名（共用名在逐轮行存在时展开为 _1/_2）。"""
    out = {}
    for name in required:
        if name in names:
            out[name] = [name]
        else:
            out[name] = [n for n in (f"{name}_1", f"{name}_2") if n in names]
    return out


def tr30_acceptance(report, case):
    """按分档判据给出例1–4 的逐行与逐例验收结论；不改 strict_match 诊断列。"""
    from .tr30_case import load_suite
    table = []
    for row in report.get("rows", []):
        item = {k: row.get(k) for k in ("quantity", "source_quantity", "stage", "reference", "unit", "display", "citation")}
        item["source_kind"] = "table"
        if row.get("status") in ("match", "divergence"):
            quantum = display_quantum(row.get("display"))
            if quantum is None:
                item["status"] = "unparsed_display"
            else:
                item.update(status="computed", actual=row["actual"],
                            strict_on_rounded=row.get("strict_match"),
                            **tier_verdict(row["actual"], row["reference"], quantum))
        else:
            item["status"] = "not_implemented" if row.get("status") == "unsupported_no_formula" else row.get("status")
        table.append(item)
    annex = _annex_rows(case)
    computed = [r for r in table + annex if r["status"] == "computed"]
    published = {r["quantity"] for r in table + annex if r.get("quantity")}
    required = load_suite()["required_formula_outputs"]
    mandated = _mandated_names(required, published)
    mandated_rows, not_published, missing = [], [], []
    for name, rows in mandated.items():
        if not rows:
            not_published.append(name)
            continue
        hits = [r for r in computed if r["quantity"] in rows]
        if {r["quantity"] for r in hits} != set(rows):
            missing.append(name)
        mandated_rows += hits
    fails = [r for r in computed if r["acceptance_verdict"] == "fail"]
    mandated_fail = [r for r in mandated_rows if r["acceptance_verdict"] == "fail"]
    not_impl = sorted({r.get("quantity") or r.get("symbol") for r in table + annex if r["status"] == "not_implemented"})
    verdict = "pass" if not fails and not missing and mandated_rows else "fail"
    count = lambda rows, v: sum(r["acceptance_verdict"] == v for r in rows)
    summary = {}
    for kind, rows in (("table", table), ("annex_A", annex)):
        done = [r for r in rows if r["status"] == "computed"]
        summary[kind] = {"computed": len(done), "pass_A": count(done, "pass_A"), "pass_B": count(done, "pass_B"),
                         "fail": count(done, "fail"), "strict_on_rounded": sum(bool(r.get("strict_on_rounded")) for r in done),
                         "not_implemented": sum(r["status"] == "not_implemented" for r in rows),
                         "input_not_formula": sum(r["status"] == "input_not_formula" for r in rows)}
    first = next((r for r in table + annex if r["status"] == "computed" and r["acceptance_verdict"] == "fail"), None)
    # 全表门（契约：输出表 Table 4/6/8/10 每行都要有公式结果并通过）。未实现、域外（如根切超出
    # A.6 前提）、阻断都算未覆盖；input_not_formula 与原表无参考值的行不计。附录A 中间量另列。
    covered = ("computed", "input_not_formula", "reference_not_applicable")
    table_uncovered = sorted({r["quantity"] for r in table if r["status"] not in covered})
    annex_not_output = sorted({r.get("quantity") or r.get("symbol") for r in annex if r["status"] not in covered})
    assumptions = sorted((report.get("assumptions") or {}).keys())
    premise_audit = report.get("premise_audit") or {}
    eliminated = sorted(k for k, v in premise_audit.items() if v.get("status") == "eliminated_by_formula")
    full_table = verdict == "pass" and not table_uncovered
    blockers = []
    if verdict != "pass":
        blockers.append("分档数值验收未通过")
    if table_uncovered:
        blockers.append("输出表未覆盖行：" + "、".join(table_uncovered))
    if annex_not_output:
        blockers.append("附录A 无独立输出的中间量：" + "、".join(annex_not_output))
    if assumptions:
        blockers.append("显式适用性假设未消除：" + "、".join(assumptions))
    return {"rule": "tr30_tiered_4.2.14_4.2.15", "abs_tol": ABS_TOL, "rel_tol": REL_TOL,
            "tier_a_fraction": TIER_A_FRACTION, "verdict": verdict, "summary": summary,
            "mandated_rows": len(mandated_rows), "mandated_failures": [r["quantity"] for r in mandated_fail],
            "mandated_not_published_by_source": not_published, "mandated_missing": missing,
            "first_acceptance_failure": first, "not_implemented": not_impl,
            # 全表覆盖只看输出表；E4/全表授予（e4_gate）另要求附录A 中间量齐全且无显式适用性假设
            "full_table_coverage": full_table, "table_uncovered": table_uncovered,
            "annex_not_output": annex_not_output, "applicability_assumptions": assumptions,
            "premises_eliminated_by_formula": eliminated, "premise_audit": premise_audit,
            "e4_gate": not blockers, "e4_blockers": blockers,
            "rows": table + annex}


# ---------------- 验收门（v0.8-R1）：逐例偏差登记与"有条件 / 严格"所缺证据 ----------------
# 四件事分开：资料可读（source_readable）、商业工具复算一致（commercial_recompute）、公式对拍通过
# （formula_crosscheck）、产品强度合格（product_strength，本项目不判定，恒为 not_assessed）。
# 本门从不授予验收：strict_gate 只在全部条件满足时才可能为 True，conditional 只列出需用户逐条批准的偏差。
DEVIATION_REGISTER = {
    # (例, 量) → 性质与已排除原因；未登记的失败行一律记"未知（未登记）"，只会更严
    (4, "d_Ff_1"): {"nature": "未实现", "first_divergence": "d_Ff_1（A.6 方括号为负，小轮根切）",
                    "excluded": ["A.6 原文前提'no undercut'不成立，不外推"],
                    "evidence_needed": "有根切齿形的 dFf 已核公式（ISO 21771 原文）或商业工具复算"},
    (4, "d_Nf_1"): {"nature": "未实现", "first_divergence": "d_Nf_1 的干涉核查依赖 d_Ff_1",
                    "excluded": ["dNf 数值本身按 A.6 可算（127,976），只因干涉核查需 dFf1 而域外"],
                    "evidence_needed": "同 d_Ff_1"},
    (7, "sigma_Hlim_2"): {"nature": "来源冲突", "first_divergence": "σHlim2（ISO 18265 表A.1 换算 HB→HV）",
                          "excluded": ["输入单位、材料表行、质量等级均已核；HB/0.95 近似可使该行通过"],
                          "evidence_needed": "TR30 例7 硬度换算口径的原文说明（原表数值更接近 HB/0.95；KISSsoft 2026 齿轮模块读回"
                                             "≈HB/0.9505，与 ISO 18265 表A.1 插值及原表均不同），或用户批准按来源冲突记录"},
    (7, "sigma_Flim_2"): {"nature": "来源冲突", "first_divergence": "σFlim2（同 σHlim2 的硬度换算口径）",
                          "excluded": ["同 σHlim2"], "evidence_needed": "同 σHlim2"},
    (7, "sigma_FP_2"): {"nature": "来源冲突", "first_divergence": "σFP2 由 σFlim2 传递（HB/0.95 口径下仍差 0,61 MPa）",
                        "excluded": ["同 σHlim2；HB/0.95 口径下该行仍超界 0,10 MPa，说明不止换算口径一处，余量原因未知"],
                        "evidence_needed": "同 σHlim2；另需未舍入参考值确认 σFP2 余差"},
    (7, "f_sh0"): {"nature": "来源未定义（显式选择器）", "first_divergence": "f_sh0（双斜齿 specific load 口径）",
                   "excluded": ["total_width（ISO 6336-1 7.5.1 b=2b_B 字面）得 0,01998 → 失败；per_helix（式(60) 2F_m/b=F_m/b_B）得 0,00999 → 通过"],
                   "evidence_needed": "fsh0 对双斜齿的原文定义（ISO 6336-1 其它版次或 TR30 计算说明），或用户选定口径"},
    (8, "d_Ff_1"): {"nature": "未实现", "first_divergence": "d_Ff_1（残余凸台 pr=0,267、q=0,22、凸台角 10°）",
                    "excluded": ["A.6 齿条式不适用（原文前提无凸台）；精加工/预加工齿条按 A.6 代入得 64,94/65,49 均不符 65,87（仅诊断，未采用）",
                                 "ISO 6336-3 图2（PDF23/印15）只定义 pr、q、s_pr，未给凸台高度与凸台角，几何不封闭",
                                 "K1：主图外数值包络（ISO 6336-3 式(26) 预加工圆角 + A.6 展成原理 + xEV）得 65,874865/284,033308 mm，"
                                 "与 KISSsoft 2026 dNf0.E 差 3,4e-7/1,8e-7 mm，与原表显示一致；交点在圆角包络上，对凸台角不敏感"],
                    "evidence_needed": "dFf（磨削渐开线与预加工齿廓交点）定义的原文核图（ISO 21771 不在资料包）；"
                                       "并由用户决定是否把主图外数值方法结果接入公式图（接入前本行仍记未实现）"},
    (8, "d_Ff_2"): {"nature": "未实现", "first_divergence": "d_Ff_2（同 d_Ff_1）", "excluded": ["同 d_Ff_1"],
                    "evidence_needed": "同 d_Ff_1"},
    (8, "sigma_F0_1"): {"nature": "未知", "first_divergence": "σF0_1（几何/载荷/K/Z/Y 全部在显示量子内，首分歧在应力段）",
                        "excluded": ["F_t 舍入", "ISO 6336-3 5.2 NOTE 宽轮承载宽", "预加工/精加工齿条装配", "fε", "Yβ 两种实现偏差",
                                     "统一 s_pr 扫描 0–0,06 mm",
                                     "K1：KISSsoft 2026 复算 σF0_1=291,7367（本库 291,7343，差 0,0025 MPa）、Y_F/Y_S 两实现在双门内，"
                                     "两者都高于印刷 291：本库实现偏差基本排除，原表印刷为候选，不能断言原表错误"],
                        "evidence_needed": "例8 未舍入参考值（附录级）或 TR30 勘误；KISSsoft 复算已到位但不能替代原表"},
    (8, "sigma_F_2"): {"nature": "未知", "first_divergence": "σF_2（与 σF0_1 同一共有乘子 k≈0,9989–0,9992）",
                       "excluded": ["同 σF0_1"], "evidence_needed": "同 σF0_1"},
    (8, "sigma_HP_1"): {"nature": "来源冲突", "first_divergence": "σHP_1（Rz 取 6·Ra=2,28 时）",
                        "excluded": ["选 printed_rz（原表括号 2,3）时通过；TR30 4.2.7 规定 Rz=6Ra"],
                        "evidence_needed": "用户裁定 Rz 口径（rz_source），或 TR30 勘误"},
    (8, "sigma_HP_2"): {"nature": "来源冲突", "first_divergence": "σHP_2（同 σHP_1）", "excluded": ["同 σHP_1"],
                        "evidence_needed": "同 σHP_1"},
}
K_DEVIATION_REGISTER = {
    ("K03-premachining", "c_s"): {"nature": "原表精度", "excluded": ["报告 hfP* 只印 3 位，c′ 多项式对其敏感"],
                                  "evidence_needed": "KISSsoft 原生文件中未舍入 hfP*"},
    ("K03-premachining", "c_gamma_alpha"): {"nature": "原表精度", "excluded": ["由 c′ 传递"], "evidence_needed": "同 c_s"},
    ("K03-premachining", "c_gamma_beta"): {"nature": "原表精度", "excluded": ["由 c′ 传递"], "evidence_needed": "同 c_s"},
    ("K03-premachining", "n_E1"): {"nature": "原表精度", "excluded": ["由 cγα 传递"], "evidence_needed": "同 c_s"},
}


# ---------------- 用户决定 2026-10-30（docs/接力交接-2026-10-30.md 第 3 节 8 项） ----------------
# 只记录决定、决定者与依据，并据此给出"决定后"视图（user_decided）。它不放宽任何判据、不改参考值、不改门限：
# strict_gate 的计算不读取本表；accepted_by_tool / m33_accepted 恒为 False（只有用户能宣布 M33 验收）。
DECISION_DATE = "2026-10-30"
USER_DECISIONS = {
    "D1-ex6-dFf2-composition": {
        "items": ["TR30-6"], "decided_by": "用户", "status": "approved",
        "decision": "认可例6 d_Ff_2 组合式（A.6 SAP 原理 + ISO 6336-3 式(37)(40)–(43)），结果与原表一致",
        "basis": "两条已核原式组合；−1212,794 对原表 −1212,79（界 0,015）"},
    "D2-ex7-fsh0-per_helix": {
        "items": ["TR30-7"], "decided_by": "O（用户授权）", "status": "approved_conditional",
        "decision": "fsh0_basis=per_helix（specific load 取 F_m/b_B）",
        "basis": "按 ISO 6336-1:2019 式(60) 与式(59) 同形、b→b_B 的读法 fsh0=0,00999，与 TR30 原表 0,010 相符；"
                 "per_helix 下 95/98 通过、total_width 下 94/98；7.5.1 字面'specific load 取总宽'读法（0,01998）与原表不符",
        "condition": "物理量 fsh/KHβ 已获 KISSsoft 2026 外部一致；fsh0 符号口径 KISSsoft 未直接导出，仍待标准明文或原生 fsh0 字段",
        "pending_external": "fsh0 符号定义（KISSsoft 无直接 fsh0 导出；fsh 与 KHβ 对两种口径均不变，不能判别）",
        "external_evidence": {
            "tool": "KISSsoft Release 2026 (26.0.0.0), Z012, 例7 原样运行 edits=[]", "date": "2026-10-31",
            "extract": "data/kisssoft_v014/P1-TR30-ex7.json",
            "sources": {"run.json": {"path": "P1-TR30-example7-unchanged/run.json", "sha256": "6251b32c233921a25c40139a3027e5dd155ce5d5018e221144d315385b4dd5fe"},
                        "report_txt": {"path": "P1-TR30-example7-unchanged/P1-TR30-example7-unchanged.txt", "sha256": "4f6f79a2fbb62e8d25d0e82909181d4627c8be679342e9a56c6fb0a36d3b4b85"},
                        "preflight": {"path": "P1-preflight.md", "sha256": "59be14b0e93276f04067daacfe281e229b0ca06d3df30667f58cacfa10fcadfa"}},
            "physical_fsh_khbeta": "consistent",
            "fsh0_symbol_basis": "not_discriminated",
            "result": "fsh 本库 1,403009 vs KISSsoft 1,402990 µm（相对差 1,4e-5，全部由 K_V 差 1,4e-5 解释）；KHβ 1,380982 vs 1,380949；"
                      "两口径下 fsh/KHβ/SH/SF 逐位相同（选择器只改 fsh0 报告行）。KISSsoft 归一派生值 0,0099918（单侧）/0,0199836（总宽）"
                      "与本库 per_helix/total_width 的 fsh0 各自一致，但属派生而非 KISSsoft 导出",
            "conclusion": "外部确认（物理量 fsh 与 KHβ 一致；fsh0 符号定义差异已说明）；per_helix 作为 fsh0 符号口径仍为有条件（采用依据：TR30 原表 0,010）"}},
    "D3-ex7-HB_to_HV": {
        "items": ["TR30-7"], "decided_by": None, "status": "pending",
        "decision": "未决定（用户未表态）。延续 v0.10 用户核查建议：保留 ISO 18265 表A.1 口径作为计算口径，但不记作已决定",
        "basis": "ISO 18265 插值 315,556 HV、KISSsoft 读回 315,623 HV、原表接近 HB/0,95，三者冲突"},
    "D4-ex8-Rz-printed": {
        "items": ["TR30-8"], "decided_by": "用户", "status": "approved",
        "decision": "Rz 取原表印刷值 2,3（rz_source=printed_rz），不用 6·Ra=2,28",
        "basis": "用户裁定；与 KISSsoft 复算同输入"},
    "D5-ex8-sigmaF-known-deviation": {
        "items": ["TR30-8"], "decided_by": "用户", "status": "approved_conditional",
        "decision": "σF0_1、σF_2 对 TR30 印刷值的偏差记为'用户接受的已知偏差（有条件）'；不改参考值、不改门限，行仍判 fail",
        "basis": "gearbase 与 KISSsoft 2026 两个独立实现相差 <0,003 MPa，二者同向偏离印刷值；偏差不能由印刷舍入 q/2 解释（见 deviation_review）",
        "condition": "TR30 勘误或未舍入参考值出现时重新判定"},
    "D6-LCa-0.5mn": {
        "items": ["TR30-7", "TR30-8"], "decided_by": "O（用户授权）", "status": "approved_conditional",
        "decision": "KISSsoft 复算修缘长度 LCa=0,5·mn（候选文件现用值），记为附属假设",
        "basis": "0,5mn 与 1mn 两点敏感性下全部可映射输出不变；本库方法 B 不使用 LCa",
        "condition": "strict_input_closure 仍为 false（TR30 未给修缘长度/形状）"},
    "D7-ex8-protuberance-dFf-in-graph": {
        "items": ["TR30-8"], "decided_by": "用户", "status": "approved",
        "decision": "凸台 dFf 数值方法接入主图（tr30_full58 选择器 protuberance_dff=numerical_envelope，derived 输入节点，E1 上限）",
        "basis": "与 KISSsoft 2026 dNf0.E 差 ≤3,4e-7 mm；dFf 定义原图仍无法确认（不影响本例数值）"},
    "D8-premises-conditional-evidence": {
        "items": [f"TR30-{n}" for n in range(1, 9)], "decided_by": "用户", "status": "approved_conditional",
        "decision": "矿物油、VI95、两轮齿根表面完好 4 项适用性假设作为条件证据（复现 TR30 例题口径）",
        "basis": "TR30 A.9.2 式(42)、A.10 式(87) 对例1 实际套用以其为前提的式；模型内 provenance 仍为 assumption（E0），产品强度目的不适用",
        "premises": ["surface_oil_mineral", "surface_nu40_vi95", "root_surface_intact_1", "root_surface_intact_2"]},
}
APPROVED_PREMISES = set(USER_DECISIONS["D8-premises-conditional-evidence"]["premises"])
# 用户批准的偏差登记：行仍为 fail、性质仍为 DEVIATION_REGISTER 原值；只追加批准记录
USER_APPROVED_DEVIATIONS = {
    (8, "sigma_F0_1"): {"decision": "D5-ex8-sigmaF-known-deviation", "label": "用户接受的已知偏差（有条件）"},
    (8, "sigma_F_2"): {"decision": "D5-ex8-sigmaF-known-deviation", "label": "用户接受的已知偏差（有条件）"},
}
# 决定后的计算口径（例5/6 无选择器）
DECIDED_RUNS = {
    5: ("decided", {}),
    6: ("decided", {}),
    7: ("decided: fsh0=per_helix, hardness=ISO18265_A1_linear(待决)", {"fsh0_basis": "per_helix"}),
    8: ("decided: rz=printed_rz, dFf=numerical_envelope", {"rz_source": "printed_rz", "protuberance_dff": "numerical_envelope"}),
}
REMAINING_BLOCKERS = [
    "例7 HB→HV 正式口径待用户决定（D3；σHlim2/σFlim2/σFP2 仍为来源冲突，σFP2 另有未知余差）",
    "例7 fsh0=per_helix 为 O 决策（用户授权）的有条件结论，待用户在 KISSsoft 输出 fsh0/fsh 外部确认（D2）",
    "扩展严格几何门 2/6 失败明细待用户提供（v0.10 用户独立核查，接力交接 7.3）",
    "例4 根切 dFf1/dNf1 未实现，啮合线不缩短仍为显式假设（无用户决定覆盖）",
    "例1 附录A 11 个中间量无独立输出",
    "例8 σF0_1/σF_2 为用户接受的已知偏差（有条件），严格门仍不通过；需 TR30 勘误或未舍入值才能关闭",
    "例7/8 strict_input_closure=false（LCa 附属假设，D6）",
    "K01–K05：商业工具/报告值输入、KHβ external、K03 齿根链未实现",
]


def deviation_review_sigma_f(rows):
    """D5 复核：gearbase 与 KISSsoft 对 TR30 印刷值的绝对/相对偏差，及能否由印刷舍入（q/2）解释。只读，不改判据。"""
    from .tr30_kisssoft78 import load_comparison
    ks = {k["quantity"]: float(k["kisssoft"]) for k in load_comparison(8) if k["kisssoft"]}
    out = {}
    for q in ("sigma_F0_1", "sigma_F_2"):
        r = rows[q]
        ref, quantum = r["reference"], display_quantum(r["display"])
        band = min(ABS_TOL, REL_TOL * abs(ref))
        entry = {"printed": ref, "display_quantum": quantum, "rounding_half_quantum": quantum / 2,
                 "acceptance_bound": quantum / 2 + band}
        for side, v in (("gearbase", r["actual"]), ("kisssoft", ks[q])):
            d = v - ref
            entry[side] = {"value": v, "abs_dev": d, "rel_dev": d / ref,
                           "explained_by_rounding": abs(d) <= quantum / 2,
                           "excess_over_half_quantum": abs(d) - quantum / 2,
                           "excess_over_bound": abs(d) - (quantum / 2 + band)}
        entry["gearbase_minus_kisssoft"] = r["actual"] - ks[q]
        entry["conclusion"] = ("不能由印刷舍入解释（两实现都超出 q/2，且同向）；两实现互差远小于 4.2.15 双门。"
                               "原表印刷/勘误为候选原因，不能断言原表错误")
        out[q] = entry
    return out


def _deviation(example, row, variant=""):
    reg = DEVIATION_REGISTER.get((example, row["quantity"]))
    base = {"quantity": row["quantity"], "status": row.get("status"), "variant": variant,
            "actual": row.get("actual"), "reference": row.get("reference"), "difference": row.get("difference"),
            "bound": row.get("quantum_tolerance", row.get("acceptance_bound"))}
    if reg is None:
        return {**base, "nature": "未知（未登记）", "first_divergence": row["quantity"], "excluded": [],
                "evidence_needed": "逐段排查后登记"}
    return {**base, **reg}


def _tr30_full58_item(number):
    from .tr30_full58 import compare_full
    variants = {5: {"": {}}, 6: {"": {}},
                7: {"fsh0=total_width": {"fsh0_basis": "total_width"}, "fsh0=per_helix": {"fsh0_basis": "per_helix"}},
                8: {"rz=ra_times_6": {"rz_source": "ra_times_6"}, "rz=printed_rz": {"rz_source": "printed_rz"}}}[number]
    runs, deviations, premises = {}, [], {}
    for label, kw in variants.items():
        r = compare_full(number, **kw)
        runs[label or "default"] = {"counts": r["counts"], "selectors": {k: v for k, v in r.get("selectors", {}).items()
                                                                        if k in ("method.f_sh0_specific_load", "method.Rz_H_source")}}
        premises = r.get("premise_audit", {})
        for row in r["rows"]:
            if row["status"] in ("fail", "not_implemented", "blocked"):
                deviations.append(_deviation(number, row, label))
    computed = {k: v["counts"].get("pass", 0) + v["counts"].get("fail", 0) for k, v in runs.items()}
    # 决定后视图（用户决定 2026-10-30）：只多跑一个口径，不改上面各口径的诊断
    label, kw = DECIDED_RUNS[number]
    r = compare_full(number, **kw)
    decided_rows = {row["quantity"]: row for row in r["rows"]}
    residual = []
    for row in r["rows"]:
        if row["status"] in ("fail", "not_implemented", "blocked"):
            d = _deviation(number, row, label)
            approval = USER_APPROVED_DEVIATIONS.get((number, row["quantity"]))
            if approval:
                d["user_approval"] = {**approval, "date": DECISION_DATE,
                                      "decided_by": USER_DECISIONS[approval["decision"]]["decided_by"]}
            residual.append(d)
    decided = {"run": label, "selectors": {k: v for k, v in r.get("selectors", {}).items()
                                           if k in ("method.f_sh0_specific_load", "method.Rz_H_source",
                                                    "method.d_Ff_protuberance")},
               "counts": r["counts"], "computed_rows": r["counts"].get("pass", 0) + r["counts"].get("fail", 0),
               "residual_deviations": residual, "premise_audit": r.get("premise_audit", {}),
               "numerical_nodes": r.get("numerical_nodes", {})}
    if number == 8:
        decided["deviation_review"] = deviation_review_sigma_f(decided_rows)
    return {"runs": runs, "computed_rows": computed, "deviations": deviations, "premise_audit": premises,
            "decided": decided}


def _user_decided_view(key, item, decided=None):
    """按用户决定 2026-10-30 给出：已批准条件、仍待批准/待证据的项。不改 strict_gate。"""
    decisions = {k: v for k, v in USER_DECISIONS.items() if key in v["items"]}
    approved, pending = [], []
    for k, v in decisions.items():
        (pending if v["status"] == "pending" else approved).append(
            f"{k}（{v['decided_by'] or '未决定'}，{v['status']}）：{v['decision']}")
        if v.get("pending_external"):
            pending.append(f"{k} 待外部确认：{v['pending_external']}")
    if decided is not None:
        deviations = decided["residual_deviations"]
        premises = decided["premise_audit"]
        assumptions = sorted(n for n, a in premises.items() if a.get("status") == "assumption")
    else:
        deviations, assumptions = item["deviations"], item["open_assumptions"]
        if item.get("annex_not_output"):
            pending.append("附录A 无独立输出的中间量：" + "、".join(item["annex_not_output"]))
    for d in deviations:
        if "user_approval" not in d:
            pending.append(f"{d['quantity']}（{d['nature']}）")
    for a in assumptions:
        if a not in APPROVED_PREMISES:
            pending.append(f"{a}（显式假设，无用户决定覆盖）")
    view = {"decision_date": DECISION_DATE, "decisions": sorted(decisions), "approved_conditions": approved,
            "approved_premises_as_conditional_evidence": sorted(set(assumptions) & APPROVED_PREMISES),
            "still_pending": pending, "accepted": False,
            "note": "决定后视图只汇总用户/O（用户授权）决定；不宣布验收，strict_gate 不读取本视图"}
    if decided is not None:
        view.update({k: decided[k] for k in ("run", "selectors", "counts", "computed_rows", "residual_deviations",
                                             "numerical_nodes")})
        if "deviation_review" in decided:
            view["deviation_review"] = decided["deviation_review"]
    return view


def acceptance_gate(tr30_suite, k01, multi):
    """逐项（例1–8、K01–K05）给出验收材料；从不授予验收（由用户决定）。判定只严不松：
    strict_gate 要求 0 偏差、0 未实现、0 显式假设、无组合式/选择器依赖、有独立复算或未舍入参考。"""
    items = {}
    by_slot = {c.get("id"): c for c in tr30_suite.get("cases", [])}
    from .tr30_kisssoft78 import evidence_summary
    kisssoft78 = evidence_summary()
    for number in range(1, 9):
        slot = by_slot.get(f"TR30-slot-0{number}", {})
        # 资料可读 = 原件字节经契约哈希核对（需 --evidence-root）；未提供时如实记 False，不影响公式对拍列
        item = {"source_readable": bool(slot.get("source_identity_verified")),
                "commercial_recompute": "none（TR30 无商业工具复算）", "product_strength": "not_assessed"}
        decided = None
        if number <= 4:
            acc = slot.get("acceptance")
            if acc is None:
                from .tr30_rating import compare_rating, load_cases as load14
                case14 = next(c for c in load14() if c["example_number"] == number)
                acc = tr30_acceptance(compare_rating(case14), case14)
            table = acc.get("summary", {}).get("table", {})
            annex = acc.get("summary", {}).get("annex_A", {})
            item["formula_crosscheck"] = {"table": table, "annex_A": annex, "verdict": acc.get("verdict")}
            item["deviations"] = [_deviation(number, {"quantity": q, "status": "out_of_domain"})
                                  for q in acc.get("table_uncovered", [])]
            item["open_assumptions"] = acc.get("applicability_assumptions", [])
            item["premises_eliminated_by_formula"] = acc.get("premises_eliminated_by_formula", [])
            item["annex_not_output"] = acc.get("annex_not_output", [])
            item["e4_gate"] = acc.get("e4_gate", False)
        else:
            full = _tr30_full58_item(number)
            item["formula_crosscheck"] = {"runs": full["runs"], "computed_rows": full["computed_rows"]}
            item["deviations"] = full["deviations"]
            decided = full["decided"]
            item["open_assumptions"] = sorted(k for k, v in full["premise_audit"].items() if v.get("status") == "assumption")
            item["premises_eliminated_by_formula"] = sorted(k for k, v in full["premise_audit"].items()
                                                            if v.get("status") == "eliminated_by_formula")
            item["e4_gate"] = False
        item["composition_formulas"] = ["d_Ff_2：A.6 SAP 原理 + ISO 6336-3 式(37)(40)–(43) 组合"] if number == 6 else []
        item["numerical_methods_outside_graph"] = []
        if number in (7, 8):
            # K1：用户本地 KISSsoft 2026 复算（候选证据）。只追加字段与条件，不放宽任何判定
            ks = kisssoft78[f"TR30-{number}"]
            item["commercial_recompute"] = ("KISSsoft 2026 本地复算（用户上传 2026-10-29，候选证据；修缘长度为附属假设，"
                                            "strict_input_closure=false）")
            item["kisssoft_recompute"] = {**ks, "accepted": False, "strict_input_closure": False,
                                          "source": kisssoft78["source"],
                                          "native_z12_sha256": kisssoft78["native_z12_sha256"][number]}
            item["strict_input_closure"] = False
            if number == 8:
                item["numerical_methods_outside_graph"] = [
                    "d_Ff_1/d_Ff_2：凸台刀预加工+磨削有效 dFf 数值包络（dFf 定义原图无法确认）；用户决定 2026-10-30（D7）"
                    "已以选择器 protuberance_dff=numerical_envelope 接入主图（derived 节点，E1 上限），不选时原路径仍为未实现"]
        item["selector_dependent"] = {7: ["method.f_sh0_specific_load"], 8: ["method.Rz_H_source"]}.get(number, [])
        item["strict_gate"] = bool(item["e4_gate"] and not item["deviations"] and not item["open_assumptions"]
                                   and not item["composition_formulas"] and not item["selector_dependent"]
                                   and not item["numerical_methods_outside_graph"] and item.get("strict_input_closure", True))
        item["conditional_requires_user_approval"] = sorted({f"{d['quantity']}（{d['nature']}）" for d in item["deviations"]}) \
            + [f"{a}（显式假设）" for a in item["open_assumptions"]] + item["composition_formulas"] \
            + [f"{s}（无默认选择器，须用户选定）" for s in item["selector_dependent"]] \
            + item["numerical_methods_outside_graph"] \
            + (["KISSsoft 复算的修缘长度 LCa=0.5·mn（原表未给，附属假设；两点敏感性输出不变）"] if number in (7, 8) else [])
        item["user_decided"] = _user_decided_view(f"TR30-{number}", item, decided)
        items[f"TR30-{number}"] = item
    items["K01"] = {"source_readable": "report_transcribed（报告行转录，原件哈希记录在 data/）", "commercial_recompute": "KISSsoft 报告逐行对拍",
                    "formula_crosscheck": {"compared_rows": len(k01["rows"]), "first_divergence": k01["first_divergence"]},
                    "deviations": [], "open_assumptions": sorted(k01.get("assumptions", {})),
                    "evidence_inputs": sorted(k01.get("evidence_inputs", {})), "product_strength": "not_assessed",
                    "strict_gate": False,
                    "conditional_requires_user_approval": ["evidence 输入（商业工具/报告值）：" + "、".join(sorted(k01.get("evidence_inputs", {})))]
                    + [f"{a}（显式假设）" for a in sorted(k01.get("assumptions", {}))]}
    for c in multi.get("cases", []):
        devs = []
        for row in c["rows"]:
            if row.get("verdict") != "一致":
                reg = K_DEVIATION_REGISTER.get((c["case"], row["quantity"]),
                                               {"nature": "未知（未登记）", "excluded": [], "evidence_needed": "逐段排查后登记"})
                devs.append({"quantity": row["quantity"], "actual": row.get("gearmath"), "reference": row.get("kisssoft"),
                             "rel_diff": row.get("rel_diff"), "tolerance": row.get("tolerance"), **reg})
        devs += [{"quantity": q, "nature": "未实现", "excluded": [], "evidence_needed": "插齿/凸台齿根几何实现"}
                 for q in c.get("unsupported", [])]
        items[c["case"].split("-")[0]] = {
            "source_readable": "report_transcribed（报告行转录，原件哈希记录在 data/）",
            "commercial_recompute": f"{c['matched_rows']}/{c['compared_rows']} 行一致",
            "formula_crosscheck": {"status": c["status"], "full_formula_validation": c["full_formula_validation"]},
            "deviations": devs, "open_assumptions": sorted(c.get("assumptions", {})),
            "evidence_inputs": sorted(c.get("evidence_inputs", {})),
            "factor_evidence_remaining": c.get("factor_evidence_remaining", []),
            "standard_applicability_pending": c.get("standard_applicability_pending", []),
            "product_strength": "not_assessed", "strict_gate": False,
            "conditional_requires_user_approval": [f"{d['quantity']}（{d['nature']}）" for d in devs]
                + (["evidence 输入（商业工具/报告值）：" + "、".join(sorted(c.get("evidence_inputs", {})))] if c.get("evidence_inputs") else [])
                + [f"{a}（显式假设）" for a in sorted(c.get("assumptions", {}))]
                + [f"{p}（适用条件待定）" for p in c.get("standard_applicability_pending", [])]}
    strict_missing = {
        "TR30-1": "附录A 11 个中间量无独立输出；4 项显式假设需原文或用户批准",
        "TR30-4": "根切 dFf 已核公式（ISO 21771）或商业复算",
        "TR30-6": "dFf2 为组合式：需原文直接式或商业复算确认",
        "TR30-7": "ISO 18265、KISSsoft 读回（≈HB/0.9505）与原表（≈HB/0.95）三种硬度换算口径冲突需原文说明；fsh0 双斜齿口径原文定义；"
                  "KISSsoft 复算修缘长度未闭合（strict_input_closure=false）",
        "TR30-8": "σF0_1/σF_2 的未舍入参考值或 TR30 勘误（KISSsoft 复算与本库一致、均高于印刷值）；凸台 dFf 定义原文核图并决定是否接入主图；"
                  "Rz 口径裁定；KISSsoft 复算修缘长度未闭合（strict_input_closure=false）",
        "K01": "evidence 输入逐项公式化", "K02": "ZNT/YNT/Yδ/YR/YX/ZW/ZX 公式化", "K03": "插齿/凸台齿根实现；未舍入 hfP*",
        "K04": "KHβ external 改公式化；6.4 高重合度适用条件", "K05": "KHβ external 改公式化",
    }
    return {"schema": "gearmath.m33_acceptance_gate/v1", "accepted_by_tool": False,
            "decision": "由用户决定；本工具不宣布验收通过",
            "distinctions": {"source_readable": "资料可读（原件可渲染核图）",
                             "commercial_recompute": "商业工具复算一致（仅 K01–K05 有）",
                             "formula_crosscheck": "公式对拍通过（本库公式对原表/附录）",
                             "product_strength": "产品强度合格（本项目不判定）"},
            "items": items, "strict_missing_evidence": strict_missing,
            "conditional_deviation_list": {k: v["conditional_requires_user_approval"] for k, v in items.items()
                                           if v["conditional_requires_user_approval"]},
            "strict_gate_all": all(v["strict_gate"] for v in items.values()),
            "user_decisions": {"date": DECISION_DATE, "decisions": USER_DECISIONS,
                               "approved_deviations": {f"TR30-{n}:{q}": v for (n, q), v in USER_APPROVED_DEVIATIONS.items()},
                               "status": "M33 未验收：只有用户能宣布验收；本工具不授予",
                               "remaining_blockers": REMAINING_BLOCKERS}}


def run(evidence_root=None):
    k01 = compare(factor_selectors=K01_FULL_FACTOR_SELECTORS)
    from .kisssoft_multi import run_suite as multi_suite
    evidence = {}
    if evidence_root is not None:
        path = Path(evidence_root) / "standards/core/ISO-TR-6336-30-2022-supplemented-reading-copy.pdf"
        evidence["tr30"] = path.read_bytes()
    factor_names = {name for name, _, _ in EVIDENCE_MAP}
    tr30 = run_suite(evidence)
    multi = multi_suite()
    return {
        "schema": "gearmath.m33_progress/v1",
        "m33_accepted": False,
        "product_strength": "not_assessed",
        "K01": {
            "compared_rows": len(k01["rows"]),
            "numerically_matched": k01["first_divergence"] is None,
            "remaining_evidence_factors": sorted(factor_names & k01["evidence_inputs"].keys()),
            "comparison": k01,
        },
        "TR30": tr30,
        "K02_K05": multi,
        "acceptance_gate": acceptance_gate(tr30, k01, multi),
        "remaining_work": [
            "TR30例1–4：fHβ5（ISO 1328-1:2013 式(10)+5.2.3，图内取整）与 fsh0（ISO 6336-1 表F.1）已实现；"
            "例1–3 输出表全覆盖，例4 dFf1/dNf1 根切超出附录A A.6 前提；E4 仍受附录A 中间量与显式适用性假设阻断（见各例 e4_blockers）",
            "适用性前提：例1–3（及例5–7）啮合线不缩短已由 A.6 dFf/dNf 公式判定；矿物油、VI95、齿根表面完好 4 项原文无法消除，"
            "需用户批准为条件证据（见 acceptance_gate.items.*.premise/open_assumptions）",
            "例6 dFf2 已用组合式实现（非原文直接式）；例8 凸台 dFf1/2 有主图外数值包络（与 KISSsoft 差 <1e-6 mm），dFf 定义原图无法确认，"
            "主图仍记未实现；例7 fsh0 口径为显式选择器（两种结果均报告）。用户决定 2026-10-30：dFf 数值方法以选择器接入主图（D7）、"
            "fsh0=per_helix（D2，O 决策有条件，待 KISSsoft 确认）、HB→HV 待决（D3）；见 acceptance_gate.user_decisions",
            "TR30 例7/例8 KISSsoft 2026 复算已入库（data/kisssoft/tr30-7-8，tr30_kisssoft78）：例7 正式口径 91/99、外部 HV 变体 99/99，"
            "例8 101/101 严格双门；修缘长度附属假设使 strict_input_closure=false；M33 未验收（用户结论）",
            "完善TR30混合材料/内齿/双斜齿/残余凸台的完整强度链",
            "解决K03插齿及凸台齿根，并核实K04/K05显示末位差异",
            "扩展已核分支之外的材料/修形/有限寿命与高重合度适用域",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence-root", type=Path, help="解压后的原始M33资料包目录")
    args = parser.parse_args()
    result = run(args.evidence_root)
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(json.dumps({"m33_accepted": result["m33_accepted"],
                      "K01_rows": result["K01"]["compared_rows"],
                      "K01_numerically_matched": result["K01"]["numerically_matched"],
                      "remaining_evidence_factors": result["K01"]["remaining_evidence_factors"],
                      "TR30_total": result["TR30"]["total"],
                      "TR30_blocked": result["TR30"]["blocked"],
                      "TR30_accepted": result["TR30"]["accepted"],
                      "TR30_numerically_accepted": result["TR30"].get("numerically_accepted"),
                      "acceptance_gate_strict_all": result["acceptance_gate"]["strict_gate_all"],
                      "acceptance_gate_conditional_items": sorted(result["acceptance_gate"]["conditional_deviation_list"]),
                      "TR30_acceptance": {c["id"]: c["acceptance"]["verdict"] for c in result["TR30"].get("cases", [])
                                          if "acceptance" in c}}, ensure_ascii=False, indent=2))
    return 0 if result["m33_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
