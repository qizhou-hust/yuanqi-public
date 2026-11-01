"""意图工具（M38）：requirement_compile 与 explain_infeasible。

原则（与 ai_tools 一致）：模型不产生数值。
  - requirement_compile 只做"结构化需求 → 已有问题模板参数 / 模型输入覆盖"的确定性映射；缺项一律返回
    needs_clarification 与具体追问，绝不填默认值（模板里的默认值不会被采用）；换算只走登记的推导式（DERIVATIONS），
    每个派生数都带 formula_id 与操作数，可被独立重算；需求里无处安放的项（寿命、材料、中心距上限等）列入
    unapplied，原样回显，不静默丢弃。所有由此编译出的数值一律标 agent_proposed，结论为 pass_pending_human_confirmation。
  - explain_infeasible 对"已编译模板 + 数值参数"在声明域内求值（公式图），找出最小违反量，列出每条约束单独放松时
    所需的放松量与代价（目标值变化），可选用 kernel 的局部 NLP 在放松后的点上确认并给出乘子。
    网格上的结论是"声明网格上的最小违反量"，不是不可行性证明（not_claimed 明示）。
"""
from __future__ import annotations

import math

from . import nlp_templates as NT

TEMPLATE = "stage_sizing"
CONSISTENCY_REL_TOL = 0.01      # 同时给出转矩与 功率+转速 时，两者换算相差超过此相对量即追问（一致性判据，不是设计默认值）

# 需求字段：名 → (类型说明, 单位说明, 下限开/闭)；全部为正有限数
FIELDS = {
    "power_kW": "输入功率，kW",
    "torque_Nm": "小轮名义转矩，N·m",
    "speed_rpm": "小轮转速，r/min",
    "ratio": "目标传动比 i = z2/z1（> 1）",
    "ratio_tol_percent": "传动比允许相对偏差，以百分数计（不要写成小数）；可为 0，表示不允许偏差",
    "life_h": "要求寿命，小时",
    "max_center_distance_mm": "中心距上限，mm",
    "max_face_width_mm": "齿宽上限，mm",
    "max_b_over_d1": "齿宽/小轮分度圆直径 上限（齿宽系数）",
    "min_S_H": "接触安全系数下限",
    "min_S_F": "弯曲安全系数下限",
}
NONNEG = ("ratio_tol_percent",)          # 允许为 0 的字段
SUPPORTED_GEAR_TYPES = ("spur", "直齿")


def input_schema():
    from .flagship_workflow import requirement_schema
    props = {k: ({"type": "number", "minimum": 0} if k in NONNEG else {"type": "number", "exclusiveMinimum": 0}) | {"description": d}
             for k, d in FIELDS.items()}
    props["material"] = {"type": "string", "description": "材料/热处理偏好或 σHlim、σFlim 的出处说明（文本，不被解释成数值）"}
    props["stages"] = {"type": "integer", "description": "级数；本模板只覆盖 1"}
    props["gear_type"] = {"type": "string", "description": "齿轮类型；本模板只覆盖直齿（spur / 直齿）"}
    return {"type": "object", "additionalProperties": False,
            "properties": {"requirement": {"type":"object","properties":props,"oneOf":[{"type": "object", "additionalProperties": False, "properties": props},requirement_schema()],
                                           "description": "结构化需求；Stage0 旗舰须显式 scope；缺项不补默认值"}},
            "required": ["requirement"]}


# ---------------------------------------------------------------- 登记的推导式（评测器按 formula_id 独立重算）
def _torque_from_power_speed(power_kW, speed_rpm):
    return power_kW * 1000.0 / (speed_rpm * 2.0 * math.pi / 60.0)


DERIVATIONS = {
    "torque_from_power_speed": {"expr": "T[N·m] = P[kW]·1000 / (n[r/min]·2π/60)", "unit": "N*m",
                                "fn": _torque_from_power_speed, "operands": ("power_kW", "speed_rpm")},
    "w_to_kw": {"expr": "P[kW] = P[W] / 1000", "unit": "kW", "fn": lambda power_W: power_W / 1000.0, "operands": ("power_W",)},
    "percent_to_fraction": {"expr": "x = p / 100", "unit": "1", "fn": lambda percent: percent / 100.0,
                            "operands": ("percent",)},
}


