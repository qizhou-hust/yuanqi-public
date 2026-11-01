"""每题的作业清单与研究级汇总（网格收敛 / Richardson / penalty 外推 / 相位 / 对比参考值 / 本地验收）。

本地验收（local_assessment）只是给用户的即时提示；正式判定由 gearbase 侧 ingest_fea_results.py 依据
各级原始值重新计算，不采信本地结论。
"""
from __future__ import annotations

import math

import cases as C
import post

# 验收线（与 docs/分路设计报告/L3-fea-tool.md §3 一致；L0 按 .dat 7 位有效数字放宽，见题目说明）
ACCEPT = {
    "L0": {"disp_rel_err": 1e-6, "stress_rel_err": 1e-5, "force_balance_rel": 1e-5},
    "L0c": {"pressure_rel_err": 1e-4, "force_balance_rel": 1e-5},
    "L1": {"mesh_last_change": 0.02, "p_max_err": 0.03, "half_width_err": 0.05, "force_err": 1e-3},
    "L2": {"mesh_last_change": 0.02, "ratio_lo": 0.90, "ratio_hi": 1.10, "min_points": 12, "force_err": 1e-4},
    "L3": {"mesh_last_change": 0.02, "sigmaH_lo": 0.92, "sigmaH_hi": 1.08, "c_lo": 0.8, "c_hi": 1.2,
           "phase_change": 0.03, "torque_err": 1e-3, "contact_force_err": 1e-3},
}


# 作业清单函数的 coord 参数是可变 dict {"coord": bool}：建模时才读取，便于 ccx 不支持 COORD 时中途关闭


def job(id_, build, post_fn, group, **tags):
    return {"id": id_, "build": build, "post": post_fn, "group": group, "tags": tags}


# ------------------------------------------------------------------ 作业清单
def jobs_L0(case, exp, wd, coord, opts):
    out = []
    for elem in case["mesh"]["elements"]:
        for lv in range(len(case["mesh"]["h_mm"])):
            out.append(job(f"L0_patch_{elem}_h{lv}", lambda e=elem, l=lv: C.build_L0(case, l, e, wd, coord["coord"]),
                           C.post_L0, "patch", elem=elem, level=lv))
    c = case["contact_patch"]
    for kind in ["penalty"] + (["mortar"] if opts.get("mortar", True) else []):
        for lv in range(len(c["mesh"]["h_mm"])):
            out.append(job(f"L0c_{kind}_h{lv}", lambda k=kind, l=lv: C.build_L0c(c, l, k, wd), C.post_L0c,
                           "contact_patch", contact=kind, level=lv))
    return out


def jobs_L1(case, exp, wd, coord, opts):
    out = []
    divs = case["mesh"]["contact_divisions"]
    a0 = case["penalty"]["alpha_mesh_study"]
    for lv, d in enumerate(divs):
        out.append(job(f"L1_penalty_d{d}_a{a0:g}", lambda l=lv: C.build_L1(case, l, "penalty", a0, wd),
                       C.post_L1, "mesh", contact="penalty", level=lv, alpha=a0))
    for al in case["penalty"]["alpha_penalty_study"]:
        if al == a0:
            continue
        lv = len(divs) - 1
        out.append(job(f"L1_penalty_d{divs[lv]}_a{al:g}", lambda a=al, l=lv: C.build_L1(case, l, "penalty", a, wd),
                       C.post_L1, "penalty", contact="penalty", level=lv, alpha=al))
    if opts.get("mortar", True):
        for lv, d in enumerate(divs):
            out.append(job(f"L1_mortar_d{d}", lambda l=lv: C.build_L1(case, l, "mortar", 0.0, wd), C.post_L1,
                           "mortar", contact="mortar", level=lv))
    return out


def jobs_L2(case, exp, wd, coord, opts):
    out = []
    pts = case["points"]
    if opts.get("l2_points"):
        pts = [p for p in pts if p["id"] in opts["l2_points"]]
    for pt in pts:
        for lv, d in enumerate(case["mesh"]["root_divisions"]):
            out.append(job(f"L2_{pt['id']}_d{d}", lambda p=pt, l=lv: C.build_L2(case, p, l, wd, coord["coord"]), C.post_L2,
                           "mesh", point=pt["id"], level=lv))
    return out


def l3_ref(case, exp):
    v = exp["values"]
    return {"hertz_half_width_C_mm": v["hertz_half_width_C_mm"]["value"],
            "T1_per_b_Nmm_per_mm": v["T1_per_b"]["value"],
            "c_prime_th_CB_N_per_mm_um": v["c_prime_th_CB"]["value"]}


