"""M37 严格字段读取器（外部审查 FEA-readiness-R1 R03 / 待办 T2）。零依赖。

与 ccx_io.py 的 last_block / nodal / ip_table / contact_tables 并列，不替换、不改变它们的行为：
旧读取器按"最后一个标题匹配的块"取值，不核对时刻、覆盖与唯一性；本模块按以下契约读取，任何一条不满足即拒绝。

契约（READER_VERSION 变化即契约变化）：
  1. 终态由 .sta 决定：最后一条已收敛记录的 (step, increment, total time)。若给出 .frd（调用方只在 deck 请求了
     *... FILE 输出时给出），其中必须有 1PSTEP 行，且最后一个 PSTEP 的 (step, increment) 必须与 .sta 一致；
     给了 .frd 却没有 PSTEP 即拒绝（不静默跳过）。打印时刻相同的不同增量（如 step2 的 inc4 与 inc5 都
     打印 time 2）是合法情形：按 (step, increment) 选择，不按打印时刻选择，也不判为冲突。
  2. .dat 中每个字段块都绑定 S T E P / INCREMENT 标记给出的 (step, increment)、标题中的 time、字段名、
     set/region、位置（node / element_ip / contact_row / statistics）与分量表；没有状态标记的块不可用。
  3. 调用方必须预先声明期望终步号、期望总时间、运行身份（run_id、input_sha256）以及每个请求字段的覆盖：
     exact_keys（节点号或 (单元, 积分点) 全集）；elements_ip_registered（单元全集 × 积分点 1..n，n 由
     IP_REGISTRY 按 (求解器版本, 单元类型) 预注册，未注册即拒绝）；rows_within_faces（接触行：每行 (单元, 面号)
     必须是声明的从面 (单元, deck 边号) 经 FACE_REGISTRY 映射后的结果，未注册即拒绝；.dat 只打印活跃接触行，
     完整覆盖无法预注册，记录中标 coverage_unverifiable=True，依赖这些行的量不得单凭它们授予验收）；
     statistics_parts（接触统计：声明的每个分项恰好一行）。空覆盖本身即拒绝。
  4. 拒绝：缺块、终态内重复块（无论数值一致或冲突）、终态之后的块、时刻不符、分量表不符、行形状不符、
     缺行、重复键、多余键、非有限值、空块、孤立数值行、.sta 缺失/格式不明/不单调/终步或终时刻与声明不符。

时刻容差（按输出格式预注册，不是数值调参）：.sta 的 TOT TIME 为 6 位尾数（0.dddddd E±xx），最坏半单位相对误差
5e-6；.dat 标题时刻为 7 位尾数，最坏 5e-7。两者相加 TIME_REL_TOL = 5.5e-6。

注册表均为实测登记，不是手册条文；不在表内的 (版本, 单元类型[, 边号]) 一律拒绝，不外推：
  - IP_REGISTRY：ccx 2.21（Ubuntu calculix-ccx 2.21-1，/usr/bin/ccx sha256 6adaabf5…faa1b）实测 CPE6 展开后每单元 9 个
    积分点、CPE8 为 27 个，.dat 单元号与 deck 相同（lanes/F2/REPORT.md §3）。
  - FACE_REGISTRY：2D 边号 n ↔ .dat 面号 n+2。ccx 2.21：L0c 从面 S1→3、L1 从面 S3→5（F2 §3）；ccx 2.23：ph10
    PFL 从面 S3→5，4038 行（F3 / 审查 G-02）。其余边号（如 CPE6 S2、全部 CPE8 边）没有实测，未登记。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

READER_VERSION = "m37.ccx-strict-dat/1.1"
TIME_REL_TOL = 5.5e-6
ALL_CONTACT = "ALL_CONTACT_ELEMENTS"

# 字段名 → (位置, 标题分量表)。标题分量表按 CCX .dat 原样（去空格、小写）；键列：node 1 列，element_ip 2 列，
# contact_row 2 列（slave element+face 占两列：单元号、面号）。
FIELD_FORMATS = {
    "displacements": ("node", ("vx", "vy", "vz")),
    "forces": ("node", ("fx", "fy", "fz")),
    "stresses": ("element_ip", ("elem", "integ.pnt.", "sxx", "syy", "szz", "sxy", "sxz", "syz")),
    "global coordinates": ("element_ip", ("elem", "integ.pnt.", "x", "y", "z")),
    "contact stress": ("contact_row", ("slave element+face", "press", "tang1", "tang2")),
    "relative contact displacement": ("contact_row", ("slave element+face", "normal", "tang1", "tang2")),
}
KEY_COLS = {"node": 1, "element_ip": 2, "contact_row": 2}
KEY_HEADER_COMPS = {"node": 0, "element_ip": 2, "contact_row": 1}     # 标题分量表中属于键的项数
STAT_PARTS = {
    "total surface force": (re.compile(r"^total surface force \(fx,fy,fz\) and moment about the origin\s*\(mx,my,mz\)$"), 6),
    "center of gravity and mean normal": (re.compile(r"^center of gravity and mean normal$"), 6),
    "moment about the center of gravity": (re.compile(r"^moment about the center of gravity\s*\(mx,my,mz\)$"), 3),
    "area normal shear": (re.compile(r"^area,\s+normal force \(\+ = tension\) and shear force \(size\)$"), 3),
}
COVERAGE_MODES = ("exact_keys", "elements_ip_registered", "rows_within_faces", "statistics_parts")
RETIRED_MODES = {"elements_exact_ip_uniform": "积分点数须按 (求解器版本, 单元类型) 预注册（IP_REGISTRY）",
                 "rows_within_elements": "接触行须按 (单元, deck 边号) 声明并经 FACE_REGISTRY 映射核对"}
# (ccx 版本, 单元类型) → 每单元积分点数（实测登记，见模块说明）
IP_REGISTRY = {("2.21", "CPE6"): 9, ("2.21", "CPE8"): 27}
# (ccx 版本, 单元类型) → {deck 2D 边号: .dat 面号}（实测登记，见模块说明）
FACE_REGISTRY = {("2.21", "CPE6"): {1: 3, 3: 5}, ("2.23", "CPE6"): {3: 5}}
REGISTRY_EVIDENCE = {"ip": "lanes/F2/REPORT.md §3（ccx 2.21 实测）",
                     "face": "lanes/F2/REPORT.md §3（ccx 2.21：S1→3、S3→5）；F3/审查 G-02 ph10（ccx 2.23：S3→5，4038 行）",
                     "nature": "实测登记，非手册条文"}

_STEP_RE = re.compile(r"^S\s+T\s+E\s+P\s+(\d+)$")
_INC_RE = re.compile(r"^INCREMENT\s+(\d+)$")
_FIELD_RE = re.compile(r"^(?P<field>[a-z][a-z ]*?)\s*\((?P<comps>[^)]*)\)\s+for\s+(?:set\s+(?P<set>\S+)|(?P<all>all contact elements))"
                       r"\s+and\s+time\s+(?P<time>\S+)$")
_STAT_RE = re.compile(r"^statistics for slave set (?P<slave>\S+), master set (?P<master>\S+) and time\s+(?P<time>\S+)$")


class StrictReadError(ValueError):
    """严格读取被拒绝。reasons：[{code, detail, ...}]；record：可 JSON 化的 rejected 记录。"""

    def __init__(self, reasons, record=None):
        self.reasons = list(reasons)
        self.record = record
        super().__init__("; ".join(f"{r['code']}: {r['detail']}" for r in self.reasons))

    @property
    def codes(self):
        return {r["code"] for r in self.reasons}


# ------------------------------------------------------------------ 小工具
def _num(tok):
    return float(tok.replace("D", "E").replace("d", "e"))


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compact_ints(values):
    """升序整数 → [[a, b], ...] 闭区间；用于在记录中完整保存声明覆盖（可重建），不是摘要。"""
    out = []
    for v in sorted(set(int(x) for x in values)):
        if out and v == out[-1][1] + 1:
            out[-1][1] = v
        else:
            out.append([v, v])
    return out


def expand_ints(ranges):
    return [v for a, b in ranges for v in range(int(a), int(b) + 1)]


def _time_close(a, b):
    return abs(a - b) <= TIME_REL_TOL * max(abs(a), abs(b), 1e-30)


def _reason(code, detail, **ctx):
    r = {"code": code, "detail": detail}
    r.update(ctx)
    return r


# ------------------------------------------------------------------ .sta / .frd
def parse_sta_text(text):
    """返回 (rows, problems)。rows：[{line, step, increment, attempt, unconverged, iterations, total_time, step_time,
    inc_time}]。表头两行之外的任何非空行若不是 7 列记录即为 problem（不猜测）。"""
    rows, problems = [], []
    for ln, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        up = s.upper()
        if up.startswith("SUMMARY OF JOB INFORMATION") or up.split()[:2] == ["STEP", "INC"]:
            continue
        t = s.split()
        m = re.fullmatch(r"(\d+)(U?)", t[2]) if len(t) == 7 else None
        if not m:
            problems.append(_reason("sta_malformed", f".sta 第 {ln} 行无法按 7 列记录解析：{s[:80]}", line=ln))
            continue
        try:
            row = {"line": ln, "step": int(t[0]), "increment": int(t[1]), "attempt": int(m.group(1)),
                   "unconverged": bool(m.group(2)), "iterations": int(t[3]), "total_time": _num(t[4]),
                   "step_time": _num(t[5]), "inc_time": _num(t[6])}
        except ValueError:
            problems.append(_reason("sta_malformed", f".sta 第 {ln} 行数值无法解析：{s[:80]}", line=ln))
            continue
        if not all(math.isfinite(row[k]) for k in ("total_time", "step_time", "inc_time")):
            problems.append(_reason("sta_malformed", f".sta 第 {ln} 行含非有限时间", line=ln))
            continue
        rows.append(row)
    return rows, problems


def sta_final_state(text):
    """.sta → 终态 dict；不满足即抛 StrictReadError。"""
    rows, problems = parse_sta_text(text)
    reasons = list(problems)
    conv = [r for r in rows if not r["unconverged"]]
    if not conv:
        reasons.append(_reason("sta_empty", ".sta 没有任何已收敛增量记录"))
    else:
        for a, b in zip(conv, conv[1:]):
            if (b["step"], b["increment"]) <= (a["step"], a["increment"]) or b["total_time"] < a["total_time"]:
                reasons.append(_reason("sta_nonmonotonic", f".sta 第 {b['line']} 行 (step,inc,time) 不单调", line=b["line"]))
        if rows and rows[-1]["unconverged"]:
            reasons.append(_reason("sta_final_unconverged", f".sta 最后一行（第 {rows[-1]['line']} 行）为未收敛尝试"))
    if reasons:
        raise StrictReadError(reasons)
    f = conv[-1]
    return {"step": f["step"], "increment": f["increment"], "total_time": f["total_time"], "step_time": f["step_time"],
            "sta_line": f["line"], "sta_converged_rows": len(conv)}


def frd_pstep_states(text):
    """.frd 中 1PSTEP 行 → [(step, increment)]（按出现顺序）。格式：'1PSTEP  <n>  <increment>  <step>'。"""
    out = []
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("1PSTEP"):
            t = s.split()
            try:
                out.append((int(t[-1]), int(t[-2])))
            except (ValueError, IndexError):
                raise StrictReadError([_reason("pstep_malformed", f"无法解析 1PSTEP 行：{s[:80]}")])
    return out


def frd_contact_cpress_max(text, step, increment):
    """.frd 中 (step, increment) 状态唯一的 CONTACT 节点块 → (max |CPRESS|, 节点数)。缺块 / 重复 / 无 CPRESS /
    空 / 非有限即抛 StrictReadError。状态由块前的 1PSTEP 行给出（与 frd_pstep_states 同一格式）。"""
    state, mode, name, comps, data, found = None, None, None, [], {}, []
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("1PSTEP"):
            t = s.split()
            state = (int(t[-1]), int(t[-2]))
            continue
        key = raw[:3].strip()
        if raw.startswith("  100C"):
            mode, name, comps, data = "res", None, [], {}
            continue
        if mode != "res":
            continue
        if key == "-4":
            name = raw[5:13].strip().upper()
        elif key == "-5":
            comps.append(raw[5:13].strip().upper())
        elif key == "-1":
            nid = int(raw[3:13])
            rest = raw[13:].rstrip("\n")
            vals = [float(rest[k:k + 12]) for k in range(0, len(rest), 12) if rest[k:k + 12].strip()]
            if nid in data:
                raise StrictReadError([_reason("frd_duplicate_node", f".frd {name} 块节点 {nid} 重复")])
            data[nid] = vals
        elif key == "-3":
            if name == "CONTACT":
                found.append((state, comps, data))
            mode = None
    hits = [f for f in found if f[0] == (step, increment)]
    if len(hits) != 1:
        raise StrictReadError([_reason("frd_contact_block", f".frd 中 step {step} inc {increment} 的 CONTACT 块数为 "
                                       f"{len(hits)}（应为 1）")])
    _, comps, data = hits[0]
    if "CPRESS" not in comps or not data:
        raise StrictReadError([_reason("frd_contact_block", ".frd CONTACT 块没有 CPRESS 分量或为空")])
    i = comps.index("CPRESS")
    vals = [v[i] for v in data.values()]
    if not all(math.isfinite(v) for v in vals):
        raise StrictReadError([_reason("nonfinite", ".frd CPRESS 含非有限值")])
    return max(abs(v) for v in vals), len(vals)


# ------------------------------------------------------------------ .dat 扫描
def scan_dat(text):
    """把 .dat 切成带状态的块。返回 {'blocks': [...], 'unknown': [...], 'orphan_rows': [行号...]}。
    块：field {kind, field, components, region, time, step, increment, line, header, rows:[(行号, [数值])]}；
        statistics {kind, slave, master, time, step, increment, line, header, parts:{name:[part块]}}；
        part {kind:'stat_part', name, line, header, rows}；unknown {kind, line, header, rows}。"""
    blocks, unknown, orphans = [], [], []
    step = inc = None
    cur = stat = None
    for ln, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        m = _STEP_RE.match(s)
        if m:
            step, inc, cur, stat = int(m.group(1)), None, None, None
            continue
        m = _INC_RE.match(s)
        if m:
            inc, cur, stat = int(m.group(1)), None, None
            continue
        try:
            vals = [_num(t) for t in s.split()]
        except ValueError:
            vals = None
        if vals is not None:
            if cur is None:
                orphans.append(ln)
            else:
                cur["rows"].append((ln, vals))
            continue
        low = " ".join(s.lower().split())
        m = _FIELD_RE.match(low)
        if m:
            try:
                t = _num(m.group("time"))
            except ValueError:
                t = float("nan")
            comps = tuple(c.strip() for c in m.group("comps").split(","))
            region = ALL_CONTACT if m.group("all") else m.group("set").upper()
            cur = {"kind": "field", "field": m.group("field").strip(), "components": comps, "region": region,
                   "time": t, "step": step, "increment": inc, "line": ln, "header": s, "rows": []}
            blocks.append(cur)
            stat = None
            continue
        m = _STAT_RE.match(low)
        if m:
            try:
                t = _num(m.group("time"))
            except ValueError:
                t = float("nan")
            stat = {"kind": "statistics", "slave": m.group("slave").upper(), "master": m.group("master").upper(),
                    "time": t, "step": step, "increment": inc, "line": ln, "header": s, "parts": {}}
            blocks.append(stat)
            cur = None
            continue
        part = next((name for name, (rx, _) in STAT_PARTS.items() if rx.match(low)), None)
        if part is not None and stat is not None:
            cur = {"kind": "stat_part", "name": part, "line": ln, "header": s, "rows": []}
            stat["parts"].setdefault(part, []).append(cur)
            continue
        cur = {"kind": "unknown", "line": ln, "header": s, "rows": [], "step": step, "increment": inc}
        unknown.append(cur)
        stat = None
    return {"blocks": blocks, "unknown": unknown, "orphan_rows": orphans}


# ------------------------------------------------------------------ 请求（覆盖声明）
def field_request(field, region, components, coverage, rid=None):
    """构造字段请求。coverage：{'mode': 'exact_keys', 'keys': [...]} 等；见模块说明。"""
    loc = FIELD_FORMATS[field][0] if field in FIELD_FORMATS else None
    return {"id": rid or f"{field}@{region}", "kind": "field", "field": field, "region": region.upper(),
            "location": loc, "components": list(components), "coverage": coverage}


def statistics_request(slave, master, parts=tuple(STAT_PARTS), rid=None):
    return {"id": rid or f"statistics@{slave.upper()}/{master.upper()}", "kind": "statistics", "slave": slave.upper(),
            "master": master.upper(), "location": "statistics", "coverage": {"mode": "statistics_parts", "parts": list(parts)}}


def _norm_keys(location, keys):
    if location == "node":
        return {int(k) for k in keys}
    return {(int(k[0]), int(k[1])) for k in keys}


def _validate_request(rq, solver_version=None):
    """返回 (问题列表, 规范化覆盖)。积分点与接触面模式需要 solver_version 查注册表。"""
    probs = []
    cov = rq.get("coverage") or {}
    mode = cov.get("mode")
    rid = rq.get("id")
    if mode in RETIRED_MODES:
        return [_reason("request_invalid", f"{rid}: 覆盖模式 {mode} 已停用：{RETIRED_MODES[mode]}", request=rid)], None
    if mode not in COVERAGE_MODES:
        return [_reason("request_invalid", f"{rid}: 未知覆盖模式 {mode!r}", request=rid)], None
    if rq.get("kind") == "statistics":
        parts = cov.get("parts") or []
        if not parts:
            probs.append(_reason("empty_coverage", f"{rid}: 统计分项为空", request=rid))
        bad = [p for p in parts if p not in STAT_PARTS]
        if bad:
            probs.append(_reason("request_invalid", f"{rid}: 未知统计分项 {bad}", request=rid))
        return probs, {"mode": mode, "parts": list(parts)}
    fmt = FIELD_FORMATS.get(rq.get("field"))
    if fmt is None:
        return [_reason("request_invalid", f"{rid}: 不支持的字段 {rq.get('field')!r}", request=rid)], None
    loc, comps = fmt
    if rq.get("location") != loc:
        probs.append(_reason("request_invalid", f"{rid}: 位置 {rq.get('location')} 与字段格式 {loc} 不符", request=rid))
    if tuple(rq.get("components") or ()) != comps:
        probs.append(_reason("request_invalid", f"{rid}: 声明分量 {rq.get('components')} 与格式 {list(comps)} 不符",
                             request=rid))
    norm = {"mode": mode}
    if mode == "exact_keys":
        if loc == "contact_row":
            probs.append(_reason("request_invalid", f"{rid}: 接触行没有唯一键，不能用 exact_keys", request=rid))
        keys = _norm_keys(loc, cov.get("keys") or [])
        if not keys:
            probs.append(_reason("empty_coverage", f"{rid}: 声明覆盖为空", request=rid))
        norm["keys"] = keys
    elif mode == "elements_ip_registered":
        groups = {g: {int(e) for e in els} for g, els in (cov.get("element_groups") or {}).items()}
        if loc != "element_ip":
            probs.append(_reason("request_invalid", f"{rid}: {mode} 只用于积分点字段", request=rid))
        allel = [e for s in groups.values() for e in s]
        if not allel:
            probs.append(_reason("empty_coverage", f"{rid}: 声明单元集合为空", request=rid))
        if len(allel) != len(set(allel)):
            probs.append(_reason("request_invalid", f"{rid}: 单元组之间重叠", request=rid))
        nips = {}
        for g in groups:
            n = IP_REGISTRY.get((solver_version, g))
            if n is None:
                probs.append(_reason("registry_missing", f"{rid}: (ccx {solver_version!r}, {g}) 的积分点数未登记，拒绝读取",
                                     request=rid))
            nips[g] = n
        norm["element_groups"], norm["ip_per_element"] = groups, nips
        norm["keys"] = {(e, ip) for g, els in groups.items() if nips.get(g) for e in els for ip in range(1, nips[g] + 1)}
    elif mode == "rows_within_faces":
        if loc != "contact_row":
            probs.append(_reason("request_invalid", f"{rid}: {mode} 只用于接触行", request=rid))
        faces = {(int(e), int(sd)) for e, sd in cov.get("faces") or []}
        types = {int(e): t for e, t in (cov.get("element_types") or {}).items()}
        if not faces:
            probs.append(_reason("empty_coverage", f"{rid}: 声明从面为空", request=rid))
        allowed, missing = set(), set()
        for e, sd in faces:
            m = FACE_REGISTRY.get((solver_version, types.get(e)), {})
            if sd not in m:
                missing.add((solver_version, types.get(e), sd))
            else:
                allowed.add((e, m[sd]))
        if missing:
            probs.append(_reason("registry_missing", f"{rid}: 面号映射未登记 {sorted(missing, key=str)[:5]}，拒绝读取",
                                 request=rid))
        norm["faces"], norm["element_types"], norm["allowed"] = faces, types, allowed
    else:
        probs.append(_reason("request_invalid", f"{rid}: 字段请求不能用 {mode}", request=rid))
    return probs, norm


def _declaration_entry(rq, norm):
    """记录中保存的覆盖声明：完整、可重建（区间压缩），另附摘要哈希。"""
    e = {k: rq.get(k) for k in ("id", "kind", "field", "region", "slave", "master", "location", "components") if k in rq}
    mode = norm["mode"]
    e["mode"] = mode
    if mode == "exact_keys":
        keys = sorted(norm["keys"])
        if rq["location"] == "node":
            e["keys_ranges"] = compact_ints(keys)
        else:
            e["keys_pairs"] = [list(k) for k in keys]
        e["declared_count"] = len(keys)
        e["declared_sha256"] = canonical_sha([list(k) if isinstance(k, tuple) else k for k in keys])
    elif mode == "elements_ip_registered":
        e["element_groups_ranges"] = {g: compact_ints(s) for g, s in sorted(norm["element_groups"].items())}
        e["ip_per_element_registered"] = dict(sorted(norm["ip_per_element"].items()))
        e["declared_count"] = len(norm["keys"])
        e["declared_sha256"] = canonical_sha({g: sorted(s) for g, s in norm["element_groups"].items()})
    elif mode == "rows_within_faces":
        by = {}
        for el, sd in sorted(norm["faces"]):
            by.setdefault(norm["element_types"][el], {}).setdefault(str(sd), []).append(el)
        e["faces_by_type_side"] = {t: {sd: compact_ints(v) for sd, v in d.items()} for t, d in sorted(by.items())}
        e["face_map_registered"] = {t: FACE_REGISTRY.get((rq.get("_solver_version"), t)) for t in by}
        e["declared_count"] = len(norm["faces"])
        e["declared_sha256"] = canonical_sha(sorted(list(f) for f in norm["faces"]))
        e["coverage_unverifiable"] = True
    else:
        e["parts"] = list(norm["parts"])
        e["declared_count"] = len(norm["parts"])
        e["declared_sha256"] = canonical_sha(list(norm["parts"]))
    return e


def requests_from_record(record):
    """由记录中的 coverage_declaration 重建请求（入库复核用）。"""
    out = []
    for e in record.get("coverage_declaration") or []:
        mode = e.get("mode")
        if e.get("kind") == "statistics":
            out.append(statistics_request(e["slave"], e["master"], e.get("parts") or [], rid=e.get("id")))
            continue
        if mode == "exact_keys":
            keys = expand_ints(e["keys_ranges"]) if "keys_ranges" in e else [tuple(k) for k in e.get("keys_pairs", [])]
            cov = {"mode": mode, "keys": keys}
        elif mode == "elements_ip_registered":
            cov = {"mode": mode, "element_groups": {g: expand_ints(r) for g, r in e["element_groups_ranges"].items()}}
        elif mode == "rows_within_faces":
            faces, types = [], {}
            for t, d in e["faces_by_type_side"].items():
                for sd, r in d.items():
                    for el in expand_ints(r):
                        faces.append([el, int(sd)])
                        types[el] = t
            cov = {"mode": mode, "faces": faces, "element_types": types}
        else:
            cov = {"mode": mode}
        out.append(field_request(e["field"], e["region"], e["components"], cov, rid=e.get("id")))
    return out


# ------------------------------------------------------------------ 主读取
def _state_key(b):
    return (b["step"], b["increment"])


def _select(cands, final, rid, what):
    """按状态挑块：无状态标记 / 终态之后 / 终态内 0 个或多于 1 个 → 拒绝。返回 (块或 None, reasons)。"""
    reasons = []
    fk = (final["step"], final["increment"])
    for b in cands:
        if b["step"] is None or b["increment"] is None:
            reasons.append(_reason("no_state_marker", f"{rid}: 第 {b['line']} 行 {what} 块之前没有 STEP/INCREMENT 标记",
                                   request=rid, line=b["line"]))
        elif _state_key(b) > fk:
            reasons.append(_reason("state_beyond_sta", f"{rid}: 第 {b['line']} 行块属于 step {b['step']} inc "
                                   f"{b['increment']}，晚于 .sta 终态 {fk}", request=rid, line=b["line"]))
    inf = [b for b in cands if b["step"] is not None and b["increment"] is not None and _state_key(b) == fk]
    if not inf:
        reasons.append(_reason("missing_block", f"{rid}: 终态 step {fk[0]} inc {fk[1]} 中没有 {what} 块", request=rid))
        return None, reasons
    if len(inf) > 1:
        reasons.append(_reason("duplicate_final_block", f"{rid}: 终态中有 {len(inf)} 个 {what} 块（行 "
                               f"{[b['line'] for b in inf]}），不以最后一块覆盖", request=rid, lines=[b["line"] for b in inf]))
    for b in inf:
        if not (math.isfinite(b["time"]) and _time_close(b["time"], final["total_time"])):
            reasons.append(_reason("time_mismatch", f"{rid}: 第 {b['line']} 行块时刻 {b['time']} 与 .sta 终态总时间 "
                                   f"{final['total_time']} 不符", request=rid, line=b["line"]))
    return inf[-1], reasons


def _check_rows(rid, rows, width):
    reasons = []
    if not rows:
        reasons.append(_reason("empty_block", f"{rid}: 块没有数据行", request=rid))
    for ln, v in rows:
        if len(v) != width:
            reasons.append(_reason("row_shape", f"{rid}: 第 {ln} 行有 {len(v)} 列，应为 {width}", request=rid, line=ln))
        elif not all(math.isfinite(x) for x in v):
            reasons.append(_reason("nonfinite", f"{rid}: 第 {ln} 行含非有限值", request=rid, line=ln))
    return reasons


def _int_key(x):
    return int(x) if float(x).is_integer() else None


def _read_field(rq, norm, scan, final):
    rid, loc = rq["id"], rq["location"]
    cands = [b for b in scan["blocks"] if b["kind"] == "field" and b["field"] == rq["field"] and b["region"] == rq["region"]]
    blk, reasons = _select(cands, final, rid, f"{rq['field']} / {rq['region']}")
    if blk is None:
        return None, None, reasons
    if tuple(blk["components"]) != tuple(rq["components"]):
        reasons.append(_reason("component_mismatch", f"{rid}: 第 {blk['line']} 行标题分量 {list(blk['components'])} 与声明 "
                               f"{rq['components']} 不符", request=rid, line=blk["line"]))
        return blk, None, reasons
    ncomp = len(rq["components"]) - KEY_HEADER_COMPS[loc]
    width = KEY_COLS[loc] + ncomp
    reasons += _check_rows(rid, blk["rows"], width)
    if reasons:
        return blk, None, reasons
    obs = {}
    if loc == "contact_row":
        allowed = norm["allowed"]
        dec_el = {e for e, _ in norm["faces"]}
        rows = []
        for ln, v in blk["rows"]:
            e, f = _int_key(v[0]), _int_key(v[1])
            if e is None or f is None:
                reasons.append(_reason("row_shape", f"{rid}: 第 {ln} 行单元/面号不是整数", request=rid, line=ln))
            elif e not in dec_el:
                reasons.append(_reason("unexpected_key", f"{rid}: 第 {ln} 行单元 {e} 不在声明的从面内", request=rid, line=ln))
            elif (e, f) not in allowed:
                reasons.append(_reason("face_mismatch", f"{rid}: 第 {ln} 行 (单元 {e}, .dat 面 {f}) 与 deck 从面经注册映射"
                                       "后的面号不一致", request=rid, line=ln))
            rows.append(v)
        obs = {"rows": len(rows), "distinct_faces": len({(int(r[0]), int(r[1])) for r in rows}),
               "declared_faces": len(norm["faces"]), "faces_observed": sorted({int(r[1]) for r in rows})[:10],
               "face_mapping": "FACE_REGISTRY（实测登记，非手册条文）", "coverage_unverifiable": True,
               "note": ".dat 只打印活跃接触行；行缺失或冲突重复行无法由本读取器发现，依赖这些行的量须独立交叉核对"}
        return blk, (rows, obs), reasons
    values, dup = {}, []
    for ln, v in blk["rows"]:
        if loc == "node":
            k = _int_key(v[0])
            bad = k is None
        else:
            k = (_int_key(v[0]), _int_key(v[1]))
            bad = None in k
        if bad:
            reasons.append(_reason("row_shape", f"{rid}: 第 {ln} 行键不是整数", request=rid, line=ln))
            continue
        if k in values:
            dup.append((ln, k))
            continue
        values[k] = v[KEY_COLS[loc]:]
    for ln, k in dup:
        reasons.append(_reason("duplicate_key", f"{rid}: 第 {ln} 行键 {k} 重复（不以后行覆盖）", request=rid, line=ln))
    got = set(values)
    if norm["mode"] == "exact_keys":
        miss, extra = sorted(norm["keys"] - got), sorted(got - norm["keys"])
        if miss:
            reasons.append(_reason("missing_key", f"{rid}: 缺 {len(miss)} 个声明键，如 {miss[:5]}", request=rid, count=len(miss)))
        if extra:
            reasons.append(_reason("unexpected_key", f"{rid}: 多出 {len(extra)} 个未声明键，如 {extra[:5]}", request=rid,
                                   count=len(extra)))
        obs = {"keys": len(got)}
    else:   # elements_ip_registered：键集合由注册表预先确定，与 exact_keys 同样精确比较
        miss, extra = sorted(norm["keys"] - got), sorted(got - norm["keys"])
        if miss:
            reasons.append(_reason("missing_key", f"{rid}: 缺 {len(miss)} 个 (单元, 积分点)，如 {miss[:5]}（注册积分点数 "
                                   f"{norm['ip_per_element']}）", request=rid, count=len(miss)))
        if extra:
            reasons.append(_reason("unexpected_key", f"{rid}: 多出 {len(extra)} 个 (单元, 积分点)，如 {extra[:5]}", request=rid,
                                   count=len(extra)))
        obs = {"keys": len(got), "ip_per_element_registered": norm["ip_per_element"], "ip_count_source": "IP_REGISTRY"}
    return blk, (values, obs), reasons


def _read_statistics(rq, norm, scan, final):
    rid = rq["id"]
    cands = [b for b in scan["blocks"] if b["kind"] == "statistics" and b["slave"] == rq["slave"] and b["master"] == rq["master"]]
    blk, reasons = _select(cands, final, rid, f"statistics {rq['slave']}/{rq['master']}")
    if blk is None:
        return None, None, reasons
    vals = {}
    for p in norm["parts"]:
        parts = blk["parts"].get(p, [])
        if not parts:
            reasons.append(_reason("statistics_missing_part", f"{rid}: 第 {blk['line']} 行统计块缺分项 {p!r}", request=rid))
            continue
        if len(parts) > 1:
            reasons.append(_reason("statistics_duplicate_part", f"{rid}: 统计分项 {p!r} 出现 {len(parts)} 次", request=rid))
            continue
        rows = parts[0]["rows"]
        n = STAT_PARTS[p][1]
        if len(rows) != 1:
            reasons.append(_reason("row_shape", f"{rid}: 统计分项 {p!r} 有 {len(rows)} 行，应为 1", request=rid))
            continue
        reasons += _check_rows(f"{rid}/{p}", rows, n)
        vals[p] = rows[0][1]
    return blk, (vals, {"parts": sorted(vals)}), reasons


def read_strict(dat_text, sta_text, requests, *, expected_final_step, expected_total_time, identity, frd_text=None,
                solver_version=None):
    """严格读取。成功返回 {'record': 可 JSON 化记录, 'values': {request_id: 值}}；失败抛 StrictReadError（.record 为
    rejected 记录）。identity 必须含 run_id 与 input_sha256（运行/输入身份）。"""
    reasons = []
    ident = dict(identity or {})
    for k in ("run_id", "input_sha256"):
        if not ident.get(k):
            reasons.append(_reason("identity_missing", f"缺少运行身份字段 {k}"))
    ident["dat_sha256"] = sha256_text(dat_text) if dat_text is not None else None
    ident["sta_sha256"] = sha256_text(sta_text) if sta_text is not None else None
    expected = {"final_step": expected_final_step, "total_time": expected_total_time}
    if not isinstance(expected_final_step, int) or expected_final_step < 1:
        reasons.append(_reason("expectation_missing", f"期望终步号未声明或非法：{expected_final_step!r}"))
    if not isinstance(expected_total_time, (int, float)) or not math.isfinite(expected_total_time) or expected_total_time <= 0:
        reasons.append(_reason("expectation_missing", f"期望总时间未声明或非法：{expected_total_time!r}"))
    decl, norms = [], []
    if not requests:
        reasons.append(_reason("empty_coverage", "没有任何字段请求（覆盖声明为空）"))
    ids = [rq.get("id") for rq in requests or []]
    if len(ids) != len(set(ids)):
        reasons.append(_reason("request_invalid", f"请求 id 重复：{ids}"))
    for rq in requests or []:
        rq = dict(rq, _solver_version=solver_version)
        p, norm = _validate_request(rq, solver_version)
        reasons += p
        norms.append(norm)
        if norm is not None and not p:
            decl.append(_declaration_entry(rq, norm))
    record = {"reader_version": READER_VERSION, "status": "rejected", "reasons": [], "identity": ident,
              "expected": expected, "final_state": None, "pstep": None, "coverage_declaration": decl, "fields": [],
              "unrecognised_headers": [], "orphan_rows": 0, "time_rel_tol": TIME_REL_TOL, "solver_version": solver_version,
              "registry_evidence": REGISTRY_EVIDENCE}

    def fail(rs):
        record["reasons"] = rs
        raise StrictReadError(rs, record)

    if dat_text is None:
        reasons.append(_reason("no_dat", "没有 .dat"))
    if sta_text is None:
        reasons.append(_reason("no_sta", "没有 .sta：终态无法确定"))
    if reasons:
        fail(reasons)
    try:
        final = sta_final_state(sta_text)
    except StrictReadError as ex:
        fail(reasons + ex.reasons)
    record["final_state"] = final
    if final["step"] != expected_final_step:
        reasons.append(_reason("sta_final_step_mismatch", f".sta 终态 step {final['step']} 与声明终步 {expected_final_step} 不符"))
    if not _time_close(final["total_time"], expected_total_time):
        reasons.append(_reason("sta_final_time_mismatch", f".sta 终态总时间 {final['total_time']} 与声明 {expected_total_time} 不符"))
    if frd_text is not None:
        try:
            ps = frd_pstep_states(frd_text)
        except StrictReadError as ex:
            ps = None
            reasons += ex.reasons
        if ps is not None and not ps:
            reasons.append(_reason("pstep_missing", "给出了 .frd 但其中没有 1PSTEP 行：终态交叉核对无法进行"))
        if ps:
            record["pstep"] = {"step": ps[-1][0], "increment": ps[-1][1], "count": len(ps)}
            if ps[-1] != (final["step"], final["increment"]):
                reasons.append(_reason("pstep_mismatch", f".frd 最后 PSTEP {ps[-1]} 与 .sta 终态 "
                                       f"{(final['step'], final['increment'])} 不符"))
    scan = scan_dat(dat_text)
    record["unrecognised_headers"] = [{"line": u["line"], "header": u["header"][:120]} for u in scan["unknown"]][:20]
    record["orphan_rows"] = len(scan["orphan_rows"])
    if scan["orphan_rows"]:
        reasons.append(_reason("orphan_rows", f".dat 有 {len(scan['orphan_rows'])} 行数值不属于任何标题，如第 "
                               f"{scan['orphan_rows'][:3]} 行"))
    values = {}
    for rq, norm in zip(requests, norms):
        if norm is None:
            continue
        if rq["kind"] == "statistics":
            blk, got, rs = _read_statistics(rq, norm, scan, final)
        else:
            blk, got, rs = _read_field(rq, norm, scan, final)
        reasons += rs
        if blk is None or got is None or rs:
            continue
        val, obs = got
        values[rq["id"]] = val
        jv = {str(k): v for k, v in val.items()} if isinstance(val, dict) else val
        record["fields"].append({
            "id": rq["id"], "run_id": ident.get("run_id"), "input_sha256": ident.get("input_sha256"),
            "step": blk["step"], "increment": blk["increment"], "time": blk["time"],
            "field": rq.get("field", "statistics"), "region": rq.get("region") or f"{rq['slave']}/{rq['master']}",
            "location": rq["location"], "components": rq.get("components") or norm.get("parts"),
            "header_line": blk["line"], "header": blk["header"][:160], "coverage_mode": norm["mode"],
            "coverage_observed": obs, "values_sha256": canonical_sha(jv)})
    if reasons:
        fail(reasons)
    record["status"] = "accepted"
    return {"record": record, "values": values}


def strict_record(dat_text, sta_text, requests, **kw):
    """不抛异常的包装：返回 (record, values 或 None)。"""
    try:
        r = read_strict(dat_text, sta_text, requests, **kw)
        return r["record"], r["values"]
    except StrictReadError as ex:
        return ex.record, None


def _read_opt(p):
    p = Path(p) if p is not None else None
    return p.read_text(errors="replace") if (p is not None and p.is_file()) else None


def read_strict_files(dat_path, sta_path, requests, *, frd_path=None, **kw):
    """文件版：缺文件按 no_dat / no_sta 拒绝；.frd 只用于 PSTEP 一致性（可省略）。"""
    return read_strict(_read_opt(dat_path), _read_opt(sta_path), requests, frd_text=_read_opt(frd_path), **kw)
