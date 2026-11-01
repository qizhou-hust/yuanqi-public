"""声明式问题（零依赖，纯数学）：把"变量 / 目标 / 约束"的显式声明编译成 optimize.Problem 与区间界函数。

本模块不知道任何领域：量（quantity）只是名字，单位只是字符串；求值由调用方提供的"量求值器"完成。
声明格式（gearmath.problem_declaration/v1，JSON 可序列化）：

    {"schema": "gearmath.problem_declaration/v1", "id": "...", "description": "...",
     "variables":   [{"name", "kind": integer|ordered_choice|unordered_choice|continuous,
                      "lo"/"hi" 或 "values", "unit", "source", 连续变量另需 "resolution"}],
     "objective":   {"quantity", "sense": min|max, "unit", "source"},
     "constraints": [{"id", "quantity", "sense": ">="|"<=", "limit": {"value", "unit", "source"}}],
     "parameters":  {...}}            # 领域层自用，本模块不解释

缺任何必需字段即阻断（validate_declaration 返回逐项错误），不补默认：下限、离散系列、变量界、制造分辨率都必须显式给出。

量求值器（领域层实现）须提供：
    point(x: dict, wrt: tuple) -> {"status": "ok" | "error", "values": {量: float}, "derivatives": {量: {变量: ∂}},
                                   "applicability_violated": bool, "message": str}
    interval(box: {变量: (lo, hi)}, quantities: list) -> {"values": {量: (lo, hi) 或 None}, "unsupported": {量: 原因},
                                                          "applicability_violated": bool}   # 只求所列的量
数值一律按声明里给出的单位交换。interval 必须是保证包含（盒内任一点的 point 值都落在区间内）；
给不出保证的量返回 None（视为无界，不参与剪枝）。

约束变换（写死）：">=" → g = (limit − q)/|limit|，"<=" → g = (q − limit)/|limit|（limit = 0 时除数取 1）；g ≤ 0 为可行。
另加一条 "applicability"：公式适用域被违反 = +1，否则 −1（阶跃，非光滑；区间上只在"盒内必然违反"时取 [1, 1]，
否则取 [−1, 1]，从不声称盒内必然满足）。
"""
from __future__ import annotations

import math

from . import interval as IV
from .optimize import Choice, Constraint, Continuous, Integer, Objective, Problem, _canonical

DECL_SCHEMA = "gearmath.problem_declaration/v1"
APPLICABILITY = "applicability"
_KINDS = ("integer", "ordered_choice", "unordered_choice", "continuous")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _src(v):
    return isinstance(v, str) and v.strip() != ""


