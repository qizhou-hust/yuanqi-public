"""gears.math-source/2：唯一可编辑真源文档（M34）。格式见 docs/真源格式-v2.md，模式见 data/source/gears.math-source-2.schema.json。

文档只含作者输入、证据（带证书引用）、约束、方法选择器、标准版次；派生量不存。本模块提供：
  validate(doc)            结构校验 + 跨字段规则（不装配模型）；返回错误列表
  build_model(doc)         文档 -> 圆柱齿轮副 Model（逐项收集错误，派生量被锁定即拒绝；不设任何默认）
  source_from_model(m)     已装配 Model -> 文档（design_store 的提交单元；证书缺失时退化为文字引用）
  convert_m31_case(...)    由 M31 案例 + 收据（data/m31 + gear/m31_case.py 的装配结果）生成文档（含证书哈希）
  project_receipt(doc)     只读投影：校核回执（含 source_sha256）；project_parameter_table(doc) 只读投影：参数表
  compare_receipts(a, b)   新旧回执逐位对比（迁移期双写）
投影不写回源文档；函数不修改传入的 doc。
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib

from ..kernel import source_doc as SD
from ..kernel.expr import FormulaError
from . import m31_case
from .factor_methods import FACTOR_OPTIONS
from .rating import pair_model, rate

SCHEMA_ID = "gears.math-source/2"
SourceError = SD.SourceError
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data" / "source" / "gears.math-source-2.schema.json"
C001_SOURCE_PATH = ROOT / "data" / "source" / "C001.math-source.json"
_SCHEMA = None


def schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


def load_file(path=C001_SOURCE_PATH):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def source_sha256(doc):
    return SD.sha256_of(doc)


def validate(doc):
    """结构（JSON Schema）+ 跨字段规则。返回 [{"path","code","message"}]；空 = 合格。"""
    if not isinstance(doc, dict):
        return [{"path": "$", "code": "type", "message": "源文档必须是对象"}]
    errs = SD.validate_schema(doc, schema())
    return errs if errs else SD.check_semantics(doc)


def _sel_split(doc):
    sel = {k: r["value"] for k, r in doc["selectors"].items()}
    src = {k: r["source"] for k, r in doc["selectors"].items()}
    fsel = {k: v for k, v in sel.items() if k in FACTOR_OPTIONS}
    return {k: v for k, v in sel.items() if k not in fsel}, src, fsel


def build_model(doc):
    """文档 -> Model。校验失败、选择器非法、输入被公式锁定/未声明/量纲不符 -> SourceError（含逐项错误）。"""
    errs = validate(doc)
    if errs:
        raise SD.SourceError(errs)
    sel, src, fsel = _sel_split(doc)
    try:
        m = pair_model(selectors=sel, selector_sources=src, factor_selectors=fsel or None,
                       factor_selector_sources=src if fsel else None)
    except (FormulaError, TypeError, ValueError) as e:
        raise SD.SourceError([{"path": "$.selectors", "code": "invalid_selector", "message": str(e)}]) from e
    return SD.apply_sections(m, doc)


def source_from_model(model, doc_id, title, certificates=None, note=None):
    """已装配 Model -> 源文档（校验通过才返回）。派生来源的输入、缺来源的条目 -> SourceError。"""
    doc = {"schema": SCHEMA_ID, "id": doc_id, "title": title, **SD.model_to_sections(model, certificates)}
    if note:
        doc["note"] = note
    errs = validate(doc)
    if errs:
        raise SD.SourceError(errs)
    return doc


# ---------------------------------------------------------------- 投影（只读）
def receipt_of(model):
    """回执：校核输出（去掉 Result 对象）+ 全部已求值量。新旧双写对比的统一口径。"""
    r = rate(model)
    res = r.pop("result", None)
    r["values"] = dict(res.values) if res is not None else {}
    r["evidence"] = copy.deepcopy(res.evidence) if res is not None else {}
    return r


def project_receipt(doc):
    """只读投影：由源文档生成校核回执。回执不是源，不能写回。"""
    m = build_model(doc)
    return {"projection": "receipt", "source_schema": SCHEMA_ID, "source_id": doc["id"],
            "source_sha256": source_sha256(doc), "receipt": receipt_of(m)}


def project_parameter_table(doc):
    """只读投影：参数表。source 行来自文档；derived 行是在选定方法与输入下的模型输出（仅在可求值时给出）。"""
    m = build_model(doc)
    rows = []
    for section in ("inputs", "evidence", "constraints"):
        for name, r in sorted(doc[section].items()):
            row = {"name": name, "section": section, "value": r["value"], "unit": r["unit"],
                   "provenance": r["provenance"], "source": r["source"], "derived": False, "writable": True}
            if "certificate" in r:
                row["certificate"] = copy.deepcopy(r["certificate"])
            rows.append(row)
    rec = receipt_of(m)
    for name, v in sorted(rec["values"].items()):
        f = m.formulas.get(name)
        if f is not None:
            rows.append({"name": name, "section": "derived", "value": v, "unit": "canonical:" + f.unit,
                         "formula": f.id, "ref": f.ref, "derived": True, "writable": False})
    return {"projection": "parameter_table", "source_sha256": source_sha256(doc), "status": rec["status"], "rows": rows}


def compare_receipts(a, b):
    """逐位对比两份回执（规范 JSON 文本相等才算一致；浮点按 repr 精确比较）。返回差异路径列表，空 = 逐位一致。"""
    diffs = []

    def walk(x, y, p):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y:
                    diffs.append(p + "." + str(k))
                else:
                    walk(x[k], y[k], p + "." + str(k))
        elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)) and len(x) == len(y):
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, f"{p}[{i}]")
        elif type(x) is not type(y) or x != y or repr(x) != repr(y):
            diffs.append(p)

    walk(a, b, "$")
    return diffs


# ---------------------------------------------------------------- 由 M31 案例生成
def _file_cert(rel, locator):
    p = m31_case.DATA / rel
    return {"kind": "file", "ref": "data/m31/" + rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "locator": locator}


def _m31_certificates(model, case, receipt, stage):
    certs = {}
    for name, (sec, key) in m31_case.RECEIPT_EVIDENCE.items():
        if name in model.inputs:
            certs[name] = _file_cert(receipt, f"stages[{stage}].{sec}.{key}")
    for name, loc in {"E": "engineering.material.elastic_modulus_MPa", "nu": "engineering.material.poissons_ratio",
                      "rho_1": "engineering.material.density_kg_per_mm3", "rho_2": "engineering.material.density_kg_per_mm3"}.items():
        if name in model.inputs:
            certs[name] = _file_cert(case, loc)
    for name in ("f_pt_1", "f_pt_2", "f_falpha_1", "f_falpha_2"):
        if name in model.inputs:
            certs[name] = {"kind": "tool_calculation", "ref": "gearmath.gear.dynamic.iso1328_tolerances",
                           "locator": "ISO 1328-1:2013 式(5)/(8)+5.2.3 圆整；精度等级见 Q_grade"}
    return certs


def convert_m31_case(case="golden/C001/derived-candidate.json", receipt="golden/C001/gear-rating.json", stage=0,
                     doc_id="C001", title="M31 C001 平行轴双级直齿减速器 第一级（K_V 方法B）"):
    """M31 案例 + 收据 -> 源文档。装配沿用 m31_case.stage_model（迁移期的旧路径），再把作者输入分区落成文档。"""
    m, _ = m31_case.stage_model(case=case, receipt=receipt, stage=stage)
    return source_from_model(m, doc_id, title, _m31_certificates(m, case, receipt, stage),
                             note="由 data/m31 案例与收据经 gear/m31_case.py 转换生成；只含作者输入与证据，派生量不存。")


def verify_certificates(doc, root=ROOT):
    """核对 kind=file 的证书：文件存在且 sha256 与登记一致。返回错误列表。"""
    errs = []
    for name, r in doc.get("evidence", {}).items():
        c = r["certificate"]
        if c["kind"] != "file":
            continue
        p = pathlib.Path(root) / c["ref"]
        if not p.is_file():
            errs.append({"path": f"$.evidence.{name}.certificate", "code": "certificate_missing", "message": f"证书文件不存在：{c['ref']}"})
        elif hashlib.sha256(p.read_bytes()).hexdigest() != c.get("sha256"):
            errs.append({"path": f"$.evidence.{name}.certificate", "code": "certificate_hash", "message": f"证书文件哈希不符：{c['ref']}"})
    return errs


def write_c001(path=C001_SOURCE_PATH):
    doc = convert_m31_case()
    pathlib.Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return doc