def jobs_L3(case, exp, wd, coord, opts):
    case["_ref"] = l3_ref(case, exp)
    pg = C.PairGeo(case)
    ms, pen = case["mesh"], case["penalty"]
    divs, a0 = ms["contact_divisions"], pen["alpha_mesh_study"]
    cid = case["id"]
    out = []
    for lv, d in enumerate(divs):
        out.append(job(f"{cid}_C_d{d}_a{a0:g}", lambda d=d: C.build_L3(case, wd, s_ref=0.0, div=d, alpha=a0,
                       contact="penalty", tag=f"{cid}_C_d{d}_a{a0:g}"), C.post_L3, "mesh", level=lv, alpha=a0, s=0.0))
    for al in pen["alpha_penalty_study"]:
        if al != a0:
            d = divs[-1]
            out.append(job(f"{cid}_C_d{d}_a{al:g}", lambda d=d, al=al: C.build_L3(case, wd, s_ref=0.0, div=d, alpha=al,
                           contact="penalty", tag=f"{cid}_C_d{d}_a{al:g}"), C.post_L3, "penalty",
                           level=len(divs) - 1, alpha=al, s=0.0))
    if opts.get("mortar", True) and case.get("mortar_variant", True):
        d = divs[-1]
        out.append(job(f"{cid}_C_d{d}_mortar", lambda d=d: C.build_L3(case, wd, s_ref=0.0, div=d, alpha=0.0,
                       contact="mortar", tag=f"{cid}_C_d{d}_mortar"), C.post_L3, "mortar", level=len(divs) - 1, s=0.0))
    N = case["phases"]["count"]
    dph = case["phases"]["division"]
    for j in range(N):
        s = pg.sA + (j + 0.5) * pg.pb / N
        out.append(job(f"{cid}_ph{j:02d}_d{dph}", lambda s=s, j=j: C.build_L3(case, wd, s_ref=s, div=dph, alpha=a0,
                       contact="penalty", tag=f"{cid}_ph{j:02d}_d{dph}"), C.post_L3, "phase", phase=j, s=s,
                       alpha=a0))
    return out


JOBS = {"L0": jobs_L0, "L1": jobs_L1, "L2": jobs_L2, "L3": jobs_L3}


# ------------------------------------------------------------------ 汇总
def _ok(rec):
    return rec.get("status") == "solved" and rec.get("extracted")


def _get(rec, k):
    return (rec.get("extracted") or {}).get(k)


def summarize_L0(case, exp, recs):
    A = ACCEPT["L0"]
    patch = [r for r in recs if r["group"] == "patch"]
    cp = [r for r in recs if r["group"] == "contact_patch"]
    rows, ok = [], True
    for r in patch:
        e = r.get("extracted") or {}
        good = _ok(r) and all(e.get(k) is not None and e[k] <= v for k, v in A.items())
        ok &= bool(good)
        rows.append({"job": r["id"], "pass": bool(good), **{k: e.get(k) for k in A}, "ip_per_element": e.get("ip_per_element")})
    crow, cpen_ok, cmor = [], True, None
    for r in cp:
        e = r.get("extracted") or {}
        good = _ok(r) and all(e.get(k) is not None and e[k] <= v for k, v in ACCEPT["L0c"].items())
        crow.append({"job": r["id"], "contact": r["tags"]["contact"], "pass": bool(good),
                     **{k: e.get(k) for k in ("pressure_rel_err", "force_balance_rel", "penetration_rel_err")}})
        if r["tags"]["contact"] == "penalty":
            cpen_ok &= bool(good)
        else:
            cmor = (cmor if cmor is not None else True) and bool(good)
    coord = any((r.get("extracted") or {}).get("coord_supported") for r in patch)
    return {"case_id": "L0", "ladder_level": "L0", "patch": rows, "contact_patch": crow,
            "coord_supported": coord, "mortar_contact_patch_pass": cmor,
            "local_assessment": {"pass": ok and cpen_ok and bool(patch) and bool(cp),
                                 "criteria": {"patch": A, "contact_patch": ACCEPT["L0c"]}}}


