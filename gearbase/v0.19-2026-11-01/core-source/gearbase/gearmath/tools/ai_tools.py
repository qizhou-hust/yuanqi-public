"""面向 AI 的工具层（我们自己的 MCP 服务器）：自描述、可校验、不让模型产生数值。

工具名只用字母、数字、下划线、连字符（^[a-zA-Z0-9_-]{1,64}$）。工程数值由 L2 公式计算（齿轮副用公式图，原始 Stage0 旗舰用有界枚举）；模型传入的数值必须声明来源，
来源为 agent_proposed 的输入会在结果中被单独标出，且不能让校核状态显示为"通过"。
输入不合格（未声明的名字、量纲不符的单位、超出取值域、缺限值、缺版次配置、缺方法选择器）时返回结构化的
blocked_* 状态，不抛异常。

MCP P0（接续文档第 7 节第 6 项，针对 M31 gear_mcp_server 的三个缺陷）：
  1. 标识：design_id / base_sha256 / preview_token 一律是规范 JSON（排序键、紧凑分隔、UTF-8）的 sha256，
     不使用 Python hash()（其字符串哈希按进程随机化，不可复现）。
  2. 不丢参数：每个模型类工具的结果都带 parameters（模型全部输入的值、单位、来源、出处）和 requested_overrides
     （调用方传入的原样覆盖），被阻断时也带；不做 M31 `_slim()` 式的剥离。
  3. 写操作两段式：gear_preview_edit 只读，返回 diff 与 preview_token = sha256(设计名 + 基线状态 sha + 编辑)；
     gear_commit 必须带 preview_token 与同一份 edit，按基线 sha 做比较并交换（CAS），基线已变则拒绝（stale）。
设计状态默认只保存在本服务器进程内存里（进程重启即丢失）；显式给出状态目录（serve(state_dir=…)、命令行 --state-dir 或环境变量
GEARBASE_STATE_DIR）时改为文件存储（gearmath/tools/design_store.py）：每次 commit 写一条不可变记录（版本号、父版本哈希、
model_sha256、spec、edit、diff），先写临时文件再原子发布，重启后从记录链恢复；同一设计并发写入以版本号做乐观锁
（gear_commit 可带 expected_version；记录版本已被占用则 rejected_version_conflict）。不给目录则保持纯内存模式，
并在 initialize 的 serverInfo.persistence 与各结果的 persistence 字段中声明。
新能力：registry_lookup（公式注册表查询）、list_nlp_templates / optimize_nlp（只接受已编译模板与数值参数）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import re
import sys
import threading
import os

from ..gear.formulas import CYLINDRICAL_PAIR
from ..gear import math_source as MS
from ..gear.inputs import full_input_table
from ..gear.rating import C001_G1_SELECTOR_SOURCES, C001_G1_SELECTORS, SELECTOR_OPTIONS, c001_g1, pair_model, rate
from ..kernel import units as U
from ..kernel.expr import FormulaError
from ..kernel.graph import InputError
from . import design_store as DS
from . import declared_tool as DT
from . import design_check_tool as DCT
from . import optimize_commit as OC          # v0.15 OPT3：受控写路径（默认不列出，见 optimize_commit.listed）
from . import nlp_templates as NT
from . import intent as IT
from . import flagship_workflow as FW
from . import nearest_feasible_edit_tool as NFET
from . import mcp_extras as MX

_SPECS = full_input_table()
_REGISTRY = pathlib.Path(__file__).resolve().parents[2] / "data" / "registry" / "formulas-v1.json"
_LEVELS = None            # 公式注册表里已评估的证据等级（公式 id → 等级）；缺文件 = 全部未评估
_DYN_ONLY = None          # 仅方法B 才需要的输入名（延迟计算）
_TOOL_PROVENANCE = ["user", "agent_proposed", "evidence", "assumption"]
_DESIGN_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


# ---------------------------------------------------------------- 标识：规范 JSON 的 sha256
def canonical_json(obj) -> str:
    """规范 JSON：键排序、紧凑分隔、不转义非 ASCII、拒绝 NaN/Infinity；同一内容恒得同一字符串。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_id(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _safe_id(obj):
    try:
        return sha256_id(obj)
    except (TypeError, ValueError):      # 含 NaN、不可序列化对象的非法请求：没有可复现的 id
        return None


_PARAM_SCHEMA = {
    "type": "object",
    "description": "覆盖基线的输入。键为变量名（见 gear_list_inputs），值为 {value, unit, provenance}；unit 的量纲须与声明一致。",
    "propertyNames": {"enum": sorted(s.name for s in _SPECS)},
    "additionalProperties": {
        "type": "object",
        "properties": {"value": {"type": "number"}, "unit": {"type": "string", "enum": sorted(U.UNITS)},
                       "provenance": {"type": "string", "enum": _TOOL_PROVENANCE}},
        "required": ["value", "unit", "provenance"], "additionalProperties": False},
}
_BASELINE = {"type": "string", "enum": ["C001_G1", "none"],
             "description": "C001_G1（默认）：在 M31 C001 第一级基线上覆盖（K_V 默认取收据证据，即 method.K_V=external）；"
                            "none：全部输入、版次与方法选择器由调用方给出"}
_EDITIONS = {"type": "object", "additionalProperties": {"type": "string"},
             "description": "按标准分册的版次配置，如 {\"ISO 6336-2\": \"2019\"}；覆盖基线中的同名分册"}
_SELECTORS = {"type": "object", "propertyNames": {"enum": sorted(SELECTOR_OPTIONS)},
              "additionalProperties": {"type": "string", "enum": sorted({v for o in SELECTOR_OPTIONS.values() for v in o})},
              "description": "方法选择器，如 {\"method.K_V\": \"B\"}：B = 方法B 公式推出 K_V；external = K_V 作为 evidence 输入。"
                             "baseline=none 时必须给出，否则阻断（blocked_missing_selectors），不使用默认方法"}
_DESIGN = {"type": "string", "pattern": "^[A-Za-z0-9_.-]{1,64}$",
           "description": "设计名（命名设计，缺省 default；状态在内存或 --state-dir 文件存储中，见 serverInfo.persistence）"}
_MODEL_ARGS = {"params": _PARAM_SCHEMA, "baseline": _BASELINE, "editions": _EDITIONS, "selectors": _SELECTORS}
_EDIT = {"type": "object", "additionalProperties": False,
         "description": "对设计 spec 的编辑：params 中值为 null 表示删除该覆盖；editions、selectors 按键合并",
         "properties": {"params": {"type": "object", "additionalProperties": {
                            "anyOf": [{"type": "null"}, _PARAM_SCHEMA["additionalProperties"]]}},
                        "editions": _EDITIONS, "selectors": _SELECTORS, "baseline": _BASELINE}}
_RO = {"readOnlyHint": True}

_DM = {"design": _DESIGN, **_MODEL_ARGS}     # 模型类工具的参数：stateless 覆盖，或引用服务器内存中的命名设计

TOOLS = [
    {"name": "gear_list_formulas", "description": "列出公式库：输出量、单位、表达式、标准条款。可按关键字过滤。",
     "annotations": _RO,
     "inputSchema": {"type": "object", "properties": {"contains": {"type": "string"}}, "additionalProperties": False}},
    {"name": "gear_list_inputs",
     "description": "列出模型输入声明：名字、期望单位与量纲、含义、取值域、角色（input/limit）、仅在哪个方法选择下才需要（used_when）。",
     "annotations": _RO, "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "gear_rate",
     "description": "对一对圆柱齿轮做统一校核（接触、弯曲、重合度），返回每项的值、限值、裕度、版次配置、方法选择、"
                    "design_id，以及全部参数回显（parameters，含单位与来源）。",
     "annotations": _RO, "inputSchema": {"type": "object", "properties": dict(_DM), "additionalProperties": False}},
    {"name": "gear_explain", "description": "给出某个量的完整公式链（每步公式、条款、数值、来源），附参数回显与有效证据等级（依赖链最弱一环及弱化来源；输入量为 null）。",
     "annotations": _RO,
     "inputSchema": {"type": "object", "properties": {"quantity": {"type": "string"}, **_DM},
                     "required": ["quantity"], "additionalProperties": False}},
    {"name": "gear_sensitivity", "description": "精确偏导数（自动微分）：quantity 对各输入的灵敏度，含相对弹性，附参数回显。",
     "annotations": _RO,
     "inputSchema": {"type": "object", "properties": {"quantity": {"type": "string"},
                                                      "wrt": {"type": "array", "items": {"type": "string"}}, **_DM},
                     "required": ["quantity", "wrt"], "additionalProperties": False}},
    {"name": "gear_get_design",
     "description": "读取服务器内存中的命名设计：spec、design_id（= spec 的规范 JSON sha256，写操作的基线）与全部参数回显。",
     "annotations": _RO, "inputSchema": {"type": "object", "properties": {"design": _DESIGN}, "additionalProperties": False}},
    {"name": "gear_preview_edit",
     "description": "写操作第一段（只读，不改状态）：校验编辑并返回 diff、参数变化、校核预览，以及 preview_token"
                    " = sha256(设计名 + 基线 sha256 + 编辑)。编辑不合格时不发 token。",
     "annotations": _RO,
     "inputSchema": {"type": "object", "properties": {"design": _DESIGN, "edit": _EDIT},
                     "required": ["edit"], "additionalProperties": False}},
    {"name": "gear_commit",
     "description": "写操作第二段：必须带 gear_preview_edit 返回的 preview_token 与同一份 edit。按基线 sha256 比较并交换，"
                    "基线在预览之后已变（stale）或 token 与编辑不符则拒绝，状态不变。状态存于内存或 --state-dir 文件存储，每次提交写不可变记录。",
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
     "inputSchema": {"type": "object", "properties": {"design": _DESIGN, "edit": _EDIT,
                                                      "preview_token": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                                                      "expected_version": {"type": "integer", "minimum": 0,
                                                                           "description": "可选乐观锁：调用方读到的设计版本（未保存 = 0）；与当前版本不符则 rejected_version_conflict"}},
                     "required": ["edit", "preview_token"], "additionalProperties": False}},
    {"name": "registry_lookup",
     "description": "查询公式注册表（只读）：按 id（精确）或 output（精确，可有多条）返回条目，含 clause、edition、method、"
                    "evidence_level、source_check、note 与 test_vectors；output 同时返回对应的 external_slots。至少给 id 或 output 之一。",
     "annotations": _RO,
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "output": {"type": "string"}},
                     "additionalProperties": False}},
    {"name": "list_nlp_templates",
     "description": "列出 optimize_nlp 可用的已编译问题模板：参数范围、变量域、目标名。",
     "annotations": _RO, "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "optimize_nlp",
     "description": "对已编译的问题模板运行零依赖局部 NLP（增广拉格朗日 + 带界拟牛顿，精确导数）。只接受模板名与数值参数，"
                    "不接受表达式或代码。返回 assurance 四项（search_claim、optimality、solver_convergence、evidence_level）分开；"
                    "结果只是一阶 KKT 局部候选；调用方给了 x0/weights/discrete_assignments 时结论为 pass_pending_human_confirmation。",
     "annotations": _RO, "inputSchema": NT.input_schema()},
    {"name": "requirement_compile",
     "description": "意图编译（只读、确定性）：把结构化需求（功率/转矩、转速、传动比及允许偏差、齿宽系数上限、安全系数下限、寿命、材料、空间约束）"
                    "编译成已有问题模板的参数与模型输入覆盖。缺项或冲突时返回 needs_clarification 与具体追问，绝不填默认值；"
                    "超出模板范围返回 blocked_*；无处安放的项（寿命、材料、中心距上限）列入 unapplied/post_checks。"
                    "全部数值标 agent_proposed，成功结论为 pass_pending_human_confirmation。",
     "annotations": _RO, "inputSchema": IT.input_schema()},
    {"name": "explain_infeasible",
     "description": "解释不可行（只读）：对已编译模板与数值参数，在声明网格上求最小违反量，列出每条约束单独放松所需的量与代价、"
                    "ratio_tol 与 max_b_over_d1 的联合放松组合，并可用 kernel 局部 NLP 确认（返回乘子）。结论只对声明网格成立，不是不可行性证明。",
     "annotations": _RO, "inputSchema": IT.explain_input_schema()},
    DT.TOOL,
    DCT.TOOL,
    NFET.TOOL,
    FW.TOOL,
]

