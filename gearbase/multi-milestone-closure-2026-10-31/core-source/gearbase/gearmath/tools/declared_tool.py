"""MCP 工具 optimize_declared（只读）：对白名单内的声明式问题（data/optimize/*.decl.json + 真源 v2 文档）
给出问题描述（变量/约束/hold 清单与理由/系数逐项重算或保持）或运行 M34 闭环（剪枝格搜索 + NLP → 回写候选 → 独立复核）。

只接受白名单中的声明 id 与动作名；不接受表达式、文档内容、路径或求解器选项。运行结果中的新文档只作为返回值
（候选修订，带父文档 sha256 / 声明 sha256 / 求解器指纹），本工具不写盘、不进 design_store（写入仍须 gear_commit 路径，TODO）。
"""
from __future__ import annotations

import math

# 声明 id -> (父文档加载方式, 文档 id)
DECLARED = {
    "C001-G1-min-volume": ("m31", "C001"),
    "K01-spur-min-volume": ("kisssoft", "K01-spur"),
    "C001-G1-min-volume-recompute": ("factors", "C001.factors"),
    "K01-spur-min-volume-recompute": ("factors", "K01-spur.factors"),
}
ACTIONS = ("describe", "run")


def input_schema():
    return {"type": "object", "additionalProperties": False, "required": ["declaration", "action"],
            "properties": {"declaration": {"type": "string", "enum": sorted(DECLARED),
                                           "description": "白名单声明 id（data/optimize/<id>.decl.json）"},
                           "action": {"type": "string", "enum": list(ACTIONS),
                                      "description": "describe：只读描述（含 hold 清单与理由、系数重算状态）；run：运行闭环（K01 约 2 分钟）"}}}


TOOL = {"name": "optimize_declared",
        "description": "声明式优化问题（只读）：describe 返回变量/目标/约束、证据保持清单与理由、各系数是随几何重算还是保持；"
                       "run 运行剪枝格搜索 + 精确梯度 NLP，回圆后生成候选新文档并从文档独立复核。只接受白名单声明 id；"
                       "结果中 held_not_updated 列出未随几何更新的量，结论只在这些量不变的前提下成立。",
        "annotations": {"readOnlyHint": True}, "inputSchema": input_schema()}


def _load(decl_id):
    from ..gear import factor_recompute as FR
    from ..gear import math_source as MS
    from ..gear import math_source_kisssoft as MK
    from ..gear import source_optimize as SO
    kind, doc_id = DECLARED[decl_id]
    doc = MS.load_file() if kind == "m31" else MK.load_doc(doc_id) if kind == "kisssoft" else FR.load_doc(doc_id)
    return doc, SO.load_declaration(decl_id)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if o is None or isinstance(o, (bool, int, str)):
        return o
    return str(o)


def run(args):
    from ..gear import math_source as MS
    from ..gear import source_optimize as SO
    if not isinstance(args, dict):
        return {"status": "blocked_invalid_inputs", "errors": [{"name": "arguments", "code": "invalid_argument", "message": "参数必须是对象"}]}
    errs = [{"name": k, "code": "unknown_argument", "message": f"不接受参数 {k!r}"} for k in sorted(set(args) - {"declaration", "action"})]
    d, a = args.get("declaration"), args.get("action")
    if d not in DECLARED:
        errs.append({"name": "declaration", "code": "unknown_declaration", "message": f"须是白名单之一 {sorted(DECLARED)}"})
    if a not in ACTIONS:
        errs.append({"name": "action", "code": "invalid_argument", "message": f"action 须是 {list(ACTIONS)}"})
    if errs:
        return {"status": "blocked_invalid_inputs", "errors": errs}
    doc, decl = _load(d)
    if a == "describe":
        try:
            ev = SO.SourceEvaluator(doc, decl)
        except SO.OptimizeBlocked as e:
            return {"status": "blocked_invalid_declaration", "errors": e.errors}
        from ..gear import factor_recompute as FR
        st = FR.coefficient_status(ev.model, decl)
        return _clean({"status": "ok", "declaration": decl, "parent_id": doc["id"], "parent_sha256": MS.source_sha256(doc),
                       "coefficient_status": st, "held_not_updated": [r for r in st if r["status"] == "held"]})
    rep = SO.optimize_source(doc, decl)
    new = rep.pop("new_document", None)
    rep["candidate_document"] = new
    rep["persisted"] = False
    rep["conclusion"] = ("candidate_pending_human_confirmation" if rep.get("status") == "written_and_confirmed" else rep.get("status"))
    return _clean(rep)
