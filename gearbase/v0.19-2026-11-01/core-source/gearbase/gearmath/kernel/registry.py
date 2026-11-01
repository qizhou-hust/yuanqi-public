"""公式注册表 schema v1 的校验器与读取（零依赖）。字段定义见 docs/注册表-schema-v1.md。

注册表是公式对象的 JSON 快照：真源仍是代码里的公式对象，导出物由测试核对"与代码一致"。
无法由现有元数据确定的字段为 null（不编造）。本模块不知道任何领域概念。
"""
from __future__ import annotations

import json
import math
import re

from . import evidence as EV
from . import units as U
from .expr import FormulaError
from .graph import Formula, Model, compile_expr, parse_standard_ref

SCHEMA = "gearbase.formula-registry/1"
CASE_SCHEMA = "gearbase.case-registry/1"
ASSESSMENT_SCHEMA = "gearbase.formula-assessments/1"
VECTOR_KEYS = {"inputs", "expected", "rel_tol", "abs_tol", "note", "source", "basis", "case"}
VECTOR_BASES = ("direct_reference", "chain_replay")
SOURCE_CHECKS = ("pdf_image_checked", "ocr_only", "from_memory", "not_in_evidence")
KINDS = ("explicit", "fixed_point")
LEVELS = EV.EVIDENCE_LEVELS
FIELDS = ("id", "output", "unit", "expr", "kind", "start", "tol", "domain", "clause", "edition", "method",
          "test_vectors", "evidence_level", "source_check", "note")
OPTIONAL_FIELDS = ("fixed_point_derivative",)
REQUIRED_NONNULL = ("id", "output", "unit", "expr", "kind", "tol", "domain", "clause")
_EDITION = re.compile(r"^.+:\d{4}$")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_vectors(fid, tv, errs):
    if not isinstance(tv, list) or not tv:
        errs.append(f"{fid}：test_vectors 必须是 null 或非空数组")
        return
    for i, v in enumerate(tv):
        ok = isinstance(v, dict) and set(v) >= {"inputs", "expected"} and set(v) <= VECTOR_KEYS
        for key in ("inputs", "expected"):
            part = v.get(key) if isinstance(v, dict) else None
            ok = ok and isinstance(part, dict) and (bool(part) or key == "inputs") and all(
                isinstance(p, list) and len(p) == 2 and _num(p[0]) and p[1] in U.UNITS for p in part.values())
        for key in ("rel_tol", "abs_tol"):
            if ok and key in v and not (_num(v[key]) and v[key] >= 0):
                ok = False
        for key in ("note", "source", "case"):
            if ok and key in v and not (isinstance(v[key], str) and v[key].strip()):
                ok = False
        if ok and "basis" in v and v["basis"] not in VECTOR_BASES:
            ok = False
        if not ok:
            errs.append(f"{fid}：test_vectors[{i}] 格式应为 {{inputs:{{名:[数值,单位]}}, expected:{{名:[数值,单位]}}, "
                        "rel_tol?:数, abs_tol?:数, source?:文, basis?:direct_reference|chain_replay, case?:文, note?:文}")


def formula_from_entry(e):
    """Restore execution metadata; old snapshots retain the implicit default."""
    return Formula(e["id"], e["output"], e["unit"], e["expr"], e["clause"], tuple(e["domain"]), e["kind"],
                e["start"] if e["start"] is not None else 0.0, e["tol"], e["note"] or "",
                *((e["edition"].rsplit(":", 1)) if e["edition"] else ("", "")),
                fixed_point_derivative=e.get("fixed_point_derivative", "implicit"))