_MODEL_TOOLS = ("gear_rate", "gear_explain", "gear_sensitivity")


# ---------------------------------------------------------------- 设计 spec 与模型装配
BASELINE_SPEC = {"baseline": "C001_G1", "selectors": {"method.K_V": "external"}, "editions": {}, "params": {}}


def _norm_spec(args):
    """把工具参数规范化成 spec（原样保留调用方给的内容，不做静默丢弃）。"""
    return {"baseline": args.get("baseline", "C001_G1"), "selectors": dict(args.get("selectors") or {}),
            "editions": dict(args.get("editions") or {}), "params": dict(args.get("params") or {})}


def _echo(m):
    """模型全部输入的回显：原单位数值、单位、来源类别、出处（不剥离任何参数）。"""
    return {k: {"value": U.from_canonical(i.value, i.unit), "unit": i.unit, "provenance": i.provenance,
                "source": i.source, "canonical_value": i.value}
            for k, i in sorted(m.inputs.items())}


def _model(spec, *, trusted_projection=False):
    """按 spec 装配模型；逐项收集输入错误（不在第一项错误处中断），返回 (模型, agent_proposed 输入, 错误)。"""
    baseline = spec.get("baseline", "C001_G1")
    errors = []
    sel = dict(spec.get("selectors") or {})
    src = {k: "AI 工具调用" for k in sel}
    if baseline == "C001_G1":                 # 未给出的选择器取 C001 G1 回放契约值（来源记入）
        for k, v in C001_G1_SELECTORS.items():
            if k not in sel:
                sel[k], src[k] = v, f"baseline C001_G1 约定：{C001_G1_SELECTOR_SOURCES[k]}"
    try:
        from ..gear.factor_methods import FACTOR_OPTIONS
        factors = {k:v for k,v in sel.items() if k in FACTOR_OPTIONS} if trusted_projection else {}
        base = pair_model(selectors={k:v for k,v in sel.items() if k not in factors}, selector_sources=src,
                          factor_selectors=factors or None, factor_selector_sources=src if factors else None)
    except (FormulaError, TypeError, ValueError) as e:
        base = pair_model()
        errors.append({"name": "selectors", "code": "invalid_selector", "message": str(e)})
    if baseline == "C001_G1":
        m = c001_g1(base)
    elif baseline == "none":
        m = base
    else:
        m = base
        errors.append({"name": "baseline", "code": "invalid_argument", "message": f"未知基线 {baseline!r}"})
    try:
        m.set_editions(spec.get("editions") or {}, "AI 工具调用")
    except (InputError, TypeError, ValueError, AttributeError) as e:
        errors.append(e.as_dict() if isinstance(e, InputError) else
                      {"name": "editions", "code": "invalid_argument", "message": f"版次配置格式错误：{e}"})
    agent = []
    params = spec.get("params") or {}
    if not isinstance(params, dict):
        return m, agent, errors + [{"name": "params", "code": "invalid_argument", "message": "params 必须是对象"}]
    for k, row in params.items():
        if not isinstance(row, dict) or not {"value", "unit", "provenance"} <= set(row):
            errors.append({"name": k, "code": "invalid_argument", "message": f"{k}：须给出 value、unit、provenance"})
            continue
        if row["provenance"] not in _TOOL_PROVENANCE and not (trusted_projection and row['provenance'] in ('optimizer','standard_constant')):
            errors.append({"name": k, "code": "unknown_provenance", "message": f"{k}：工具调用只接受来源 {_TOOL_PROVENANCE}"})
            continue
        try:
            m.set(k, row["value"], row["unit"], row["provenance"], "AI 工具调用")
        except InputError as e:
            errors.append(e.as_dict())
            continue
        if row["provenance"] == "agent_proposed":
            agent.append(k)
    return m, agent, errors


