"""MCP 受控写路径 optimize_and_commit（v0.15 OPT3）：白名单声明 → M34 闭环（剪枝格搜索 + NLP → 回圆 → 写回候选 → 独立复核）
→ 统一报告；只有显式 confirm=true 才写入 design_store（父哈希链 + 来源链校验，见 design_store.commit_optimization）。

默认 dry-run：返回候选文档的 sha256、统一报告、提交预检（preflight）结果，不改任何状态。
confirm=true：设计链为空 → 先导入父文档（source_import），再提交优化修订；设计链头不是该父文档 → 拒绝（断链）。
可选 candidate_sha256：确认时要求重算出的候选与 dry-run 时一致（防止两次调用之间代码/数据漂移）。
只接受白名单声明 id、设计名、confirm、candidate_sha256；不接受表达式、文档内容、路径或求解器选项。
求解结果按（声明 sha256、父文档 sha256、求解器指纹）在进程内缓存：确认调用不重复求解（求解是确定性的）。

注册：默认不出现在 tools/list（现有测试锁定"唯一写工具 = gear_commit"）；服务器以环境变量 GEARBASE_ENABLE_OPT_COMMIT=1
启用后列出。call() 分发不受此开关影响（由 confirm=true 守门写入）。
"""
from __future__ import annotations

import os
import re

DECLARED = {
    "K01-spur-recompute-local": "K01-spur.factors",
    "K01-spur-recompute-local-kxauto": "K01-spur.factors",
    "K02-helical-min-volume-recompute": "K02-helical.factors",
    "K04-EV-stage1-min-volume-recompute": "K04-EV-stage1.factors",
}
ENABLE_ENV = "GEARBASE_ENABLE_OPT_COMMIT"
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_CACHE = {}


def input_schema():
    return {"type": "object", "additionalProperties": False, "required": ["declaration", "design"],
            "properties": {"declaration": {"type": "string", "enum": sorted(DECLARED),
                                           "description": "白名单声明 id（data/optimize/<id>.decl.json，须显式给出 tip_shortening）"},
                           "design": {"type": "string", "pattern": "^[A-Za-z0-9_.-]{1,64}$",
                                      "description": "design_store 中的设计名（链：父文档导入 → 优化修订…）"},
                           "confirm": {"type": "boolean", "description": "true 才写入；缺省/false = dry-run（不改状态）"},
                           "candidate_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$",
                                                "description": "可选：dry-run 返回的候选文档 sha256，确认时必须一致"}}}


TOOL = {"name": "optimize_and_commit",
        "description": "受控写路径：对白名单声明运行优化闭环并给出统一报告（最优点、活跃集、KKT/收敛、证据、hold 清单、KISSsoft 复核请求）。"
                       "默认 dry-run 不写；confirm=true 时把写回修订提交到 design_store（父哈希链、声明 sha256、求解器指纹逐项校验，"
                       "断链/伪造即拒绝）。只接受白名单声明 id。",
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        "inputSchema": input_schema()}


def listed():
    """服务器 tools/list 是否列出本工具（显式开关，默认不列）。"""
    return os.environ.get(ENABLE_ENV) == "1"


def _blocked(errs):
    return {"status": "blocked_invalid_inputs", "persisted": False, "errors": errs}


def _solve(decl_id):
    from ..gear import factor_recompute as FR
    from ..gear import math_source as MS
    from ..gear import opt_report as OR
    from ..gear import source_optimize as SO
    from ..kernel import declared as DC
    from ..kernel import gridprune as GP
    doc = FR.load_doc(DECLARED[decl_id])
    decl = SO.load_declaration(decl_id)
    SO.require_tip_shortening(decl)
    key = (DC.declaration_sha256(decl), MS.source_sha256(doc), GP.solver_fingerprint()["kernel_sources_sha256"])
    cached = key in _CACHE
    if not cached:
        rep = SO.optimize_source(doc, decl)
        _CACHE[key] = (rep, OR.unified_report(rep, decl, doc))
    rep, ur = _CACHE[key]
    return doc, decl, rep, ur, cached