def replay_vector(e, v) -> list:
    """用记录里的公式（id/expr/unit/domain/…）单独重算一条测试向量，返回问题列表（空 = 复现）。
    判据：|计算值 − 期望值| ≤ abs_tol + rel_tol·|期望值|（两者都缺省时按相对 1e-9）。"""
    f = formula_from_entry(e)
    m = Model([f])
    if f.standard:
        m.set_edition(f.standard, f.edition)
    for name, (val, unit) in v["inputs"].items():
        m.set(name, val, unit, "user", "test_vector")
    r = m.evaluate([f.output])
    if r.status not in ("ok", "out_of_domain"):
        return [f"{e['id']}：向量求值状态 {r.status} {r.missing or r.errors}"]
    out = []
    at, rt = v.get("abs_tol", 0.0), v.get("rel_tol", 0.0)
    if "abs_tol" not in v and "rel_tol" not in v:
        rt = 1e-9
    for name, (want, unit) in v["expected"].items():
        if name != f.output:
            out.append(f"{e['id']}：期望量 {name} 不是本公式输出 {f.output}")
            continue
        got = U.from_canonical(r.values[f.output], unit)
        bound = (at + rt * abs(want)) * (1 + 1e-9) + 1e-15
        if abs(got - want) > bound:
            out.append(f"{e['id']}：向量不复现：计算 {got!r} 期望 {want!r} 容差 {bound:g}")
    return out


def validate_entry(e) -> list:
    """校验一条公式记录；返回问题列表（空 = 合格）。"""
    if not isinstance(e, dict):
        return ["记录不是对象"]
    fid = e.get("id", "?")
    errs = []
    for k in sorted(set(e) - set(FIELDS) - set(OPTIONAL_FIELDS)):
        errs.append(f"{fid}：未知字段 {k}")
    for k in FIELDS:
        if k not in e:
            errs.append(f"{fid}：缺字段 {k}（未知时须显式填 null）")
    if errs:
        return errs
    for k in REQUIRED_NONNULL:
        if e[k] is None:
            errs.append(f"{fid}：{k} 不能为 null")
    for k in ("id", "output", "unit", "expr", "clause"):
        if e[k] is not None and (not isinstance(e[k], str) or not e[k].strip()):
            errs.append(f"{fid}：{k} 必须是非空字符串")
    if errs:
        return errs
    if e["unit"] not in U.UNITS:
        errs.append(f"{fid}：未登记的单位 {e['unit']!r}")
    elif U.is_affine(e["unit"]):
        errs.append(f"{fid}：公式单位不能是仿射单位 {e['unit']}")
    if e["kind"] not in KINDS:
        errs.append(f"{fid}：kind 必须是 {KINDS}")
    if e.get("fixed_point_derivative", "implicit") not in ("implicit", "finite_iteration"):
        errs.append(f"{fid}：fixed_point_derivative 必须是 implicit 或 finite_iteration")
    if e["kind"] == "fixed_point" and not _num(e["start"]):
        errs.append(f"{fid}：fixed_point 必须给数值 start")
    if e["kind"] == "explicit" and e["start"] is not None:
        errs.append(f"{fid}：explicit 公式的 start 必须为 null")
    if not (_num(e["tol"]) and e["tol"] > 0):
        errs.append(f"{fid}：tol 必须是正数")
    try:
        compile_expr(e["expr"])
    except FormulaError as ex:
        errs.append(f"{fid}：expr 无法解析：{ex}")
    if not isinstance(e["domain"], list) or not all(isinstance(p, str) and p.strip() for p in e["domain"]):
        errs.append(f"{fid}：domain 必须是字符串数组（可为空）")
    else:
        for p in e["domain"]:
            try:
                compile_expr(p)
            except FormulaError as ex:
                errs.append(f"{fid}：domain 谓词 {p!r} 无法解析：{ex}")
    if e["edition"] is not None:
        if not isinstance(e["edition"], str) or not _EDITION.match(e["edition"]):
            errs.append(f"{fid}：edition 必须是 null 或 '标准分册:四位年份'")
        else:
            std, ed = parse_standard_ref(e["clause"])
            if std and f"{std}:{ed}" != e["edition"]:
                errs.append(f"{fid}：edition {e['edition']} 与 clause 开头引用 {std}:{ed} 不一致")
    if e["method"] is not None:
        m = e["method"]
        if not (isinstance(m, dict) and m and all(isinstance(k, str) and isinstance(v, str) for k, v in m.items())):
            errs.append(f"{fid}：method 必须是 null 或非空 {{选择器: 取值}} 对象")
    if e["test_vectors"] is not None:
        _check_vectors(fid, e["test_vectors"], errs)
    if e["evidence_level"] is not None and e["evidence_level"] not in LEVELS:
        errs.append(f"{fid}：evidence_level 必须是 null 或 {LEVELS}")
    if e["source_check"] is not None and e["source_check"] not in SOURCE_CHECKS:
        errs.append(f"{fid}：source_check 必须是 null 或 {SOURCE_CHECKS}")
    if e["note"] is not None and not isinstance(e["note"], str):
        errs.append(f"{fid}：note 必须是 null 或字符串")
    return errs