def _context(spec, m):
    """所有模型类结果共有的字段：设计标识、方法选择、参数回显、调用方原样覆盖。"""
    return {"design_id": _safe_id(spec), "selectors": dict(m.selectors), "selector_sources": dict(m.selector_sources),
            "parameters": _echo(m), "requested_overrides": copy.deepcopy(spec.get("params") or {})}


def _blocked_invalid(errors, agent, spec, m):
    return {"status": "blocked_invalid_inputs", "errors": errors, "checks": [], "agent_proposed_inputs": agent,
            **_context(spec, m)}


def _unknown_quantity(m, q):
    if not isinstance(q, str) or (q not in m.formulas and q not in m.specs):
        return {"status": "blocked_invalid_inputs",
                "errors": [{"name": str(q), "code": "unknown_quantity", "message": f"未知的量 {q!r}（见 gear_list_formulas）"}]}
    return None


def _blocked(res):
    out = {"status": res.status, "missing": res.missing, "missing_editions": res.missing_editions, "errors": res.errors}
    if res.status == "blocked_missing_selectors":
        out["options"] = SELECTOR_OPTIONS
    return {k: v for k, v in out.items() if v or k == "status"}


# ---------------------------------------------------------------- 设计状态（内存或文件）与两段式写
_LOCK = threading.RLock()
_STORE = DS.MemoryStore()
_ISSUED: dict = {}         # preview_token → {"design", "base_sha256"}（仅用于区分 stale 与伪造/不符；进程内）