def _derive(fid, quantity, **operands):
    d = DERIVATIONS[fid]
    return {"quantity": quantity, "value": d["fn"](**operands), "unit": d["unit"], "formula_id": fid,
            "expr": d["expr"], "operands": dict(operands)}


def recompute(derivation):
    """按 formula_id 与 operands 独立重算一条推导；返回重算值（未知 formula_id 抛 KeyError）。"""
    d = DERIVATIONS[derivation["formula_id"]]
    return d["fn"](**derivation["operands"])


def _q(field, question, why):
    return {"field": field, "question": question, "why": why}


def _num_ok(v, k=None):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and (v >= 0 if k in NONNEG else v > 0)


def open_items(req):
    """需求里仍缺的或冲突的项：返回 (questions, notes, derivations)。questions 的 field 集合 = required_fields(req)。"""
    questions, notes, derivations = [], [], []
    have_torque = "torque_Nm" in req
    have_ps = "power_kW" in req and "speed_rpm" in req
    if "speed_rpm" not in req:
        questions.append(_q("speed_rpm", "小轮（输入轴）转速是多少 r/min？", "n_1 是模型输入，不能推测"))
    if not have_torque and "power_kW" not in req:
        questions.append(_q("torque_Nm", "请给出小轮名义转矩（N·m），或给出输入功率（kW）与转速。", "T_1 是模型输入，不能推测"))
    elif not have_torque and "speed_rpm" in req:
        derivations.append(_derive("torque_from_power_speed", "T_1", power_kW=req["power_kW"], speed_rpm=req["speed_rpm"]))
    if have_torque and have_ps:
        t_d = _derive("torque_from_power_speed", "T_1", power_kW=req["power_kW"], speed_rpm=req["speed_rpm"])
        if abs(t_d["value"] - req["torque_Nm"]) > CONSISTENCY_REL_TOL * req["torque_Nm"]:
            questions.append(_q("torque_Nm", "给出的转矩与 功率+转速 换算的转矩不一致，请确认以哪个为准（或更正其中一项）。",
                                "两个来源冲突时不择一"))
            notes.append({"conflict": "torque_vs_power_speed", "derivation": t_d, "given_torque_Nm": req["torque_Nm"]})
    for field, text, why in (
            ("ratio", "目标传动比 i 是多少？", "target_ratio 是模板参数，无默认"),
            ("ratio_tol_percent", "传动比允许的相对偏差是多少（百分数）？", "ratio_tol 是模板参数，不采用模板默认值"),
            ("max_b_over_d1", "齿宽/小轮分度圆直径（齿宽系数）上限是多少？", "max_b_over_d1 是模板参数，不采用模板默认值"),
            ("min_S_H", "接触安全系数下限是多少？", "S_Hmin 是模型限值，不采用基线值"),
            ("min_S_F", "弯曲安全系数下限是多少？", "S_Fmin 是模型限值，不采用基线值"),
            ("life_h", "要求寿命是多少小时（若以年计，请同时给出每天运行小时数与每年天数）？", "寿命决定 Z_NT/Y_NT，需要明确"),
            ("material", "材料与热处理是什么？σHlim、σFlim 取自哪个标准或试验证据？", "材料极限是模型输入，不能推测")):
        if field not in req:
            questions.append(_q(field, text, why))
    return questions, notes, derivations


def required_fields(req):
    """给定（已通过类型校验的）需求对象，必须追问的字段名（评测器用它核对追问完整性）。"""
    return [q["field"] for q in open_items(req)[0]]


