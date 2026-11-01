#!/usr/bin/env python3
"""不需要 CalculiX 的自检：语法、几何（与 gearbase/ISO 参考值逐点对比）、啮合位置、两轮不干涉、
后处理数学、.dat/.frd 解析器；可选 --mesh 再生成全部网格与 .inp 并检查单元质量、目标尺寸、格式。

  python selfcheck.py            # 约 10 秒
  python selfcheck.py --mesh     # 另做全部网格（约 4–6 分钟），输出 results/selfcheck.json
"""
from __future__ import annotations

import argparse
import json
import math
import py_compile
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")      # Windows 非 UTF-8 控制台下中文输出不致报错
    except Exception:  # noqa: BLE001
        pass
sys.path.insert(0, str(HERE))
PACK = HERE.parent

import cases as C          # noqa: E402
import ccx_io              # noqa: E402
import post                # noqa: E402
import study               # noqa: E402
from gear_geom import SpurGear, single_contact_diameter   # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})
    print(("  OK   " if ok else "  FAIL ") + name + (f"  —  {detail}" if detail else ""))
    return ok


def load(n):
    return json.loads((PACK / n).read_text(encoding="utf-8"))


def syntax():
    for f in sorted(HERE.glob("*.py")):
        try:
            py_compile.compile(str(f), doraise=True, cfile=str(Path(tempfile.gettempdir()) / (f.stem + ".pyc")))
            check(f"语法 {f.name}", True)
        except py_compile.PyCompileError as ex:
            check(f"语法 {f.name}", False, str(ex))


def geometry_L2():
    case, exp = load("cases/L2_yfs_matrix.json"), load("expected/L2_yfs_matrix.json")
    worst = (0, None)
    for pt in case["points"]:
        g = C.l2_gear(pt, case["common"])
        cs = g.critical_section_30deg()
        e = exp["points"][pt["id"]]
        d1 = abs(cs["sFn"] / e["sFn_mm"] - 1)
        d2 = abs(cs["rhoF"] / e["rhoF_mm"] - 1)
        mate = case["common"]["mate"]
        den = single_contact_diameter(pt["z"], mate["z"], case["common"]["m_mm"], case["common"]["alpha_deg"], pt["x"],
                                      mate["x"], case["common"]["haP"])["den"]
        d3 = abs(den / e["den_mm"] - 1)
        worst = max(worst, (max(d1, d2, d3), pt["id"]), key=lambda t: t[0])
    check("L2 齿形：展成齿根 30° 切点 sFn、ρF 及 HPSTC 直径 den 与 gearbase(ISO 6336-3 方法 B) 一致（相对差 <1e-6）",
          worst[0] < 1e-6, f"最大相对差 {worst[0]:.2e}（{worst[1]}）")
    check("L2 矩阵覆盖 z=17..100、x=-0.5..+0.8、ρfP*=0.25..0.40、≥12 点",
          len(case["points"]) >= 12 and min(p["z"] for p in case["points"]) == 17 and max(p["z"] for p in case["points"]) == 100
          and min(p["x"] for p in case["points"]) == -0.5 and max(p["x"] for p in case["points"]) == 0.8
          and min(p["rhofP"] for p in case["points"]) == 0.25 and max(p["rhofP"] for p in case["points"]) == 0.4,
          f"{len(case['points'])} 点")


