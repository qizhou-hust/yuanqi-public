"""从已通过的对拍行抽取"公式 → 对拍证据"与测试向量（只读调用各案例模块，不修改它们；零依赖）。

对拍来源与等级（顶层设计 E0–E6 的映射，规则见 docs/注册表-schema-v1.md）：
  C001-G1          M31 收据（python-gearbox 独立实现）           E2
  TR30-ex1..ex8    ISO/TR 6336-30:2022 配套算例（逐行通过）       E4
  KISSsoft-K01..K05 KISSsoft 同输入报告/COM（逐行一致）            E5

只有"通过"的行才计入；一行通过时，其求值链（model.order）上的每条公式都算被用到：
  direct = 该行比较量本身就是这条公式的输出；chain = 仅作为上游被用到。
案例适配器会改写个别库公式（同 id、内容不同）或新增公式：与库公式完全相同（Formula 相等）的计入库级；
其余计入案例级（带 case id），不会把案例改写版的证据记到库公式头上。
"""
from __future__ import annotations

import functools
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gearmath.kernel import evidence as EV            # noqa: E402
from gearmath.kernel import units as U                # noqa: E402

LEVEL_OF_KIND = {"m31_receipt": "E2", "tr30_example": "E4", "kisssoft_report": "E5"}
KIND_TEXT = {"m31_receipt": "M31 收据（python-gearbox 独立实现）", "tr30_example": "ISO/TR 6336-30:2022 配套算例",
             "kisssoft_report": "KISSsoft 同输入报告/COM"}
MAX_VECTORS = 3                     # 每条公式最多保留的测试向量数（直接对拍优先、等级高优先）
CHAIN_REL_TOL, CHAIN_ABS_TOL = 1e-9, 1e-12

# 收据字段 → 模型量（与 tests/test_package.py 的 RECEIPT_RESULTS 同口径）；K_V 为方法B 公式，逐位复现
_RECEIPT = {
    "Z_H": ("contact", "zone_factor"), "Z_E": ("contact", "elasticity_factor"), "Z_eps": ("contact", "contact_ratio_factor"),
    "Z_B": ("contact", "single_pair_contact_factor_pinion"), "sigma_H_1": ("contact", "contact_stress_pinion"),
    "sigma_H_2": ("contact", "contact_stress_wheel"), "S_H_1": ("contact", "safety_factor_pinion"),
    "S_H_2": ("contact", "safety_factor_wheel"), "K_Fbeta": ("root", "face_load_factor"),
    "Y_F_1": ("root", "form_factor_pinion"), "Y_F_2": ("root", "form_factor_wheel"),
    "Y_S_1": ("root", "stress_correction_factor_pinion"), "Y_S_2": ("root", "stress_correction_factor_wheel"),
    "sigma_F_1": ("root", "tooth_root_stress_pinion"), "sigma_F_2": ("root", "tooth_root_stress_wheel"),
    "S_F_1": ("root", "safety_factor_pinion"), "S_F_2": ("root", "safety_factor_wheel"),
    "K_V": ("contact", "dynamic_factor"),
}


def _row(quantity, reference, unit, source, *, abs_tol=None, rel_tol=None):
    return {"quantity": quantity, "reference": float(reference), "unit": unit, "source": source,
            "abs_tol": abs_tol, "rel_tol": rel_tol}


def _library():
    from . import export_registry as X
    return {f.id: f for f, _ in X.collect()[0]}


# ---------------------------------------------------------------- 各对拍的 (模型, 通过的行) 抽取

def _c001():
    from ..gear import m31_case
    model, receipt = m31_case.stage_model()
    rows = []
    for q, (sec, key) in _RECEIPT.items():
        if q not in model.formulas:
            continue
        tol = 1e-12 if q == "K_V" else (5e-10 if sec == "contact" or q == "K_Fbeta" else 5e-6)   # 与 test_package 的 places 9/5 同
        rows.append(_row(q, receipt[sec][key], "1", f"M31 data/m31/golden/C001/gear-rating.json stages[0].{sec}.{key}", rel_tol=tol))
    return [("C001-G1", "m31_receipt", "M31 C001 G1 收据（数据驱动装配，K_V 方法B）", model, rows)]