def configure_state(state_dir=None):
    """显式选择存储：给目录 = 文件存储（不存在则创建）；None = 纯内存。返回当前模式。"""
    global _STORE
    with _LOCK:
        _STORE = DS.FileStore(state_dir) if state_dir else DS.MemoryStore()
        _ISSUED.clear()
    return _STORE.mode


def _persistence():
    return "file" if _STORE.mode == "file" else "in_memory_per_process"


def reset_state():
    """清空进程内设计状态并回到纯内存模式（测试用；不删除磁盘文件）。"""
    configure_state(None)


def _design_name(args):
    name = args.get("design", "default")
    if not isinstance(name, str) or not _DESIGN_NAME.match(name) or set(name) == {"."}:
        raise ValueError(f"设计名无效：{name!r}（须匹配 {_DESIGN_NAME.pattern}）")
    return name


def _current(name):
    """已保存的设计 spec；尚未保存时是基线 spec 的副本（首次 commit 即创建）。"""
    h = _STORE.head(name)
    if h and 'source' in h and h['spec'].get('kind') in (DS.IMPORT_KIND, DS.OPT_KIND):
        # Imported/optimized records have no editable legacy spec. Materialize
        # a complete compatibility projection from the authoritative source.
        doc = h['source']
        params = {n: {k: row[k] for k in ('value','unit','provenance')}
                  for section in ('inputs','evidence','constraints') for n,row in doc[section].items()}
        return dict(baseline='none',params=params,
                    selectors={n:r['value'] for n,r in doc['selectors'].items()},
                    editions={n:r['edition'] for n,r in doc['editions'].items()})
    return copy.deepcopy(h["spec"] if h else BASELINE_SPEC)