def requirement_compile(args):
    """结构化需求 → stage_sizing 模板参数 + 模型输入覆盖（供 gear_preview_edit）。无默认值。"""
    if not isinstance(args, dict) or set(args) - {"requirement"}:
        return {"status": "blocked_invalid_inputs", "errors": [{"name": "arguments", "code": "invalid_argument",
                "message": "只接受参数 requirement（对象）"}]}
    req = args.get("requirement")
    if isinstance(req,dict) and req.get('scope')=='stage0':
        from .flagship_workflow import compile_requirement
        return compile_requirement(req)
    req = {} if req is None else req
    if not isinstance(req, dict):
        return {"status": "blocked_invalid_inputs", "errors": [{"name": "requirement", "code": "invalid_argument",
                "message": "requirement 必须是对象"}]}
    errors = []
    for k, v in req.items():
        if k in FIELDS:
            if not _num_ok(v, k):
                errors.append({"name": k, "code": "invalid_argument", "message": f"{k} 须为{'非负' if k in NONNEG else '正'}的有限数（{FIELDS[k]}）"})
        elif k == "material":
            if not isinstance(v, str) or not v.strip():
                errors.append({"name": k, "code": "invalid_argument", "message": "material 须为非空字符串"})
        elif k == "stages":
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                errors.append({"name": k, "code": "invalid_argument", "message": "stages 须为正整数"})
        elif k == "gear_type":
            if not isinstance(v, str) or not v.strip():
                errors.append({"name": k, "code": "invalid_argument", "message": "gear_type 须为非空字符串"})
        else:
            errors.append({"name": k, "code": "unknown_argument", "message": f"未知需求字段 {k!r}（可用 {sorted(FIELDS) + ['material', 'stages', 'gear_type']}）"})
    if errors:
        return {"status": "blocked_invalid_inputs", "errors": errors, "requirement": req}

    # 范围外：本模板只覆盖单级直齿，不勉强编译
    scope = []
    if req.get("stages", 1) != 1:
        scope.append({"name": "stages", "code": "unsupported_scope", "message": f"模板 {TEMPLATE} 只覆盖单级传动"})
    if "gear_type" in req and req["gear_type"].strip().lower() not in SUPPORTED_GEAR_TYPES:
        scope.append({"name": "gear_type", "code": "unsupported_scope", "message": f"模板 {TEMPLATE} 只覆盖直齿（spur / 直齿）"})
    if scope:
        return {"status": "blocked_unsupported_scope", "errors": scope, "requirement": req,
                "available_templates": sorted(NT.TEMPLATES)}

    questions, notes, derivations = open_items(req)
    have_torque = "torque_Nm" in req
    derivations = [d for d in derivations]
    # 模板定义域
    dom = []
    tp = {}
    if "ratio" in req:
        tp["target_ratio"] = req["ratio"]
    if "ratio_tol_percent" in req:
        tp["ratio_tol"] = _derive("percent_to_fraction", "ratio_tol", percent=req["ratio_tol_percent"])["value"]
    if "max_b_over_d1" in req:
        tp["max_b_over_d1"] = req["max_b_over_d1"]
    kw, perrs = NT.validate_params(TEMPLATE, tp)
    for e in perrs:
        dom.append({**e, "message": e["message"] + "；超出模板范围，不裁剪也不替换，请改需求或另选模板"})
    if dom:
        return {"status": "blocked_invalid_inputs", "errors": dom, "questions": questions, "requirement": req}

    if questions:
        return {"status": "needs_clarification", "questions": questions, "requirement": req,
                "understood": {k: v for k, v in req.items()}, "notes": notes,
                "message": "缺项或冲突项见 questions；未使用任何默认值，也未编译。"}

    # 编译
    ders = []
    for f, key in (("ratio_tol_percent", "ratio_tol"),):
        ders.append(_derive("percent_to_fraction", key, percent=req[f]))
    if not have_torque:
        ders.append(_derive("torque_from_power_speed", "T_1", power_kW=req["power_kW"], speed_rpm=req["speed_rpm"]))
        t_val = ders[-1]["value"]
    else:
        t_val = req["torque_Nm"]
    prov = "agent_proposed"
    edit_params = {
        "T_1": {"value": t_val, "unit": "N*m", "provenance": prov},
        "n_1": {"value": req["speed_rpm"], "unit": "rpm", "provenance": prov},
        "S_Hmin": {"value": req["min_S_H"], "unit": "1", "provenance": prov},
        "S_Fmin": {"value": req["min_S_F"], "unit": "1", "provenance": prov},
    }
    # 用真实模型校验输入域（lazy import 避免循环）
    from . import ai_tools
    spec = {"baseline": "C001_G1", "selectors": {}, "editions": {}, "params": edit_params}
    _, _, merrs = ai_tools._model(spec)
    if merrs:
        return {"status": "blocked_invalid_inputs", "errors": merrs, "requirement": req}
    unapplied = [
        {"field": "life_h", "value": req["life_h"], "reason": "寿命经 Z_NT/Y_NT 进入模型，这两个系数是证据输入，本工具不推算；请按 ISO 6336-2/3 的寿命曲线给出证据值后用 gear_preview_edit 写入"},
        {"field": "material", "value": req["material"], "reason": "材料极限 σHlim/σFlim 是证据输入，本工具不把材料名映射成数值；基线保留 C001 的值（assumption）"},
    ]
    post = []
    for f, qty in (("max_center_distance_mm", "a_w"), ("max_face_width_mm", "b")):
        if f in req:
            post.append({"field": f, "limit": req[f], "check_quantity": qty, "sense": "<=",
                         "how": f"优化后用 gear_explain({qty}) 取值与该上限比较；模板 {TEMPLATE} 的约束集不含此项"})
    return {
        "status": "pass_pending_human_confirmation",
        "requirement": req,
        "agent_proposed_inputs": sorted(list(edit_params) + list(kw)),
        "template_call": {"tool": "optimize_nlp", "arguments": {"template": TEMPLATE, "template_params": kw}},
        "rating_edit": {"tool": "gear_preview_edit", "arguments": {"edit": {"params": edit_params}}},
        "derivations": ders,
        "post_checks": post,
        "unapplied": unapplied,
        "applicability": ("optimize_nlp 的 stage_sizing 模板内部固定 C001 G1 载荷工况，只接收 template_params；"
                          "rating_edit 中的转矩/转速/安全系数下限只作用于 gear_rate 等模型类工具，不进入该模板的求解。"),
        "scope_assumptions": ["转速 speed_rpm 按小轮（输入轴）转速理解", f"模板 {TEMPLATE} 覆盖单级直齿"],
        "message": "以上均为 agent_proposed 数值，须由人工确认后才能作为设计依据；本工具未做任何校核计算。",
    }