def _tr30_1_4():
    from ..gear import tr30_rating as TR
    from ..gear.m33_acceptance import tr30_acceptance
    out = []
    for case in TR.load_cases():
        n = case["example_number"]
        if n not in (1, 2, 3, 4):
            continue
        report = TR.compare_rating(case)
        acc = tr30_acceptance(report, case)
        rows = []
        for r in acc["rows"]:
            if r.get("status") != "computed" or r.get("acceptance_verdict") not in ("pass_A", "pass_B"):
                continue
            cite = r.get("citation") or {}
            where = f"{cite.get('location', '')}（PDF{cite.get('pdf_page', '?')}）" if isinstance(cite, dict) else str(cite)
            kind = "附录A" if r.get("source_kind") == "annex_A" else "表"
            rows.append(_row(r["quantity"], r["reference"], r["unit"], f"ISO/TR 6336-30:2022 例{n} {kind} {where}",
                             abs_tol=r["acceptance_bound"]))
        out.append((f"TR30-ex{n}", "tr30_example", f"ISO/TR 6336-30:2022 例{n}（分档判据逐行通过）", TR.build_model(case), rows))
    return out


def _tr30_5_8():
    from ..gear import tr30_full58 as F
    out = []
    for n in (5, 6, 7, 8):
        kw = {"rz_source": "ra_times_6"} if n == 8 else {}
        report = F.compare_full(n, **kw)
        rows = []
        for r in report["rows"]:
            if r.get("status") != "pass":
                continue
            cite = r.get("citation") or {}
            where = f"{cite.get('location', '')}（PDF{cite.get('pdf_page', '?')}）" if isinstance(cite, dict) else str(cite)
            rows.append(_row(r["quantity"], r["reference"], r["unit"], f"ISO/TR 6336-30:2022 例{n} 表 {where}",
                             abs_tol=r["quantum_tolerance"]))
        model = F.build_model(n, zv_velocity="v_ref", hardness_conversion="ISO18265_A1_linear", **kw)
        out.append((f"TR30-ex{n}", "tr30_example", f"ISO/TR 6336-30:2022 例{n}（显示量子判据逐行通过；整例未验收）", model, rows))
    return out


def _tol_of(text):
    m = re.match(r"^(rel|abs)≤([0-9.eE+-]+)", text)
    if not m:
        return None, None
    return (None, float(m.group(2))) if m.group(1) == "rel" else (float(m.group(2)), None)


def _kisssoft():
    from ..gear import kisssoft_case as KC
    from ..gear import kisssoft_multi as KM
    from ..gear.factor_methods import K01_FULL_FACTOR_SELECTORS
    out = []
    d = KC.load("K01-spur")
    model, _ = KC.build_model(d, None, factor_selectors=K01_FULL_FACTOR_SELECTORS)
    rep = KC.compare(factor_selectors=K01_FULL_FACTOR_SELECTORS)
    jobs = [("KISSsoft-K01", model, rep["rows"], "K01 直齿全系数分支")]
    for case in KM.CASES:
        m, _ = KM.build_model(case)
        jobs.append((f"KISSsoft-{case.split('-')[0]}", m, KM.compare(case)["rows"], f"{case} 条件端到端"))
    for bid, m, rows_in, desc in jobs:
        rows = []
        for r in rows_in:
            if r.get("verdict") != "一致" or r["quantity"] not in m.formulas or not isinstance(r["kisssoft"], (int, float)):
                continue
            a, rel = _tol_of(r["tolerance"])
            if a is None and rel is None:
                continue
            rows.append(_row(r["quantity"], r["kisssoft"], r["unit"], f"KISSsoft {bid[9:]} {r['source']}", abs_tol=a, rel_tol=rel))
        out.append((bid, "kisssoft_report", f"{desc}（逐行一致）", m, rows))
    return out


# ---------------------------------------------------------------- 抽取与聚合

def _dep_names(f):
    from ..kernel.graph import compile_expr
    names = set(compile_expr(f.expr).names)
    for p in f.domain:
        names |= set(compile_expr(p).names)
    names.discard(f.output)
    return sorted(names)


