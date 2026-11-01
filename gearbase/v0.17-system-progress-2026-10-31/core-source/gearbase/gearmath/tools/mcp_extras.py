"""MCP Resources 与 Prompts（M38）：resources/list、resources/read、resources/templates/list、prompts/list、prompts/get。

资源全部只读，内容来自包内文件或代码常量（公式注册表、案例对拍摘要、证据等级说明、AI 使用规则、问题模板）；
URI 方案为 gearbase://。提示词只给"工作流指令"，不含任何数值；指令要求模型：不凭空给数、缺项先追问、
模型提出的数一律标 agent_proposed 并等待人工确认。
"""
from __future__ import annotations

import json
import pathlib

from . import nlp_templates as NT

_DATA = pathlib.Path(__file__).resolve().parents[2] / "data" / "registry"

EVIDENCE_LEVELS_MD = """# 证据等级说明（E0–E6）

| 等级 | 含义 |
|---|---|
| unassessed | 没有任何通过的对拍用到该公式；比 E0 更弱，不当作"已验证到 E0" |
| E0 | 未验证草稿；agent_proposed 与 assumption 输入的上限 |
| E1 | 自洽；derived（模型外推导）输入的上限 |
| E2 | 独立实现交叉（如 C001 收据 vs python-gearbox）；evidence 输入的上限 |
| E3 | 公开出版算例复现（至少一条带 source 的测试向量） |
| E4 | 标准配套算例复现（ISO/TR 6336-30 例 1–8 逐行通过） |
| E5 | 商业软件同输入逐字段一致（KISSsoft K01–K05） |
| E6 | 实测或台架 |

- 一个量的有效等级 = 依赖链（自身公式 + 全部上游公式 + 全部上游输入）上最弱的一环；`gear_explain` 的 `evidence` 字段给出等级与 `weakened_by`。
- 注册表里 `evidence_level` 为 null = 未评估；`source_check` 为 null = 未核对原文。
- 本说明只复述规则，等级本身由注册表与测试推导，不手填。
"""

AI_RULES_MD = """# AI 使用规则

1. 模型不产生数值。所有数值来自公式图、注册表、用户或证据；模型自己提出的数必须声明 provenance = agent_proposed。
2. 依赖 agent_proposed 输入的校核，结论最高到 pass_pending_human_confirmation，不会显示为 pass。
3. 需求缺项时先追问（requirement_compile 返回 needs_clarification），不使用默认值。
4. 写操作两段式：gear_preview_edit 取得 preview_token，gear_commit 带同一份 edit 与 token；基线已变则被拒绝。
5. 优化器的结果只是一阶 KKT 局部候选；"网格上无可行点"不等于"证明不可行"。
6. 输出里出现的每个数字都应能追溯到：用户输入、公式链、或工具公开的常量（如模板参数范围）。
"""


def _read(path):
    return path.read_text(encoding="utf-8")


def _cases_summary():
    d = json.loads(_read(_DATA / "cases-v1.json"))
    rows = [{"case_id": c["case_id"], "benchmark": c.get("benchmark")} for c in d["cases"]]
    return json.dumps({"schema": d["schema"], "count": d["count"], "note": d["note"], "cases": rows},
                      ensure_ascii=False, indent=1)


# uri → (name, title, description, mimeType, loader)
_RES = {
    "gearbase://registry/formulas": ("formulas-v1", "公式注册表", "全部公式记录（id、output、clause、edition、method、evidence_level、test_vectors）与 external_slots",
                                     "application/json", lambda: _read(_DATA / "formulas-v1.json")),
    "gearbase://registry/cases": ("cases-v1-summary", "案例对拍摘要", "对拍案例清单（case_id、对拍种类、等级、通过行数）；完整行级数据见包内 data/registry/cases-v1.json",
                                  "application/json", _cases_summary),
    "gearbase://docs/evidence-levels": ("evidence-levels", "证据等级说明", "E0–E6 与来源类别上限、有效等级规则", "text/markdown",
                                        lambda: EVIDENCE_LEVELS_MD),
    "gearbase://docs/ai-rules": ("ai-rules", "AI 使用规则", "agent_proposed、两段式提交、追问与局部最优声明规则", "text/markdown",
                                 lambda: AI_RULES_MD),
    "gearbase://nlp/templates": ("nlp-templates", "问题模板", "optimize_nlp / explain_infeasible 可用的已编译问题模板、参数范围与变量域",
                                 "application/json", lambda: json.dumps(NT.list_templates(), ensure_ascii=False, indent=1)),
}


def resources_list():
    return {"resources": [{"uri": u, "name": n, "title": t, "description": d, "mimeType": m}
                          for u, (n, t, d, m, _) in _RES.items()]}


def resources_templates_list():
    return {"resourceTemplates": []}


class McpError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def resources_read(params):
    uri = (params or {}).get("uri")
    if not isinstance(uri, str):
        raise McpError(-32602, "resources/read 需要字符串参数 uri")
    if uri not in _RES:
        raise McpError(-32002, f"资源不存在：{uri}")
    _, _, _, mime, loader = _RES[uri]
    return {"contents": [{"uri": uri, "mimeType": mime, "text": loader()}]}


# ---------------------------------------------------------------- prompts
_RULE = ("规则：不得自己给出任何数值；缺项先向用户追问；你提出的任何数只能标 provenance=agent_proposed，"
         "结论最多是 pass_pending_human_confirmation；回答里出现的数字必须来自用户、工具返回值或公式链。")

