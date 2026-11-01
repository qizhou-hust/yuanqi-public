"""M37 FEA 回传结果入库（gearbase 侧）：校验 → 独立复算收敛 → 证据记录 + 验证阶梯判定。只记录，不进公式图。

  python3 -I gearmath/tools/fea_ingest.py <results.json | M37-results-*.zip> --pack data/m37_fea_pack [--out evidence.json]

（合入 gearbase：原 fea-pack/ingest/ingest_fea_results.py；题目包随包在 data/m37_fea_pack/，测试夹具在 tests/fixtures/m37/。
本模块仅用标准库，不写公式图；重算时从题目包 scripts/ 导入后处理函数，显式实测 profile 可加载内部 fea_prepare。）

做什么
  1. 结构校验：results-schema.json（内置 JSON-Schema 子集校验器，零依赖）；full 模式另要求求解器身份。
  2. 来源一致：results.inputs_sha256 与本地题目包 cases/expected/scripts 逐文件比对（防"跑的不是这一版"）。
  3. 附件一致（输入为 zip 时）：每个 solved 作业须带 .dat，且 sha256 与作业记录一致；可选 --repost 用题目包
     后处理脚本对回传 .dat + .meta.json 重算提取量，与记录比对。
  4. 独立复算：只取各作业逐级原始值（h、penalty、相位、提取量），自行做 Richardson / penalty 外推 / 相位平均，
     不采信 cases[].local_assessment。
  5. 输出与 docs/分路设计报告/L3-fea-tool.md §1.3 证书契约一致的证据记录（ToolResult + Certificate）与
     §3 阶梯判定（逐级解锁）。每条记录 graph_admission.admitted = false：M37 只记录，不写入公式图。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import re
import sys
import zipfile
import functools
import threading
from pathlib import Path

_PACK_IMPORT_LOCK = threading.RLock()
_PACK_MODULES = ('cases', 'ccx_io', 'ccx_strict', 'deck_state', 'gear_geom', 'inp_writer', 'mesh_gmsh', 'post', 'study')

def _readonly_pack_imports(fn):
    """Isolate pack imports for the entire call, including lazy postprocessing imports."""
    @functools.wraps(fn)
    def wrapped(jobs, attachments, pack, *args, **kwargs):
        with _PACK_IMPORT_LOCK:
            old_path = sys.path[:]
            old_flag = sys.dont_write_bytecode
            saved = {name: sys.modules.pop(name) for name in _PACK_MODULES if name in sys.modules}
            try:
                sys.dont_write_bytecode = True
                sys.path.insert(0, str(Path(pack).resolve() / 'scripts'))
                return fn(jobs, attachments, pack, *args, **kwargs)
            finally:
                for name in _PACK_MODULES:
                    sys.modules.pop(name, None)
                sys.modules.update(saved)
                sys.path[:] = old_path
                sys.dont_write_bytecode = old_flag
    return wrapped

EVIDENCE_SCHEMA = "gearbase.fea-evidence/v1"
SOLVER_RANGE = ("2.21", "2.23")

# 验收线：L3-fea-tool.md §3（L0 的位移/力平衡按 .dat 7 位有效数字放宽，见题目说明 L0 节）
ACCEPT = {
    "L0": {"disp_rel_err": 1e-6, "stress_rel_err": 1e-5, "force_balance_rel": 1e-5},
    "L0c": {"pressure_rel_err": 1e-4, "force_balance_rel": 1e-5},
    "L1": {"mesh_last_change": 0.02, "p_max_err": 0.03, "half_width_err": 0.05, "force_err": 1e-3},
    "L2": {"mesh_last_change": 0.02, "band": (0.90, 1.10), "min_points": 12, "force_err": 1e-4},
    "L3": {"mesh_last_change": 0.02, "sigmaH_band": (0.92, 1.08), "c_band": (0.8, 1.2), "phase_change": 0.03,
           "torque_err": 1e-3, "contact_force_err": 1e-3},
}
USES = {"L1": "复核（verification，配合对应几何级）", "L2": "标定 YF·YS（fe_calibrated: YFS）",
        "L3": "标定 c′、cγ（fe_calibrated: c_prime, c_gamma）"}

# 严格字段读取入库门（外部审查 FEA-readiness-R1 R03/T2；R02/R04 的发算前检查与运行身份随同核对）。
# results.json 必须带 field_read_protocol，每个 solved 作业必须带：严格读取记录（读取器版本 + 预先声明的覆盖 +
# accepted）、通过的 STEP 状态检查、三次一致且含求解器可执行文件的运行身份。缺任一项即整包拒绝入库
# （verdict=rejected_field_read）。没有任何旧版本 / 自报豁免路径：1.0 旧包一律拒绝。
STRICT_READER_VERSIONS = ("m37.ccx-strict-dat/1.1",)
STEP_STATE_VERSIONS = ("m37.step-state/1.0",)
IDENTITY_VERSIONS = ("m37.run-identity/1.1",)
CROSSCHECK_VERSIONS = ("m37.contact-crosscheck/1.0",)
COVERAGE_MODES = ("exact_keys", "elements_ip_registered", "rows_within_faces", "statistics_parts")
# 接触行派生量（.dat 只打印活跃接触行，覆盖无法预注册）：阶梯中不得单凭它们授予 passed，须有独立交叉核对。
# 判定用各自已有验收线，不新增门限：L0c 平均压力误差 ≤ ACCEPT["L0c"]["pressure_rel_err"]；p_max 两通道相对差
# ≤ 该量验收带半宽（L1 p_max_err；L3 sigmaH_band 半宽）——两通道之差超过验收带时，验收结论取决于取哪个通道，不可判定。
CONTACT_ROW_KEYS = {"L0c": ("pressure_rel_err", "cf_statistics_mean_pressure"),
                    "L1": ("p_max_MPa", "frd_cpress_final_pstep"), "L3": ("p_max_MPa", "frd_cpress_final_pstep")}


# ================================================================== JSON-Schema 子集校验器
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(v, t):
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def validate(inst, sch, path="$"):
    """支持 type/const/enum/required/properties/additionalProperties/items/minItems/maxItems/minimum/maximum/pattern。"""
    errs = []
    if "const" in sch and inst != sch["const"]:
        return [f"{path}: 应为 {sch['const']!r}"]
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is(inst, t) for t in ts):
            return [f"{path}: 类型应为 {ts}，实为 {type(inst).__name__}"]
    if "enum" in sch and inst not in sch["enum"]:
        errs.append(f"{path}: 取值 {inst!r} 不在 {sch['enum']}")
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            if k not in inst:
                errs.append(f"{path}: 缺少字段 {k}")
        props = sch.get("properties", {})
        for k, v in inst.items():
            if k in props:
                errs += validate(v, props[k], f"{path}.{k}")
            elif sch.get("additionalProperties") is False:
                errs.append(f"{path}: 不允许的字段 {k}")
    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"]:
            errs.append(f"{path}: 至少 {sch['minItems']} 项")
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            errs.append(f"{path}: 至多 {sch['maxItems']} 项（实为 {len(inst)}）")
        if "items" in sch:
            for i, v in enumerate(inst):
                errs += validate(v, sch["items"], f"{path}[{i}]")
    if _is(inst, "number"):
        if "minimum" in sch and inst < sch["minimum"]:
            errs.append(f"{path}: {inst} < {sch['minimum']}")
        if "maximum" in sch and inst > sch["maximum"]:
            errs.append(f"{path}: {inst} > {sch['maximum']}")
    if isinstance(inst, str) and "pattern" in sch and not re.search(sch["pattern"], inst):
        errs.append(f"{path}: {inst!r} 不匹配 {sch['pattern']}")
    return errs


# ================================================================== 独立数值复算
def richardson(hs, fs, p_assumed=2.0):
    """与题目包 post.richardson 独立实现：最细三级、Celik(2008) 非等比迭代；单调且 0.5≤p≤5 用观测阶，否则假定 p=2。"""
    hs, fs = list(hs), list(fs)
    rel = [abs(fs[i + 1] - fs[i]) / abs(fs[i + 1]) for i in range(len(fs) - 1)]
    out = {"levels_h": hs, "values": fs, "relative_changes": rel}
    if len(fs) < 3:
        r = hs[-2] / hs[-1] if len(hs) >= 2 else None
        ext = fs[-1] + (fs[-1] - fs[-2]) / (r ** p_assumed - 1) if r else fs[-1]
        out.update(observed_order=None, order_used=p_assumed, extrapolated=ext, monotone=None,
                   status="fewer_than_three_levels")
        return out
    (h1, h2, h3), (f1, f2, f3) = hs[-3:], fs[-3:]
    r21, r32 = h1 / h2, h2 / h3
    e21, e32 = f2 - f1, f3 - f2
    mono = e21 * e32 > 0
    p = None
    if mono and e32:
        # Solve the signed three-grid power-law equation, including unequal ratios.
        # log(R) = p*log(r32) + log(expm1(p*log(r21))/expm1(p*log(r32))).
        def log_ratio(order):
            a, b = math.log(r21), math.log(r32)
            if abs(order) < 1e-12:
                return math.log(a / b)
            return order * b + math.log(math.expm1(order * a) / math.expm1(order * b))
        target = math.log(abs(e21 / e32))
        lo, hi = -20.0, 20.0
        if log_ratio(lo) <= target <= log_ratio(hi):
            for _ in range(100):
                mid = (lo + hi) / 2
                if log_ratio(mid) < target:
                    lo = mid
                else:
                    hi = mid
            p = (lo + hi) / 2
    used = p if (p is not None and 0.5 <= p <= 5.0) else p_assumed
    ext = f3 + e32 / (r32 ** used - 1)
    out.update(observed_order=p, order_used=used, extrapolated=ext, monotone=mono,
               gci_fine=1.25 * abs(e32) / (r32 ** used - 1) / abs(f3) if f3 else None,
               status="observed_order" if used == p else "assumed_order",
               assumption_reason=None if used == p else ("oscillatory" if not mono else "order_out_of_range_or_unresolved"))
    return out


def penalty_fit(Ks, fs):
    n = len(Ks)
    x = [1 / k for k in Ks]
    mx, mf = sum(x) / n, sum(fs) / n
    sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (f - mf) for a, f in zip(x, fs)) / sxx
    a = mf - b * mx
    i = max(range(n), key=lambda j: Ks[j])
    return {"penalties": list(Ks), "values": list(fs), "model": "f(K) = f_inf - c/K", "f_inf": a, "c": -b,
            "rel_diff_stiffest_vs_inf": abs(fs[i] - a) / abs(a),
            "max_residual_rel": max(abs(f - (a + b * xx)) for f, xx in zip(fs, x)) / abs(a)}


# ================================================================== 读取
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_results(path):
    p = Path(path)
    if p.suffix.lower() == ".zip":
        z = zipfile.ZipFile(p)
        names = set(z.namelist())
        if "results.json" not in names:
            raise SystemExit("zip 中没有 results.json")
        res = json.loads(z.read("results.json").decode("utf-8"))
        att = {n: z.read(n) for n in names if not n.endswith("/")}
        return res, att, sha256_bytes(p.read_bytes())
    b = p.read_bytes()
    return json.loads(b.decode("utf-8")), None, sha256_bytes(b)


def canonical_hash(obj):
    return sha256_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


# ================================================================== 证书与记录
def field_integrity(jobs):
    bad = [j["id"] for j in jobs if j.get("status") != "solved"]
    warn = sorted({w for j in jobs for w in j.get("warnings", [])})
    return {"jobs": [j["id"] for j in jobs], "all_solved": not bad, "not_solved": bad,
            "lint_errors": sum(len(j.get("lint_errors", [])) for j in jobs),
            "min_minSJ": min((j["mesh"]["quality"]["minSJ"]["min"] for j in jobs if j.get("mesh")), default=None),
            "solver_warnings_total": sum((j.get("run") or {}).get("warnings_count", 0) for j in jobs),
            "job_warnings": warn[:20]}


def certificate(method, study, *, rule, accepted, ladder_level, solver, jobs, penalty_study=None,
                phase_study=None, conservation=None):
    st = study or {}
    ext = st.get("extrapolated")
    vals = st.get("values") or []
    return {"property": "numerical_convergence", "kind": "level_refinement",
            "status": "converged" if accepted else "not_converged",
            "method": method, "levels": st.get("levels_h"), "values": vals,
            "relative_changes": st.get("relative_changes"), "assumed_order": 2.0,
            "observed_order": st.get("observed_order"), "order_used": st.get("order_used"),
            "richardson_estimate": ext,
            "discretization_error_estimate": abs(ext - vals[-1]) if (ext is not None and vals) else None,
            "gci_fine": st.get("gci_fine"),
            "penalty_study": penalty_study, "phase_study": phase_study, "conservation": conservation,
            "field_integrity": field_integrity(jobs), "ladder_level": ladder_level,
            "solver_identity": {k: solver.get(k) for k in ("version", "sha256", "version_output", "threads")},
            "accepted": bool(accepted), "rule": rule,
            "meaning": "数值收敛：只说明加密后数值稳定并估计离散误差；不表示模型正确，也不是证据等级"}


def record(quantity, value, unit, ref, band, cert, case_def, tool, validity, note=""):
    ratio = (value / ref["value"]) if (value is not None and ref and ref.get("value")) else None
    within = ratio is not None and band[0] <= ratio <= band[1]
    prov = "fe_verified" if (cert["accepted"] and within) else None
    rec = {"quantity": quantity, "value": value, "unit": unit, "field_summary": None,
           "reference": ref, "ratio_FE_over_reference": ratio, "acceptance_band": list(band), "within_band": within,
           "certificate": cert, "provenance": prov, "provenance_if_admitted": "fe_verified",
           "graph_admission": {"admitted": False, "reason": "M37 记录模式：证据只记录，不进入公式图；入图另需用途对应的阶梯级别与人工批准"},
           "tool": tool, "projection_hash": canonical_hash(case_def), "validity": validity, "note": note}
    rec["record_id"] = canonical_hash({k: rec[k] for k in ("quantity", "value", "projection_hash")})[:16]
    return rec


# ================================================================== 各级判定
def _ok(j):
    return j.get("status") == "solved" and isinstance(j.get("extracted"), dict)


def _x(j, k):
    return (j.get("extracted") or {}).get(k)


def assess_L0(jobs, exp, solver):
    A = ACCEPT
    patch = [j for j in jobs if j["group"] == "patch"]
    cp = [j for j in jobs if j["group"] == "contact_patch"]
    rows, ok = [], bool(patch)
    for j in patch:
        e = j.get("extracted") or {}
        g = _ok(j) and all(e.get(k) is not None and e[k] <= v for k, v in A["L0"].items())
        ok &= g
        rows.append({"job": j["id"], "pass": g, **{k: e.get(k) for k in A["L0"]}})
    pen = [j for j in cp if j["tags"].get("contact") == "penalty"]
    cok = bool(pen)
    for j in cp:
        e = j.get("extracted") or {}
        g = _ok(j) and all(e.get(k) is not None and e[k] <= v for k, v in A["L0c"].items())
        if j["tags"].get("contact") == "penalty":
            cok &= g
        rows.append({"job": j["id"], "pass": g, **{k: e.get(k) for k in A["L0c"]}})
    complete = bool(patch) and bool(pen) and all(j.get("status") != "dry_run" for j in patch + cp)
    return {"own_result": "passed" if ok and cok else ("failed" if complete else "incomplete"), "rows": rows,
            "coord_supported": any(_x(j, "coord_supported") for j in patch)}, []


def assess_L1(jobs, exp, solver, case_def):
    A = ACCEPT["L1"]
    p0, a0 = exp["values"]["p0_MPa"]["value"], exp["values"]["half_width_mm"]["value"]
    routes, recs = {}, []
    mesh = sorted([j for j in jobs if j["group"] == "mesh" and _ok(j)], key=lambda j: j["tags"]["level"])
    nl = len(case_def["mesh"]["contact_divisions"])
    if mesh:
        st = richardson([j["h"] for j in mesh], [_x(j, "p_max_MPa") for j in mesh])
        fine = [j for j in jobs if j["tags"].get("level") == nl - 1 and j["group"] in ("mesh", "penalty") and _ok(j)]
        ps = penalty_fit([j["penalty"] for j in fine], [_x(j, "p_max_MPa") for j in fine]) if len(fine) >= 3 else None
        pf = st["extrapolated"] + ((ps["f_inf"] - _x([j for j in fine if j["group"] == "mesh"][0], "p_max_MPa")) if ps else 0)
        aw = [_x(j, "half_width_mm") for j in mesh]
        ast = richardson([j["h"] for j in mesh], aw) if all(aw) else None
        af = ast["extrapolated"] if ast else None
        ferr = max((_x(j, "contact_normal_force_rel_err") or 0) for j in mesh)
        conv = len(mesh) >= 3 and st["relative_changes"][-1] < A["mesh_last_change"]
        acc = conv and ps is not None and ferr < A["force_err"]
        cert = certificate("CCX 2D CPE6 face-to-face penalty, force control", st, rule=f"三级网格末级变化 <{A['mesh_last_change']}；penalty 三点外推；接触合力误差 <{A['force_err']}",
                           accepted=acc, ladder_level="L1", solver=solver, jobs=mesh + fine, penalty_study=ps,
                           conservation={"max_contact_force_rel_err": ferr})
        r1 = record("hertz_p0", pf, "MPa", {"value": p0, "source": exp.get("source")}, (1 - A["p_max_err"], 1 + A["p_max_err"]),
                    cert, case_def, "ccx_plane_contact_penalty", {"geometry": "two cylinders R=10 mm, plane strain"},
                    note="网格 Richardson 外推 + (penalty→∞ 外推值 − 最细网格同 α 值)")
        r2 = record("hertz_half_width", af, "mm", {"value": a0, "source": exp.get("source")},
                    (1 - A["half_width_err"], 1 + A["half_width_err"]), cert, case_def, "ccx_plane_contact_penalty",
                    {"method": _x(mesh[-1], "half_width_method")})
        recs += [r1, r2]
        routes["penalty"] = r1["within_band"] and r2["within_band"] and acc
    mor = sorted([j for j in jobs if j["group"] == "mortar"], key=lambda j: j["tags"]["level"])
    if mor:
        if all(_ok(j) for j in mor) and len(mor) >= 3:
            st = richardson([j["h"] for j in mor], [_x(j, "p_max_MPa") for j in mor])
            acc = st["relative_changes"][-1] < A["mesh_last_change"]
            cert = certificate("CCX 2D CPE6 MORTAR (no penalty)", st, rule="三级网格末级变化 <2%", accepted=acc,
                               ladder_level="L1", solver=solver, jobs=mor, penalty_study={"note": "mortar：无 penalty"})
            r = record("hertz_p0", st["extrapolated"], "MPa", {"value": p0, "source": exp.get("source")},
                       (1 - A["p_max_err"], 1 + A["p_max_err"]), cert, case_def, "ccx_plane_contact_mortar", {})
            af = _x(mor[-1], "half_width_mm")
            hw_ok = af is not None and abs(af / a0 - 1) < A["half_width_err"]
            recs.append(r)
            routes["mortar"] = r["within_band"] and acc and hw_ok
        else:
            routes["mortar"] = False
    passed = any(routes.values())
    complete = bool(mesh)
    return {"own_result": "passed" if passed else ("failed" if complete else "incomplete"), "routes": routes}, recs


def assess_L2(jobs, exp, solver, case_def):
    A = ACCEPT["L2"]
    recs, rows = [], []
    for pt in case_def["points"]:
        js = sorted([j for j in jobs if j["tags"].get("point") == pt["id"] and _ok(j)], key=lambda j: j["tags"]["level"])
        e = exp["points"][pt["id"]]
        if not js:
            rows.append({"point": pt["id"], "pass": False, "reason": "无已求解作业"})
            continue
        st = richardson([j["h"] for j in js], [_x(j, "YFS_FE") for j in js])
        fb = max((_x(j, "force_balance_rel") or 0) for j in js)
        conv = len(js) >= 3 and st["relative_changes"][-1] < A["mesh_last_change"]
        meth = _x(js[-1], "sigma_root_method") or ""
        acc = conv and fb < A["force_err"]
        cert = certificate("CCX 2D 三齿扇区，HPSTC 力加载，受拉侧过渡曲线 σ1 积分点外推（无节点平滑）", st,
                           rule=f"三级网格末级变化 <{A['mesh_last_change']}；力平衡 <{A['force_err']}", accepted=acc,
                           ladder_level="L2", solver=solver, jobs=js, conservation={"max_force_balance_rel": fb})
        r = record("YFS_root", st["extrapolated"], "1",
                   {"value": e["YFS"], "Y_F": e["Y_F"], "Y_S": e["Y_S"], "source": "gearbase ISO 6336-3:2019 方法 B",
                    "formula_ids": sorted({c.get("id") for c in e["formula_chain"]["Y_F"] + e["formula_chain"]["Y_S"] if c.get("id")})},
                   A["band"], cert, {"pt": pt, "common": case_def["common"], "model": case_def["model"]},
                   "ccx_plane_root_sector", {"z": pt["z"], "x": pt["x"], "rhofP": pt["rhofP"], "mate": case_def["common"]["mate"]},
                   note="" if meth.startswith("gauss_point_polynomial") else "σ 为积分点最大值（未外推），偏低")
        recs.append(r)
        rows.append({"point": pt["id"], "pass": bool(acc and r["within_band"]), "ratio": r["ratio_FE_over_reference"],
                     "converged": conv})
    npass = sum(r["pass"] for r in rows)
    solved_any = any(_ok(j) for j in jobs)
    own = "passed" if (npass == len(rows) and len(rows) >= A["min_points"]) else ("failed" if solved_any else "incomplete")
    return {"own_result": own, "n_pass": npass, "n_points": len(rows), "rows": rows,
            "trend": _trend(rows, case_def)}, recs


def _trend(rows, case_def):
    """偏差趋势（供'可解释'审查）：FE/ISO 对 z、x、ρfP* 的线性相关系数。"""
    pts = {p["id"]: p for p in case_def["points"]}
    data = [(pts[r["point"]], r["ratio"]) for r in rows if r.get("ratio")]
    if len(data) < 4:
        return None
    out = {}
    for k in ("z", "x", "rhofP"):
        xs, ys = [p[k] for p, _ in data], [y for _, y in data]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sx = math.sqrt(sum((a - mx) ** 2 for a in xs)); sy = math.sqrt(sum((b - my) ** 2 for b in ys))
        out[f"corr_ratio_vs_{k}"] = (sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sx * sy)) if sx and sy else None
    return out


def assess_L3(jobs, exp, solver, case_def):
    A = ACCEPT["L3"]
    v = exp["values"]
    nl = len(case_def["mesh"]["contact_divisions"])
    mesh = sorted([j for j in jobs if j["group"] == "mesh" and _ok(j)], key=lambda j: j["tags"]["level"])
    fine = [j for j in jobs if j["tags"].get("level") == nl - 1 and j["group"] in ("mesh", "penalty") and _ok(j)]
    ph = sorted([j for j in jobs if j["group"] == "phase"], key=lambda j: j["tags"]["phase"])
    allj = [j for j in jobs if _ok(j)]
    terr = max(((_x(j, "wheel_torque_rel_err") or 0) for j in allj), default=None)
    cerr = max(((_x(j, "contact_normal_force_rel_err") or 0) for j in allj), default=None)
    cons = {"max_wheel_torque_rel_err": terr, "max_contact_force_rel_err": cerr}
    cons_ok = terr is not None and terr < A["torque_err"] and cerr is not None and cerr < A["contact_force_err"]
    recs, checks = [], {}
    single = all(j.get("pairs_in_contact") == 1 for j in mesh) if mesh else False
    checks["pitch_phase_single_pair"] = single
    for q, key, ref, band, unit in (("sigma_H_C", "p_max_MPa", v["sigma_H_C_hertz"], A["sigmaH_band"], "MPa"),
                                    ("c_prime", "mesh_stiffness_N_per_mm_um", v["c_prime_th_CB"], A["c_band"], "N/(mm*um)")):
        if not mesh:
            checks[q] = False
            continue
        st = richardson([j["h"] for j in mesh], [_x(j, key) for j in mesh])
        ps = None
        val = st["extrapolated"]
        if len(fine) >= 3:
            ps = penalty_fit([j["penalty"] for j in fine], [_x(j, key) for j in fine])
            val += ps["f_inf"] - _x([j for j in fine if j["group"] == "mesh"][0], key)
        conv = len(mesh) >= 3 and st["relative_changes"][-1] < A["mesh_last_change"]
        acc = conv and ps is not None and cons_ok and single
        cert = certificate("CCX 2D 整轮直齿副，扭矩控制，面-面 penalty", st,
                           rule="三级网格末级变化 <2%；penalty 外推；扭矩/接触合力守恒 <1e-3；节点相位单齿对",
                           accepted=acc, ladder_level="L3", solver=solver, jobs=mesh + fine, penalty_study=ps,
                           conservation=cons)
        r = record(q, val, unit, {"value": ref["value"], "source": ref["source"],
                                  "info": {"sigma_H0_with_Zeps": v["sigma_H0"]["value"], "c_prime_ISO_with_CM": v["c_prime_ISO"]["value"]}},
                   band, cert, case_def, "ccx_plane_spur_pair", {"pair": case_def["pair"]})
        recs.append(r)
        checks[q] = bool(acc and r["within_band"])
    if ph and all(_ok(j) for j in ph):
        cs = [_x(j, "mesh_stiffness_N_per_mm_um") for j in ph]
        c16, c8 = sum(cs) / len(cs), sum(cs[0::2]) / len(cs[0::2])
        chg = abs(c16 - c8) / c16
        acc = chg < A["phase_change"] and cons_ok
        cert = certificate("CCX 2D 整轮直齿副，16 相位", None, rule="8/16 相位均值变化 <3%；守恒 <1e-3", accepted=acc,
                           ladder_level="L3", solver=solver, jobs=ph,
                           phase_study={"phases": len(cs), "values": cs, "mean_16": c16, "mean_8_even": c8, "relative_change": chg},
                           conservation=cons)
        cert["values"] = cs
        r = record("c_gamma", c16, "N/(mm*um)", {"value": v["c_gamma_alpha_th"]["value"], "source": v["c_gamma_alpha_th"]["source"],
                                                 "info": {"c_gamma_alpha_ISO": v["c_gamma_alpha_ISO"]["value"]}},
                   A["c_band"], cert, case_def, "ccx_plane_spur_pair", {"pair": case_def["pair"]},
                   note="网格级别为相位研究所用中间级；其网格收敛由 c_prime 记录佐证")
        r["field_summary"] = {"c_phi": cs, "TE_proxy_um_per_N": [1 / c for c in cs]}
        recs.append(r)
        checks["c_gamma"] = bool(acc and r["within_band"])
    else:
        checks["c_gamma"] = False
    checks["conservation"] = cons_ok
    solved_any = bool(allj)
    own = "passed" if all(checks.values()) else ("failed" if solved_any else "incomplete")
    return {"own_result": own, "checks": checks}, recs


# ================================================================== 严格字段读取门
def _job_strict_errors(j, solver_sha=None):
    """单个 solved 作业的严格读取 / 运行身份 / STEP 检查记录核对。返回错误列表（空 = 通过）。"""
    jid, errs = j.get("id"), []
    sr = j.get("strict_read")
    if not isinstance(sr, dict):
        return [f"{jid}: 无严格读取记录"]
    if sr.get("reader_version") not in STRICT_READER_VERSIONS:
        errs.append(f"{jid}: 读取器版本 {sr.get('reader_version')!r} 不被接受")
    if sr.get("status") != "accepted" or sr.get("reasons"):
        errs.append(f"{jid}: 严格读取未通过（{[r.get('code') for r in (sr.get('reasons') or [])][:5]}）")
    decl, fields = sr.get("coverage_declaration") or [], sr.get("fields") or []
    if not decl:
        errs.append(f"{jid}: 无覆盖声明")
    for d in decl:
        if d.get("mode") not in COVERAGE_MODES or not isinstance(d.get("declared_count"), int) or d["declared_count"] < 1:
            errs.append(f"{jid}: 覆盖声明 {d.get('id')} 模式或数量非法")
        if d.get("location") == "contact_row" and (d.get("mode") != "rows_within_faces" or d.get("coverage_unverifiable") is not True):
            errs.append(f"{jid}: 接触行声明 {d.get('id')} 未按面号映射声明或未标 coverage_unverifiable")
    if sorted(d.get("id") or "" for d in decl) != sorted(f.get("id") or "" for f in fields):
        errs.append(f"{jid}: 已读字段与覆盖声明不一一对应")
    ident, fs, exp = sr.get("identity") or {}, sr.get("final_state") or {}, sr.get("expected") or {}
    if ident.get("run_id") != jid:
        errs.append(f"{jid}: 严格读取记录的 run_id {ident.get('run_id')!r} 不是本作业")
    if not j.get("inp_sha256") or ident.get("input_sha256") != j.get("inp_sha256"):
        errs.append(f"{jid}: 严格读取记录的 input_sha256 与作业 inp_sha256 不一致")
    if not j.get("dat_sha256") or ident.get("dat_sha256") != j.get("dat_sha256"):
        errs.append(f"{jid}: 严格读取记录的 dat_sha256 与作业 dat_sha256 不一致")
    if not fs or fs.get("step") != exp.get("final_step"):
        errs.append(f"{jid}: 终态步号与声明不符")
    for f in fields:
        if (f.get("step"), f.get("increment")) != (fs.get("step"), fs.get("increment")) or f.get("run_id") != jid:
            errs.append(f"{jid}: 字段 {f.get('id')} 不属于记录终态或本运行")
    ri = j.get("run_identity")
    if not isinstance(ri, dict) or ri.get("version") not in IDENTITY_VERSIONS:
        errs.append(f"{jid}: 无运行身份记录")
    else:
        dg = [(ri.get(k) or {}).get("digest") for k in ("prepared", "prelaunch", "post")]
        if ri.get("consistent") is not True or None in dg or len(set(dg)) != 1:
            errs.append(f"{jid}: 准备/启动前/结束后三次输入身份不一致或不全")
        elif ((ri["prepared"].get("files") or {}).get("inp") or {}).get("sha256") != j.get("inp_sha256"):
            errs.append(f"{jid}: 运行身份中的 INP 哈希与作业 inp_sha256 不一致")
        elif not solver_sha or ((ri["prepared"].get("files") or {}).get("solver") or {}).get("sha256") != solver_sha:
            errs.append(f"{jid}: 运行身份未含求解器可执行文件，或其 sha256 与 results.solver.sha256 不一致")
    sc = j.get("step_check")
    if not isinstance(sc, dict) or sc.get("version") not in STEP_STATE_VERSIONS or sc.get("pass") is not True \
            or sc.get("input_sha256") != j.get("inp_sha256"):
        errs.append(f"{jid}: 无通过的 STEP 状态检查记录（或与 INP 不对应）")
    return errs


def strict_read_gate(results):
    """返回 {pass: True/False, path, errors}。"""
    jobs = results.get("jobs") or []
    proto = results.get("field_read_protocol")
    if proto is None:
        return {"pass": False, "path": "missing_protocol",
                "errors": ["results.json 没有 field_read_protocol：无法确认字段经严格读取（旧版 1.0 包不入库）"]}
    errs = []
    if not isinstance(proto, dict) or proto.get("reader_version") not in STRICT_READER_VERSIONS \
            or proto.get("step_state_version") not in STEP_STATE_VERSIONS or proto.get("identity_version") not in IDENTITY_VERSIONS \
            or proto.get("contact_crosscheck_version") not in CROSSCHECK_VERSIONS:
        errs.append(f"field_read_protocol 版本不被接受：{proto}")
    solved = [j for j in jobs if j.get("status") == "solved"]
    solver_sha = (results.get("solver") or {}).get("sha256")
    for j in solved:
        errs += _job_strict_errors(j, solver_sha)
    return {"pass": not errs, "path": "strict_protocol", "errors": errs[:50], "error_count": len(errs),
            "jobs_checked": len(solved)}


def _crosscheck(case_key, j, cases):
    """接触行派生量的独立交叉核对。返回 (ok, 原因)。只用已有验收线，见 CONTACT_ROW_KEYS 说明。"""
    key, src = CONTACT_ROW_KEYS[case_key]
    cc = j.get("contact_crosscheck")
    if not isinstance(cc, dict) or cc.get("version") not in CROSSCHECK_VERSIONS:
        return False, "无接触交叉核对记录"
    ent = [e for e in cc.get("entries") or [] if e.get("quantity") == key]
    if len(ent) != 1:
        return False, f"{key} 的交叉核对条目数为 {len(ent)}"
    e, x = ent[0], _x(j, key)
    if x is None or e.get("dat_value") != x:
        return False, f"交叉核对记录的 .dat 值 {e.get('dat_value')} 与提取量 {x} 不一致"
    v = e.get("independent_value")
    if e.get("independent_source") != src or not _is(v, "number"):
        return False, f"没有可用的独立通道（需要 {src}）：{e.get('unavailable', '')}"[:300]
    if case_key == "L0c":
        q = cases["L0"]["contact_patch"]["load"]["pressure_MPa"]
        dev, tol = abs(v - q) / q, ACCEPT["L0c"]["pressure_rel_err"]
    else:
        lo, hi = (1 - ACCEPT["L1"]["p_max_err"], 1 + ACCEPT["L1"]["p_max_err"]) if case_key == "L1" else ACCEPT["L3"]["sigmaH_band"]
        dev, tol = (abs(v / x - 1) if x else math.inf), max(1 - lo, hi - 1)
    return (dev <= tol), f"{src}: 偏差 {dev:.3g}，容许 {tol:.3g}"


def _cap_contact(c, res, jobs, cases):
    """阶梯封顶：接触行派生量没有通过独立交叉核对的作业，不能支撑 passed（只把 passed 降级，不改 failed）。"""
    if c == "L0":
        rel = {"L0c": [j for j in jobs if j["group"] == "contact_patch" and j["tags"].get("contact") == "penalty" and _ok(j)]}
    elif c == "L1":
        rel = {"L1": [j for j in jobs if j["group"] in ("mesh", "penalty", "mortar") and _ok(j)]}
    elif c == "L3":
        rel = {"L3": [j for j in jobs if j["group"] in ("mesh", "penalty") and _ok(j)]}
    else:
        return res
    (ck, js), = rel.items()
    bad = {}
    for j in js:
        ok, why = _crosscheck(ck, j, cases)
        if not ok:
            bad[j["id"]] = why
    res["contact_crosscheck"] = {"checked": len(js), "unverified": bad,
                                 "rule": "接触行覆盖无法预注册：依赖其的量须与独立通道在原验收线内一致"}
    was = res["own_result"]
    if c == "L1":
        if res["routes"].get("penalty") and any(j["id"] in bad for j in js if j["group"] in ("mesh", "penalty")):
            res["routes"]["penalty"] = False
        if res["routes"].get("mortar") and any(j["id"] in bad for j in js if j["group"] == "mortar"):
            res["routes"]["mortar"] = False
        if was == "passed" and not any(res["routes"].values()):
            res["own_result"] = "contact_unverified"
    elif c == "L3":
        if res["checks"].get("sigma_H_C") and bad:
            res["checks"]["sigma_H_C"] = False
            if was == "passed":
                res["own_result"] = "contact_unverified"
    elif was == "passed" and bad:
        res["own_result"] = "contact_unverified"
    return res


@_readonly_pack_imports
def strict_repost_check(jobs, attachments, pack, reader=None):
    """入库复核：用题目包 ccx_strict 按记录中的覆盖声明重读回传 .dat/.sta，状态与逐字段 values_sha256 须与记录一致。"""
    try:
        import ccx_strict as canonical_reader
    except Exception as ex:   # noqa: BLE001
        return {"pass": False, "error": f"无法导入 ccx_strict：{ex}"}
    ccx_strict = reader or canonical_reader
    bad, n, skipped = [], 0, []
    for j in jobs:
        sr = j.get("strict_read")
        if j.get("status") != "solved" or not isinstance(sr, dict):
            continue
        base = f"runs/{j['case']}/{j['id']}"
        if base + ".dat" not in attachments or base + ".sta" not in attachments:
            skipped.append(j["id"])
            continue
        exp = sr.get("expected") or {}
        frd_key = base + ".frd"
        if sr.get("pstep") is not None and frd_key not in attachments:
            bad.append({"job": j["id"], "repost_status": "not_reverified", "reasons": ["frd_not_attached"], "mismatch": []})
            continue
        rec, _ = ccx_strict.strict_record(
            attachments[base + ".dat"].decode("utf-8", "replace"), attachments[base + ".sta"].decode("utf-8", "replace"),
            ccx_strict.requests_from_record(sr), expected_final_step=exp.get("final_step"),
            expected_total_time=exp.get("total_time"),
            identity={"run_id": j["id"], "input_sha256": (sr.get("identity") or {}).get("input_sha256")},
            frd_text=attachments[frd_key].decode("utf-8", "replace") if sr.get("pstep") is not None else None,
            solver_version=sr.get("solver_version"))
        n += 1
        got = {f["id"]: f["values_sha256"] for f in rec.get("fields", [])}
        claim = {f.get("id"): f.get("values_sha256") for f in sr.get("fields", [])}
        if rec["status"] != "accepted" or got != claim:
            bad.append({"job": j["id"], "repost_status": rec["status"],
                        "reasons": [r["code"] for r in rec.get("reasons", [])][:10],
                        "mismatch": sorted(k for k in set(got) | set(claim) if got.get(k) != claim.get(k))[:10]})
            continue
        # 交叉核对的 .frd 独立值：附件中有 .frd 时重算
        for e in (j.get("contact_crosscheck") or {}).get("entries") or []:
            if e.get("independent_source") == "frd_cpress_final_pstep" and frd_key in attachments:
                try:
                    pm, _n = ccx_strict.frd_contact_cpress_max(attachments[frd_key].decode("utf-8", "replace"),
                                                               *(e.get("state") or [None, None]))
                except ccx_strict.StrictReadError as ex:
                    pm = str(ex)
                if pm != e.get("independent_value"):
                    bad.append({"job": j["id"], "repost_status": "crosscheck_mismatch", "reasons": ["frd_cpress"],
                                "mismatch": [e.get("quantity")]})
    return {"pass": not bad and not skipped, "jobs_reread": n, "not_attached": skipped[:20], "failures": bad[:20]}


# ================================================================== 主流程
def ingest(results, pack, attachments=None, repost=False, source_sha=None, verified_profile=None):
    pack = Path(pack)
    out = {"schema": EVIDENCE_SCHEMA, "ingested_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": {"results_sha256": source_sha, "pack_version": results.get("pack_version"),
                      "mode": results.get("mode"), "machine": results.get("machine"), "solver": results.get("solver")},
           "checks": {}, "warnings": [], "records": [], "ladder": {}}
    out['checks']['numerical_method'] = {'richardson': 'signed-unequal-grid/1', 'ingest_sha256': sha256_bytes(Path(__file__).read_bytes())}
    schema = json.loads((pack / "results-schema.json").read_text(encoding="utf-8"))
    serr = validate(results, schema)
    if results.get("mode") == "full":
        sv = results.get("solver") or {}
        for k in ("version_output", "sha256", "version"):
            if not sv.get(k):
                serr.append(f"$.solver: full 模式缺 {k}")
    out["checks"]["schema"] = {"pass": not serr, "errors": serr[:50]}
    if serr:
        out["verdict"] = "rejected_schema"
        return out
    # 来源一致
    mism = []
    for rel, h in (results.get("inputs_sha256") or {}).items():
        f = pack / rel
        if f.is_file():
            if sha256_bytes(f.read_bytes()) != h:
                mism.append(rel)
        else:
            mism.append(rel + "（本地缺）")
    expected_files = [f"expected/{p.name}" for p in (pack / "expected").glob("*.json")]
    missing_exp = [e for e in expected_files if e not in (results.get("inputs_sha256") or {})]
    out["checks"]["inputs_match_pack"] = {"pass": not mism and not missing_exp, "mismatch": mism, "not_reported": missing_exp}
    reader = None
    if verified_profile is not None:
        from . import fea_prepare
        if not repost or attachments is None or mism or missing_exp:
            raise ValueError('verified profile requires matching pack and attached raw repost')
        if pack.resolve() != fea_prepare.PACK.resolve():
            raise ValueError('verified profile requires the bundled pack')
        for name in ('cases.py', 'study.py', 'mesh_gmsh.py', 'inp_writer.py', 'gear_geom.py', 'ccx_io.py', 'post.py', 'run_m37.py', 'deck_state.py', 'ccx_strict.py'):
            rel = 'scripts/' + name
            if (results.get('inputs_sha256') or {}).get(rel) != fea_prepare.sha(pack / rel):
                raise ValueError('profile source identity mismatch: ' + rel)
        probe_dir, solver_path = verified_profile
        reader = fea_prepare.verified_profile(probe_dir, solver_path)
        if (results.get('solver') or {}).get('sha256') != fea_prepare.sha(solver_path) or (results.get('solver') or {}).get('version') != '2.23':
            raise ValueError('profile solver identity or version mismatch')
        import tempfile
        for j in results['jobs']:
            if j.get('status') != 'solved':
                continue
            if j.get('case') != 'L2' or j.get('group') != 'mesh':
                raise ValueError('verified profile currently supports L2 mesh jobs only')
            extracted = j.get('extracted') or {}
            if any(not _is(extracted.get(key), 'number') or not math.isfinite(extracted[key]) for key in ('YFS_FE', 'force_balance_rel')):
                raise ValueError('profile required extracted quantity missing or nonfinite')
            case_file = 'cases/L2_yfs_matrix.json'
            if (results.get('inputs_sha256') or {}).get(case_file) != fea_prepare.sha(pack / case_file):
                raise ValueError('L2 case identity mismatch')
            base = f"runs/L2/{j['id']}"
            inp, meta = attachments.get(base + '.inp'), attachments.get(base + '.meta.json')
            dat, sta = attachments.get(base + '.dat'), attachments.get(base + '.sta')
            files = ((j.get('run_identity') or {}).get('prepared') or {}).get('files') or {}
            if not inp or not meta or sha256_bytes(inp) != j.get('inp_sha256') or sha256_bytes(meta) != (files.get('metadata') or {}).get('sha256'):
                raise ValueError('profile input or metadata identity mismatch')
            sr_identity = (j.get('strict_read') or {}).get('identity') or {}
            if not dat or not sta or sha256_bytes(dat) != j.get('dat_sha256') or sha256_bytes(dat) != sr_identity.get('dat_sha256') or sha256_bytes(sta) != sr_identity.get('sta_sha256'):
                raise ValueError('profile raw output identity mismatch')
            m = json.loads(meta.decode('utf-8'))
            points = json.loads((pack / case_file).read_text(encoding='utf-8'))['points']
            point = next((p for p in points if p['id'] == j.get('tags', {}).get('point')), None)
            if m.get('case') != 'L2' or m.get('point') != point or point is None or m.get('level') != j.get('tags', {}).get('level') or m.get('h') != j.get('h'):
                raise ValueError('profile case or mesh metadata mismatch')
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / 'job.inp'
                path.write_bytes(inp)
                state, report = fea_prepare.deck_state.check_file(path)
                sr = j.get('strict_read') or {}
                if not report.get('pass') or report.get('includes') or state.expectation() != {'expected_final_step': (sr.get('expected') or {}).get('final_step'), 'expected_total_time': (sr.get('expected') or {}).get('total_time')}:
                    raise ValueError('profile deck state mismatch')
                actual = state.strict_requests()
                # Re-read directly against the deck, rather than trusting a claimed declaration.
                rec, _ = reader.strict_record(attachments.get(base + '.dat', b'').decode('utf-8', 'replace'), attachments.get(base + '.sta', b'').decode('utf-8', 'replace'), actual, identity={'run_id': j['id'], 'input_sha256': j['inp_sha256']}, solver_version='2.23', **state.expectation())
                if state.frd_requested() or rec.get('status') != 'accepted' or rec.get('coverage_declaration') != sr.get('coverage_declaration') or [f['values_sha256'] for f in rec.get('fields', [])] != [f['values_sha256'] for f in sr.get('fields', [])]:
                    raise ValueError('profile deck-derived raw read mismatch')
        out['checks']['verified_profile'] = {'name': 'v017_verified_probe', 'solver_sha256': fea_prepare.sha(solver_path)}
    # 严格字段读取门：没有严格读取记录（读取器版本 + 覆盖声明 + 通过）的结果包拒绝入库
    gate = strict_read_gate(results)
    out["checks"]["strict_field_read"] = gate
    if gate["pass"] is False:
        out["verdict"] = "rejected_field_read"
        return out

    if mism:
        out["warnings"].append(f"回传结果对应的输入与本地题目包不一致：{mism[:10]}（判定照算，但不能作为本版证据）")
    ver = (results.get("solver") or {}).get("version")
    if results.get("mode") == "full" and not (ver and SOLVER_RANGE[0] <= ver <= SOLVER_RANGE[1]):
        out["warnings"].append(f"ccx 版本 {ver} 不在 {SOLVER_RANGE}")
    # 附件
    jobs = results["jobs"]
    if attachments is not None:
        miss, bad = [], []
        for j in jobs:
            if j.get("status") != "solved":
                continue
            key = f"runs/{j['case']}/{j['id']}.dat"
            if key not in attachments:
                miss.append(key)
            elif j.get("dat_sha256") and sha256_bytes(attachments[key]) != j["dat_sha256"]:
                bad.append(key)
        frd = [n for n in attachments if n.endswith(".frd")]
        out["checks"]["attachments"] = {"pass": not miss and not bad, "missing_dat": miss[:20], "sha_mismatch": bad[:20],
                                        "frd_included": len(frd)}
        if repost:
            out["checks"]["repost"] = repost_check(jobs, attachments, pack)
            if verified_profile is not None and not out["checks"]["repost"].get("pass"):
                out["verdict"] = "rejected_field_read"
                return out
            if gate["pass"] is True:
                out["checks"]["strict_repost"] = srp = strict_repost_check(jobs, attachments, pack, reader)
                if not srp["pass"]:
                    out["verdict"] = "rejected_field_read"
                    return out
    # 分级
    cases = {c: json.loads((pack / "cases" / f).read_text(encoding="utf-8")) for c, f in
             (("L0", "L0_patch.json"), ("L1", "L1_hertz.json"), ("L2", "L2_yfs_matrix.json"), ("L3", "L3_C001_G1.json"))}
    exps = {c: json.loads((pack / "expected" / f).read_text(encoding="utf-8")) for c, f in
            (("L0", "L0_patch.json"), ("L1", "L1_hertz.json"), ("L2", "L2_yfs_matrix.json"), ("L3", "L3_C001_G1.json"))}
    solver = results.get("solver") or {}
    by = {c: [j for j in jobs if j["case"] == c] for c in ("L0", "L1", "L2", "L3")}
    own = {}
    for c in ("L0", "L1", "L2", "L3"):
        if not by[c]:
            own[c] = {"own_result": "not_run"}
            continue
        if c == "L0":
            res, recs = assess_L0(by[c], exps[c], solver)
        else:
            res, recs = {"L1": assess_L1, "L2": assess_L2, "L3": assess_L3}[c](by[c], exps[c], solver, cases[c])
        res = _cap_contact(c, res, by[c], cases)
        own[c] = res
        out["records"] += recs
    lower_ok = True
    for c in ("L0", "L1", "L2", "L3"):
        o = own[c]["own_result"]
        status = o if lower_ok else ("blocked_by_lower_level" if o != "not_run" else "not_run")
        out["ladder"][c] = {"status": status, **own[c], "unlocks_if_passed": USES.get(c)}
        lower_ok = lower_ok and o == "passed"
    passed = [c for c in ("L0", "L1", "L2", "L3") if out["ladder"][c]["status"] == "passed"]
    out["ladder_level_reached"] = passed[-1] if passed else None
    for r in out["records"]:
        lv = r["certificate"]["ladder_level"]
        r["certificate"]["ladder_level_reached_by_toolchain"] = out["ladder_level_reached"]
        if out["ladder"][lv]["status"] != "passed":
            r["provenance"] = None
    out["verdict"] = "recorded"
    out["summary"] = {c: out["ladder"][c]["status"] for c in out["ladder"]}
    return out


@_readonly_pack_imports
def repost_check(jobs, attachments, pack):
    """用题目包后处理函数重算回传 .dat（需要同目录 .meta.json），与作业记录的提取量逐项比对。"""
    try:
        import ccx_io
        import cases as C
    except Exception as ex:   # noqa: BLE001
        return {"pass": None, "error": f"无法导入题目包脚本：{ex}"}
    import tempfile
    posts = {"L0": C.post_L0, "L0c": C.post_L0c, "L1": C.post_L1, "L2": C.post_L2, "L3": C.post_L3}
    diffs, n = [], 0
    for j in jobs:
        if j.get("status") != "solved":
            continue
        base = f"runs/{j['case']}/{j['id']}"
        if base + ".dat" not in attachments or base + ".meta.json" not in attachments:
            continue
        meta = json.loads(attachments[base + ".meta.json"].decode("utf-8"))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.dat"
            p.write_bytes(attachments[base + ".dat"])
            fn = posts["L0c" if j["id"].startswith("L0c") else j["case"]]
            ex, _ = fn(meta, ccx_io.parse_dat(p))
        n += 1
        for k, v in (j.get("extracted") or {}).items():
            if isinstance(v, float) and k in ex and isinstance(ex[k], float):
                if abs(ex[k] - v) > 1e-9 * max(1.0, abs(v)) and not k.startswith("half_width"):
                    diffs.append({"job": j["id"], "key": k, "record": v, "repost": ex[k]})
    return {"pass": not diffs, "jobs_reposted": n, "diffs": diffs[:20],
            "note": "L1 半宽若来自 .frd（未回传）则不比对"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out")
    ap.add_argument("--repost", action="store_true", help="zip 输入时，用题目包后处理重算回传 .dat")
    a = ap.parse_args(argv)
    res, att, sha = load_results(a.results)
    ev = ingest(res, a.pack, att, a.repost, sha)
    txt = json.dumps(ev, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    print(json.dumps({"verdict": ev["verdict"], "ladder": ev.get("summary"), "warnings": ev["warnings"],
                      "schema_errors": ev["checks"]["schema"]["errors"][:5]}, ensure_ascii=False, indent=1))
    return 0 if ev["verdict"] == "recorded" else 2


if __name__ == "__main__":
    sys.exit(main())