def summarize_L1(case, exp, recs):
    A = ACCEPT["L1"]
    ref = exp["values"]
    p0, a0 = ref["p0_MPa"]["value"], ref["half_width_mm"]["value"]
    out = {"case_id": "L1", "ladder_level": "L1", "reference": {"p0_MPa": p0, "half_width_mm": a0}}
    mesh = sorted([r for r in recs if r["group"] == "mesh" and _ok(r)], key=lambda r: r["tags"]["level"])
    routes = {}
    if len(mesh) >= 2:
        hs = [r["h"] for r in mesh]
        rp = post.richardson(hs, [_get(r, "p_max_MPa") for r in mesh])
        ra = post.richardson(hs, [_get(r, "half_width_mm") for r in mesh]) if all(_get(r, "half_width_mm") for r in mesh) else None
        pen = [r for r in recs if r["tags"].get("level") == len(case["mesh"]["contact_divisions"]) - 1
               and r["group"] in ("mesh", "penalty") and _ok(r)]
        pstudy = None
        p_final = rp["extrapolated"]
        if len(pen) >= 3:
            pstudy = post.penalty_extrapolate([r["penalty"] for r in pen], [_get(r, "p_max_MPa") for r in pen])
            fine_a0 = [r for r in pen if r["group"] == "mesh"][0]
            p_final = rp["extrapolated"] + (pstudy["f_inf"] - _get(fine_a0, "p_max_MPa"))
        a_final = ra["extrapolated"] if ra else _get(mesh[-1], "half_width_mm")
        ferr = max(_get(r, "contact_normal_force_rel_err") or 0 for r in mesh)
        good = (len(mesh) >= 3 and rp["relative_changes"][-1] < A["mesh_last_change"] and pstudy is not None
                and abs(p_final / p0 - 1) < A["p_max_err"] and a_final is not None and abs(a_final / a0 - 1) < A["half_width_err"]
                and ferr < A["force_err"])
        routes["penalty"] = {"mesh_study": rp, "half_width_study": ra, "penalty_study": pstudy,
                             "p_max_final_MPa": p_final, "p_max_rel_err": p_final / p0 - 1,
                             "half_width_final_mm": a_final, "half_width_rel_err": (a_final / a0 - 1) if a_final else None,
                             "half_width_method": _get(mesh[-1], "half_width_method"),
                             "max_contact_force_rel_err": ferr, "pass": bool(good)}
    mor = sorted([r for r in recs if r["group"] == "mortar" and _ok(r)], key=lambda r: r["tags"]["level"])
    tried = [r for r in recs if r["group"] == "mortar"]
    if mor and len(mor) == len(tried) and len(mor) >= 2:
        rp = post.richardson([r["h"] for r in mor], [_get(r, "p_max_MPa") for r in mor])
        af = _get(mor[-1], "half_width_mm")
        good = (len(mor) >= 3 and rp["relative_changes"][-1] < A["mesh_last_change"] and abs(rp["extrapolated"] / p0 - 1) < A["p_max_err"]
                and af and abs(af / a0 - 1) < A["half_width_err"])
        routes["mortar"] = {"mesh_study": rp, "p_max_final_MPa": rp["extrapolated"], "p_max_rel_err": rp["extrapolated"] / p0 - 1,
                            "half_width_final_mm": af, "pass": bool(good)}
    elif tried:
        routes["mortar"] = {"status": "failed_or_unsupported", "jobs": [r["id"] for r in tried if not _ok(r)]}
    out["routes"] = routes
    out["local_assessment"] = {"pass": any(v.get("pass") for v in routes.values()), "criteria": A}
    return out


def summarize_L2(case, exp, recs):
    A = ACCEPT["L2"]
    rows = []
    for pt in case["points"]:
        rs = sorted([r for r in recs if r["tags"].get("point") == pt["id"] and _ok(r)], key=lambda r: r["tags"]["level"])
        e = exp["points"].get(pt["id"])
        row = {"point": pt["id"], "z": pt["z"], "x": pt["x"], "rhofP": pt["rhofP"], "levels": len(rs),
               "YFS_ISO": e["YFS"] if e else None}
        if len(rs) >= 2:
            st = post.richardson([r["h"] for r in rs], [_get(r, "YFS_FE") for r in rs])
            row.update(mesh_study=st, YFS_FE=st["extrapolated"], ratio=st["extrapolated"] / e["YFS"] if e else None,
                       sigma_method=_get(rs[-1], "sigma_root_method"),
                       peak_offset_from_30deg_mm=_get(rs[-1], "peak_offset_from_30deg_point_mm"),
                       force_balance_rel=max(_get(r, "force_balance_rel") or 0 for r in rs))
            row["pass"] = bool(len(rs) >= 3 and st["relative_changes"][-1] < A["mesh_last_change"] and row["ratio"]
                               and A["ratio_lo"] <= row["ratio"] <= A["ratio_hi"] and row["force_balance_rel"] < A["force_err"])
        else:
            row["pass"] = False
        rows.append(row)
    npass = sum(r["pass"] for r in rows)
    return {"case_id": "L2", "ladder_level": "L2", "points": rows,
            "local_assessment": {"pass": npass == len(rows) and len(rows) >= A["min_points"], "n_pass": npass,
                                 "n_points": len(rows), "criteria": A}}