def _version(name):
    h = _STORE.head(name)
    return h["version"] if h else 0


def _apply_edit(spec, edit):
    if not isinstance(edit, dict):
        return None, [{"name": "edit", "code": "invalid_argument", "message": "edit 必须是对象"}]
    bad = sorted(set(edit) - {"params", "editions", "selectors", "baseline"})
    if bad:
        return None, [{"name": k, "code": "invalid_argument", "message": f"edit 中未知的键 {k}（可用：params、editions、selectors、baseline）"} for k in bad]
    new = copy.deepcopy(spec)
    if "baseline" in edit:
        new["baseline"] = edit["baseline"]
    for key in ("editions", "selectors"):
        if key in edit:
            if not isinstance(edit[key], dict):
                return None, [{"name": key, "code": "invalid_argument", "message": f"{key} 必须是对象"}]
            new[key].update(edit[key])
    for k, row in (edit.get("params") or {}).items():
        if row is not None and isinstance(row,dict) and row.get('provenance') not in _TOOL_PROVENANCE:
            return None, [{"name": k, "code": "unknown_provenance", "message": "编辑须给出工具允许的来源类别"}]
        if row is None:
            new["params"].pop(k, None)
        else:
            new["params"][k] = row
    return new, []


def _diff(old, new):
    rows = []
    for sec in ("baseline",):
        if old.get(sec) != new.get(sec):
            rows.append({"path": sec, "before": old.get(sec), "after": new.get(sec)})
    for sec in ("selectors", "editions", "params"):
        for k in sorted(set(old[sec]) | set(new[sec])):
            if old[sec].get(k) != new[sec].get(k):
                rows.append({"path": f"{sec}.{k}", "before": old[sec].get(k), "after": new[sec].get(k)})
    return rows


def _param_changes(before, after):
    out = []
    for k in sorted(set(before) | set(after)):
        a, b = before.get(k), after.get(k)
        if a != b:
            out.append({"name": k, "before": a, "after": b})
    return out


def _token(name, base_sha, edit):
    head = _STORE.head(name)
    payload = {"design": name, "base_sha256": base_sha, "edit": edit}
    if head and 'source' in head:
        payload['source_sha256'] = head['source_sha256']
    return sha256_id(payload)


