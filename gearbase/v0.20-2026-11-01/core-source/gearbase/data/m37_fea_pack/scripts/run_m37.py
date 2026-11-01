#!/usr/bin/env python3
"""M37 FEA 题目包一键运行：生成网格与 .inp → 调用 CalculiX → 后处理 → 收敛外推 → results/results.json。

  python run_m37.py --ccx <ccx 可执行文件> [--threads 4] [--cases L0,L1,L2,L3]
  python run_m37.py --dry-run           # 只生成网格与 .inp 并自检，不求解（不需要 ccx）
  python run_m37.py --smoke --ccx ...   # 约 1–3 分钟的工具链冒烟测试（L0 + L1 最粗级）

依赖：Python ≥ 3.10、gmsh Python 包（pip install gmsh）。不联网、不下载。
可中断续跑：已求解的作业（存在 <job>.record.json、.inp 未变且已有当前版本的严格读取与运行身份记录）会跳过；
--force 全部重算。

发算门（外部审查 FEA-readiness-R1 R02/R03/R04）：
  - 发算前：deck_state 受限 STEP 状态机检查（过程卡位置、重复过程、空步、未闭合、BC/CLOAD 继承与覆盖、profile 外语法），
    不通过即记 lint_failed，不启动求解器；dry-run 同样执行并记录。
  - 运行身份：准备时（建模后）、启动前、结束后三次计算 INP、<job>.meta.json、INP 中显式 *INCLUDE 文件与求解器
    可执行文件（readlink -f 后）的 sha256；
    启动前不一致则不启动，结束后不一致则该次运行记 solver_failed（failure=input_identity_drift_postrun），保留全部输出。
  - 结束后：ccx_strict 按 deck 预先声明的覆盖严格读取 .dat/.sta（终态以 .sta 为准）；被拒绝则记 post_failed。
    旧后处理（ccx_io.last_block 等）照旧计算提取量，但须与严格读取的同一块逐值一致。
  - 接触行（.dat 只打印活跃行，覆盖无法预注册）派生的量另做独立交叉核对（contact_crosscheck）：p_max 对 .frd 终态
    CONTACT/CPRESS（deck 请求了 *CONTACT FILE 时），L0c 压力误差对接触统计的平均压力 |Fn|/area。判定在入库端做。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")      # Windows 非 UTF-8 控制台下中文输出不致报错
    except Exception:  # noqa: BLE001
        pass
sys.path.insert(0, str(HERE))

import ccx_io  # noqa: E402
import ccx_strict  # noqa: E402
import deck_state  # noqa: E402
import study   # noqa: E402

PACK = HERE.parent
PACK_VERSION = "M37-FEA-pack 1.1 (2026-10-30)"
IDENTITY_VERSION = "m37.run-identity/1.1"
CROSSCHECK_VERSION = "m37.contact-crosscheck/1.0"
FIELD_READ_PROTOCOL = {"reader_version": ccx_strict.READER_VERSION, "step_state_version": deck_state.STATE_VERSION,
                       "identity_version": IDENTITY_VERSION, "contact_crosscheck_version": CROSSCHECK_VERSION}
CASE_FILES = {"L0": "L0_patch.json", "L1": "L1_hertz.json", "L2": "L2_yfs_matrix.json", "L3": "L3_C001_G1.json"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def machine_info():
    info = {"platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0], "hostname_sha8":
            hashlib.sha256(platform.node().encode()).hexdigest()[:8]}
    try:
        import gmsh
        gmsh.initialize()
        info["gmsh_version"] = gmsh.option.getString("General.Version")
        gmsh.finalize()
    except Exception as ex:      # noqa: BLE001
        info["gmsh_version"] = f"unavailable: {ex}"
    try:
        if sys.platform.startswith("linux"):
            for ln in Path("/proc/meminfo").read_text().splitlines():
                if ln.startswith("MemTotal"):
                    info["mem_total_kB"] = int(ln.split()[1])
    except Exception:            # noqa: BLE001
        pass
    return info


# ------------------------------------------------------------------ 运行身份（R04）
def input_identity(inp, meta_path, exe=None):
    """INP、metadata、INP 中显式 *INCLUDE 文件与求解器可执行文件（readlink -f 后）的 sha256 快照。
    缺文件记 missing（与任何正常快照都不相等）。exe 为 None（dry-run）时求解器项记 missing。"""
    inp, meta_path = Path(inp), Path(meta_path)

    def one(p, label):
        p = Path(p)
        return {"path": label, "sha256": ccx_io.sha256(p) if p.is_file() else None, "missing": not p.is_file()}
    files = {"inp": one(inp, inp.name), "metadata": one(meta_path, meta_path.name), "includes": []}
    if exe is None:
        files["solver"] = {"path": None, "sha256": None, "missing": True}
    else:
        rp = Path(exe).resolve()
        files["solver"] = one(rp, str(rp))
    if inp.is_file():
        try:
            files["includes"] = [one(p, raw) for raw, p in deck_state.include_paths(inp)]
        except deck_state.DeckStateError as ex:
            files["include_error"] = str(ex)
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"files": files, "digest": digest, "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}


def identity_drift(a, b):
    """两次快照之间变化的文件（标签列表）。"""
    out = []
    for k in ("inp", "metadata", "solver"):
        if a["files"].get(k) != b["files"].get(k):
            out.append(k)
    ia = {d["path"]: d for d in a["files"]["includes"]}
    ib = {d["path"]: d for d in b["files"]["includes"]}
    out += [f"include:{p}" for p in sorted(set(ia) | set(ib)) if ia.get(p) != ib.get(p)]
    if a["files"].get("include_error") != b["files"].get("include_error"):
        out.append("include_error")
    return out


def _out_hashes(inp):
    return {sfx: (ccx_io.sha256(inp.with_suffix(sfx)) if inp.with_suffix(sfx).is_file() else None)
            for sfx in (".dat", ".sta", ".frd", ".log", ".cvg")}


def preflight(inp, meta_path, exe=None):
    """建模后的发算前检查（R02）+ 准备时身份（R04）。返回 (DeckState 或 None, step_check, prepared_identity)。"""
    prepared = input_identity(inp, meta_path, exe)
    st, report = deck_state.check_file(inp)
    step_check = {k: report.get(k) for k in ("version", "profile", "pass", "errors", "error_count", "steps", "total_time",
                                             "includes")}
    step_check["input_sha256"] = prepared["files"]["inp"]["sha256"]
    return st, step_check, prepared


def execute_job(exe, inp, meta_path, prepared, run_id, threads=1, timeout_s=3600, state=None, solver_version=None):
    """启动前身份 → 求解 → 结束后身份 → 严格读取。返回 dict：status（solved/solver_failed/post_failed）、failure、
    run、run_identity、strict_read、strict_values（仅内存）、outputs_sha256。不删除任何输出文件。"""
    inp, meta_path = Path(inp), Path(meta_path)
    ident = {"version": IDENTITY_VERSION, "prepared": prepared}
    out = {"status": None, "failure": None, "run": None, "run_identity": ident, "strict_read": None, "strict_values": None}
    pre = input_identity(inp, meta_path, exe)
    ident["prelaunch"] = pre
    drift = identity_drift(prepared, pre)
    if drift:
        ident.update(consistent=False, drift_stage="prelaunch", drift=drift)
        out.update(status="solver_failed", failure="input_identity_drift_prelaunch")
        return out                                   # 不启动求解器
    run = ccx_io.run_job(Path(exe).resolve(), inp, threads, timeout_s)    # 启动已哈希的解析后路径
    out["run"] = run
    post = input_identity(inp, meta_path, exe)
    ident["post"] = post
    drift = identity_drift(prepared, post)
    out["outputs_sha256"] = _out_hashes(inp)
    if drift:
        ident.update(consistent=False, drift_stage="postrun", drift=drift)
        out.update(status="solver_failed", failure="input_identity_drift_postrun")
        return out                                   # 输出全部保留，不做后处理
    ident["consistent"] = True
    if not run["ok"]:
        out.update(status="solver_failed", failure="solver_run_not_ok")
        return out
    if state is None:
        state, report = deck_state.check_file(inp)
        if not report.get("pass"):
            out.update(status="post_failed", failure="step_check_failed_after_run")
            return out
    reqs = state.strict_requests()
    rec, vals = ccx_strict.strict_record(
        *(inp.with_suffix(s).read_text(errors="replace") if inp.with_suffix(s).is_file() else None for s in (".dat", ".sta")),
        reqs, identity={"run_id": run_id, "input_sha256": prepared["files"]["inp"]["sha256"]},
        frd_text=(inp.with_suffix(".frd").read_text(errors="replace") if inp.with_suffix(".frd").is_file() else "")
        if state.frd_requested() else None,
        solver_version=solver_version, **state.expectation())
    out["strict_read"], out["strict_values"] = rec, vals
    if rec["status"] != "accepted":
        out.update(status="post_failed", failure="strict_field_read_rejected")
        return out
    out["status"] = "solved"
    return out


def contact_crosscheck(job_id, meta, extracted, strict_record, strict_values, inp, state):
    """接触行派生量的独立交叉核对数据（只记录数值，判定在入库端按其验收线做）。
    p_max_MPa：对 .frd 终态（与 .sta 终态同一 PSTEP）CONTACT 块的 max|CPRESS|；deck 未请求 *CONTACT FILE 时记 unavailable。
    pressure_rel_err（L0c）：对接触统计 area/normal force 给出的平均压力 |Fn|/area。"""
    entries = []
    fs = strict_record.get("final_state") or {}
    cstr = [f for f in strict_record["fields"] if f["field"] == "contact stress"]
    if "p_max_MPa" in extracted and cstr:
        dat_max = max(abs(r[2]) for r in strict_values[cstr[0]["id"]])
        e = {"quantity": "p_max_MPa", "dat_value": dat_max, "dat_source": f"strict {cstr[0]['id']}"}
        frd = inp.with_suffix(".frd")
        if state.frd_requested() and frd.is_file():
            try:
                pm, n = ccx_strict.frd_contact_cpress_max(frd.read_text(errors="replace"), fs["step"], fs["increment"])
                e.update(independent_source="frd_cpress_final_pstep", independent_value=pm, frd_nodes=n,
                         frd_sha256=ccx_io.sha256(frd), state=[fs["step"], fs["increment"]])
            except ccx_strict.StrictReadError as ex:
                e.update(independent_source=None, unavailable=str(ex)[:300])
        else:
            e.update(independent_source=None, unavailable="deck 未请求 *CONTACT FILE：没有独立的 CPRESS 通道")
        entries.append(e)
    if job_id.startswith("L0c") and "pressure_rel_err" in extracted:
        cf = [f for f in strict_record["fields"] if f["location"] == "statistics"]
        e = {"quantity": "pressure_rel_err", "dat_value": extracted["pressure_rel_err"]}
        if cf and "area normal shear" in strict_values.get(cf[0]["id"], {}):
            area, fn, _ = strict_values[cf[0]["id"]]["area normal shear"]
            e.update(independent_source="cf_statistics_mean_pressure", independent_value=abs(fn) / area if area else None,
                     reference_pressure=meta.get("q"))
        else:
            e.update(independent_source=None, unavailable="没有接触统计")
        entries.append(e)
    return {"version": CROSSCHECK_VERSION, "entries": entries}


def legacy_consistency(blocks, strict_record, strict_values):
    """旧提取（ccx_io.last_block 选块）与严格读取同一字段块逐值比较；返回不一致项列表（空 = 一致）。"""
    bad = []
    for f in strict_record["fields"]:
        sv = strict_values.get(f["id"])
        if f["location"] == "statistics":
            ct = ccx_io.contact_tables(blocks)
            for part, key in (("total surface force", "force_moment"), ("center of gravity and mean normal", "cog_normal"),
                              ("area normal shear", "area_normal_shear")):
                if part in sv and list(ct.get(key) or []) != list(sv[part]):
                    bad.append(f"{f['id']}/{part}")
            continue
        key = f["field"] if f["field"] != "global coordinates" else "coord"
        b = ccx_io.last_block(blocks, key, None if f["location"] == "contact_row" else f["region"])
        if b is None:
            bad.append(f"{f['id']}: 旧读取器找不到块")
            continue
        rows = b["rows"]
        if f["location"] == "contact_row":
            if [list(r) for r in rows] != [list(r) for r in sv]:
                bad.append(f["id"])
        elif f["location"] == "node":
            if {int(r[0]): list(r[1:]) for r in rows} != {k: list(v) for k, v in sv.items()} or len(rows) != len(sv):
                bad.append(f["id"])
        else:
            if {(int(r[0]), int(r[1])): list(r[2:]) for r in rows} != {k: list(v) for k, v in sv.items()} or len(rows) != len(sv):
                bad.append(f["id"])
    return bad


def _resumable(old, rec):
    sr, ri = old.get("strict_read") or {}, old.get("run_identity") or {}
    return (old.get("inp_sha256") == rec["inp_sha256"] and old.get("status") == "solved"
            and sr.get("reader_version") == ccx_strict.READER_VERSION and sr.get("status") == "accepted"
            and ri.get("version") == IDENTITY_VERSION and ri.get("consistent") is True
            and (ri.get("prepared") or {}).get("digest") == rec["run_identity"]["prepared"]["digest"])


def run_case(cid, case, exp, wd, exe, opts, coord_state, log):
    specs = study.JOBS[cid](case, exp, wd, coord_state, opts)
    if opts.get("smoke"):
        specs = [s for s in specs if s["tags"].get("level", 0) == 0][: (6 if cid == "L0" else 2)]
    recs = []
    for i, sp in enumerate(specs, 1):
        rec = {"id": sp["id"], "case": cid, "group": sp["group"], "tags": sp["tags"], "warnings": []}
        rfile = wd / f"{sp['id']}.record.json"
        t0 = time.perf_counter()
        try:
            inp, meta = sp["build"]()
        except Exception as ex:      # noqa: BLE001
            rec.update(status="build_failed", error=f"{type(ex).__name__}: {ex}", traceback=traceback.format_exc()[-1500:])
            recs.append(rec); log(f"[{cid}] {i}/{len(specs)} {sp['id']} 建模失败：{ex}")
            continue
        meta_path = inp.with_suffix(".meta.json")
        state, step_check, prepared = preflight(inp, meta_path, exe)
        rec.update(build_s=round(time.perf_counter() - t0, 2), h=meta.get("h"), penalty=meta.get("penalty"),
                   pairs_in_contact=meta.get("pairs_in_contact"), element_types=meta.get("element_types"),
                   h_check=meta.get("h_check"),
                   mesh=meta["mesh"], lint_errors=meta["lint_errors"][:20], inp_sha256=prepared["files"]["inp"]["sha256"],
                   step_check=step_check, run_identity={"version": IDENTITY_VERSION, "prepared": prepared})
        if meta["lint_errors"]:
            rec["status"] = "lint_failed"; recs.append(rec)
            log(f"[{cid}] {i}/{len(specs)} {sp['id']} 自检失败：{meta['lint_errors'][:3]}")
            continue
        if not step_check["pass"]:
            rec.update(status="lint_failed", failure="step_check_failed"); recs.append(rec)
            log(f"[{cid}] {i}/{len(specs)} {sp['id']} STEP 状态检查未通过，不发算："
                f"{[e['code'] for e in step_check['errors'][:3]]}")
            continue
        if exe is None:
            rec["status"] = "dry_run"; recs.append(rec)
            q = meta["mesh"]["quality"]
            log(f"[{cid}] {i}/{len(specs)} {sp['id']}  单元 {meta['mesh']['elements']}  minSJ {q['minSJ']['min']:.3f}"
                f"  gamma_min {q['gamma']['min']:.3f}  （未求解）")
            continue
        if rfile.is_file() and not opts.get("force"):
            old = load(rfile)
            if _resumable(old, rec):
                recs.append(old); log(f"[{cid}] {i}/{len(specs)} {sp['id']} 已有结果，跳过"); continue
        log(f"[{cid}] {i}/{len(specs)} {sp['id']}  单元 {meta['mesh']['elements']}  求解中 …")
        res = execute_job(exe, inp, meta_path, prepared, sp["id"], opts["threads"], opts["timeout"], state,
                              opts.get("solver_version"))
        run = res["run"] or {}
        if res["failure"] == "solver_run_not_ok" and meta.get("coord_requested") and \
                any("COOR" in e.upper() for e in run["errors"] + [run.get("log_tail", "")]):
            # 本 ccx 不支持 *EL PRINT COORD：全局关闭（后续作业建模时即不再请求），重建并重算本作业
            coord_state["coord"] = False
            coord_state["note"] = "ccx 拒绝 *EL PRINT COORD，已关闭；齿根应力退化为积分点最大值"
            log("  ! " + coord_state["note"])
            inp, meta = sp["build"]()
            state, step_check, prepared = preflight(inp, meta_path, exe)
            rec.update(inp_sha256=prepared["files"]["inp"]["sha256"], step_check=step_check)
            if not step_check["pass"]:
                rec.update(status="lint_failed", failure="step_check_failed", run_identity={"version": IDENTITY_VERSION,
                                                                                            "prepared": prepared})
                rfile.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
                recs.append(rec)
                continue
            res = execute_job(exe, inp, meta_path, prepared, sp["id"], opts["threads"], opts["timeout"], state,
                              opts.get("solver_version"))
            run = res["run"] or {}
        rec["run_identity"] = res["run_identity"]
        if res.get("outputs_sha256"):
            rec["outputs_sha256"] = res["outputs_sha256"]
        if res["run"] is not None:
            rec["run"] = {k: run[k] for k in ("ok", "returncode", "timeout", "wall_s", "finished_marker", "errors",
                                              "warnings_count", "warnings_head")}
            rec["solve_s"] = run["wall_s"]
            rec["sta"] = ccx_io.parse_sta(inp.with_suffix(".sta"))
        if res["strict_read"] is not None:
            rec["strict_read"] = res["strict_read"]
        if res["failure"]:
            rec["failure"] = res["failure"]
        if res["status"] == "solver_failed":
            rec["status"] = "solver_failed"
            if res["failure"].startswith("input_identity_drift"):
                rec["warnings"].append(f"运行身份漂移（{res['run_identity'].get('drift_stage')}）：{res['run_identity'].get('drift')}；"
                                       "输出全部保留，不采用")
                log(f"  ! 运行身份漂移：{res['run_identity'].get('drift')}（{res['run_identity'].get('drift_stage')}）")
            else:
                rec["log_tail"] = run.get("log_tail", "")
                log(f"  ! 求解失败：{(run.get('errors') or [run.get('log_tail', '')[-300:]])[:2]}")
        elif res["status"] == "post_failed":
            rec["status"] = "post_failed"
            reasons = (res["strict_read"] or {}).get("reasons") or []
            rec["error"] = "严格字段读取拒绝：" + "; ".join(f"{r['code']}" for r in reasons[:10])
            if inp.with_suffix(".dat").is_file():
                rec["dat_sha256"] = ccx_io.sha256(inp.with_suffix(".dat"))
            log(f"  ! {rec['error']}")
        else:
            try:
                blocks = ccx_io.parse_dat(inp.with_suffix(".dat"))
                incons = legacy_consistency(blocks, res["strict_read"], res["strict_values"])
                if incons:
                    raise ValueError(f"旧提取与严格读取不一致：{incons[:10]}")
                frd = inp.with_suffix(".frd")
                ex, warn = (sp["post"](meta, blocks, frd) if cid == "L1" else sp["post"](meta, blocks))
                rec.update(status="solved", extracted=ex)
                rec["contact_crosscheck"] = contact_crosscheck(sp["id"], meta, ex, res["strict_read"], res["strict_values"],
                                                               inp, state)
                rec["warnings"] += warn
                rec["dat_sha256"] = ccx_io.sha256(inp.with_suffix(".dat"))
                log("    " + ", ".join(f"{k}={v:.6g}" for k, v in ex.items() if isinstance(v, float))[:300])
            except Exception as ex:  # noqa: BLE001
                rec.update(status="post_failed", error=f"{type(ex).__name__}: {ex}", traceback=traceback.format_exc()[-1500:])
                log(f"  ! 后处理失败：{ex}")
        rfile.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        recs.append(rec)
    return recs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ccx", help="CalculiX 可执行文件（或设置环境变量 M37_CCX）")
    ap.add_argument("--threads", type=int, default=int(os.environ.get("M37_THREADS", "1")))
    ap.add_argument("--cases", default="L0,L1,L2,L3")
    ap.add_argument("--l2-points", default="", help="只跑 L2 的部分点，如 P01,P03")
    ap.add_argument("--no-mortar", action="store_true", help="跳过 MORTAR 实验变体")
    ap.add_argument("--dry-run", action="store_true", help="只生成网格与 .inp 并自检，不求解")
    ap.add_argument("--smoke", action="store_true", help="冒烟测试：L0 + L1 最粗级")
    ap.add_argument("--force", action="store_true", help="忽略已有结果，全部重算")
    ap.add_argument("--timeout", type=int, default=3600, help="单个作业超时（秒）")
    ap.add_argument("--out", default=str(PACK / "results"), help="结果目录（默认 results/）")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    runs = out / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    logf = open(out / "run.log", "a", encoding="utf-8")

    def log(s):
        line = f"{dt.datetime.now():%H:%M:%S} {s}"
        print(line, flush=True)
        logf.write(line + "\n"); logf.flush()

    cases = [c.strip() for c in a.cases.split(",") if c.strip()]
    if a.smoke:
        cases = [c for c in cases if c in ("L0", "L1")] or ["L0", "L1"]
    exe, solver = None, {"status": "not_run (dry-run)"}
    if not a.dry_run:
        exe = ccx_io.find_ccx(a.ccx)
        vout, ver = ccx_io.ccx_version(exe, a.threads)
        solver = {"path": str(exe), "version_output": vout[-500:], "version": ver, "sha256": ccx_io.sha256(exe),
                  "threads": a.threads}
        log(f"CalculiX：{exe}  版本 {ver}")
        if ver is None or not ("2.21" <= ver <= "2.23"):
            log(f"  ! 版本 {ver} 不在 2.21–2.23 范围内；继续运行，结果中会记录警告")
    opts = {"solver_version": solver.get("version"), "threads": a.threads, "timeout": a.timeout, "mortar": not a.no_mortar, "force": a.force, "smoke": a.smoke,
            "l2_points": [p for p in a.l2_points.split(",") if p]}
    coord_state = {"coord": True, "note": None}
    t_all = time.perf_counter()
    all_recs, summaries, warnings = [], [], []
    if solver.get("version") and not ("2.21" <= solver["version"] <= "2.23"):
        warnings.append(f"ccx 版本 {solver['version']} 不在要求的 2.21–2.23")
    for cid in cases:
        case = load(PACK / "cases" / CASE_FILES[cid])
        exp = load(PACK / "expected" / CASE_FILES[cid])
        wd = runs / cid
        wd.mkdir(parents=True, exist_ok=True)
        log(f"===== {cid}：{case.get('title', '')}")
        t0 = time.perf_counter()
        recs = run_case(cid, case, exp, wd, exe, opts, coord_state, log)
        all_recs += recs
        if exe is not None:
            try:
                s = study.SUMMARY[cid](case, exp, recs)
            except Exception as ex:  # noqa: BLE001
                s = {"case_id": cid, "status": "summary_failed", "error": f"{type(ex).__name__}: {ex}",
                     "traceback": traceback.format_exc()[-1500:]}
            s["wall_s"] = round(time.perf_counter() - t0, 1)
            summaries.append(s)
            la = s.get("local_assessment", {})
            log(f"----- {cid} 本地判定：{'通过' if la.get('pass') else '未通过/不完整'}")
    if coord_state["note"]:
        warnings.append(coord_state["note"])
    bad = [r["id"] for r in all_recs if r.get("status") not in ("solved", "dry_run")]
    if bad:
        warnings.append(f"{len(bad)} 个作业未成功：{bad[:20]}")
    res = {"schema": "m37.fea-results/v1", "pack_version": PACK_VERSION, "field_read_protocol": dict(FIELD_READ_PROTOCOL),
           "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "mode": "dry_run" if exe is None else ("smoke" if a.smoke else "full"),
           "machine": machine_info(), "solver": solver, "coord_supported": coord_state["coord"],
           "options": {k: v for k, v in opts.items()}, "total_wall_s": round(time.perf_counter() - t_all, 1),
           "inputs_sha256": {str(p.relative_to(PACK)).replace("\\", "/"): ccx_io.sha256(p) for p in
                             sorted(list((PACK / "cases").glob("*.json")) + list((PACK / "expected").glob("*.json"))
                                    + list((PACK / "scripts").glob("*.py")))},
           "cases": summaries, "jobs": all_recs, "warnings": warnings}
    fn = out / ("results.json" if exe is not None else "dry-run.json")
    fn.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"写出 {fn}（总耗时 {res['total_wall_s']} s）")
    if exe is not None:
        log("下一步：python scripts/pack_results.py  → 生成回传 zip")
    hard = [b for b in bad if "mortar" not in b]          # MORTAR 是实验变体，失败不算整体失败
    return 0 if not hard else 1


if __name__ == "__main__":
    sys.exit(main())
