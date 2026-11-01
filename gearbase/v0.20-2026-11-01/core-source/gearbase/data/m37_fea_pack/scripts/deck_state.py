"""M37 受限 STEP 状态机（外部审查 FEA-readiness-R1 R02 / 待办 T0）。零依赖，不调用 ccx。

按顺序解析 MODEL → STEP → PROCEDURE → 历史数据 → END STEP，并计算每一步的有效 *BOUNDARY / *CLOAD 状态
（继承、OP=NEW 重置、同一自由度覆盖）。只接受本包生成器使用的受限 profile；profile 外的关键字、参数或结构一律拒绝，
不依赖求解器稍后报错。与 inp_writer.lint（格式自检）并列，互不替代。

profile（STATE_VERSION 变化即 profile 变化）：
  - 模型数据只能出现在第一个 *STEP 之前；*BOUNDARY 可作为模型数据（基础约束），被第 1 步继承。
    例外：步内可新建 *NSET / *ELSET（L2 生成器在步内定义输出用的 ROOTT），但不得改写或扩充已有集合。
  - 每个 *STEP 的第一个关键字必须是唯一的过程卡（只支持 *STATIC，且不带参数）；过程卡出现在 STEP 外、
    同一步重复过程卡、空步（无过程卡）、STEP 未闭合 / 嵌套 / 多余 END STEP 均拒绝。
  - *STEP 只接受 INC=正整数（NLGEOM、PERTURBATION 等均拒绝）；*STATIC 数据行为 0 或 4 个数，
    第 2 个为时间段；不写数据行时按 CCX 文档的缺省时间段 1.0 记录（period_source=ccx_default，已在报告中注明）。
  - *BOUNDARY / *CLOAD：OP 只允许 NEW / MOD；OP=NEW 必须是该步该类卡的第一张；同一自由度后写覆盖先写。
    同一步内既被约束又施加集中力的自由度（典型来源：上一步的位移驱动被继承而没有 OP=NEW）拒绝；
    *EQUATION 的被消去自由度若同时被约束也拒绝。
  - 输出请求（*NODE PRINT / *EL PRINT / *CONTACT PRINT / *... FILE）只允许出现在最后一步，同一请求不得重复。
  - *INCLUDE,INPUT=相对路径：只允许一层（被包含文件中再出现 *INCLUDE 拒绝），路径不得为绝对路径或含 ..，
    路径中任何一级不得是符号链接，resolve 后必须仍在 INP 所在目录之内；
    被包含文件列入 includes，供运行身份（run_m37 三次哈希）使用。
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path, PurePosixPath, PureWindowsPath

STATE_VERSION = "m37.step-state/1.0"
PROFILE = "m37-restricted-2d-static/1.0"
STATIC_DEFAULT_PERIOD = 1.0      # CCX 用户手册 *STATIC：时间段缺省 1.0（本环境未核对手册原文，见 REPORT）

MODEL_KW = {"HEADING", "NODE", "ELEMENT", "NSET", "ELSET", "SURFACE", "MATERIAL", "ELASTIC", "SOLID SECTION",
            "SURFACE INTERACTION", "SURFACE BEHAVIOR", "CONTACT PAIR", "EQUATION"}
PROCEDURES = {"STATIC"}
OUTPUT_KW = {"NODE PRINT", "EL PRINT", "CONTACT PRINT", "NODE FILE", "EL FILE", "CONTACT FILE"}
HISTORY_KW = {"BOUNDARY", "CLOAD"} | OUTPUT_KW
PARAMS = {"HEADING": set(), "NODE": set(), "ELEMENT": {"TYPE", "ELSET"}, "NSET": {"NSET"}, "ELSET": {"ELSET"},
          "SURFACE": {"NAME", "TYPE"}, "MATERIAL": {"NAME"}, "ELASTIC": set(), "SOLID SECTION": {"ELSET", "MATERIAL"},
          "SURFACE INTERACTION": {"NAME"}, "SURFACE BEHAVIOR": {"PRESSURE-OVERCLOSURE"},
          "CONTACT PAIR": {"INTERACTION", "TYPE"}, "EQUATION": set(), "BOUNDARY": {"OP"}, "CLOAD": {"OP"},
          "STEP": {"INC"}, "STATIC": set(), "END STEP": set(), "NODE PRINT": {"NSET"}, "EL PRINT": {"ELSET"},
          "CONTACT PRINT": {"SLAVE", "MASTER"}, "NODE FILE": {"NSET"}, "EL FILE": {"ELSET"}, "CONTACT FILE": set(),
          "INCLUDE": {"INPUT"}}
OUTPUT_KEYS = {"NODE PRINT": {"U", "RF"}, "EL PRINT": {"S", "COORD"}, "CONTACT PRINT": {"CDIS", "CSTR", "CF"},
               "NODE FILE": {"U", "RF"}, "EL FILE": {"S", "E"}, "CONTACT FILE": {"CDIS", "CSTR"}}
ELEMENT_NODES = {"CPE6": 6, "CPE8": 8, "CPE8R": 8}
SURFACE_SIDES = {"CPE6": 3, "CPE8": 4, "CPE8R": 4}

# 严格读取请求的分量表（与 ccx_strict.FIELD_FORMATS 一致；此处不 import，保持两模块各自独立可审）
_REQ = {("NODE PRINT", "U"): ("displacements", ("vx", "vy", "vz")),
        ("NODE PRINT", "RF"): ("forces", ("fx", "fy", "fz")),
        ("EL PRINT", "S"): ("stresses", ("elem", "integ.pnt.", "sxx", "syy", "szz", "sxy", "sxz", "syz")),
        ("EL PRINT", "COORD"): ("global coordinates", ("elem", "integ.pnt.", "x", "y", "z")),
        ("CONTACT PRINT", "CSTR"): ("contact stress", ("slave element+face", "press", "tang1", "tang2")),
        ("CONTACT PRINT", "CDIS"): ("relative contact displacement", ("slave element+face", "normal", "tang1", "tang2"))}


class DeckStateError(ValueError):
    pass


def _err(code, detail, src=None, line=None):
    return {"code": code, "detail": detail, "file": src, "line": line}


def _keyword(line):
    parts = [p.strip() for p in line[1:].split(",")]
    kw = " ".join(parts[0].upper().split())
    prm = {}
    for p in parts[1:]:
        if not p:
            continue
        k, eq, v = p.partition("=")
        prm[" ".join(k.upper().split())] = " ".join(v.strip().split()) if eq else True
    return kw, prm


def _include_target(base_dir, raw):
    """解析 *INCLUDE 目标：路径中任何一级是符号链接、或 resolve 后不在 INP 所在目录之内，均返回 None（拒绝）。"""
    base = Path(base_dir)
    cur = base
    for part in PurePosixPath(raw.replace("\\", "/")).parts:
        cur = cur / part
        if cur.is_symlink():
            return None
    try:
        cur.resolve().relative_to(base.resolve())
    except ValueError:
        return None
    return cur


def _safe_include(raw):
    if not isinstance(raw, str) or not raw:
        return False
    if PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute() or PureWindowsPath(raw).drive:
        return False
    return ".." not in PurePosixPath(raw.replace("\\", "/")).parts


def _lines(path, errors, include_list):
    """展开一层 *INCLUDE，返回 [(源文件名, 行号, 原文)]。"""
    path = Path(path)
    out = []
    for i, raw in enumerate(path.read_text(errors="replace").splitlines(), 1):
        s = raw.strip()
        if s.upper().startswith("*INCLUDE"):
            kw, prm = _keyword(s)
            extra = set(prm) - PARAMS["INCLUDE"]
            inp = prm.get("INPUT")
            if extra or not _safe_include(inp):
                errors.append(_err("include_invalid", f"*INCLUDE 参数不在 profile 内或路径不安全：{s[:100]}", path.name, i))
                continue
            inc = _include_target(path.parent, inp)
            if inc is None:
                errors.append(_err("include_invalid", f"*INCLUDE 路径含符号链接或越出 INP 所在目录：{inp}", path.name, i))
                continue
            if not inc.is_file():
                errors.append(_err("include_missing", f"*INCLUDE 文件不存在：{inp}", path.name, i))
                continue
            include_list.append({"input": inp, "path": str(inc), "line": i})
            for j, r2 in enumerate(inc.read_text(errors="replace").splitlines(), 1):
                if r2.strip().upper().startswith("*INCLUDE"):
                    errors.append(_err("nested_include", "被包含文件中再次 *INCLUDE（profile 只允许一层）", inp, j))
                    continue
                out.append((inp, j, r2))
            continue
        out.append((path.name, i, raw))
    return out


def include_paths(inp):
    """只解析 *INCLUDE（不做状态机），供运行身份使用：[(INPUT 原文, 解析后的路径)]。路径不安全时抛 DeckStateError。"""
    inp = Path(inp)
    out = []
    for i, raw in enumerate(inp.read_text(errors="replace").splitlines(), 1):
        s = raw.strip()
        if s.upper().startswith("*INCLUDE"):
            _, prm = _keyword(s)
            raw_in = prm.get("INPUT")
            tgt = _include_target(inp.parent, raw_in) if _safe_include(raw_in) else None
            if tgt is None:
                raise DeckStateError(f"{inp.name}:{i}: *INCLUDE 路径不安全（绝对路径、..、符号链接或越界）：{s[:100]}")
            out.append((raw_in, tgt))
    return out


def analyse_text(text, name="<deck>"):
    """无 *INCLUDE 的文本版（测试与小样例用）。"""
    return _analyse([(name, i, raw) for i, raw in enumerate(text.splitlines(), 1)], [], [])


def analyse_file(inp):
    """解析 .inp（展开一层 *INCLUDE）。返回 DeckState。"""
    errors, incs = [], []
    lines = _lines(inp, errors, incs)
    st = _analyse(lines, errors, incs)
    st.report["input"] = Path(inp).name
    st.report["input_sha256"] = hashlib.sha256(Path(inp).read_bytes()).hexdigest()
    st.report["includes"] = [{"input": d["input"], "sha256": hashlib.sha256(Path(d["path"]).read_bytes()).hexdigest()}
                             for d in incs]
    return st


class DeckState:
    def __init__(self):
        self.nodes, self.elements, self.elem_type = set(), {}, {}
        self.nsets, self.elsets, self.surfaces = {}, {}, {}
        self.equations, self.base_bc, self.steps = [], {}, []
        self.materials, self.interactions = {}, set()
        self.errors = []
        self.report = {}

    @property
    def ok(self):
        return not self.errors

    # -------------------------------------------------- 严格读取请求（覆盖声明由 deck 预先给出，不看输出）
    def strict_requests(self):
        """最后一步的输出请求 → ccx_strict 请求列表（JSON 化 dict）。只覆盖 .dat（*... PRINT）。"""
        if not self.ok or not self.steps:
            raise DeckStateError("deck 未通过状态机检查，不能生成覆盖声明")
        reqs = []
        for o in self.steps[-1]["outputs"]:
            kw, prm, keys = o["keyword"], o["params"], o["keys"]
            if kw == "NODE PRINT":
                nodes = sorted(self.nsets[prm["NSET"]])
                for k in keys:
                    field, comps = _REQ[(kw, k)]
                    reqs.append({"id": f"{k}@{prm['NSET']}", "kind": "field", "field": field, "region": prm["NSET"],
                                 "location": "node", "components": list(comps),
                                 "coverage": {"mode": "exact_keys", "keys": nodes}})
            elif kw == "EL PRINT":
                groups = {}
                for e in sorted(self.elsets[prm["ELSET"]]):
                    groups.setdefault(self.elem_type[e], []).append(e)
                for k in keys:
                    field, comps = _REQ[(kw, k)]
                    reqs.append({"id": f"{k}@{prm['ELSET']}", "kind": "field", "field": field, "region": prm["ELSET"],
                                 "location": "element_ip", "components": list(comps),
                                 "coverage": {"mode": "elements_ip_registered", "element_groups": groups}})
            elif kw == "CONTACT PRINT":
                faces = sorted({(e, int(sd[1:])) for e, sd in self.surfaces[prm["SLAVE"]]})
                types = {e: self.elem_type[e] for e, _ in faces}
                for k in keys:
                    if k == "CF":
                        reqs.append({"id": f"CF@{prm['SLAVE']}/{prm['MASTER']}", "kind": "statistics",
                                     "slave": prm["SLAVE"], "master": prm["MASTER"], "location": "statistics",
                                     "coverage": {"mode": "statistics_parts",
                                                  "parts": ["total surface force", "center of gravity and mean normal",
                                                            "moment about the center of gravity", "area normal shear"]}})
                        continue
                    field, comps = _REQ[(kw, k)]
                    reqs.append({"id": f"{k}@{prm['SLAVE']}", "kind": "field", "field": field,
                                 "region": "ALL_CONTACT_ELEMENTS", "location": "contact_row", "components": list(comps),
                                 "coverage": {"mode": "rows_within_faces", "faces": [list(f) for f in faces],
                                              "element_types": types}})
        return reqs

    def frd_requested(self):
        """最后一步是否请求了 .frd 输出（*NODE FILE / *EL FILE / *CONTACT FILE）。只有请求了才把 .frd 交给严格读取。"""
        return bool(self.steps) and any(o["keyword"].endswith(" FILE") for o in self.steps[-1]["outputs"])

    def expectation(self):
        return {"expected_final_step": len(self.steps), "expected_total_time": sum(s["period"] for s in self.steps)}


def _floats(fields):
    return [float(v) for v in fields]


def _analyse(lines, errors, incs):
    st = DeckState()
    st.errors = errors
    E = lambda code, detail, src=None, ln=None: errors.append(_err(code, detail, src, ln))   # noqa: E731
    phase = "model"            # model | step | between
    cur_step = None
    kw, prm, kw_src, kw_line = None, {}, None, None
    eq_pending, eq_n = None, None
    cur_set = cur_material = None
    seen_output = set()

    def targets(tok, src, ln, what):
        t = tok.strip().upper()
        if t.lstrip("-").isdigit():
            n = int(t)
            if n not in st.nodes:
                E("undefined_node", f"{what} 引用未定义节点 {n}", src, ln)
                return []
            return [n]
        if t not in st.nsets:
            E("undefined_set", f"{what} 引用未定义 NSET {t}", src, ln)
            return []
        return sorted(st.nsets[t])

    def close_step(src, ln):
        s = cur_step
        if s["procedure"] is None:
            E("empty_step" if not s["keywords"] else "missing_procedure",
              f"第 {s['index']} 步（{s['src']}:{s['line']}）没有过程卡" + ("（空步）" if not s["keywords"] else ""), src, ln)
        s["bc"] = dict(s["bc_state"])
        s["cload"] = dict(s["cl_state"])
        for (n, d), v in s["cload"].items():
            if (n, d) in s["bc"]:
                E("load_on_prescribed_dof", f"第 {s['index']} 步：节点 {n} 自由度 {d} 同时被约束与施加集中力"
                  + ("（约束继承自前一步，未用 OP=NEW 重置）" if s["bc_inherited"].get((n, d)) else ""), src, ln)
                break
        for eq in st.equations:
            dep = (eq[0][0], eq[0][1])
            if dep in s["bc"]:
                E("mpc_dependent_prescribed", f"第 {s['index']} 步：*EQUATION 被消去自由度 {dep} 同时被约束", src, ln)
                break

    for src, ln, raw in lines:
        line = raw.strip()
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            if line.endswith(","):
                E("keyword_continuation", f"关键字行续行不在 profile 内：{line[:80]}", src, ln)
            kw, prm = _keyword(line)
            kw_src, kw_line = src, ln
            cur_set = None
            if kw not in PARAMS:
                E("unsupported_keyword", f"profile 外关键字 *{kw}", src, ln)
                kw = None
                continue
            extra = set(prm) - PARAMS[kw]
            if extra:
                E("unsupported_parameter", f"*{kw} 的参数 {sorted(extra)} 不在 profile 内", src, ln)
            if kw == "INCLUDE":       # 已在 _lines 中展开；文本版不支持
                E("include_invalid", "*INCLUDE 只在 analyse_file 中展开", src, ln)
                continue
            if eq_pending is not None:
                E("equation_incomplete", "*EQUATION 项数与数据不符", src, ln)
                eq_pending, eq_n = None, None
            # ---------------- 状态转移
            if kw == "STEP":
                if phase == "step":
                    E("step_not_closed", f"第 {cur_step['index']} 步尚未 *END STEP 又开新步", src, ln)
                    close_step(src, ln)
                inc = prm.get("INC")
                if inc is not None and not (isinstance(inc, str) and inc.isdigit() and int(inc) > 0):
                    E("unsupported_parameter", f"*STEP INC={inc!r} 不是正整数", src, ln)
                prev_bc = dict(st.steps[-1]["bc_state"]) if st.steps else dict(st.base_bc)
                prev_cl = dict(st.steps[-1]["cl_state"]) if st.steps else {}
                cur_step = {"index": len(st.steps) + 1, "src": src, "line": ln, "inc": inc, "procedure": None,
                            "procedure_line": None, "period": None, "period_source": None, "keywords": [],
                            "bc_state": prev_bc, "cl_state": prev_cl, "bc_inherited": {k: True for k in prev_bc},
                            "bc_cards": 0, "cl_cards": 0, "bc_op_new": False, "cl_op_new": False, "outputs": []}
                st.steps.append(cur_step)
                phase = "step"
                continue
            if kw == "END STEP":
                if phase != "step":
                    E("end_without_step", "多余的 *END STEP", src, ln)
                    continue
                close_step(src, ln)
                phase = "between"
                continue
            if kw in PROCEDURES:
                if phase != "step":
                    E("procedure_outside_step", f"过程卡 *{kw} 位于 *STEP 之外", src, ln)
                    kw = None
                    continue
                if cur_step["procedure"] is not None:
                    E("duplicate_procedure", f"第 {cur_step['index']} 步重复过程卡 *{kw}（已在第 "
                      f"{cur_step['procedure_line']} 行）", src, ln)
                    kw = None
                    continue
                if cur_step["keywords"]:
                    E("history_before_procedure", f"第 {cur_step['index']} 步在过程卡之前已有 "
                      f"{cur_step['keywords']}", src, ln)
                cur_step["procedure"], cur_step["procedure_line"] = kw, ln
                cur_step["period"], cur_step["period_source"] = STATIC_DEFAULT_PERIOD, "ccx_default"
                cur_step["keywords"].append(kw)
                continue
            if kw in ("NSET", "ELSET") and phase == "step":
                # 题目包 L2 生成器在步内定义 *ELSET ROOTT（只供输出）；只接受步内新建集合，不接受改写/扩充已有集合
                name = prm.get(kw)
                if name in (st.nsets if kw == "NSET" else st.elsets):
                    E("set_redefined_in_step", f"第 {cur_step['index']} 步内改写已有集合 {name}", src, ln)
                    kw = None
                    continue
                if cur_step["procedure"] is None:
                    E("history_before_procedure", f"第 {cur_step['index']} 步 *{kw} 出现在过程卡之前", src, ln)
                cur_step["keywords"].append(kw)
            elif kw in MODEL_KW:
                if phase != "model":
                    E("model_keyword_in_step" if phase == "step" else "model_keyword_after_step",
                      f"模型数据 *{kw} 出现在第一个 *STEP 之后", src, ln)
                    kw = None
                    continue
            elif kw in HISTORY_KW:
                if phase == "between":
                    E("history_outside_step", f"*{kw} 位于两步之间", src, ln)
                    kw = None
                    continue
                if phase == "model":
                    if kw != "BOUNDARY":
                        E("history_outside_step", f"*{kw} 位于第一个 *STEP 之前", src, ln)
                        kw = None
                        continue
                    if prm.get("OP") not in (None, "MOD"):
                        E("unsupported_parameter", "模型数据 *BOUNDARY 不允许 OP=NEW", src, ln)
                else:
                    if cur_step["procedure"] is None:
                        E("history_before_procedure", f"第 {cur_step['index']} 步 *{kw} 出现在过程卡之前", src, ln)
                    cur_step["keywords"].append(kw)
                    if kw in ("BOUNDARY", "CLOAD"):
                        op = prm.get("OP", "MOD")
                        if op not in ("NEW", "MOD"):
                            E("unsupported_parameter", f"*{kw} OP={op} 不在 profile 内", src, ln)
                        tag = "bc" if kw == "BOUNDARY" else "cl"
                        if op == "NEW":
                            if cur_step[f"{tag}_cards"]:
                                E("op_new_not_first", f"第 {cur_step['index']} 步 *{kw},OP=NEW 不是该步第一张 *{kw}", src, ln)
                            cur_step[f"{tag}_state"] = {}
                            cur_step[f"{tag}_op_new"] = True
                            if tag == "bc":
                                cur_step["bc_inherited"] = {}
                        cur_step[f"{tag}_cards"] += 1
                    else:
                        o = {"keyword": kw, "params": {k: v for k, v in prm.items()}, "keys": [], "line": ln}
                        for p, v in o["params"].items():
                            if v is True:
                                E("unsupported_parameter", f"*{kw} 参数 {p} 无值", src, ln)
                        cur_step["outputs"].append(o)
            # 关键字自身的引用检查
            if kw == "ELEMENT" and prm.get("TYPE") not in ELEMENT_NODES:
                E("unsupported_element", f"单元类型 {prm.get('TYPE')} 不在 profile 内", src, ln)
            if kw == "NSET":
                cur_set = prm.get("NSET")
                st.nsets.setdefault(cur_set, set())
            elif kw == "ELSET":
                cur_set = prm.get("ELSET")
                st.elsets.setdefault(cur_set, set())
            elif kw == "ELEMENT" and prm.get("ELSET"):
                st.elsets.setdefault(prm["ELSET"], set())
            elif kw == "SURFACE":
                if prm.get("TYPE", "ELEMENT") != "ELEMENT":
                    E("unsupported_parameter", "只支持 TYPE=ELEMENT 面", src, ln)
                st.surfaces[prm.get("NAME")] = []
            elif kw == "EQUATION":
                eq_pending, eq_n = [], None
            elif kw == "MATERIAL":
                cur_material = prm.get("NAME")
                if cur_material in st.materials:
                    E("duplicate_material", f"材料 {cur_material} 重复定义", src, ln)
                st.materials[cur_material] = None
            elif kw == "SURFACE INTERACTION":
                st.interactions.add(prm.get("NAME"))
            elif kw == "SURFACE BEHAVIOR" and prm.get("PRESSURE-OVERCLOSURE") == "HARD":
                kw = None          # HARD 无数据行（MORTAR 实验变体）
            if kw == "ELASTIC" and cur_material is None:
                E("material_data", "*ELASTIC 没有所属 *MATERIAL", src, ln)
            continue
        # ------------------------------------------------ 数据行
        if kw is None:
            continue
        f = [x.strip() for x in line.split(",") if x.strip() != ""]
        try:
            if kw == "HEADING":
                continue
            if kw == "NODE":
                n = int(f[0])
                if n in st.nodes:
                    E("duplicate_node", f"节点号重复 {n}", src, ln)
                st.nodes.add(n)
                _floats(f[1:])
            elif kw == "ELEMENT":
                e, conn = int(f[0]), [int(v) for v in f[1:]]
                et = prm.get("TYPE")
                if et in ELEMENT_NODES and len(conn) != ELEMENT_NODES[et]:
                    E("element_shape", f"单元 {e} 节点数 {len(conn)} ≠ {ELEMENT_NODES[et]}", src, ln)
                if e in st.elements:
                    E("duplicate_element", f"单元号重复 {e}", src, ln)
                missing = [n for n in conn if n not in st.nodes]
                if missing:
                    E("undefined_node", f"单元 {e} 引用未定义节点 {missing[:3]}", src, ln)
                st.elements[e], st.elem_type[e] = conn, et
                if prm.get("ELSET"):
                    st.elsets[prm["ELSET"]].add(e)
            elif kw in ("NSET", "ELSET"):
                pool = st.nsets if kw == "NSET" else st.elsets
                base = st.nodes if kw == "NSET" else st.elements
                for v in f:
                    if v.lstrip("-").isdigit():
                        if int(v) not in base:
                            E("undefined_member", f"*{kw} {cur_set} 含未定义编号 {v}", src, ln)
                        pool[cur_set].add(int(v))
                    elif v.upper() in pool:
                        pool[cur_set] |= pool[v.upper()]
                    else:
                        E("undefined_set", f"*{kw} {cur_set} 引用未定义集合 {v}", src, ln)
            elif kw == "SURFACE":
                e, side = int(f[0]), f[1].upper()
                if e not in st.elements:
                    E("undefined_member", f"面引用未定义单元 {e}", src, ln)
                elif not (len(side) == 2 and side[0] == "S" and side[1].isdigit()
                          and 1 <= int(side[1]) <= SURFACE_SIDES.get(st.elem_type[e], 0)):
                    E("surface_side", f"单元 {e} 边号 {side} 非法", src, ln)
                st.surfaces[prm.get("NAME")].append((e, side))
            elif kw == "EQUATION":
                if eq_pending is None:
                    E("equation_shape", f"*EQUATION 已写完后仍有数据行：{line[:60]}", src, ln)
                elif eq_n is None:
                    eq_n = int(f[0])
                    if eq_n < 2 or len(f) != 1:
                        E("equation_shape", f"*EQUATION 项数行非法：{line[:60]}", src, ln)
                else:
                    if len(f) % 3:
                        E("equation_shape", f"*EQUATION 数据行字段数 {len(f)}", src, ln)
                    for k in range(0, len(f) - len(f) % 3, 3):
                        n, d, c = int(f[k]), int(f[k + 1]), float(f[k + 2])
                        if n not in st.nodes:
                            E("undefined_node", f"*EQUATION 引用未定义节点 {n}", src, ln)
                        eq_pending.append((n, d, c))
                    if len(eq_pending) >= eq_n:
                        if len(eq_pending) != eq_n:
                            E("equation_shape", "*EQUATION 项数与数据不符", src, ln)
                        st.equations.append(eq_pending)
                        eq_pending, eq_n = None, None
            elif kw == "BOUNDARY":
                d1 = int(f[1])
                d2 = int(f[2]) if len(f) > 2 else d1
                val = float(f[3]) if len(f) > 3 else 0.0
                if len(f) > 4 or not (1 <= d1 <= d2 <= 6) or not math.isfinite(val):
                    E("boundary_shape", f"*BOUNDARY 数据行非法：{line[:60]}", src, ln)
                tgt = st.base_bc if phase == "model" else cur_step["bc_state"]
                for n in targets(f[0], src, ln, "*BOUNDARY"):
                    for d in range(d1, d2 + 1):
                        tgt[(n, d)] = val
                        if phase == "step":
                            cur_step["bc_inherited"].pop((n, d), None)
            elif kw == "CLOAD":
                d, val = int(f[1]), float(f[2])
                if len(f) != 3 or not (1 <= d <= 6) or not math.isfinite(val):
                    E("cload_shape", f"*CLOAD 数据行非法：{line[:60]}", src, ln)
                for n in targets(f[0], src, ln, "*CLOAD"):
                    cur_step["cl_state"][(n, d)] = val
            elif kw == "STATIC":
                v = _floats(f)
                if len(v) != 4 or not all(math.isfinite(x) and x > 0 for x in v) or v[0] > v[1]:
                    E("procedure_data", f"*STATIC 数据行应为 4 个正数（初始增量 ≤ 时间段）：{line[:60]}", src, ln)
                elif cur_step["period_source"] == "data":
                    E("procedure_data", "*STATIC 有多于一行数据", src, ln)
                else:
                    cur_step["period"], cur_step["period_source"] = v[1], "data"
            elif kw == "ELASTIC":
                v = _floats(f)
                if len(v) != 2 or not (v[0] > 0 and -1.0 < v[1] < 0.5) or st.materials.get(cur_material) is not None:
                    E("material_data", f"*ELASTIC 应恰好一行 E>0、-1<nu<0.5：{line[:60]}", src, ln)
                st.materials[cur_material] = v
            elif kw == "SOLID SECTION":
                v = _floats(f)
                if len(v) != 1 or not v[0] > 0:
                    E("section_data", f"*SOLID SECTION 厚度行非法：{line[:60]}", src, ln)
                if prm.get("ELSET") not in st.elsets or prm.get("MATERIAL") not in st.materials:
                    E("undefined_set", f"*SOLID SECTION 引用未定义 ELSET/MATERIAL：{prm}", src, ln)
            elif kw == "SURFACE BEHAVIOR":
                v = _floats(f)
                if prm.get("PRESSURE-OVERCLOSURE") != "LINEAR" or len(v) != 1 or not v[0] > 0:
                    E("contact_data", f"*SURFACE BEHAVIOR 只接受 LINEAR + 一个正罚刚度：{line[:60]}", src, ln)
            elif kw == "CONTACT PAIR":
                if prm.get("TYPE") not in ("SURFACE TO SURFACE", "MORTAR") or prm.get("INTERACTION") not in st.interactions:
                    E("contact_data", f"*CONTACT PAIR 类型或相互作用不在 profile 内：{prm}", src, ln)
                if len(f) != 2 or any(x.upper() not in st.surfaces for x in f):
                    E("undefined_set", f"*CONTACT PAIR 引用未定义面：{line[:60]}", src, ln)
            elif kw in OUTPUT_KW:
                o = cur_step["outputs"][-1]
                keys = [k.upper() for k in f]
                bad = [k for k in keys if k not in OUTPUT_KEYS[kw]]
                if bad:
                    E("unsupported_output", f"*{kw} 输出变量 {bad} 不在 profile 内", src, ln)
                o["keys"] += [k for k in keys if k not in bad]
            else:
                E("unexpected_data", f"*{kw} 后不应有数据行：{line[:60]}", src, ln)
        except (ValueError, IndexError) as ex:
            E("data_parse", f"*{kw} 数据行无法解析：{line[:60]}（{ex}）", src, ln)
    if eq_pending is not None:
        E("equation_incomplete", "*EQUATION 未写完", None, None)
    if phase == "step":
        E("step_not_closed", f"第 {cur_step['index']} 步到文件末尾仍未 *END STEP", None, None)
        close_step(None, None)
    if not st.steps:
        E("no_step", "没有 *STEP", None, None)
    # 输出请求：只允许在最后一步；引用必须存在；不得重复
    for s in st.steps:
        for o in s["outputs"]:
            kw, p = o["keyword"], o["params"]
            if s is not st.steps[-1]:
                E("output_not_in_final_step", f"第 {s['index']} 步有输出请求 *{kw}（profile 只允许最后一步）", None, o["line"])
            if not o["keys"]:
                E("unsupported_output", f"*{kw} 没有输出变量", None, o["line"])
            for k in o["keys"]:
                sig = (kw, tuple(sorted(p.items())), k)
                if sig in seen_output:
                    E("duplicate_output_request", f"*{kw} {p} {k} 重复请求", None, o["line"])
                seen_output.add(sig)
            if kw in ("NODE PRINT", "NODE FILE") and p.get("NSET") not in st.nsets:
                E("undefined_set", f"*{kw} 引用未定义 NSET {p.get('NSET')}", None, o["line"])
            if kw in ("EL PRINT", "EL FILE") and p.get("ELSET") not in st.elsets:
                E("undefined_set", f"*{kw} 引用未定义 ELSET {p.get('ELSET')}", None, o["line"])
            if kw == "NODE PRINT" and p.get("NSET") in st.nsets and not st.nsets[p["NSET"]]:
                E("empty_set", f"*{kw} 的 NSET {p['NSET']} 为空", None, o["line"])
            if kw == "EL PRINT" and p.get("ELSET") in st.elsets and not st.elsets[p["ELSET"]]:
                E("empty_set", f"*{kw} 的 ELSET {p['ELSET']} 为空", None, o["line"])
            if kw == "CONTACT PRINT":
                for side in ("SLAVE", "MASTER"):
                    if p.get(side) not in st.surfaces or not st.surfaces.get(p.get(side)):
                        E("undefined_set", f"*CONTACT PRINT 引用未定义或空面 {p.get(side)}", None, o["line"])
    st.report = {
        "version": STATE_VERSION, "profile": PROFILE, "pass": not errors, "errors": errors[:50], "error_count": len(errors),
        "steps": [{"index": s["index"], "line": s["line"], "procedure": s["procedure"], "period": s["period"],
                   "period_source": s["period_source"], "bc_op_new": s["bc_op_new"], "cload_op_new": s["cl_op_new"],
                   "bc_count": len(s.get("bc", s["bc_state"])), "cload_count": len(s.get("cload", s["cl_state"])),
                   "bc_inherited_count": len(s["bc_inherited"]),
                   "outputs": [f"*{o['keyword']} {o['params']} {o['keys']}" for o in s["outputs"]]} for s in st.steps],
        "model_bc_count": len(st.base_bc), "equations": len(st.equations),
        "total_time": sum((s["period"] or 0.0) for s in st.steps) if st.steps else None,
    }
    return st


def check_file(inp):
    """run_m37 发算前调用：返回 (DeckState, report)。report['pass'] 为 False 即阻断发算。"""
    try:
        st = analyse_file(inp)
    except (OSError, DeckStateError) as ex:
        return None, {"version": STATE_VERSION, "profile": PROFILE, "pass": False,
                      "errors": [_err("read_failed", f"{type(ex).__name__}: {ex}")], "error_count": 1}
    return st, st.report
