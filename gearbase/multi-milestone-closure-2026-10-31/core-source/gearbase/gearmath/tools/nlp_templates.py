"""optimize_nlp 的问题模板白名单与参数校验。

只接受已编译的问题模板（名字）与数值参数；不接受表达式、代码、可调用对象或模块路径。
模板登记表是代码常量，调用方不能增加条目；每个参数有类型与取值范围，越界即拒绝。
"""
from __future__ import annotations

import math

from ..gear.problem import stage_sizing_problem
from ..kernel.optimize import Choice, Continuous, Integer, solve_nlp

# 模板名 → {factory, description, params: {名: (下限, 上限, 默认)}}
TEMPLATES = {
    "stage_sizing": {
        "factory": stage_sizing_problem,
        "description": "C001 G1 单级直齿尺寸设计：变量 z1、m_n、b、x1；目标 volume_mm3 与 center_distance_mm 最小。",
        "params": {"target_ratio": (1.0, 8.0, 1.8), "ratio_tol": (0.0, 0.5, 0.02), "max_b_over_d1": (0.1, 3.0, 1.2)},
    },
}
MAX_DISCRETE_LIMIT = 2000
_ARG_KEYS = {"template", "template_params", "weights", "x0", "discrete_assignments", "relax_discrete", "max_discrete"}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _err(name, code, msg):
    return {"name": name, "code": code, "message": msg}


def input_schema():
    return {
        "type": "object", "additionalProperties": False, "required": ["template"],
        "properties": {
            "template": {"type": "string", "enum": sorted(TEMPLATES), "description": "已编译的问题模板名（白名单）；不接受表达式或代码"},
            "template_params": {"type": "object", "description": "模板数值参数；各模板允许的键与范围见 gear_nlp_templates 的 parameters",
                                "additionalProperties": {"type": "number"}},
            "weights": {"type": "object", "description": "目标名 → 非负权重（加权标量化）；缺省全 1",
                        "additionalProperties": {"type": "number", "minimum": 0}},
            "x0": {"type": "object", "description": "连续变量起点（AI 提出的值，使结论为 pass_pending_human_confirmation）",
                   "additionalProperties": {"type": "number"}},
            "discrete_assignments": {"type": "array", "maxItems": MAX_DISCRETE_LIMIT,
                                     "description": "只在这些离散组合上求解；每项须给全部整数/选项变量且在声明域内",
                                     "items": {"type": "object", "additionalProperties": {"type": "number"}}},
            "relax_discrete": {"type": "boolean", "description": "整数与有序选项连续松弛 + 分支定界"},
            "max_discrete": {"type": "integer", "minimum": 1, "maximum": MAX_DISCRETE_LIMIT},
        },
    }


def list_templates():
    out = []
    for name, t in sorted(TEMPLATES.items()):
        p = t["factory"]()
        out.append({"template": name, "description": t["description"],
                    "parameters": {k: {"min": lo, "max": hi, "default": d} for k, (lo, hi, d) in t["params"].items()},
                    "variables": [{"name": v.name, "kind": v.kind, **({"lo": v.lo, "hi": v.hi} if hasattr(v, "lo") else
                                                                    {"values": list(v.values)})} for v in p.variables],
                    "objectives": [o.name for o in p.objective_specs]})
    return out


def _clean(o):
    """转成严格 JSON 可序列化结构：非有限数 → None，元组 → 列表，未知对象 → 字符串。"""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if o is None or isinstance(o, (bool, int, str)):
        return o
    return str(o)


def validate_params(tname, tp):
    """校验模板数值参数（白名单键 + 取值范围）；返回 (kw, errors)。越界即拒绝，不裁剪、不补默认。"""
    t = TEMPLATES[tname]
    errs, kw = [], {}
    tp = {} if tp is None else tp
    if not isinstance(tp, dict):
        return kw, [_err("template_params", "invalid_argument", "必须是对象")]
    for k, v in tp.items():
        if k not in t["params"]:
            errs.append(_err(k, "unknown_template_param", f"模板 {tname} 没有参数 {k!r}（可用 {sorted(t['params'])}）"))
        elif not _num(v) or not t["params"][k][0] <= v <= t["params"][k][1]:
            errs.append(_err(k, "out_of_domain", f"{k} 须为 [{t['params'][k][0]}, {t['params'][k][1]}] 内的有限数"))
        else:
            kw[k] = float(v)
    return kw, errs


