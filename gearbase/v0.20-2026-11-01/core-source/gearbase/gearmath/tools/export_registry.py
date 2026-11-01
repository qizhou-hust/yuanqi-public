"""从 Python 公式对象导出公式注册表 data/registry/formulas-v1.json（可复现、排序稳定、零依赖）。

用法（在包根目录）：
    python3 -I gearmath/tools/export_registry.py           # 重写 data/registry/formulas-v1.json
    python3 -I gearmath/tools/export_registry.py --check   # 只核对是否与代码一致，不一致退出 2

真源是代码里的公式对象；本工具只做快照。收录范围：gearmath.gear 各模块顶层可达的 Formula / Variant
（含 pair_variants() 与 factor_variants() 里的方法条件）。无法由现有元数据确定的字段填 null，并在文件的 coverage 中统计，不编造。

M34 续：另外写出
  data/registry/assessments-v1.json  规则评定（assess_registry.py 生成；写入模式下先重新生成，--check 同时核对）
  data/registry/cases-v1.json        案例适配器改写/新增的公式（只读调用各案例的 build 函数，不修改它们），带 case id
并把评定（evidence_level / source_check）与自动抽取的测试向量（benchmarks.py，来自已通过的对拍行）合并进
formulas-v1.json 与 cases-v1.json。
"""
from __future__ import annotations

import importlib
import json
import pathlib
import pkgutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gearmath.kernel.graph import Formula                      # noqa: E402
from gearmath.kernel.registry import CASE_SCHEMA, FIELDS, SCHEMA, alternatives, validate_registry  # noqa: E402
from gearmath.kernel.select import Variant                     # noqa: E402

OUT = ROOT / "data" / "registry" / "formulas-v1.json"
CASES_OUT = ROOT / "data" / "registry" / "cases-v1.json"
ASSESS_OUT = ROOT / "data" / "registry" / "assessments-v1.json"


def _walk(o, sink, depth=0):
    if isinstance(o, Formula):
        sink.append((o, None))
    elif isinstance(o, Variant):
        if o.formula is not None:
            sink.append((o.formula, dict(o.when) or None))
    elif depth < 4 and isinstance(o, (list, tuple)):
        for x in o:
            _walk(x, sink, depth + 1)
    elif depth < 4 and isinstance(o, dict):
        for x in o.values():
            _walk(x, sink, depth + 1)


def collect():
    """返回 ([(Formula, when|None)], [external 槽位])。带方法条件的变体优先于模块顶层的裸对象。"""
    import gearmath.gear as pkg
    from gearmath.gear.factor_methods import factor_variants
    from gearmath.gear.rating import pair_variants
    bare, with_when, ext = [], [], []
    for mi in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"gearmath.gear.{mi.name}")
        for k in sorted(vars(mod)):
            if not k.startswith("__"):
                _walk(vars(mod)[k], bare)
    for v in pair_variants() + factor_variants():
        if v.formula is None:
            ext.append(v)
        else:
            _walk(v, with_when)
    by_id = {}
    for f, w in with_when + bare:        # 先放有条件的；裸对象只补缺
        slot = by_id.setdefault(f.id, {})
        slot.setdefault(f, [])
        if w is not None and w not in slot[f]:
            slot[f].append(w)
    out = []
    for fid in sorted(by_id):
        forms = by_id[fid]
        if len(forms) > 1:
            raise ValueError(f"公式 id {fid} 对应多个不同的公式对象（唯一真源冲突）")
        (f, whens), = forms.items()
        if len(whens) > 1:
            raise ValueError(f"公式 {fid} 出现在多个方法条件下：{whens}")
        out.append((f, whens[0] if whens else None))
    return out, ext


def entry(f, when):
    edition = f"{f.standard}:{f.edition}" if f.standard else None
    row = {
        "id": f.id, "output": f.output, "unit": f.unit, "expr": f.expr, "kind": f.kind,
        "start": float(f.start) if f.kind == "fixed_point" else None,
        "tol": f.tol, "domain": list(f.domain), "clause": f.ref, "edition": edition,
        "method": dict(sorted(when.items())) if when else None,
        "test_vectors": None,                      # 由 merge_assessment 合并（对拍抽取）
        "evidence_level": None,                    # 同上（assessments-v1.json）
        "source_check": None,                      # 同上
        "note": f.note or None,
    }
    if f.fixed_point_derivative != "implicit":
        row["fixed_point_derivative"] = f.fixed_point_derivative
    return row