def validate_declaration(decl):
    """结构校验。返回 [{"path","code","message"}]；空 = 合格。缺字段即报错（blocked_missing_declaration）。"""
    errs = []

    def e(path, code, msg):
        errs.append({"path": path, "code": code, "message": msg})

    if not isinstance(decl, dict):
        return [{"path": "$", "code": "type", "message": "声明必须是对象"}]
    if decl.get("schema") != DECL_SCHEMA:
        e("$.schema", "schema", f"schema 必须为 {DECL_SCHEMA}")
    if not _src(decl.get("id")):
        e("$.id", "missing", "缺 id")
    vs = decl.get("variables")
    if not isinstance(vs, list) or not vs:
        e("$.variables", "missing", "至少声明一个变量")
        vs = []
    names = set()
    for i, v in enumerate(vs):
        p = f"$.variables[{i}]"
        if not isinstance(v, dict):
            e(p, "type", "变量声明必须是对象")
            continue
        n = v.get("name")
        if not _src(n):
            e(p + ".name", "missing", "缺变量名")
        elif n in names:
            e(p + ".name", "duplicate", f"变量 {n} 重复")
        names.add(n)
        k = v.get("kind")
        if k not in _KINDS:
            e(p + ".kind", "kind", f"kind 须为 {_KINDS}")
            continue
        if not _src(v.get("source")):
            e(p + ".source", "missing", f"变量 {n} 缺来源说明（取值域的依据）")
        if not _src(v.get("unit")):
            e(p + ".unit", "missing", f"变量 {n} 缺单位")
        if k in ("integer", "continuous"):
            lo, hi = v.get("lo"), v.get("hi")
            if not (_num(lo) and _num(hi)):
                e(p, "missing", f"变量 {n} 须显式给出有限的 lo/hi")
            elif lo > hi:
                e(p, "order", f"变量 {n} 的 lo > hi")
            elif k == "integer" and not (float(lo).is_integer() and float(hi).is_integer()):
                e(p, "integer", f"整数变量 {n} 的 lo/hi 须为整数")
        else:
            vals = v.get("values")
            if not isinstance(vals, list) or not vals or not all(_num(t) for t in vals):
                e(p + ".values", "missing", f"离散变量 {n} 须显式给出非空数值系列 values")
            elif len(set(vals)) != len(vals):
                e(p + ".values", "duplicate", f"离散变量 {n} 的 values 有重复")
        if k == "continuous":
            r = v.get("resolution")
            if not (_num(r) and r > 0):
                e(p + ".resolution", "missing", f"连续变量 {n} 须显式给出写回分辨率 resolution > 0（写回真源前按它回圆并复核）")
    o = decl.get("objective")
    if not isinstance(o, dict):
        e("$.objective", "missing", "缺目标")
    else:
        if not _src(o.get("quantity")):
            e("$.objective.quantity", "missing", "缺目标量")
        if o.get("sense") not in ("min", "max"):
            e("$.objective.sense", "missing", "sense 须为 min 或 max")
        if not _src(o.get("unit")):
            e("$.objective.unit", "missing", "缺目标单位")
        if not _src(o.get("source")):
            e("$.objective.source", "missing", "缺目标来源说明")
    cs = decl.get("constraints")
    if not isinstance(cs, list):
        e("$.constraints", "missing", "缺约束列表（可为空列表，但须显式给出）")
        cs = []
    ids = set()
    for i, c in enumerate(cs):
        p = f"$.constraints[{i}]"
        if not isinstance(c, dict):
            e(p, "type", "约束声明必须是对象")
            continue
        cid = c.get("id")
        if not _src(cid):
            e(p + ".id", "missing", "缺约束 id")
        elif cid in ids or cid == APPLICABILITY:
            e(p + ".id", "duplicate", f"约束 id {cid} 重复或与保留名冲突")
        ids.add(cid)
        if not _src(c.get("quantity")):
            e(p + ".quantity", "missing", "缺约束量")
        if c.get("sense") not in (">=", "<="):
            e(p + ".sense", "missing", "sense 须为 '>=' 或 '<='")
        lim = c.get("limit")
        if not isinstance(lim, dict) or not _num(lim.get("value")) or not _src(lim.get("unit")) or not _src(lim.get("source")):
            e(p + ".limit", "missing_limit", f"约束 {cid} 须显式给出限值 limit = {{value, unit, source}}（不设默认下限）")
    return errs


def declaration_sha256(decl):
    import hashlib
    return hashlib.sha256(_canonical(decl).encode("utf-8")).hexdigest()


def requested_quantities(decl):
    """{量: 单位}：目标与约束用到的全部量及其交换单位。同一个量用不同单位 -> ValueError。"""
    out = {decl["objective"]["quantity"]: decl["objective"]["unit"]}
    for c in decl["constraints"]:
        q, u = c["quantity"], c["limit"]["unit"]
        if out.get(q, u) != u:
            raise ValueError(f"量 {q} 在声明中用了两个单位 {out[q]} / {u}")
        out[q] = u
    return out


def variables_of(decl):
    out = []
    for v in decl["variables"]:
        k = v["kind"]
        if k == "integer":
            out.append(Integer(v["name"], int(v["lo"]), int(v["hi"])))
        elif k == "continuous":
            out.append(Continuous(v["name"], float(v["lo"]), float(v["hi"])))
        else:
            vals = tuple(sorted(v["values"])) if k == "ordered_choice" else tuple(v["values"])
            out.append(Choice(v["name"], vals, ordered=(k == "ordered_choice")))
    return out


def _scale(limit):
    return abs(limit) if limit != 0 else 1.0