def summarize_L3(case, exp, recs):
    A = ACCEPT["L3"]
    v = exp["values"]
    sH_ref = v["sigma_H_C_hertz"]["value"]
    c_ref = v["c_prime_th_CB"]["value"]
    cg_ref = v["c_gamma_alpha_th"]["value"]
    out = {"case_id": case["id"], "ladder_level": "L3",
           "reference": {"sigma_H_C_hertz_MPa": sH_ref, "sigma_H0_MPa": v["sigma_H0"]["value"],
                         "c_prime_th_CB": c_ref, "c_prime_ISO": v["c_prime_ISO"]["value"],
                         "c_gamma_alpha_th": cg_ref, "c_gamma_alpha_ISO": v["c_gamma_alpha_ISO"]["value"]}}
    mesh = sorted([r for r in recs if r["group"] == "mesh" and _ok(r)], key=lambda r: r["tags"]["level"])
    res = {}
    if len(mesh) >= 2:
        hs = [r["h"] for r in mesh]
        sp = post.richardson(hs, [_get(r, "p_max_MPa") for r in mesh])
        sc = post.richardson(hs, [_get(r, "mesh_stiffness_N_per_mm_um") for r in mesh])
        pen = [r for r in recs if r["tags"].get("level") == len(case["mesh"]["contact_divisions"]) - 1
               and r["group"] in ("mesh", "penalty") and _ok(r)]
        s_final, c_final, ps, pc = sp["extrapolated"], sc["extrapolated"], None, None
        if len(pen) >= 3:
            fine = [r for r in pen if r["group"] == "mesh"][0]
            ps = post.penalty_extrapolate([r["penalty"] for r in pen], [_get(r, "p_max_MPa") for r in pen])
            pc = post.penalty_extrapolate([r["penalty"] for r in pen], [_get(r, "mesh_stiffness_N_per_mm_um") for r in pen])
            s_final += ps["f_inf"] - _get(fine, "p_max_MPa")
            c_final += pc["f_inf"] - _get(fine, "mesh_stiffness_N_per_mm_um")
        res.update(sigma_H_mesh_study=sp, c_prime_mesh_study=sc, sigma_H_penalty_study=ps, c_prime_penalty_study=pc,
                   sigma_H_FE=s_final, c_prime_FE=c_final, ratio_sigma_H=s_final / sH_ref, ratio_c_prime=c_final / c_ref,
                   ratio_sigma_H0_with_Zeps=s_final / v["sigma_H0"]["value"],
                   ratio_c_prime_ISO_with_CM=c_final / v["c_prime_ISO"]["value"],
                   pitch_single_pair=all(_get(r, "mesh_stiffness_N_per_mm_um") is not None for r in mesh)
                   and all(r.get("pairs_in_contact") == 1 for r in mesh))
    ph = sorted([r for r in recs if r["group"] == "phase" and _ok(r)], key=lambda r: r["tags"]["phase"])
    nph = len([r for r in recs if r["group"] == "phase"])
    if ph and len(ph) == nph:
        cs = [_get(r, "mesh_stiffness_N_per_mm_um") for r in ph]
        c16 = sum(cs) / len(cs)
        c8 = sum(cs[0::2]) / len(cs[0::2])
        res.update(phase_values=cs, c_gamma_FE_16=c16, c_gamma_FE_8=c8, phase_change=abs(c16 - c8) / c16,
                   ratio_c_gamma=c16 / cg_ref, ratio_c_gamma_ISO_with_CM=c16 / v["c_gamma_alpha_ISO"]["value"])
    allr = [r for r in recs if _ok(r)]
    terr = max((_get(r, "wheel_torque_rel_err") or 0) for r in allr) if allr else None
    cerr = max((_get(r, "contact_normal_force_rel_err") or 0) for r in allr) if allr else None
    res.update(max_wheel_torque_rel_err=terr, max_contact_force_rel_err=cerr)
    out["results"] = res
    g = lambda k: res.get(k)
    checks = {
        "mesh_converged": bool(len(mesh) >= 3 and res["sigma_H_mesh_study"]["relative_changes"][-1] < A["mesh_last_change"]
                               and res["c_prime_mesh_study"]["relative_changes"][-1] < A["mesh_last_change"]) if len(mesh) >= 2 else False,
        "penalty_extrapolated": res.get("sigma_H_penalty_study") is not None,
        "sigma_H_ratio": g("ratio_sigma_H") is not None and A["sigmaH_lo"] <= g("ratio_sigma_H") <= A["sigmaH_hi"],
        "c_prime_ratio": g("ratio_c_prime") is not None and A["c_lo"] <= g("ratio_c_prime") <= A["c_hi"],
        "c_gamma_ratio": g("ratio_c_gamma") is not None and A["c_lo"] <= g("ratio_c_gamma") <= A["c_hi"],
        "phase_converged": g("phase_change") is not None and g("phase_change") < A["phase_change"],
        "conservation": terr is not None and terr < A["torque_err"] and cerr is not None and cerr < A["contact_force_err"],
    }
    out["local_assessment"] = {"pass": all(checks.values()), "checks": checks, "criteria": A}
    return out


SUMMARY = {"L0": summarize_L0, "L1": summarize_L1, "L2": summarize_L2, "L3": summarize_L3}