def _preview(args):
    name = _design_name(args)
    edit = args.get("edit")
    cur = _current(name)
    base_sha = sha256_id(cur)
    new, errors = _apply_edit(cur, edit)
    base = {"design": name, "base_sha256": base_sha, "base_version": _version(name), "persistence": _persistence()}
    if errors:
        return {"status": "blocked_invalid_inputs", "errors": errors, "preview_token": None, **base}
    m, agent, errors = _model(new, trusted_projection=True)
    if errors:
        return {"status": "blocked_invalid_inputs", "errors": errors, "preview_token": None,
                "requested_edit": copy.deepcopy(edit), **base}
    try:
        new_sha = sha256_id(new)
    except (TypeError, ValueError) as e:
        return {"status": "blocked_invalid_inputs", "preview_token": None,
                "errors": [{"name": "edit", "code": "not_canonical_json", "message": f"编辑无法规范化为 JSON：{e}"}], **base}
    m0, _, _ = _model(cur, trusted_projection=True)
    r = rate(m)
    r.pop("result", None)
    token = _token(name, base_sha, edit)
    with _LOCK:
        _ISSUED[token] = {"design": name, "base_sha256": base_sha}
    return {"status": "preview", "preview_token": token, "new_sha256": new_sha, "diff": _diff(cur, new),
            "parameter_changes": _param_changes(_echo(m0), _echo(m)), "agent_proposed_inputs": agent,
            "rating_preview": {"status": r["status"], "checks": [{k: c[k] for k in ("id", "value", "limit", "margin_ratio", "pass")}
                                                                for c in r["checks"]]},
            "parameters": _echo(m), "selectors": dict(m.selectors), **base}


def _commit(args):
    name = _design_name(args)
    edit, token = args.get("edit"), args.get("preview_token")
    with _LOCK:
        cur = _current(name)
        base_sha = sha256_id(cur)
        cur_version = _version(name)
        head = {"design": name, "current_base_sha256": base_sha, "current_version": cur_version, "persistence": _persistence()}
        ev = args.get("expected_version")
        if ev is not None and (isinstance(ev, bool) or not isinstance(ev, int) or ev < 0):
            return {"status": "blocked_invalid_inputs", "errors": [{"name": "expected_version", "code": "invalid_argument",
                                                                    "message": "expected_version 必须是非负整数"}], **head}
        if ev is not None and ev != cur_version:
            return {"status": "rejected_version_conflict", "expected_version": ev,
                    "message": "设计版本已变（他人已提交），请重新 gear_get_design / gear_preview_edit", **head}
        if not isinstance(token, str) or not token:
            return {"status": "rejected_missing_token", "message": "gear_commit 必须带 gear_preview_edit 返回的 preview_token", **head}
        if token != _token(name, base_sha, edit):
            issued = _ISSUED.get(token)
            if issued and issued["design"] == name and issued["base_sha256"] != base_sha:
                return {"status": "rejected_stale_token", "preview_base_sha256": issued["base_sha256"],
                        "message": "设计在预览之后已被修改（基线 sha256 已变），请重新 gear_preview_edit", **head}
            return {"status": "rejected_invalid_token",
                    "message": "preview_token 与当前基线 + 所给 edit 不符（未经预览、被篡改或 edit 不同）", **head}
        new, errors = _apply_edit(cur, edit)
        m = None
        if not errors:
            m, _, errors = _model(new, trusted_projection=True)
        if errors:
            return {"status": "blocked_invalid_inputs", "errors": errors, **head}
        try:
            src = MS.source_from_model(m, name, f"设计 {name}")      # M34：提交单元 = gears.math-source/2（只含作者输入）
            prior = _STORE.head(name)
            if prior and 'source' in prior:
                for section in ('inputs','evidence','constraints','selectors','editions'):
                    for key,row in src[section].items():
                        old = prior['source'][section].get(key)
                        fields = ('value','unit','provenance') if section in ('inputs','evidence','constraints') else (('edition',) if section == 'editions' else ('value',))
                        if old and all(old.get(k) == row.get(k) for k in fields):
                            src[section][key] = copy.deepcopy(old)
        except MS.SourceError as e:
            return {"status": "blocked_invalid_inputs", "errors": e.errors, **head}
        rec = DS.make_record(name, _STORE.head(name), new, MS.build_model(src).sha256(), edit, _diff(cur, new), token, source=src)
        try:
            _STORE.append(name, rec)
        except DS.VersionConflict as e:
            return {"status": "rejected_version_conflict", "message": str(e), **head}
        return {"status": "committed", "design": name, "version": rec["version"], "previous_sha256": base_sha,
                "design_id": rec["sha256"], "model_sha256": rec["model_sha256"], "source_sha256": rec["source_sha256"],
                "diff": _diff(cur, new), "spec": copy.deepcopy(new), "parameters": _echo(m), "selectors": dict(m.selectors),
                "persistence": _persistence()}


# ---------------------------------------------------------------- 工具分派
def _registry_levels():
    global _LEVELS
    if _LEVELS is None:
        try:
            from ..kernel.registry import evidence_levels, load_registry
            _LEVELS = evidence_levels(load_registry(_REGISTRY))
        except (OSError, ValueError):
            _LEVELS = {}
    return _LEVELS


