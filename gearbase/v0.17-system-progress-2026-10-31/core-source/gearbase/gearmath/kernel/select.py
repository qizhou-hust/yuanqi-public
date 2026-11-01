"""方法选择器（K3）：注册表里同一输出可有多个变体，编译期按选择器特化成"一个输出一条公式"。

  - 变体 = Variant(when={"method.X": "B"}, formula=Formula(...))；when 为空表示通用（总是命中）；
    也接受带 when 属性的 Formula（若日后 Formula 增加该字段）；
  - external(output, unit, when)：该量不由公式给出，必须作为 evidence 输入提供（带证书来源）；
  - specialize(formulas, selectors) 对每个输出恰好命中一行，否则拒绝；结果直接交给 graph.Model；
  - method_diff(...) 用两个特化实例的差分回答"换方法会让哪些中间量差多少"。
选择器是无量纲的枚举，不参与求导。本模块不知道任何领域概念。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .expr import FormulaError
from .graph import Model


@dataclass(frozen=True)
class Variant:
    when: tuple                   # ((选择器, 取值), ...)
    formula: object = None        # graph.Formula；None 表示 external
    output: str = ""
    unit: str = ""
    ref: str = ""

    @property
    def out(self):
        return self.formula.output if self.formula is not None else self.output

    @property
    def label(self):
        return self.formula.id if self.formula is not None else f"external:{self.output}"


def _when(w) -> tuple:
    items = w.items() if isinstance(w, dict) else (w or ())
    return tuple(sorted((str(k), str(v)) for k, v in items))


def variant(formula, when) -> Variant:
    return Variant(_when(when), formula)


def external(output, unit, when, ref="") -> Variant:
    """命中时删除该输出的公式，改为必须提供的 evidence 输入。"""
    return Variant(_when(when), None, output, unit, ref)


def _as_variant(x) -> Variant:
    return x if isinstance(x, Variant) else Variant(_when(getattr(x, "when", ())), x)


class Specialized(list):
    """特化后的公式列表（可直接传给 Model）。附带：
    selectors：使用的选择器；chosen：输出 → 命中变体标签；
    required_evidence：输出 → {"unit", "ref", "provenance": "evidence", "when"}；
    unused_selectors：未被任何变体引用的选择器（多半是拼写错误或别的模块用的）。"""
    selectors: dict
    chosen: dict
    required_evidence: dict
    unused_selectors: list


def specialize(formulas, selectors, prune=False) -> Specialized:
    """prune=True：某输出的所有变体都带条件、且在当前选择下一个也不命中时，该输出被省略（只在某方法下才存在的中间量）
    而不是报错；选择器未选、同时命中多个变体仍然报错。"""
    sel = {str(k): str(v) for k, v in (selectors or {}).items()}
    groups: dict[str, list[Variant]] = {}
    for x in formulas:
        v = _as_variant(x)
        groups.setdefault(v.out, []).append(v)
    out = Specialized()
    out.selectors, out.chosen, out.required_evidence = dict(sel), {}, {}
    used = set()
    for name, vs in groups.items():
        keys = sorted({k for v in vs for k, _ in v.when})
        used |= set(keys)
        # 已被某个已选选择器排除的变体不再要求其余选择器（如 K_V=external 时不要求 m_red 的口径）
        live = [v for v in vs if all(sel.get(k, val) == val for k, val in v.when)]
        unset = sorted({k for v in live for k, _ in v.when if k not in sel})
        if unset:
            opts = "；".join(f"{k} ∈ {{{', '.join(sorted({val for v in live for kk, val in v.when if kk == k}))}}}"
                            for k in unset)
            raise FormulaError(f"未选择方法：{name} 需要选择器 {opts}")
        hits = [v for v in vs if all(sel[k] == val for k, val in v.when)]
        if not hits and prune and all(v.when for v in vs):
            continue
        if not hits:
            opts = "、".join(f"{v.label}{dict(v.when)}" for v in vs)
            raise FormulaError(f"无可用方法：{name} 在 {({k: sel[k] for k in keys})} 下没有匹配的变体；可选：{opts}")
        if len(hits) > 1:
            raise FormulaError(f"方法歧义：{name} 同时命中 {'、'.join(v.label for v in hits)}")
        v = hits[0]
        out.chosen[name] = v.label
        if v.formula is None:
            out.required_evidence[name] = {"unit": v.unit, "ref": v.ref, "provenance": "evidence", "when": dict(v.when)}
        else:
            out.append(v.formula)
    out.unused_selectors = sorted(set(sel) - used)
    return out


def evidence_problems(spec: Specialized, model) -> list:
    """检查 external 量是否已作为 evidence 输入提供；返回问题列表（空 = 通过）。"""
    probs = []
    for name, req in spec.required_evidence.items():
        i = model.inputs.get(name)
        if i is None:
            probs.append(f"{name} 选择了 external，必须提供 evidence 输入（单位 {req['unit']}）")
        elif i.provenance != "evidence":
            probs.append(f"{name} 选择了 external，来源必须是 evidence，实际为 {i.provenance}")
    return probs


def build(formulas, selectors, inputs, prune=False, editions=None) -> tuple:
    """特化 + 建模 + 设输入。inputs：名称 → (值, 单位[, 来源[, 出处]]) 或 {"value","unit","provenance","source"}。
    给某个特化中已是派生量的输入会被跳过（另一种方法下它才是输入）。"""
    spec = specialize(formulas, selectors, prune)
    m = Model(spec, editions=editions)
    for k, v in inputs.items():
        if k in m.formulas:
            continue
        if isinstance(v, dict):
            m.set(k, v["value"], v["unit"], v.get("provenance", "user"), v.get("source", ""))
        else:
            m.set(k, *v)
    return m, spec


def method_diff(formulas, selectors_a, selectors_b, inputs, targets, prune=False, editions=None) -> dict:
    """两个特化实例的差分。rows 为两边都有的量（规范单位），按 |相对差| 降序；
    changed=True 表示该量本身换了公式（或一边为外部证据），否则差异是传播来的。"""
    side = {}
    for tag, sel in (("a", selectors_a), ("b", selectors_b)):
        m, spec = build(formulas, sel, inputs, prune, editions)
        probs = evidence_problems(spec, m)
        r = m.evaluate(targets)
        side[tag] = (m, spec, r, probs)
    (ma, sa, ra, pa), (mb, sb, rb, pb) = side["a"], side["b"]
    res = {"status": "ok", "selectors_a": sa.selectors, "selectors_b": sb.selectors,
           "evidence_problems": {"a": pa, "b": pb}, "rows": [], "only_a": [], "only_b": []}
    if ra.status == "blocked_missing_inputs" or rb.status == "blocked_missing_inputs":
        res["status"] = "blocked_missing_inputs"
        res["missing"] = {"a": ra.missing, "b": rb.missing}
        res["missing_editions"] = {"a": ra.missing_editions, "b": rb.missing_editions}
        return res

    def label(m, spec, q):
        return m.formulas[q].id if q in m.formulas else spec.chosen.get(q, "input")

    rows = []
    for q in sorted(set(ra.values) & set(rb.values)):
        a, b = ra.values[q], rb.values[q]
        rel = 0.0 if a == b else (b - a) / abs(a) if a else math.inf
        fa, fb = label(ma, sa, q), label(mb, sb, q)
        rows.append({"name": q, "a": a, "b": b, "abs_diff": b - a, "rel_diff": rel,
                     "formula_a": fa, "formula_b": fb, "changed": fa != fb})
    res["rows"] = sorted(rows, key=lambda r: (-abs(r["rel_diff"]), r["name"]))
    res["only_a"] = sorted(set(ra.values) - set(rb.values))
    res["only_b"] = sorted(set(rb.values) - set(ra.values))
    res["status_a"], res["status_b"] = ra.status, rb.status
    return res