# ---------------------------------------------------------------- explain_infeasible
def explain_input_schema():
    return {"type": "object", "additionalProperties": False, "required": ["template"],
            "properties": {
                "template": {"type": "string", "enum": sorted(NT.TEMPLATES), "description": "已编译的问题模板名"},
                "template_params": {"type": "object", "additionalProperties": {"type": "number"},
                                    "description": "模板数值参数（缺省用模板声明的默认，并在结果中回显）"},
                "confirm_with_nlp": {"type": "boolean",
                                     "description": "默认 true：在最小放松点上用 kernel 局部 NLP 确认并返回乘子；false 只做声明网格分析"}}}


def _grid_points(problem, n_cont=5):
    import itertools
    axes = [v.grid(n_cont) if v.kind == "continuous" else v.grid(0) for v in problem.variables]
    names = [v.name for v in problem.variables]
    for p in itertools.product(*axes):
        yield dict(zip(names, p))


def _rating_limit(cid):
    from ..gear.rating import c001_g1
    m = c001_g1()
    return {"pitting.pinion": "S_Hmin", "pitting.wheel": "S_Hmin", "bending.pinion": "S_Fmin",
            "bending.wheel": "S_Fmin", "geometry.contact_ratio": "eps_alpha_min"}.get(cid), m