def run(args):
    """校验并求解；返回 (结果字典)。任何不合格输入返回 blocked_invalid_inputs，不抛异常。"""
    if not isinstance(args, dict):
        return {"status": "blocked_invalid_inputs", "errors": [_err("arguments", "invalid_argument", "参数必须是对象")]}
    errs = [_err(k, "unknown_argument", f"optimize_nlp 不接受参数 {k!r}（不接受表达式、代码或求解器内部选项）")
            for k in sorted(set(args) - _ARG_KEYS)]
    tname = args.get("template")
    if not isinstance(tname, str) or tname not in TEMPLATES:
        errs.append(_err("template", "unknown_template", f"模板须是白名单之一 {sorted(TEMPLATES)}"))
        return {"status": "blocked_invalid_inputs", "errors": errs}
    t = TEMPLATES[tname]
    kw, perrs = validate_params(tname, args.get("template_params"))
    errs += perrs
    if errs:
        return {"status": "blocked_invalid_inputs", "errors": errs}
    problem = t["factory"](**kw)
    cont = {v.name: v for v in problem.variables if isinstance(v, Continuous)}
    disc = {v.name: v for v in problem.variables if not isinstance(v, Continuous)}
    objs = [o.name for o in problem.objective_specs]
    solver_kw, ai_values = {}, []

    w = args.get("weights")
    if w is not None:
        if not isinstance(w, dict) or not w or set(w) - set(objs) or not all(_num(v) and v >= 0 for v in w.values()) \
                or not any(v > 0 for v in w.values()):
            errs.append(_err("weights", "invalid_argument", f"权重键须是目标名 {objs} 的非空子集，值为非负有限数且至少一个为正"))
        else:
            solver_kw["weights"] = {k: float(v) for k, v in w.items()}
            ai_values.append("weights")
    x0 = args.get("x0")
    if x0 is not None:
        if not isinstance(x0, dict) or set(x0) - set(cont) or not all(
                _num(v) and cont[k].lo <= v <= cont[k].hi for k, v in x0.items()):
            errs.append(_err("x0", "invalid_argument", "x0 只能给连续变量 " + str({k: (v.lo, v.hi) for k, v in cont.items()}) + " 域内的有限数"))
        else:
            solver_kw["x0"] = {k: float(v) for k, v in x0.items()}
            ai_values.append("x0")
    da = args.get("discrete_assignments")
    if da is not None:
        ok = isinstance(da, list) and 0 < len(da) <= MAX_DISCRETE_LIMIT
        clean = []
        for a in (da if ok else []):
            good = isinstance(a, dict) and set(a) == set(disc)
            if good:
                for k, v in a.items():
                    d = disc[k]
                    if isinstance(d, Integer):
                        good &= _num(v) and float(v).is_integer() and d.lo <= v <= d.hi
                    else:
                        good &= _num(v) and v in d.values
            if not good:
                ok = False
                break
            clean.append({k: (int(v) if isinstance(disc[k], Integer) else v) for k, v in a.items()})
        if not ok:
            errs.append(_err("discrete_assignments", "invalid_argument",
                             "须为非空数组，每项恰含离散变量 " + str({k: (getattr(v, "values", None) or (v.lo, v.hi)) for k, v in disc.items()})
                             + " 且取值在声明域内"))
        else:
            solver_kw["discrete_assignments"] = clean
            ai_values.append("discrete_assignments")
    rd = args.get("relax_discrete", False)
    if not isinstance(rd, bool):
        errs.append(_err("relax_discrete", "invalid_argument", "必须是布尔值"))
    else:
        solver_kw["relax_discrete"] = rd
    md = args.get("max_discrete", 500)
    if isinstance(md, bool) or not isinstance(md, int) or not 1 <= md <= MAX_DISCRETE_LIMIT:
        errs.append(_err("max_discrete", "invalid_argument", f"必须是 1..{MAX_DISCRETE_LIMIT} 的整数"))
    else:
        solver_kw["max_discrete"] = md
    if errs:
        return {"status": "blocked_invalid_inputs", "errors": errs}

    try:
        r = solve_nlp(problem, **solver_kw)
    except ValueError as e:          # 如离散组合数超过 max_discrete
        return {"status": "blocked_invalid_inputs", "errors": [_err("discrete", "search_too_large", str(e))]}
    sol = r["solution"]
    solution = None if sol is None else {"x": sol.x, "objectives": sol.objectives, "constraints": sol.constraints,
                                         "feasible": sol.feasible, "feasibility_tol": sol.feasibility_tol, "info": sol.info}
    if sol is None:
        status = "no_feasible_found"
    else:
        status = "pass_pending_human_confirmation" if ai_values else "feasible_local_candidate"
    return _clean({"status": status, "template": tname, "template_params": {**{k: v[2] for k, v in t["params"].items()}, **kw},
                   "ai_proposed_inputs": ai_values, "solution": solution,
                   "scalarized_objective": r["scalarized_objective"], "claim": r["claim"],
                   "problem_ir_sha256": r["problem_ir_sha256"], "evaluations": r["evaluations"],
                   "feasible_count": r["feasible"],
                   "assurance": r["assurance"],
                   "note": "优化器给出的点只是一阶 KKT 局部候选，不是最终设计；assurance 四项（search_claim、optimality、solver_convergence、"
                           "evidence_level）分别给出，不合并为单一可信度。"})