def run(args, store, lock=None):
    from ..gear import source_optimize as SO
    from ..tools import design_store as DS
    if not isinstance(args, dict):
        return _blocked([{"name": "arguments", "code": "invalid_argument", "message": "参数必须是对象"}])
    allowed = {"declaration", "design", "confirm", "candidate_sha256"}
    errs = [{"name": k, "code": "unknown_argument", "message": f"不接受参数 {k!r}"} for k in sorted(set(args) - allowed)]
    d, name, confirm = args.get("declaration"), args.get("design"), args.get("confirm", False)
    if d not in DECLARED:
        errs.append({"name": "declaration", "code": "unknown_declaration", "message": f"须是白名单之一 {sorted(DECLARED)}"})
    if not isinstance(name, str) or not _NAME.match(name) or set(name) == {"."}:
        errs.append({"name": "design", "code": "invalid_argument", "message": "须给出合法设计名"})
    if not isinstance(confirm, bool):
        errs.append({"name": "confirm", "code": "invalid_argument", "message": "confirm 须为布尔值（true 才写入）"})
    cand = args.get("candidate_sha256")
    if cand is not None and not (isinstance(cand, str) and re.fullmatch(r"[0-9a-f]{64}", cand)):
        errs.append({"name": "candidate_sha256", "code": "invalid_argument", "message": "须为 64 位小写十六进制"})
    if errs:
        return _blocked(errs)
    try:
        doc, decl, rep, ur, cached = _solve(d)
    except SO.OptimizeBlocked as e:
        return {"status": "blocked_invalid_declaration", "persisted": False, "errors": e.errors}
    base = {"declaration": d, "design": name, "report": ur, "candidate_sha256": rep.get("new_sha256"),
            "solver_cached": cached}
    if rep.get("status") != "written_and_confirmed":
        return {**base, "status": "not_committable", "persisted": False,
                "reason": f"优化闭环状态 {rep.get('status')}：只有独立复核通过的候选才能提交"}
    prov = SO.provenance(rep, decl)
    new = rep["new_document"]

    def preflight(head):
        if head is None:
            return []
        if "source" not in head:
            return [{"code": "design_not_source_chain", "message": f"设计 {name} 的链头不是真源文档记录（gear_commit 参数链）"}]
        return DS.check_optimization_revision(head, new, decl, prov)

    if cand is not None and cand != rep.get("new_sha256"):
        return {**base, "status": "rejected_candidate_mismatch", "persisted": False,
                "errors": [{"code": "candidate_mismatch", "message": "重算候选与给定 candidate_sha256 不一致"}]}
    if not confirm:
        head = store.head(name)
        return {**base, "status": "dry_run", "persisted": False, "would_import_parent": head is None,
                "preflight_errors": preflight(head),
                "next": "确认无误后以 confirm=true（可附 candidate_sha256）再次调用才写入"}

    def commit():
        head = store.head(name)
        pf = preflight(head)
        if pf:
            return {**base, "status": "rejected_provenance", "persisted": False, "errors": pf}
        imported = None
        try:
            if head is None:
                imported = DS.commit_source(store, name, doc, f"optimize_and_commit：导入父文档 {doc['id']}")["version"]
            rec = DS.commit_optimization(store, name, new, decl, prov)
        except DS.ProvenanceError as e:
            return {**base, "status": "rejected_provenance", "persisted": imported is not None, "errors": e.errors}
        except DS.VersionConflict as e:
            return {**base, "status": "rejected_version_conflict", "persisted": imported is not None,
                    "errors": [{"code": "version_conflict", "message": str(e)}]}
        return {**base, "status": "committed", "persisted": True, "imported_parent_version": imported,
                "version": rec["version"], "history": DS.revision_history(store, name)}

    if lock is None:
        return commit()
    with lock:
        return commit()