def explain_infeasible(args):
    if not isinstance(args, dict):
        return {"status": "blocked_invalid_inputs", "errors": [{"name": "arguments", "code": "invalid_argument", "message": "参数必须是对象"}]}
    errs = [{"name": k, "code": "unknown_argument", "message": f"不接受参数 {k!r}"}
            for k in sorted(set(args) - {"template", "template_params", "confirm_with_nlp"})]
    tname = args.get("template")
    if not isinstance(tname, str) or tname not in NT.TEMPLATES:
        errs.append({"name": "template", "code": "unknown_template", "message": f"模板须是白名单之一 {sorted(NT.TEMPLATES)}"})
        return {"status": "blocked_invalid_inputs", "errors": errs}
    kw, perrs = NT.validate_params(tname, args.get("template_params"))
    errs += perrs
    cn = args.get("confirm_with_nlp", True)
    if not isinstance(cn, bool):
        errs.append({"name": "confirm_with_nlp", "code": "invalid_argument", "message": "必须是布尔值"})
    if errs:
        return {"status": "blocked_invalid_inputs", "errors": errs}
    t = NT.TEMPLATES[tname]
    problem = t["factory"](**kw)
    params_used = {**{k: v[2] for k, v in t["params"].items()}, **kw}
    ai_given = sorted(kw)

    # 声明网格上逐点求值；记录每条约束的 g（≤0 满足），ratio_error / b_over_d1 另存"与参数无关的原始量"
    pts = []
    for x in _grid_points(problem):
        o = problem.evaluate(x)
        g = o["constraints"]
        if g["domain"] > 0:
            continue                                  # 越域点不参与（硬约束，不可放松）
        pts.append({"x": x, "g": g, "obj": o["objectives"], "info": o["info"],
                    "ratio_dev": g["ratio_error"] + params_used["ratio_tol"],
                    "bd1": g["b_over_d1"] + params_used["max_b_over_d1"]})
    cids = [c for c in pts[0]["g"] if c != "domain"] if pts else []
    feas = [p for p in pts if all(p["g"][c] <= 0 for c in cids)]
    base = {"template": tname, "template_params": params_used, "agent_proposed_inputs": ai_given,
            "grid_points_evaluated": len(pts), "evaluation_scope": "declared_domain_grid",
            "not_claimed": ["proven_infeasibility", "global_optimality"],
            "constants_source": "ratio_tol / max_b_over_d1 / 约束值全部来自公式图求值，不含模型提出的数"}
    conclusion = "pass_pending_human_confirmation" if ai_given else "analysis_only"
    if feas:
        best = min(feas, key=lambda p: sum(p["obj"].values()))
        return {**base, "status": conclusion, "diagnosis": "feasible_point_exists_on_grid",
                "example_point": {"x": best["x"], "objectives": best["obj"]},
                "message": "声明网格上已有可行点，无需解释不可行；可直接 optimize_nlp。"}

    def viol(p):
        return max(p["g"][c] for c in cids)
    least = min(pts, key=viol)
    least_rows = [{"constraint": c, "g": least["g"][c], "violated": least["g"][c] > 0} for c in cids]
    relax = []
    lim_cache = {}
    for c in cids:
        others = [p for p in pts if all(p["g"][o] <= 0 for o in cids if o != c)]
        if not others:
            relax.append({"constraint": c, "single_relaxation_sufficient": False,
                          "message": "仅放松这一条仍无可行点（其余约束在声明域内无法同时满足）"})
            continue
        p = min(others, key=lambda q: q["g"][c])
        need = p["g"][c]
        row = {"constraint": c, "single_relaxation_sufficient": True, "min_violation_g": max(need, 0.0),
               "point": {"x": p["x"], "objectives": p["obj"]}, "cost_objectives_at_point": p["obj"]}
        if need <= 0:
            row["note"] = "该约束在此点已满足（不是瓶颈）"
        elif c == "ratio_error":
            req_tol = p["ratio_dev"]
            row.update(parameter="ratio_tol", required_value=req_tol, current_value=params_used["ratio_tol"],
                       within_template_range=req_tol <= t["params"]["ratio_tol"][1], relaxable_by="template_param")
        elif c == "b_over_d1":
            req_m = p["bd1"]
            row.update(parameter="max_b_over_d1", required_value=req_m, current_value=params_used["max_b_over_d1"],
                       within_template_range=req_m <= t["params"]["max_b_over_d1"][1], relaxable_by="template_param")
        else:
            lname, m = _rating_limit(c)
            if lname:
                cur = m.inputs[lname].value
                row.update(parameter=lname, current_value=cur, required_value=cur - need, relaxable_by="model_limit",
                           note="该限值是模型输入而非模板参数；放松它即降低校核要求，须由人工决定并经 gear_preview_edit 写入")
        relax.append(row)

    out = {**base, "status": conclusion, "diagnosis": "infeasible_on_declared_grid",
           "least_violation_point": {"x": least["x"], "objectives": least["obj"], "max_g": viol(least), "constraints": least_rows,
                                     "note": "最大约束值 g 最小的网格点（g>0 表示违反；各约束量纲不同，仅作定位，不作量纲统一比较）"},
           "relaxations": relax}
    # 联合放松：满足全部模型校核（不可由模板参数放松的约束）的点里，ratio_tol 与 max_b_over_d1 所需放松量的非支配集
    tp_ids = {"ratio_error", "b_over_d1"}
    hard = [p for p in pts if all(p["g"][c] <= 0 for c in cids if c not in tp_ids)]
    cand = {}
    for p in hard:
        key = (max(p["ratio_dev"], params_used["ratio_tol"]), max(p["bd1"], params_used["max_b_over_d1"]))
        if key not in cand or sum(p["obj"].values()) < sum(cand[key]["obj"].values()):
            cand[key] = p
    front = [k for k in cand if not any(o != k and o[0] <= k[0] and o[1] <= k[1] for o in cand)]
    rng_tol = t["params"]["ratio_tol"][1] - t["params"]["ratio_tol"][0]
    rng_bd = t["params"]["max_b_over_d1"][1] - t["params"]["max_b_over_d1"][0]
    front.sort(key=lambda k: (k[0] - params_used["ratio_tol"]) / rng_tol + (k[1] - params_used["max_b_over_d1"]) / rng_bd)
    joint = [{"ratio_tol": k[0], "max_b_over_d1": k[1],
              "within_template_range": k[0] <= t["params"]["ratio_tol"][1] and k[1] <= t["params"]["max_b_over_d1"][1],
              "point": {"x": cand[k]["x"], "objectives": cand[k]["obj"]}} for k in front[:5]]
    out["joint_template_param_relaxations"] = joint
    out["joint_note"] = "同时放松 ratio_tol 与 max_b_over_d1 的非支配组合（按相对于模板范围宽度的放松量之和排序，最多 5 个）；模型校核限值不动"
    # kernel NLP 确认：在放松后的参数上对该点的离散组合做局部 NLP，返回乘子
    if cn:
        conf = []
        todo = [({"ratio_tol": j["ratio_tol"], "max_b_over_d1": j["max_b_over_d1"]}, j["point"]["x"], "joint") for j in joint[:3]
                if j["within_template_range"]]
        todo += [({r["parameter"]: r["required_value"]}, r["point"]["x"], r["constraint"]) for r in relax
                 if r.get("relaxable_by") == "template_param" and r.get("within_template_range")]
        for rp, x, label in todo:
            from ..kernel.optimize import solve_nlp
            pr = t["factory"](**{**params_used, **rp})
            try:
                res = solve_nlp(pr, discrete_assignments=[{k: v for k, v in x.items() if k in ("z1", "m_n")}], second_order=False)
            except Exception as e:           # 确认失败不影响网格结论
                conf.append({"for": label, "relaxed": rp, "status": "nlp_error", "message": str(e)})
                continue
            sol = res["solution"]
            opt = res["assurance"]["optimality"]
            conf.append({"for": label, "relaxed": rp, "nlp_found_feasible": sol is not None,
                         "solution": None if sol is None else {"x": sol.x, "objectives": sol.objectives},
                         "multipliers": (opt[0].get("multipliers") if opt else None),
                         "multiplier_convention": (opt[0].get("multiplier_convention") if opt else None),
                         "claim": res["claim"]})
        out["nlp_confirmation"] = conf
    out["message"] = ("在声明网格上找不到可行点。relaxations 给出每条约束单独放松所需的量与代价；"
                      "不可行性结论只对声明网格成立，不是证明。")
    return out
