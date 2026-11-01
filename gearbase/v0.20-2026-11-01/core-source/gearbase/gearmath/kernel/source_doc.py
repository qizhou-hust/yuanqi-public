"""可编辑源文档的通用机制（零依赖）：最小 JSON Schema 校验器、规范哈希、模型 <-> 文档分区的互转。

本模块不知道任何具体领域：文档的模式标识、输入声明表、方法选择器如何装配，都由调用方的领域层提供。
文档只持久化作者输入、证据（带证书引用）、约束、方法选择器、标准版次；派生量（模型公式的输出）一律不存，
出现即拒绝（derived_locked / undeclared_input 由 Model.set 报告，这里原样收集）。

文档分区：
  inputs       作者输入（来源类别 user / assumption / standard_constant / agent_proposed / optimizer）
  evidence     外部证据输入（来源类别 evidence），每条必须带证书引用 certificate
  constraints  约束与限值（输入声明表里 role = limit 的量）
  selectors    方法选择器（取值 + 来源）
  editions     标准分册版次（版次 + 来源）
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from . import units as U
from .graph import InputError

SECTION_PROVENANCE = {"inputs": ("user", "assumption", "standard_constant", "agent_proposed", "optimizer")}
CERT_KINDS = ("file", "tool_calculation", "citation")


class SourceError(ValueError):
    """源文档不合格。errors：[{"path","code","message"}]，逐项收集，不在第一处错误中断。"""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("；".join(f"{e['path']}：{e['message']}" for e in self.errors[:6])
                         + (f"（共 {len(self.errors)} 项）" if len(self.errors) > 6 else ""))


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 最小 JSON Schema（draft 2020-12 的子集）
def _is_type(v, t):
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    raise ValueError(f"校验器不支持类型 {t}")


def validate_schema(instance, schema, path="$"):
    """支持 type、required、properties、additionalProperties（布尔或子模式）、propertyNames.pattern、enum、const、
    pattern、minLength、minimum、exclusiveMinimum、items、minProperties。返回 [{"path","code","message"}]。"""
    out = []

    def err(code, msg):
        out.append({"path": path, "code": code, "message": msg})

    t = schema.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(_is_type(instance, x) for x in ts):
            err("type", f"类型应为 {'/'.join(ts)}，实际 {type(instance).__name__}")
            return out
    if "const" in schema and instance != schema["const"]:
        err("const", f"必须等于 {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        err("enum", f"{instance!r} 不在允许值 {schema['enum']} 内")
    if isinstance(instance, float) and not math.isfinite(instance):
        err("not_finite", "数值必须有限")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            err("minLength", f"长度不得小于 {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            err("pattern", f"{instance!r} 不匹配 {schema['pattern']}")
    if _is_type(instance, "number"):
        if "minimum" in schema and instance < schema["minimum"]:
            err("minimum", f"不得小于 {schema['minimum']}")
        if "exclusiveMinimum" in schema and not instance > schema["exclusiveMinimum"]:
            err("exclusiveMinimum", f"必须大于 {schema['exclusiveMinimum']}")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        if len(instance) < schema.get("minProperties", 0):
            err("minProperties", f"至少需要 {schema['minProperties']} 个键")
        for k in schema.get("required", ()):
            if k not in instance:
                out.append({"path": f"{path}.{k}", "code": "required", "message": f"缺少必需键 {k}"})
        pn = schema.get("propertyNames", {}).get("pattern")
        for k, v in instance.items():
            sub = f"{path}.{k}"
            if pn and not re.search(pn, k):
                out.append({"path": sub, "code": "propertyNames", "message": f"键名 {k!r} 不匹配 {pn}"})
            if k in props:
                out += validate_schema(v, props[k], sub)
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    out.append({"path": sub, "code": "additionalProperties",
                                "message": f"不允许的键 {k}（源文档只接受作者输入、证据、约束、选择器、版次；派生量与结果一律不存）"})
                elif isinstance(ap, dict):
                    out += validate_schema(v, ap, sub)
    if isinstance(instance, list) and "items" in schema:
        for i, v in enumerate(instance):
            out += validate_schema(v, schema["items"], f"{path}[{i}]")
    return out


# ---------------------------------------------------------------- 模型 -> 文档分区
def _user_value(value, unit):
    """规范单位数值 → 用户单位下能逐位还原的最短数值（还原不了就报错，不静默改值）。"""
    x0 = U.from_canonical(value, unit)
    for c in [float(f"{x0:.{p}g}") for p in range(1, 18)] + [x0]:      # 最短的能逐位还原者优先
        if U.to_canonical(c, unit) == value:
            return c
    y = x0
    for _ in range(4):
        for y in (math.nextafter(y, math.inf), math.nextafter(y, -math.inf)):
            if U.to_canonical(y, unit) == value:
                return y
    raise ValueError(f"数值 {value!r}（规范单位）无法在单位 {unit} 下逐位还原")


def model_to_sections(model, certificates=None):
    """把一个已装配的 Model 的作者输入分区写成文档片段。派生来源的输入、缺来源说明的条目逐项报错。
    certificates：{输入名: 证书对象}；evidence 输入缺证书时退化为 kind=citation（仅文字引用，不可机器核验）。"""
    certificates = certificates or {}
    limits = {s.name for s in model.specs.values() if s.role == "limit"}
    sec = {"inputs": {}, "evidence": {}, "constraints": {}, "selectors": {}, "editions": {}}
    errors = []
    for name, i in sorted(model.inputs.items()):
        if not i.source:
            errors.append({"path": f"$.{name}", "code": "missing_source", "message": f"输入 {name} 缺来源说明"})
            continue
        if i.provenance == "derived":
            errors.append({"path": f"$.{name}", "code": "derived_in_source",
                           "message": f"输入 {name} 的来源类别为 derived（派生量），不得写入源文档"})
            continue
        row = {"value": _user_value(i.value, i.unit), "unit": i.unit, "provenance": i.provenance, "source": i.source}
        if name in limits:
            sec["constraints"][name] = row
        elif i.provenance == "evidence":
            row["certificate"] = certificates.get(name) or {"kind": "citation", "ref": i.source}
            sec["evidence"][name] = row
        else:
            sec["inputs"][name] = row
    for k, v in sorted(model.selectors.items()):
        s = model.selector_sources.get(k)
        if not s:
            errors.append({"path": f"$.selectors.{k}", "code": "missing_source", "message": f"选择器 {k} 缺来源说明"})
            continue
        sec["selectors"][k] = {"value": v, "source": s}
    for part, ed in sorted(model.editions.items()):
        s = model.edition_sources.get(part)
        if not s:
            errors.append({"path": f"$.editions.{part}", "code": "missing_source", "message": f"版次 {part} 缺来源说明"})
            continue
        sec["editions"][part] = {"edition": ed, "source": s}
    if errors:
        raise SourceError(errors)
    return sec


# ---------------------------------------------------------------- 文档分区 -> 模型
def apply_sections(model, doc):
    """按文档设置版次与输入；逐项收集错误（派生量被锁定、未声明、量纲不符、超出取值域……）。
    不设任何默认：文档没给的输入就没有，求值时由 Model 报告缺输入。"""
    errors = []
    for part, row in doc.get("editions", {}).items():
        try:
            model.set_edition(part, row["edition"], row["source"])
        except InputError as e:
            errors.append({"path": f"$.editions.{part}", "code": e.code, "message": str(e)})
    for section in ("inputs", "evidence", "constraints"):
        for name, row in doc.get(section, {}).items():
            try:
                model.set(name, row["value"], row["unit"], row["provenance"], row["source"])
            except InputError as e:
                errors.append({"path": f"$.{section}.{name}", "code": e.code, "message": str(e)})
    if errors:
        raise SourceError(errors)
    return model


def check_semantics(doc):
    """schema 之外的跨字段规则：证书类型的必填项；约束/输入/证据三区不得重名。"""
    errors = []
    seen = {}
    for section in ("inputs", "evidence", "constraints"):
        for name, row in doc.get(section, {}).items():
            if name in seen:
                errors.append({"path": f"$.{section}.{name}", "code": "duplicate", "message": f"{name} 同时出现在 {seen[name]} 与 {section}"})
            seen[name] = section
            if section == "inputs" and row.get("provenance") not in SECTION_PROVENANCE["inputs"]:
                errors.append({"path": f"$.inputs.{name}", "code": "provenance",
                               "message": f"inputs 区的来源类别须为 {SECTION_PROVENANCE['inputs']}"})
            if section == "evidence":
                c = row.get("certificate") or {}
                if c.get("kind") == "file" and not (c.get("sha256") and c.get("locator")):
                    errors.append({"path": f"$.evidence.{name}.certificate", "code": "certificate",
                                   "message": "kind=file 的证书必须给出 sha256 与 locator"})
    return errors