def _only_dynamic_names():
    global _DYN_ONLY
    if _DYN_ONLY is None:
        from ..gear.dynamic import DYNAMIC_INPUTS
        _DYN_ONLY = {s.name for s in DYNAMIC_INPUTS}
    return _DYN_ONLY


_REG_DOC = None


def _registry_lookup(args):
    global _REG_DOC
    if _REG_DOC is None:
        from ..kernel.registry import load_registry
        _REG_DOC = load_registry(_REGISTRY)
    rid, out = args.get("id"), args.get("output")
    bad = [k for k in args if k not in ("id", "output")]
    if bad or (rid is None and out is None) or not all(v is None or isinstance(v, str) for v in (rid, out)):
        return {"status": "blocked_invalid_inputs", "errors": [{"name": "arguments", "code": "invalid_argument",
                "message": "须给字符串 id 或 output（至少一个），不接受其他参数"}]}
    rows = [e for e in _REG_DOC["formulas"] if (rid is None or e["id"] == rid) and (out is None or e["output"] == out)]
    slots = [e for e in _REG_DOC.get("external_slots", []) if out is not None and rid is None and e.get("output") == out]
    if not rows and not slots:
        return {"status": "not_found", "id": rid, "output": out, "entries": [], "external_slots": []}
    return {"status": "ok", "schema": _REG_DOC["schema"], "entries": copy.deepcopy(rows),
            "external_slots": copy.deepcopy(slots), "count": len(rows),
            "note": "evidence_level 为 null = 未评估（unassessed）；source_check 为 null = 未核对原文"}


def call(name, args):
    if name == "gear_list_formulas":
        key = args.get("contains", "")
        return [{"id": f.id, "output": f.output, "unit": f.unit, "expr": f.expr, "ref": f.ref,
                 "standard": f.standard, "edition": f.edition}
                for f in CYLINDRICAL_PAIR if key in f.id or key in f.output or key in f.ref]
    if name == "gear_list_inputs":
        dyn = _only_dynamic_names()
        return [{"name": s.name, "unit": s.unit, "dimension": U.show(U.unit(s.unit)[0]), "description": s.description,
                 "domain": list(s.domain), "role": s.role,
                 "used_when": {"method.K_V": "B"} if s.name in dyn else {"method.K_V": "external"} if s.name == "K_V" else {}}
                for s in _SPECS]
    if name == "gear_get_design":
        dname = _design_name(args)
        with _LOCK:
            spec = _current(dname)
            head = _STORE.head(dname)
            saved = head is not None
            trusted_projection = bool(head and 'source' in head)
            version = _version(dname)
        m, agent, errors = _model(spec, trusted_projection=trusted_projection)
        return {"status": "ok" if not errors else "blocked_invalid_inputs", "design": dname, "saved": saved, "version": version,
                "base_sha256": sha256_id(spec), "spec": spec, "errors": errors, "agent_proposed_inputs": agent,
                **_context(spec, m), "persistence": _persistence()}
    if name == "registry_lookup":
        return _registry_lookup(args)
    if name == "list_nlp_templates":
        return NT.list_templates()
    if name == "optimize_nlp":
        return NT.run(args)
    if name == "optimize_declared":
        return DT.run(args)
    if name == "nearest_feasible_edit":
        return NFET.run(args)
    if name == "design_check":
        return DCT.run(args)
    if name == "optimize_and_commit":
        return DT._clean(OC.run(args, _STORE, _LOCK))
    if name == "requirement_compile":
        return IT.requirement_compile(args)
    if name == 'flagship_workflow':
        return FW.run(args)
    if name == "explain_infeasible":
        return IT.explain_infeasible(args)
    if name == "gear_preview_edit":
        return _preview(args)
    if name == "gear_commit":
        return _commit(args)
    if name not in _MODEL_TOOLS:
        raise KeyError(f"未知工具 {name}")
    trusted_projection = False
    if "design" in args:
        if {"baseline", "params", "editions", "selectors"} & set(args):
            return {"status": "blocked_invalid_inputs", "errors": [{"name": "design", "code": "invalid_argument",
                    "message": "给了 design 就不能再同时给 baseline/params/editions/selectors（避免静默忽略）；请先 gear_preview_edit + gear_commit"}]}
        with _LOCK:
            dname = _design_name(args)
            spec = _current(dname)
            head = _STORE.head(dname)
            # Only the validated store's owned source can authorize protected
            # provenance. Stateless caller params retain the public allowlist.
            trusted_projection = bool(head and 'source' in head)
    else:
        spec = _norm_spec(args)
    m, agent, errors = _model(spec, trusted_projection=trusted_projection)
    if errors:
        return _blocked_invalid(errors, agent, spec, m)
    m.set_evidence_levels(_registry_levels())
    ctx = _context(spec, m)
    if name == "gear_rate":
        r = rate(m)
        r.pop("result", None)
        r["agent_proposed_inputs"] = agent
        if agent and r["status"] == "pass":
            r["status"] = "pass_pending_human_confirmation"
        return {**r, **ctx}
    bad = _unknown_quantity(m, args.get("quantity"))
    if bad:
        return {**bad, **ctx}
    if name == "gear_explain":
        res = m.evaluate([args["quantity"]])
        if res.status.startswith("blocked"):
            return {**_blocked(res), **ctx}
        return {"status": res.status, "chain": m.explain(res, args["quantity"]), "editions": res.editions,
                "evidence": res.evidence.get(args["quantity"]), "model_sha256": res.model_sha256, "agent_proposed_inputs": agent, **ctx}
    if name == "gear_sensitivity":
        q, wrt = args["quantity"], list(args.get("wrt") or [])
        bad_wrt = [w for w in wrt if w not in m.inputs]
        if bad_wrt:
            return {"status": "blocked_invalid_inputs",
                    "errors": [{"name": w, "code": "unknown_input", "message": f"{w} 不是已设置的输入，不能对其求导"} for w in bad_wrt],
                    **ctx}
        res = m.evaluate([q], wrt=wrt)
        if res.status.startswith("blocked"):
            return {**_blocked(res), **ctx}
        out = []
        for w in wrt:
            g = m.gradient(res, q, w)
            out.append({"wrt": w, "d_quantity_d_input_canonical": g,
                        "elasticity": g * m.inputs[w].value / res.values[q] if res.values[q] else None})
        return {"status": res.status, "quantity": q, "value": res.values[q], "sensitivities": out,
                "model_sha256": res.model_sha256, **ctx}