def _pair(model, name, res):
    if name in model.formulas:
        unit = model.formulas[name].unit
        return [float(U.from_canonical(res.values[name], unit)), unit]
    i = model.inputs[name]
    return [float(U.from_canonical(i.value, i.unit)), i.unit]


def _same_dim(a, b):
    return a in U.UNITS and b in U.UNITS and U.unit(a)[0] == U.unit(b)[0]


def _new_target(f):
    return {"formula": f, "supports": {}, "candidates": []}


@functools.lru_cache(maxsize=1)
def extract(*, frozen=True):
    """跑全部对拍（只读），返回聚合结果；进程内缓存。结构：
    benchmarks：[{id, kind, level, description, rows_passed}]；
    library：{公式 id: target}；cases：{case_id: {"library_ids": [...], "targets": {公式 id: target}}}；
    target = {"formula", "supports": {对拍 id: {"direct": [量...], "chain": [量...]}}, "vectors": [...]}。"""
    lib = _library()
    jobs = _c001() + _tr30_1_4() + _tr30_5_8() + _kisssoft()
    benchmarks, library, cases = [], {}, {}
    for bid, kind, desc, model, rows in jobs:
        level = LEVEL_OF_KIND[kind]
        used = 0
        case = cases.setdefault(bid, {"library_ids": set(), "targets": {}})
        for f in model.formulas.values():             # 与库公式相同 → 库级；不同或新增 → 案例级（无论是否被对拍用到）
            if lib.get(f.id) == f:
                case["library_ids"].add(f.id)
            else:
                case["targets"].setdefault(f.id, _new_target(f))
        for row in rows:
            q = row["quantity"]
            res = model.evaluate([q])
            if res.status != "ok" or q not in model.formulas:
                continue
            used += 1
            for n in model.order([q]):
                f = model.formulas[n]
                direct = n == q
                if lib.get(f.id) == f:
                    target = library.setdefault(f.id, _new_target(f))
                else:
                    target = case["targets"][f.id]
                sup = target["supports"].setdefault(bid, {"direct": [], "chain": []})
                if q not in sup["direct" if direct else "chain"]:
                    sup["direct" if direct else "chain"].append(q)
                key = (bid, direct)
                if any(c["key"] == key for c in target["candidates"]):
                    continue
                inputs = {d: _pair(model, d, res) for d in _dep_names(f)}
                vec = {"inputs": inputs, "case": bid, "source": row["source"]}
                if direct and _same_dim(row["unit"], f.unit):
                    vec["expected"] = {f.output: [row["reference"], row["unit"]]}
                    for k in ("abs_tol", "rel_tol"):
                        if row[k] is not None:
                            vec[k] = row[k]
                    vec["basis"] = "direct_reference"
                else:
                    vec["expected"] = {f.output: _pair(model, f.output, res)}
                    vec["abs_tol"], vec["rel_tol"] = CHAIN_ABS_TOL, CHAIN_REL_TOL
                    vec["basis"] = "chain_replay"
                    vec["source"] = f"{bid} 通过行 {q} 的求值链（本库模型值重放，非独立参考值）；该行参考：{row['source']}"
                target["candidates"].append({"key": key, "level": EV.rank(level), "bid": bid, "q": q, "vec": vec})
        benchmarks.append({"id": bid, "kind": kind, "level": level, "description": desc,
                           "kind_text": KIND_TEXT[kind], "rows_passed": used})
        case["library_ids"] = sorted(case["library_ids"])
    for t in list(library.values()) + [t for c in cases.values() for t in c["targets"].values()]:
        cand = sorted(t.pop("candidates"), key=lambda c: (not c["key"][1], -c["level"], c["bid"], c["q"]))
        t["vectors"] = [c["vec"] for c in cand[:MAX_VECTORS]]
    result = {"benchmarks": benchmarks, "library": library, "cases": cases}
    if frozen:
        from .vector_seeds import apply
        apply(result)
    return result


def level_of(target, benchmarks):
    """被用到的所有通过对拍里最高的等级（规则：用到才给对应等级）；无则 None。"""
    by = {b["id"]: b["level"] for b in benchmarks}
    best = max((EV.rank(by[b]) for b in target["supports"]), default=None)
    return None if best is None else EV.label(best)