E3_PLUS = tuple(l for l in LEVELS if EV.rank(l) >= 3)


def _level_vector_rule(e) -> list:
    """E3 及以上必须有带来源（source）的测试向量：等级只能由可追溯的对拍得来。"""
    if e.get("evidence_level") in E3_PLUS:
        tv = e.get("test_vectors")
        if not tv or not any(isinstance(v, dict) and isinstance(v.get("source"), str) and v["source"].strip() for v in tv):
            return [f"{e.get('id', '?')}：证据等级 {e['evidence_level']} 要求至少一条带 source 的测试向量"]
    return []


def validate_registry(doc) -> list:
    """校验整份注册表（顶层结构 + 每条记录 + 唯一性）；返回问题列表。"""
    if not isinstance(doc, dict):
        return ["顶层不是对象"]
    errs = []
    if doc.get("schema") != SCHEMA:
        errs.append(f"schema 必须是 {SCHEMA!r}")
    rows = doc.get("formulas")
    if not isinstance(rows, list):
        return errs + ["formulas 必须是数组"]
    seen_id = {}
    for e in rows:
        errs += validate_entry(e)
        if not isinstance(e, dict):
            continue
        errs += _level_vector_rule(e)
        if e.get("id") in seen_id:
            errs.append(f"{e.get('id')}：id 重复")
        seen_id[e.get("id")] = e
    ids = [e.get("id") for e in rows if isinstance(e, dict)]
    if ids != sorted(ids):
        errs.append("formulas 必须按 id 升序排列（保证导出稳定）")
    return errs


def alternatives(doc) -> dict:
    """同一 (output, method) 下有多条公式的输出 → 公式 id 列表。注册表允许这种情况：
    这些公式由代码里的分支（材料、案例适配）选择，而非方法选择器；统计出来供评审，不算错误。"""
    slots = {}
    for e in doc["formulas"]:
        slots.setdefault((e["output"], json.dumps(e["method"], sort_keys=True)), []).append(e["id"])
    out = {}
    for (o, _), ids in slots.items():
        if len(ids) > 1:
            out.setdefault(o, []).extend(ids)
    return {o: sorted(ids) for o, ids in sorted(out.items())}


def evidence_levels(doc) -> dict:
    """注册表 → {公式 id: 证据等级}；只含已评估（非 null）的记录，其余视为 unassessed。"""
    return {e["id"]: e["evidence_level"] for e in doc["formulas"] if e.get("evidence_level")}


def validate_cases(cdoc, fdoc=None) -> list:
    """案例级注册表：每个案例 {case_id, library_formula_ids, formulas[...]}；公式记录与库级同 schema。
    给出 fdoc（库级注册表）时，library_formula_ids 必须都在其中，且案例级公式不得与库级记录逐字相同（相同的应记在库级）。"""
    if not isinstance(cdoc, dict) or cdoc.get("schema") != CASE_SCHEMA:
        return [f"schema 必须是 {CASE_SCHEMA!r}"]
    rows = cdoc.get("cases")
    if not isinstance(rows, list):
        return ["cases 必须是数组"]
    errs, seen = [], set()
    lib = {e["id"]: e for e in fdoc["formulas"]} if fdoc else None
    for c in rows:
        cid = c.get("case_id") if isinstance(c, dict) else None
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            errs.append(f"case_id 缺失或重复：{cid!r}")
            continue
        seen.add(cid)
        ids = c.get("library_formula_ids")
        if not (isinstance(ids, list) and ids == sorted(set(ids))):
            errs.append(f"{cid}：library_formula_ids 必须是升序去重的数组")
        elif lib is not None:
            errs += [f"{cid}：library_formula_ids 含未登记的 {i}" for i in ids if i not in lib]
        fs = c.get("formulas")
        if not isinstance(fs, list):
            errs.append(f"{cid}：formulas 必须是数组")
            continue
        names = [e.get("id") for e in fs if isinstance(e, dict)]
        if names != sorted(set(names)):
            errs.append(f"{cid}：formulas 必须按 id 升序且不重复")
        for e in fs:
            errs += [f"{cid}/{x}" for x in validate_entry(e)]
            if isinstance(e, dict):
                errs += [f"{cid}/{x}" for x in _level_vector_rule(e)]
                if lib is not None and e.get("id") in lib and lib[e["id"]]["expr"] == e.get("expr") and \
                        lib[e["id"]].get("fixed_point_derivative", "implicit") == e.get("fixed_point_derivative", "implicit") and \
                        {k: lib[e["id"]][k] for k in ("output", "unit", "domain", "kind", "start", "tol", "clause", "note")} == \
                        {k: e.get(k) for k in ("output", "unit", "domain", "kind", "start", "tol", "clause", "note")}:
                    errs.append(f"{cid}：{e['id']} 与库级记录相同，应记在库级")
    if [c.get("case_id") for c in rows if isinstance(c, dict)] != sorted(c.get("case_id") for c in rows if isinstance(c, dict)):
        errs.append("cases 必须按 case_id 升序排列")
    return errs