_PROMPTS = {
    "design_single_stage_reducer": {
        "description": "按需求设计一级减速器：先编译需求，再优化，再校核并解释",
        "arguments": [{"name": "requirement_text", "description": "用户的中文需求原文", "required": True}],
        "build": lambda a: (
            f"用户需求：\n{a['requirement_text']}\n\n"
            "请按顺序执行：\n"
            "1. 把需求整理成 requirement_compile 的结构化字段（只填用户明确说出的值，不要推测）并调用它。\n"
            "2. 若返回 needs_clarification，把 questions 逐条转述给用户并停止，等待回答；不要自行补值。\n"
            "3. 若返回 pass_pending_human_confirmation，用其 template_call 调用 optimize_nlp；若无可行解，调用 explain_infeasible 并把各放松选项及代价如实告诉用户，由用户决定。\n"
            "4. 用 rating_edit 经 gear_preview_edit 预览，再对候选调用 gear_rate 校核，用 gear_explain 说明关键安全系数。\n"
            "5. 最后列出 unapplied 与 post_checks 中尚未处理的项，并说明所有数值均待人工确认。\n" + _RULE)},
    "explain_safety_factor_chain": {
        "description": "解释某个安全系数（或任一量）的公式链、条款与证据等级",
        "arguments": [{"name": "quantity", "description": "量名，如 S_H_1、S_F_1", "required": True},
                      {"name": "design", "description": "命名设计（可选，缺省用基线）", "required": False}],
        "build": lambda a: (
            f"请解释量 {a['quantity']} 的公式链。\n"
            "1. 调用 gear_explain（quantity 如上" + (f"，design={a['design']}" if a.get("design") else "") + "），逐步复述每步公式、条款、数值与来源。\n"
            "2. 报告 evidence 字段的有效等级与 weakened_by，说明最弱环节是公式还是输入。\n"
            "3. 如需说明\"改哪个参数最有效\"，调用 gear_sensitivity 并引用其弹性值，不要自行估算。\n" + _RULE)},
    "explain_infeasible_design": {
        "description": "需求不可行时解释违反了哪些约束、可放松哪些约束及代价",
        "arguments": [{"name": "template_params_json", "description": "模板参数的 JSON 对象文本（来自 requirement_compile 的 template_call）", "required": True}],
        "build": lambda a: (
            f"模板参数：{a['template_params_json']}\n"
            "1. 调用 explain_infeasible（template=stage_sizing，template_params 取自上面的 JSON，原样传入）。\n"
            "2. 转述 diagnosis、least_violation_point 中被违反的约束与违反量。\n"
            "3. 逐条转述 relaxations 与 joint_template_param_relaxations：放松哪个参数、放松到多少、目标值变化（代价）。\n"
            "4. 明确说明这是声明网格上的结论，不是不可行性证明；是否放松由用户决定，不要替用户选。\n" + _RULE)},
    "audit_agent_proposed_inputs": {
        "description": "审查一次设计中哪些输入是 agent_proposed，并列出待人工确认清单",
        "arguments": [{"name": "design", "description": "命名设计（可选）", "required": False}],
        "build": lambda a: (
            "1. 调用 gear_get_design" + (f"（design={a['design']}）" if a.get("design") else "") + "，读取 parameters 与 agent_proposed_inputs。\n"
            "2. 逐项列出：名称、值、单位、provenance、出处；agent_proposed 与 assumption 项单独成表，标注\"待人工确认\"。\n"
            "3. 对每个待确认项，说明它影响哪些校核（可用 gear_sensitivity 的结果支撑）。\n" + _RULE)},
    "lookup_formula_provenance": {
        "description": "查询某个输出量的公式注册表条目、条款、版次与证据等级",
        "arguments": [{"name": "output", "description": "输出量名，如 Z_B、K_V", "required": True}],
        "build": lambda a: (
            f"请查询输出量 {a['output']}：调用 registry_lookup(output=…)，逐条列出 id、clause、edition、method、evidence_level、source_check；"
            "evidence_level 为 null 要写成\"未评估\"，source_check 为 null 要写成\"未核对原文\"；若有 external_slots，说明它们必须由证据输入提供。\n" + _RULE)},
}


def prompts_list():
    return {"prompts": [{"name": n, "description": p["description"], "arguments": p["arguments"]} for n, p in _PROMPTS.items()]}


def prompts_get(params):
    params = params or {}
    name, args = params.get("name"), params.get("arguments") or {}
    if name not in _PROMPTS:
        raise McpError(-32602, f"提示词不存在：{name!r}")
    if not isinstance(args, dict) or not all(isinstance(v, str) for v in args.values()):
        raise McpError(-32602, "arguments 必须是 字符串 → 字符串 的对象")
    p = _PROMPTS[name]
    declared = {a["name"] for a in p["arguments"]}
    unknown = sorted(set(args) - declared)
    if unknown:
        raise McpError(-32602, f"提示词 {name} 不接受参数 {unknown}")
    missing = [a["name"] for a in p["arguments"] if a["required"] and not args.get(a["name"])]
    if missing:
        raise McpError(-32602, f"缺少必需参数：{missing}")
    return {"description": p["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": p["build"](args)}}]}