def compile_declaration(decl, evaluator):
    """声明 + 量求值器 -> (Problem, bounds)。声明不合格 -> ValueError（附逐项错误）。

    bounds(box) -> {"objectives": {名: (lo, hi) 或 None}, "constraints": {名: (lo, hi) 或 None}, "unsupported": {...}}
    是保证包含的界（由求值器的区间结果经外向舍入的区间运算变换得到），供 gridprune 剪枝。
    约束按声明顺序逐条求区间、遇到盒内必然违反即停（把便宜的约束写在前面可以省时）；None = 未求或给不出界。"""
    errs = validate_declaration(decl)
    if errs:
        raise ValueError(errs)
    variables = variables_of(decl)
    cont = tuple(v.name for v in variables if isinstance(v, Continuous))
    obj = decl["objective"]
    cons = decl["constraints"]
    cache = {}

    def point(x):
        key = tuple((k, float(x[k])) for k in sorted(x))
        if cache.get("key") != key:
            r = evaluator.point(dict(x), cont)
            if r.get("status") != "ok":
                raise RuntimeError(f"求值失败：{r.get('message', r.get('status'))}")
            cache.update(key=key, r=r)
        return cache["r"]

    def evaluate(x):
        r = point(x)
        v = r["values"]
        g = {}
        for c in cons:
            lim = float(c["limit"]["value"])
            q = v[c["quantity"]]
            g[c["id"]] = ((lim - q) if c["sense"] == ">=" else (q - lim)) / _scale(lim)
        g[APPLICABILITY] = 1.0 if r.get("applicability_violated") else -1.0
        return {"objectives": {obj["quantity"]: v[obj["quantity"]]}, "constraints": g,
                "info": {"quantities": dict(v), "applicability_violated": bool(r.get("applicability_violated"))}}

    def gradient(x):
        r = point(x)
        d = r["derivatives"]
        zero = {n: 0.0 for n in cont}
        out = {"objectives": {obj["quantity"]: dict(zero, **d.get(obj["quantity"], {}))}, "constraints": {}}
        for c in cons:
            lim = float(c["limit"]["value"])
            s = (-1.0 if c["sense"] == ">=" else 1.0) / _scale(lim)
            dq = d.get(c["quantity"], {})
            out["constraints"][c["id"]] = {n: s * dq.get(n, 0.0) for n in cont}
        out["constraints"][APPLICABILITY] = dict(zero)       # 阶跃指示：几乎处处导数为 0（非光滑）
        return out

    def bounds(box):
        """按声明顺序逐条取约束量的区间；某条约束区间下端 > 0（盒内必然违反）即停止，其余记为 None（不参与剪枝）。
        全部约束都未判死时再取目标区间。每个量只向求值器要一次。"""
        res = {"objectives": {obj["quantity"]: None}, "constraints": {c["id"]: None for c in cons}, "unsupported": {}}
        got = {}

        def q_iv(q):
            if q not in got:
                r = evaluator.interval(dict(box), [q])
                got[q] = r.get("values", {}).get(q)
                res["unsupported"].update(r.get("unsupported", {}))
                if r.get("applicability_violated"):
                    got["__applicability__"] = True
            return got[q]

        for c in cons:
            q = q_iv(c["quantity"])
            if got.get("__applicability__"):
                break
            if q is None:
                continue
            lim = float(c["limit"]["value"])
            qi, li = IV.Interval(q[0], q[1]), IV.Interval(lim)
            gi = ((li - qi) if c["sense"] == ">=" else (qi - li)) / IV.Interval(_scale(lim))
            res["constraints"][c["id"]] = (gi.lo, gi.hi)
            if gi.lo > 0.0:
                break
        else:
            q = q_iv(obj["quantity"])
            res["objectives"][obj["quantity"]] = None if q is None else (q[0], q[1])
        res["constraints"][APPLICABILITY] = (1.0, 1.0) if got.get("__applicability__") else (-1.0, 1.0)
        return res

    problem = Problem(variables, evaluate, [Objective(obj["quantity"], obj["sense"])],
                      description=decl.get("description", ""),
                      constraints=[Constraint(c["id"], note=f"{c['quantity']} {c['sense']} {c['limit']['value']} {c['limit']['unit']}"
                                                            f"（{c['limit']['source']}）") for c in cons]
                                  + [Constraint(APPLICABILITY, note="适用域违反 +1 / 否则 −1（阶跃，非光滑，KKT 无意义）")],
                      parameters={"declaration_id": decl["id"], "declaration_sha256": declaration_sha256(decl)},
                      evaluator_id=f"{DECL_SCHEMA}:{decl['id']}", gradient=gradient)
    return problem, bounds


def resolutions(decl):
    return {v["name"]: float(v["resolution"]) for v in decl["variables"] if v["kind"] == "continuous"}