def validate_assessments(adoc, fdoc, cdoc=None) -> list:
    """评定数据与注册表一致：每条库级公式恰有一条评定，等级/来源核对状态与注册表记录相同；
    等级为 null 必须写明原因；案例级评定与 cases 记录相同。"""
    if not isinstance(adoc, dict) or adoc.get("schema") != ASSESSMENT_SCHEMA:
        return [f"schema 必须是 {ASSESSMENT_SCHEMA!r}"]
    errs = []

    def check(rows, recs, label):
        by = {}
        for a in rows:
            key = a.get("id")
            if key in by:
                errs.append(f"{label}{key}：评定重复")
            by[key] = a
        for e in recs:
            a = by.pop(e["id"], None)
            if a is None:
                errs.append(f"{label}{e['id']}：缺评定")
                continue
            for k in ("evidence_level", "source_check"):
                if a.get(k) != e[k]:
                    errs.append(f"{label}{e['id']}：评定的 {k}={a.get(k)!r} 与注册表 {e[k]!r} 不一致")
            if a.get("evidence_level") is not None and a["evidence_level"] not in LEVELS:
                errs.append(f"{label}{e['id']}：非法等级 {a['evidence_level']!r}")
            if a.get("evidence_level") is None and not a.get("evidence_level_null_reason"):
                errs.append(f"{label}{e['id']}：等级为 null 必须写 evidence_level_null_reason")
            if a.get("evidence_level") is not None and not a.get("basis"):
                errs.append(f"{label}{e['id']}：有等级必须写 basis（依据）")
            if a.get("source_check") is None and not a.get("source_check_null_reason"):
                errs.append(f"{label}{e['id']}：来源核对状态为 null 必须写 source_check_null_reason")
        errs.extend(f"{label}{k}：评定指向不存在的公式" for k in by)

    check(adoc.get("formulas", []), fdoc["formulas"], "")
    cases = {c["case_id"]: c for c in (cdoc or {}).get("cases", [])}
    seen = set()
    for a in adoc.get("case_formulas", []):
        c = cases.get(a.get("case_id"))
        if c is None and cdoc is not None:
            errs.append(f"案例评定指向不存在的案例 {a.get('case_id')!r}")
        seen.add(a.get("case_id"))
    for cid, c in cases.items():
        check([a for a in adoc.get("case_formulas", []) if a.get("case_id") == cid], c["formulas"], f"{cid}/")
    return errs


def case_evidence_levels(fdoc, cdoc, case_id) -> dict:
    """某个案例模型适用的 {公式 id: 等级}：库级评定，减去该案例改写/新增的同 id 公式，再加上案例级评定。
    被案例改写的库公式在该案例里不继承库级等级（内容已不同）。"""
    levels = evidence_levels(fdoc)
    case = next(c for c in cdoc["cases"] if c["case_id"] == case_id)
    for e in case["formulas"]:
        levels.pop(e["id"], None)
    levels.update({e["id"]: e["evidence_level"] for e in case["formulas"] if e.get("evidence_level")})
    return levels


def load_registry(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    errs = validate_registry(doc)
    if errs:
        raise ValueError("注册表校验失败：" + "；".join(errs[:5]))
    return doc