def _polygon(g, xf, n_arc=6):
    pcs = C.tooth_pieces(g, list(range(-(g.z // 2), g.z - g.z // 2)), xf, lambda k, p: p)
    poly = []
    for pc in pcs:
        if pc["kind"] == "arc":
            c = pc["center"]
            a0 = math.atan2(pc["pts"][0][1] - c[1], pc["pts"][0][0] - c[0])
            a1 = math.atan2(pc["pts"][1][1] - c[1], pc["pts"][1][0] - c[0])
            d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            R = math.dist(pc["pts"][0], c)
            poly += [(c[0] + R * math.cos(a0 + d * i / n_arc), c[1] + R * math.sin(a0 + d * i / n_arc)) for i in range(n_arc)]
        else:
            poly += pc["pts"][:-1]
    return poly


def _inside(p, poly):
    x, y = p
    ins = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins


def _dist_to_poly(p, poly):
    best = 1e9
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1e-30)))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best


def geometry_L3():
    case, exp = load("cases/L3_C001_G1.json"), load("expected/L3_C001_G1.json")
    case["_ref"] = study.l3_ref(case, exp)
    pg = C.PairGeo(case)
    check("L3 端面重合度与 gearbase 一致", abs(pg.eps / exp["values"]["eps_alpha"]["value"] - 1) < 1e-9,
          f"εα={pg.eps:.6f}")
    single = pg.sE - 0 < pg.pb and 0 - pg.sA < pg.pb
    check("L3 节点 C 位于单齿对啮合区（σH0、c' 取该相位）", single, f"s_A={pg.sA:.4f} s_E={pg.sE:.4f} pb={pg.pb:.4f}")
    worst_pen, min_back = 0.0, 1e9
    for s in (0.0, pg.sA + 0.5 * pg.pb / 16, pg.sA + 5.5 * pg.pb / 16):
        phi1, psi2, pairs = pg.phase(s)
        xf1 = lambda R, th: (R * math.sin(th + phi1), R * math.cos(th + phi1))
        xf2 = lambda R, th: (pg.O2[0] + R * math.sin(math.pi + th + psi2), pg.O2[1] + R * math.cos(math.pi + th + psi2))
        P1 = [p for p in _polygon(pg.g1, xf1) if math.dist(p, pg.loa(0.0)) < 4 * pg.p["m_mm"]]
        P2 = _polygon(pg.g2, xf2)
        for p in P1:
            if _inside(p, P2):
                worst_pen = max(worst_pen, _dist_to_poly(p, P2))
        # 非工作侧（左齿面渐开线）到大轮的最小距离 = 法向侧隙
        pcs = C.tooth_pieces(pg.g1, [-1, 0, 1], xf1, lambda k, p: p)
        left = [q for pc in pcs if pc["name"] == "L_INV" for q in pc["pts"]]
        min_back = min(min_back, min(_dist_to_poly(q, P2) for q in left))
    check("L3 无载装配：两轮齿廓不干涉（采样点最大侵入 <1e-4 mm）", worst_pen < 1e-4, f"最大侵入 {worst_pen:.2e} mm")
    check("L3 非工作齿面留有侧隙（>0）", min_back > 1e-3, f"最小法向间隙 {min_back:.4f} mm")


def postmath():
    # 外推：线性场在 3 个点上精确
    f = lambda x, y: [10 + 2 * x - 3 * y, 1, 2, 0.5 * x, 0, 0]
    ips = [(0.1, 0.1), (0.7, 0.1), (0.2, 0.6)]
    v, kind, _ = post.extrapolate_element(ips, [f(*p) for p in ips], [(0, 0), (1, 0)])
    check("后处理：积分点线性外推精确", max(abs(a - b) for t, row in zip([(0, 0), (1, 0)], v) for a, b in zip(row, f(*t))) < 1e-9)
    hs = [0.3, 0.2, 0.2 / 1.5]
    fs = [100 + 7 * h ** 2 for h in hs]
    r = post.richardson(hs, fs)
    check("后处理：Richardson 二阶外推与阶次", abs(r["extrapolated"] - 100) < 1e-9 and abs(r["observed_order"] - 2) < 1e-6,
          f"p={r['observed_order']:.6f}")
    pe = post.penalty_extrapolate([1e6, 2e6, 4e6], [900 - 5e7 / k for k in (1e6, 2e6, 4e6)])
    check("后处理：penalty 外推 f=f∞-c/K", abs(pe["f_inf"] - 900) < 1e-9)
    a, p0 = 0.07, 850.0
    s = [-a + 2 * a * i / 30 for i in range(31)]
    p = [p0 * math.sqrt(max(0, 1 - (x / a) ** 2)) for x in s]
    fit = post.ellipse_fit(s, p)
    check("后处理：Hertz 椭圆拟合", abs(fit["a"] / a - 1) < 1e-6 and abs(fit["p0"] / p0 - 1) < 1e-6)
    sig = (120.0, -30.0, 27.0, 40.0, 0.0, 0.0)
    s1 = post.principal_max(sig)
    check("后处理：第一主应力", abs(s1 - (45 + math.hypot(75, 40))) < 1e-9)
    h = post.hertz_line(100, 10, 10, 206000, .3, 206000, .3)
    check("后处理：Hertz 解析（R=10, q=100 N/mm）", abs(h["p0_MPa"] - 848.86) < 0.05, f"p0={h['p0_MPa']:.2f} MPa a={h['half_width_mm']:.5f} mm")


def parsers():
    dat = """
                        S T E P       1

 displacements (vx,vy,vz) for set PMASTER and time  0.1000000E+01

        15 -1.234567E-04 -2.500000E-03  0.000000E+00

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set ROOTT and time  0.1000000E+01

         7   1  1.000000E+02  2.000000E+01  3.600000E+01 -5.000000E+00  0.000000E+00  0.000000E+00
         7   2  1.100000E+02  2.000000E+01  3.900000E+01 -5.000000E+00  0.000000E+00  0.000000E+00

 contact stress (slave element+integration point) for all contact elements and time  0.1000000E+01

       101   1  8.000000E+02  0.000000E+00  0.000000E+00

 area,  normal force (+ = tension) and shear force (size) for all contact elements and time  0.1000000E+01

  1.000000E-01 -4.434000E+01  0.000000E+00
"""
    tmp = Path(tempfile.mkdtemp()) / "t.dat"
    tmp.write_text(dat)
    b = ccx_io.parse_dat(tmp)
    U = ccx_io.nodal(b, "displacements", "PMASTER")
    S = ccx_io.ip_table(b, "stresses", "ROOTT")
    ct = ccx_io.contact_tables(b)
    check(".dat 解析器（位移/积分点应力/接触表/统计行）", U[15][1] == -2.5e-3 and S[(7, 2)][0] == 110.0
          and C.pressure_col(ct["stress_rows"]) == [800.0] and ct["area_normal_shear"][1] == -44.34)
    frd = ("    1C\n    2C                             2                                     1\n"
           " -1         1 1.00000E+00 2.00000E+00 0.00000E+00\n -1         2-1.00000E+00 2.00000E+00 0.00000E+00\n -3\n"
           "  100CL  101 1.000000000           2                     0    1           1\n"
           " -4  CONTACT     6    1\n -5  COPEN       1    1    1    0\n -5  CSLIP1      1    1    2    0\n"
           " -5  CSLIP2      1    1    3    0\n -5  CPRESS      1    1    4    0\n -5  CSHEAR1     1    1    5    0\n"
           " -5  CSHEAR2     1    1    6    0\n"
           " -1         1-1.00000E-04 0.00000E+00 0.00000E+00 8.00000E+02 0.00000E+00 0.00000E+00\n -3\n")
    tmp2 = tmp.with_suffix(".frd")
    tmp2.write_text(frd)
    fr = ccx_io.parse_frd(tmp2)
    blk = fr["blocks"]["CONTACT"]
    check(".frd 定宽解析器（节点坐标 + CONTACT/CPRESS）", fr["nodes"][2][0] == -1.0
          and blk["data"][1][blk["comps"].index("CPRESS")] == 800.0)


def e2e_post():
    """端到端后处理（合成 .dat）：用已知应力场/位移代替 ccx 输出，验证建模元数据 → 后处理 → YFS / c' 的链路。"""
    tmp = Path(tempfile.mkdtemp())
    case = load("cases/L2_yfs_matrix.json")
    pt = case["points"][2]
    inp, meta = C.build_L2(case, pt, 0, tmp, True)
    sig = 250.0
    lines = [" stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set ROOTT and time  0.1000000E+01", ""]
    cl = [" global coordinates (elem, integ.pnt.,x,y,z) for set ROOTT and time  0.1000000E+01", ""]
    for e, P in meta["root_element_nodes"].items():
        for i, L in enumerate(((2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3)), 1):
            x = sum(l * p[0] for l, p in zip(L, P[:3])); y = sum(l * p[1] for l, p in zip(L, P[:3]))
            # 场：σxx 沿 x 线性变化，表面外推应精确
            s = sig * (1 + 0.01 * x)
            lines.append(f"{e} {i} {s:.9E} 0.0 {0.3 * s:.9E} 0.0 0.0 0.0")
            cl.append(f"{e} {i} {x:.12E} {y:.12E} 0.0")
    Fx, Fy = meta["load_dir"][0] * meta["Fn_per_b"], meta["load_dir"][1] * meta["Fn_per_b"]
    rf = [" forces (fx,fy,fz) for set FIXED and time  0.1000000E+01", "", f"1 {-Fx:.9E} {-Fy:.9E} 0.0"]
    d = tmp / "x.dat"
    d.write_text("\n".join(lines + [""] + cl + [""] + rf) + "\n")
    ex, warn = C.post_L2(meta, ccx_io.parse_dat(d))
    xs = [p[0] for pts in meta["root_surface_points"].values() for p in pts]
    expect = sig * (1 + 0.01 * max(xs)) * meta["m"] / meta["Ft_per_b"]
    check("端到端（合成 .dat）：L2 积分点→表面外推 → YFS_FE", abs(ex["YFS_FE"] / expect - 1) < 1e-9
          and ex["force_balance_rel"] < 1e-9 and ex["sigma_root_method"].startswith("gauss_point"),
          f"YFS_FE={ex['YFS_FE']:.6f}，期望 {expect:.6f}")
    # L3：给定小轮主节点位移 → 刚度
    c3, e3 = load("cases/L3_C001_G1.json"), load("expected/L3_C001_G1.json")
    meta3 = {"rbore1": 8.0, "rb1": 18.79385241571817, "Fn_per_b": 44.34, "O2": [0, 56.0], "T_per_b": 833.33,
             "rb2": 33.8289, "wbore_xy": {}}
    delta_um = 3.0
    v = -(delta_um * 1e-3 / meta3["rb1"]) * meta3["rbore1"]
    d.write_text(f" displacements (vx,vy,vz) for set PMASTER and time  0.2000000E+01\n\n 7 0.0 {v:.9E} 0.0\n")
    ex3, _ = C.post_L3(meta3, ccx_io.parse_dat(d))
    check("端到端（合成 .dat）：L3 主节点位移 → 沿啮合线变形 δ → 刚度 c = Fn/(b·δ)",
          abs(ex3["mesh_stiffness_N_per_mm_um"] - 44.34 / 3.0) < 1e-9, f"c={ex3['mesh_stiffness_N_per_mm_um']:.6f}")


def meshes():
    import run_m37
    out = PACK / "results"
    rc = run_m37.main(["--dry-run", "--out", str(out)])
    d = json.loads((out / "dry-run.json").read_text(encoding="utf-8"))
    jobs_all = d["jobs"]
    jobs = [j for j in jobs_all if j.get("mesh")]
    check("全部作业建模成功并通过 .inp 格式自检", rc == 0 and all(j["status"] == "dry_run" for j in jobs_all),
          f"{len(jobs_all)} 个作业；失败 {[j['id'] for j in jobs_all if j['status'] != 'dry_run'][:5]}")
    mins = min(j["mesh"]["quality"]["minSJ"]["min"] for j in jobs)
    check("单元质量：所有作业 minSJ > 0.3（gmsh 缩放雅可比，二次曲边单元）", mins > 0.3, f"最小 {mins:.3f}")
    gam = min(j["mesh"]["quality"]["gamma"]["min"] for j in jobs)
    check("单元形状：所有作业 gamma > 0.2", gam > 0.2, f"最小 {gam:.3f}")
    hc = [(j["h_check"]["max_over_target"], j["id"]) for j in jobs if j.get("h_check") and j["h_check"].get("n")]
    worst = max(hc)
    check("目标尺寸：齿根/接触区边长 ≤ 1.3×目标（L2 ρF/div；L1/L3 a/div，即接触区 ≤ a/8）", worst[0] <= 1.3,
          f"最大 {worst[0]:.2f}×（{worst[1]}）")
    n = max(j["mesh"]["elements"] for j in jobs)
    check("规模：最大作业单元数", True, f"{n} 个二次单元；作业总数 {len(jobs)}")
    return {"jobs": len(jobs), "min_minSJ": mins, "min_gamma": gam, "worst_h_ratio": worst, "max_elements": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", action="store_true")
    a = ap.parse_args()
    print("== 语法"); syntax()
    print("== 几何"); geometry_L2(); geometry_L3()
    print("== 后处理数学与解析器"); postmath(); parsers(); e2e_post()
    extra = None
    if a.mesh:
        print("== 网格与 .inp（全部作业）"); extra = meshes()
    ok = all(r["pass"] for r in RESULTS)
    out = PACK / "results"
    out.mkdir(exist_ok=True)
    (out / "selfcheck.json").write_text(json.dumps({"pass": ok, "checks": RESULTS, "mesh_summary": extra},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("自检", "全部通过" if ok else "有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