def serve(stdin=None, stdout=None, state_dir=None):
    """最小 stdio MCP（JSON-RPC 2.0）服务器：initialize / tools/list / tools/call。
    state_dir（或环境变量 GEARBASE_STATE_DIR）显式给出时用文件存储；都不给则纯内存，并在 serverInfo 中声明。"""
    # MCP stdio is UTF-8 independently of the process locale. Explicit streams
    # remain caller-owned (including StringIO and other in-process transports).
    if stdin is None:
        stdin = sys.stdin
        if hasattr(stdin, "reconfigure"):
            stdin.reconfigure(encoding="utf-8")
    if stdout is None:
        stdout = sys.stdout
        if hasattr(stdout, "reconfigure"):
            stdout.reconfigure(encoding="utf-8")
    state_dir = state_dir or os.environ.get("GEARBASE_STATE_DIR") or None
    if state_dir:
        configure_state(state_dir)
    for line in stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if "id" not in msg:          # 通知不回复
            continue
        mid, method = msg["id"], msg.get("method")
        try:
            if method == "initialize":
                result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                          "serverInfo": {"name": "gearmath-prototype", "version": "0.5",
                                         "persistence": {"mode": _STORE.mode,
                                                         "durable": _STORE.mode == "file",
                                                         "note": "文件存储：重启后恢复；内存：进程结束即丢失"}}}
            elif method == "tools/list":
                result = {"tools": TOOLS + ([OC.TOOL] if OC.listed() else [])}
            elif method == "tools/call":
                p = msg["params"]
                data = call(p["name"], p.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                          "structuredContent": {"result": data}}
            elif method == "resources/list":
                result = MX.resources_list()
            elif method == "resources/templates/list":
                result = MX.resources_templates_list()
            elif method == "resources/read":
                result = MX.resources_read(msg.get("params"))
            elif method == "prompts/list":
                result = MX.prompts_list()
            elif method == "prompts/get":
                result = MX.prompts_get(msg.get("params"))
            elif method == "ping":
                result = {}
            else:
                raise LookupError(method)
            reply = {"jsonrpc": "2.0", "id": mid, "result": result}
        except MX.McpError as e:
            reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": e.code, "message": str(e)}}
        except Exception as e:  # 错误作为结构化结果返回，便于模型自我修正
            reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": str(e)}}
        stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        stdout.flush()


if __name__ == "__main__":
    argv = sys.argv[1:]
    sd = argv[argv.index("--state-dir") + 1] if "--state-dir" in argv and argv.index("--state-dir") + 1 < len(argv) else None
    serve(state_dir=sd)