def coverage(rows):
    return {k: {"filled": sum(1 for r in rows if r[k] is not None and r[k] != []),
                "null": sum(1 for r in rows if r[k] is None)} for k in FIELDS}


def load_assessments():
    return json.loads(ASSESS_OUT.read_text(encoding="utf-8"))


def merge_assessment(rows, assessments, targets):
    """把评定（等级、来源核对）和对拍抽取的测试向量并入记录；targets：{公式 id: target}（benchmarks.extract 结构）。"""
    by = {a["id"]: a for a in assessments}
    for r in rows:
        a = by.get(r["id"])
        if a is not None:
            r["evidence_level"], r["source_check"] = a["evidence_level"], a["source_check"]
        t = targets.get(r["id"])
        if t and t["vectors"]:
            r["test_vectors"] = [dict(v) for v in t["vectors"]]
    return rows


def build(assessments=None):
    from gearmath.tools import benchmarks as BM
    from gearmath.kernel.registry import validate_assessments, validate_cases
    pairs, ext = collect()
    ex = BM.extract()
    adoc = assessments or load_assessments()
    rows = merge_assessment([entry(f, w) for f, w in pairs], adoc["formulas"], ex["library"])
    slots = sorted(({"output": v.output, "unit": v.unit, "clause": v.ref, "method": dict(sorted(dict(v.when).items()))}
                    for v in ext), key=lambda s: (s["output"], json.dumps(s["method"], sort_keys=True)))
    doc = {"schema": SCHEMA, "generated_by": "gearmath/tools/export_registry.py",
           "count": len(rows), "coverage": coverage(rows), "formulas": rows, "external_slots": slots}
    doc["alternatives"] = alternatives(doc)
    errs = validate_registry(doc)
    if errs:
        raise ValueError("导出的注册表未通过 schema 校验：" + "；".join(errs[:5]))
    cdoc = build_cases(adoc, ex)
    errs = validate_cases(cdoc, doc) + validate_assessments(adoc, doc, cdoc)
    if errs:
        raise ValueError("案例级注册表/评定未通过校验：" + "；".join(errs[:5]))
    return doc


def build_cases(assessments=None, ex=None):
    """案例级注册表：每个案例适配器相对库级注册表改写或新增的公式（同 schema 记录），带 case id。"""
    from gearmath.tools import benchmarks as BM
    ex = ex or BM.extract()
    adoc = assessments or load_assessments()
    cases = []
    for cid in sorted(ex["cases"]):
        c = ex["cases"][cid]
        rows = merge_assessment([entry(t["formula"], None) for _, t in sorted(c["targets"].items())],
                                [a for a in adoc["case_formulas"] if a["case_id"] == cid], c["targets"])
        bench = next(b for b in ex["benchmarks"] if b["id"] == cid)
        cases.append({"case_id": cid, "benchmark": {k: bench[k] for k in ("kind_text", "level", "description", "rows_passed")},
                      "library_formula_ids": c["library_ids"], "coverage": coverage(rows) if rows else {},
                      "formulas": rows})
    return {"schema": CASE_SCHEMA, "generated_by": "gearmath/tools/export_registry.py", "count": len(cases),
            "note": "formulas 只含相对库级注册表改写（同 id 内容不同）或新增的公式；与库公式逐字相同的只列 id。"
                    "含私有标准/商业软件算例数值，不得再分发。", "cases": cases}


def render(doc=None):
    return json.dumps(doc or build(), ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def render_cases(doc=None):
    return json.dumps(doc or build_cases(), ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main(argv):
    from gearmath.tools import assess_registry as AR
    if "--check" in argv:
        ok = True
        for path, text in ((ASSESS_OUT, AR.render()), (OUT, render()), (CASES_OUT, render_cases())):
            cur = path.read_text(encoding="utf-8") if path.exists() else ""
            same = cur == text
            ok &= same
            print(f"{path.name}：{'一致' if same else '不一致'}")
        if not ok:
            print("请运行 python3 -I gearmath/tools/export_registry.py")
        return 0 if ok else 2
    OUT.parent.mkdir(parents=True, exist_ok=True)
    adoc = AR.build()                                  # 评定先于合并重新生成，保证三份文件互相一致
    ASSESS_OUT.write_text(AR.render(adoc), encoding="utf-8")
    OUT.write_text(render(build(adoc)), encoding="utf-8")
    CASES_OUT.write_text(render_cases(build_cases(adoc)), encoding="utf-8")
    for p in (ASSESS_OUT, OUT, CASES_OUT):
        print(f"已写入 {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
