"""M37 各题：建模（gmsh 网格 + .inp）与单个作业后处理。研究级汇总（收敛、外推、验收）在 study.py。

作业（job）= 一个 .inp；每个作业旁写 <job>.meta.json（后处理所需的节点坐标、载荷、参考量），
它很小，随结果回传，便于我们在云端只凭 .dat + meta 复核后处理。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from gear_geom import SpurGear, single_contact_diameter, involute_normal_at, inv
from inp_writer import Deck, lint
from mesh_gmsh import mesh_2d
import post

E_DEFAULT, NU_DEFAULT = 206000.0, 0.3


# ------------------------------------------------------------------ 通用
def edge_load(mesh, edges, fx, fy):
    """二次边上的一致节点力：常值线分布力 (fx, fy)（N/mm，单位厚度）。端点 1/6、中点 2/3 × 边长。"""
    loads = {}
    for _, _, (a, b, c) in edges:
        L = math.dist(mesh.nodes[a], mesh.nodes[c]) + math.dist(mesh.nodes[c], mesh.nodes[b])
        for n, w in ((a, 1 / 6), (b, 1 / 6), (c, 2 / 3)):
            loads[(n, 1)] = loads.get((n, 1), 0.0) + fx * L * w
            loads[(n, 2)] = loads.get((n, 2), 0.0) + fy * L * w
    return loads


def h_check(mesh, curve, target, near=None, radius=None):
    """边界边长（端点间沿二次边折线长度）与目标尺寸对比；near/radius 只统计某点附近的边。"""
    L = []
    for _, _, (a, b, c) in mesh.edges.get(curve, []):
        if near is not None and min(math.dist(mesh.nodes[c], p) for p in near) > radius:
            continue
        L.append(math.dist(mesh.nodes[a], mesh.nodes[c]) + math.dist(mesh.nodes[c], mesh.nodes[b]))
    L.sort()
    if not L:
        return {"curve": curve, "n": 0, "target": target}
    return {"curve": curve, "target": target, "n": len(L), "max": L[-1], "median": L[len(L) // 2],
            "max_over_target": L[-1] / target}


def mesh_record(mesh):
    return {"nodes": len(mesh.nodes), "elements": len(mesh.elements), "element_kinds": mesh.count(),
            "quality": mesh.quality, "gmsh_version": mesh.gmsh_version}


def element_types(mesh, quad_type):
    return sorted({("CPE6" if k == "T6" else quad_type) for k, _, _ in mesh.elements.values()})


def finish(job_dir, job_id, deck, meta, mesh):
    job_dir.mkdir(parents=True, exist_ok=True)
    text = deck.text()
    errs, stats = lint(text)
    inp = job_dir / f"{job_id}.inp"
    inp.write_text(text)
    meta.update(job_id=job_id, lint_errors=errs, deck_stats=stats, mesh=mesh_record(mesh))
    (job_dir / f"{job_id}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return inp, meta


def ip_prints(deck, elset, coord):
    deck.add(f"*EL PRINT,ELSET={elset}", "S")
    if coord:
        deck.add(f"*EL PRINT,ELSET={elset}", "COORD")


def pressure_col(rows):
    """接触应力行：5 列（单元, 积分点, p, t1, t2）或 4 列（节点, p, t1, t2）。"""
    if not rows:
        return []
    k = 2 if len(rows[0]) >= 5 else 1
    return [r[k] for r in rows]


# ================================================================== L0 补丁检验
def build_L0(case, level, elem, job_dir, coord=True):
    g = case["geometry"]
    L, H = g["L_mm"], g["H_mm"]
    h = case["mesh"]["h_mm"][level]
    sig, E, nu = case["load"]["sigma_MPa"], case["material"]["E_MPa"], case["material"]["nu"]
    P = [(0, 0), (L / 2, 0), (L, 0), (L, H), (0, H)]
    surf = [{"name": "BLOCK", "outer": [
        {"kind": "line", "pts": [P[0], P[1]], "name": "BOT"}, {"kind": "line", "pts": [P[1], P[2]], "name": "BOT"},
        {"kind": "line", "pts": [P[2], P[3]], "name": "RIGHT"}, {"kind": "line", "pts": [P[3], P[4]], "name": "TOP"},
        {"kind": "line", "pts": [P[4], P[0]], "name": "LEFT"}]}]
    # 加一个内部偏心加密点，故意制造畸变单元（补丁检验要求任意形状单元都精确）
    fields = [{"kind": "disk", "center": (0.37 * L, 0.61 * H), "h_in": h / 3, "r_in": 0.05 * H, "r_out": 0.6 * H}]
    mesh = mesh_2d(surf, fields, h, quads=(elem != "CPE6"))
    deck = Deck(f"M37 L0 patch {elem} level {level}")
    bodies = deck.mesh(mesh, quad_type=elem if elem != "CPE6" else "CPE8")
    deck.material(E, nu, bodies)
    left = mesh.edge_nodes("LEFT")
    origin = min(mesh.nodes, key=lambda n: math.hypot(*mesh.nodes[n]))
    deck.nset("ALLN", mesh.nodes)
    deck.nset("LEFT", left)
    deck.boundary([("LEFT", 1, 1), (origin, 2, 2)])
    deck.add("*STEP", "*STATIC")
    deck.cload(edge_load(mesh, mesh.edges["RIGHT"], sig, 0.0))
    deck.add("*NODE PRINT,NSET=ALLN", "U", "*NODE PRINT,NSET=LEFT", "RF")
    ip_prints(deck, "BLOCK", coord)
    deck.add("*END STEP")
    meta = {"case": "L0", "variant": f"patch_{elem}", "level": level, "h": h, "elem": elem, "coord_requested": coord,
            "nodes_xy": {str(n): mesh.nodes[n] for n in mesh.nodes}, "origin": origin,
            "sigma": sig, "E": E, "nu": nu, "H": H, "element_types": element_types(mesh, elem)}
    return finish(job_dir, f"L0_patch_{elem}_h{level}", deck, meta, mesh)


def post_L0(meta, blocks):
    from ccx_io import nodal, ip_table
    E, nu, sig, H = meta["E"], meta["nu"], meta["sigma"], meta["H"]
    U = nodal(blocks, "displacements", "ALLN")
    RF = nodal(blocks, "forces", "LEFT")
    S = ip_table(blocks, "stresses", "BLOCK")
    C = ip_table(blocks, "coord", "BLOCK")
    out, warn = {}, []
    if U:
        umax, err = 0.0, 0.0
        for n, (x, y) in meta["nodes_xy"].items():
            ux, uy = sig * (1 - nu ** 2) * x / E, -sig * nu * (1 + nu) * y / E
            v = U.get(int(n))
            if v is None:
                continue
            umax = max(umax, math.hypot(ux, uy))
            err = max(err, math.hypot(v[0] - ux, v[1] - uy))
        out["disp_rel_err"] = err / umax
    if S:
        ex = (sig, 0.0, nu * sig, 0.0, 0.0, 0.0)
        out["stress_rel_err"] = max(abs(v[k] - ex[k]) for v in S.values() for k in range(min(6, len(v)))) / sig
        per = {}
        for (e, ip) in S:
            per[e] = max(per.get(e, 0), ip)
        out["ip_per_element"] = sorted(set(per.values()))
    if RF:
        tot = sum(v[0] for v in RF.values())
        out["force_balance_rel"] = abs(tot + sig * H) / (sig * H)
    out["coord_supported"] = bool(C)
    if not C and meta.get("coord_requested"):
        warn.append("COORD 积分点坐标未出现在 .dat：后续齿根外推退化为'积分点最大值'")
    return out, warn


# ================================================================== L0c 接触补丁
def build_L0c(case, level, contact, job_dir, alpha=10.0):
    g = case["geometry"]
    W, Hb = g["W_mm"], g["H_mm"]
    h = case["mesh"]["h_mm"][level]
    q, E, nu = case["load"]["pressure_MPa"], case["material"]["E_MPa"], case["material"]["nu"]
    nb, nt = max(3, int(round(W / h)) + 1), max(4, int(round(W / (0.7 * h))) + 1)
    def rect(name, y0, top_name, bot_name, nbot, ntop):
        P = [(0, y0), (W, y0), (W, y0 + Hb), (0, y0 + Hb)]
        return {"name": name, "outer": [
            {"kind": "line", "pts": [P[0], P[1]], "name": bot_name, "n_nodes": nbot},
            {"kind": "line", "pts": [P[1], P[2]], "name": name + "_R"},
            {"kind": "line", "pts": [P[2], P[3]], "name": top_name, "n_nodes": ntop},
            {"kind": "line", "pts": [P[3], P[0]], "name": name + "_L"}]}
    surf = [rect("LOWER", 0.0, "LOWER_TOP", "LOWER_BOT", nb, nb), rect("UPPER", Hb, "UPPER_TOP", "UPPER_BOT", nt, nt)]
    mesh = mesh_2d(surf, [], h, quads=False)
    deck = Deck(f"M37 L0c contact patch {contact} level {level}")
    bodies = deck.mesh(mesh)
    deck.material(E, nu, bodies)
    K = alpha * E / h
    deck.surface("SLAVE", mesh.edges["UPPER_BOT"])
    deck.surface("MASTER", mesh.edges["LOWER_TOP"])
    deck.contact("SLAVE", "MASTER", contact, K)
    deck.nset("LBOT", mesh.edge_nodes("LOWER_BOT"))
    deck.nset("XSYM", mesh.edge_nodes("LOWER_L", "UPPER_L"))
    deck.nset("UTOP", mesh.edge_nodes("UPPER_TOP"))
    fixed = [("LBOT", 2, 2), ("XSYM", 1, 1)]
    deck.boundary(fixed)
    d0 = 0.3 * q * 2 * Hb * (1 - nu ** 2) / E
    deck.add("*STEP,INC=200", "*STATIC", "0.25,1,1e-6,0.5")
    deck.boundary([("UTOP", 2, 2, -d0)])
    deck.add("*END STEP")
    deck.add("*STEP,INC=200", "*STATIC", "0.25,1,1e-6,0.5")
    deck.boundary(fixed, op_new=True)
    deck.cload(edge_load(mesh, mesh.edges["UPPER_TOP"], 0.0, -q))
    deck.add("*NODE PRINT,NSET=LBOT", "RF")
    deck.add("*CONTACT PRINT,SLAVE=SLAVE,MASTER=MASTER", "CDIS,CSTR,CF")
    deck.add("*END STEP")
    meta = {"case": "L0c", "variant": f"contact_{contact}", "level": level, "h": h, "contact": contact,
            "penalty": K if contact == "penalty" else None, "q": q, "W": W, "element_types": element_types(mesh, "CPE8")}
    return finish(job_dir, f"L0c_{contact}_h{level}", deck, meta, mesh)


def post_L0c(meta, blocks):
    from ccx_io import nodal, contact_tables
    out, warn = {}, []
    ct = contact_tables(blocks)
    p = pressure_col(ct["stress_rows"])
    q = meta["q"]
    if p:
        act = [v for v in p if abs(v) > 1e-6 * q]
        out["pressure_rel_err"] = max(abs(abs(v) - q) for v in act) / q if act else None
        out["n_contact_points"] = len(act)
    else:
        warn.append("未读到接触应力表")
    RF = nodal(blocks, "forces", "LBOT")
    if RF:
        out["force_balance_rel"] = abs(sum(v[1] for v in RF.values()) - q * meta["W"]) / (q * meta["W"])
    if ct["disp_rows"] and meta.get("penalty"):
        k = 2 if len(ct["disp_rows"][0]) >= 5 else 1
        pen = max(abs(r[k]) for r in ct["disp_rows"])
        out["penetration_rel_err"] = abs(pen / (q / meta["penalty"]) - 1)
    return out, warn


# ================================================================== L1 Hertz 圆柱
def hertz_ref(case):
    m, g, ld = case["material"], case["geometry"], case["load"]
    return post.hertz_line(ld["q_N_per_mm"], g["R_mm"], g["R_mm"], m["E_MPa"], m["nu"], m["E_MPa"], m["nu"])


def build_L1(case, level, contact, alpha, job_dir, tag=None):
    g, ld, mat = case["geometry"], case["load"], case["material"]
    R, q, E, nu = g["R_mm"], ld["q_N_per_mm"], mat["E_MPa"], mat["nu"]
    ref = hertz_ref(case)
    a = ref["half_width_mm"]
    div = case["mesh"]["contact_divisions"][level]
    hc = a / div
    tc = g["contact_surface_halfwidth_in_a"] * a / R      # 接触面角半宽
    def half(name, cy, sgn):
        # sgn=+1：上半体（圆心 (0,R)，下半圆弧 + 顶平面 y=2R? 不：平面在 y=cy）
        bot = (0.0, cy - sgn * R)       # 接触点 (0,0)
        def P(th):  # th 从接触点量起
            return (R * math.sin(th), cy - sgn * R * math.cos(th))
        flatL, flatR, mid = (-R, cy), (R, cy), (0.0, cy)
        pieces = [
            {"kind": "arc", "pts": [flatR, P(tc)], "center": (0, cy), "name": name + "_ARC"},
            {"kind": "arc", "pts": [P(tc), P(0.0)], "center": (0, cy), "name": name + "_CONT"},
            {"kind": "arc", "pts": [P(0.0), P(-tc)], "center": (0, cy), "name": name + "_CONT"},
            {"kind": "arc", "pts": [P(-tc), flatL], "center": (0, cy), "name": name + "_ARC"},
            {"kind": "line", "pts": [flatL, mid], "name": name + "_FLAT"},
            {"kind": "line", "pts": [mid, flatR], "name": name + "_FLAT"}]
        return {"name": name, "outer": pieces}
    surf = [half("UP", R, +1), half("LO", -R, -1)]
    fields = [{"kind": "disk", "center": (0.0, 0.0), "h_in": hc, "r_in": 2.5 * a, "r_out": 0.45 * R}]
    mesh = mesh_2d(surf, fields, R / 8, quads=False)
    deck = Deck(f"M37 L1 Hertz {contact} div {div} alpha {alpha}")
    bodies = deck.mesh(mesh)
    deck.material(E, nu, bodies)
    K = alpha * E / hc
    deck.surface("SUP", mesh.edges["UP_CONT"])
    deck.surface("SLO", mesh.edges["LO_CONT"])
    deck.contact("SUP", "SLO", contact, K)
    upflat = mesh.edge_nodes("UP_FLAT")
    loflat = mesh.edge_nodes("LO_FLAT")
    ref_up = min(upflat, key=lambda n: abs(mesh.nodes[n][0]))
    pin_lo = min(loflat, key=lambda n: abs(mesh.nodes[n][0]))
    deck.nset("LOFLAT", loflat)
    deck.nset("REFUP", [ref_up])
    for n in upflat:                     # 刚性压板：上平面竖向位移一致
        if n != ref_up:
            deck.equation([(n, 2, 1.0), (ref_up, 2, -1.0)])
    fixed = [("LOFLAT", 2, 2), (pin_lo, 1, 1), (ref_up, 1, 1)]
    deck.boundary(fixed)
    # 第 1 步：小位移闭合接触；第 2 步：放开位移，施加已知力（力控制）
    d0 = 0.2 * 2 * 2 * q * (1 - nu ** 2) / (math.pi * E) * (2 * math.log(4 * R / a) - 1)
    deck.add("*STEP,INC=300", "*STATIC", "0.25,1,1e-7,0.5")
    deck.boundary([(ref_up, 2, 2, -d0)])
    deck.add("*END STEP", "*STEP,INC=300", "*STATIC", "0.25,1,1e-7,0.5")
    deck.boundary(fixed, op_new=True)
    deck.cload({(ref_up, 2): -q})
    deck.add("*NODE PRINT,NSET=REFUP", "U", "*NODE PRINT,NSET=LOFLAT", "RF")
    deck.add("*CONTACT PRINT,SLAVE=SUP,MASTER=SLO", "CDIS,CSTR,CF")
    deck.add("*CONTACT FILE", "CDIS,CSTR")
    deck.add("*END STEP")
    hchk = h_check(mesh, "UP_CONT", hc, near=[(0.0, 0.0)], radius=1.5 * a)
    jid = tag or f"L1_{contact}_d{div}" + (f"_a{alpha:g}" if contact == "penalty" else "")
    meta = {"case": "L1", "variant": contact, "level": level, "h": hc, "div": div, "alpha": alpha,
            "penalty": K if contact == "penalty" else None, "q": q, "ref": ref, "element_types": element_types(mesh, "CPE8"),
            "h_check": hchk}
    return finish(job_dir, jid, deck, meta, mesh)


def post_L1(meta, blocks, frd_path=None):
    from ccx_io import contact_tables, nodal, parse_frd
    out, warn = {}, []
    ct = contact_tables(blocks)
    p = pressure_col(ct["stress_rows"])
    if not p:
        return out, ["未读到接触应力表"]
    out["p_max_MPa"] = max(abs(v) for v in p)
    ans = ct["area_normal_shear"]
    if ans:
        out["contact_normal_force_rel_err"] = abs(abs(ans[1]) - meta["q"]) / meta["q"]
        out["half_width_area_mm"] = ans[0] / 2.0          # 厚度 1 mm：接触带宽 / 2
    RF = nodal(blocks, "forces", "LOFLAT")
    if RF:
        out["reaction_rel_err"] = abs(sum(v[1] for v in RF.values()) - meta["q"]) / meta["q"]
    out["half_width_mm"] = out.get("half_width_area_mm")
    out["half_width_method"] = "contact_area_statistic"
    if frd_path and Path(frd_path).is_file():
        try:
            fr = parse_frd(frd_path, want=("CONTACT",))
            blk = fr["blocks"].get("CONTACT")
            if blk and "CPRESS" in blk["comps"]:
                k = blk["comps"].index("CPRESS")
                s, pp = [], []
                for nid, vals in blk["data"].items():
                    if nid in fr["nodes"] and len(vals) > k and abs(vals[k]) > 0:
                        s.append(fr["nodes"][nid][0]); pp.append(abs(vals[k]))
                fit = post.ellipse_fit(s, pp) if len(s) >= 4 else None
                if fit:
                    out["half_width_mm"], out["half_width_method"] = fit["a"], "frd_nodal_ellipse_fit"
                    out["ellipse_fit"] = fit
        except Exception as ex:      # noqa: BLE001
            warn.append(f".frd 接触块解析失败：{ex}")
    a, p0 = meta["ref"]["half_width_mm"], meta["ref"]["p0_MPa"]
    out["p_max_rel_err"] = out["p_max_MPa"] / p0 - 1
    if out.get("half_width_mm"):
        out["half_width_rel_err"] = out["half_width_mm"] / a - 1
    return out, warn


# ================================================================== 齿形 → gmsh 边界片段
def tooth_pieces(g: SpurGear, k_list, xform, names, n_teeth_total=None):
    """沿 θ 递减方向（从 k_list 中最右侧齿的右齿槽中心到最左侧齿的左齿槽中心）生成边界片段。
    xform(R, theta) -> (x, y) 全局坐标（theta 为局部极角，已含齿号偏移）。names(k, part) -> 曲线名。"""
    rs = g.right_side()
    pitch = 2 * math.pi / g.z
    pcs = []
    def P(R, th):
        return xform(R, th)
    def arcR(R, t0, t1, nm):
        if abs(t1 - t0) < 1e-12:
            return
        pcs.append({"kind": "arc", "pts": [P(R, t0), P(R, t1)], "center": xform(0.0, 0.0), "name": nm,
                    "ccw": None})
    for k in sorted(k_list, reverse=True):
        c = k * pitch
        th_rs, th_rf = rs["root_theta"]
        arcR(g.rf, c + th_rs, c + th_rf, names(k, "ROOT"))
        fil = [g.polar(p) for p in rs["fillet"]]
        pcs.append({"kind": "spline", "pts": [P(R, c + t) for R, t in fil], "name": names(k, "R_FIL")})
        invp = [g.polar(p) for p in rs["involute"]]
        pcs.append({"kind": "spline", "pts": [P(R, c + t) for R, t in invp], "name": names(k, "R_INV")})
        arcR(g.ra, c + rs["tip_theta"], c - rs["tip_theta"], names(k, "TIP"))
        pcs.append({"kind": "spline", "pts": [P(R, c - t) for R, t in reversed(invp)], "name": names(k, "L_INV")})
        pcs.append({"kind": "spline", "pts": [P(R, c - t) for R, t in reversed(fil)], "name": names(k, "L_FIL")})
        arcR(g.rf, c - th_rf, c - th_rs, names(k, "ROOT"))
    return pcs


# ================================================================== L2 单齿齿根
def l2_gear(pt, common):
    return SpurGear(pt["z"], common["m_mm"], pt["x"], common["alpha_deg"], common["haP"], common["hfP"], pt["rhofP"])


def build_L2(case, pt, level, job_dir, coord=True):
    cm = case["common"]
    g = l2_gear(pt, cm)
    m, z = cm["m_mm"], pt["z"]
    crit = g.critical_section_30deg()
    rhoF = crit["rhoF"]
    div = case["mesh"]["root_divisions"][level]
    h_root = rhoF / div
    h_max = m * case["mesh"]["h_max_in_m"]
    pitch = 2 * math.pi / z
    r_in = g.rf - case["model"]["rim_thickness_in_m"] * m
    half = 1.5 * pitch                                 # 三齿扇区：两侧切口在齿槽中心
    def xf(R, th):
        return (R * math.sin(th), R * math.cos(th))
    def nm(k, part):
        return f"T0_{part}" if k == 0 else f"T{k + 1}_{part}" if part in ("R_INV", "L_INV") else "OTHER"
    teeth = tooth_pieces(g, (-1, 0, 1), xf, nm)
    pieces = [{"kind": "line", "pts": [xf(r_in, half), xf(g.rf, half)], "name": "SIDE_R"}] + teeth + [
        {"kind": "line", "pts": [xf(g.rf, -half), xf(r_in, -half)], "name": "SIDE_L"},
        {"kind": "arc", "pts": [xf(r_in, -half), xf(r_in, 0.0)], "center": (0, 0), "name": "INNER"},
        {"kind": "arc", "pts": [xf(r_in, 0.0), xf(r_in, half)], "center": (0, 0), "name": "INNER"}]
    # 载荷点：HPSTC（与配对齿轮共同决定）
    mate = case["common"]["mate"]
    sc = single_contact_diameter(z, mate["z"], m, cm["alpha_deg"], pt["x"], mate["x"], cm["haP"])
    Rl = sc["den"] / 2
    pl, n_out = involute_normal_at(g, Rl)
    fields = [{"kind": "curve", "curves": ["T0_R_FIL"], "h_min": h_root, "d_min": 0.25 * rhoF, "d_max": 2.5 * m},
              {"kind": "curve", "curves": ["T0_L_FIL"], "h_min": 2 * h_root, "d_min": 0.25 * rhoF, "d_max": 2.5 * m},
              {"kind": "disk", "center": pl, "h_in": m * case["mesh"]["h_load_in_m"], "r_in": 0.1 * m, "r_out": 1.5 * m}]
    elem = case["mesh"]["element"]
    mesh = mesh_2d([{"name": "SECTOR", "outer": pieces}], fields, h_max, quads=(elem != "CPE6"))
    deck = Deck(f"M37 L2 {pt['id']} z={z} x={pt['x']} rhofP={pt['rhofP']} level {level}")
    bodies = deck.mesh(mesh, quad_type=elem if elem != "CPE6" else "CPE8")
    mat = case["material"]
    deck.material(mat["E_MPa"], mat["nu"], bodies)
    fixed = mesh.edge_nodes("INNER", "SIDE_R", "SIDE_L")
    deck.nset("FIXED", fixed)
    deck.boundary([("FIXED", 1, 2)])
    # 载荷片：右齿面渐开线上距载荷点 w 内的边，均布，方向 = -外法线（沿啮合线压入齿面）
    w = case["model"]["load_patch_halfwidth_in_m"] * m
    flank = [e for e in mesh.edges["T0_R_INV"] if math.dist(mesh.nodes[e[2][2]], pl) <= w]
    if not flank:
        flank = [min(mesh.edges["T0_R_INV"], key=lambda e: math.dist(mesh.nodes[e[2][2]], pl))]
    Lp = sum(math.dist(mesh.nodes[a], mesh.nodes[c]) + math.dist(mesh.nodes[c], mesh.nodes[b]) for _, _, (a, b, c) in flank)
    Ft_b = case["load"]["Ft_per_b_N_per_mm"]
    Fn = Ft_b / math.cos(math.radians(cm["alpha_deg"]))
    deck.add("*STEP", "*STATIC")
    deck.cload(edge_load(mesh, flank, -n_out[0] * Fn / Lp, -n_out[1] * Fn / Lp))
    # 齿根集合：受拉侧过渡曲线上的边所属单元
    root_el = sorted({e for e, _, _ in mesh.edges["T0_R_FIL"]})
    deck.elset("ROOTT", root_el)
    deck.add("*NODE PRINT,NSET=FIXED", "RF")
    ip_prints(deck, "ROOTT", coord)
    deck.add("*END STEP")
    surf_pts = {}
    for e, s, row in mesh.edges["T0_R_FIL"]:
        surf_pts.setdefault(str(e), []).extend([mesh.nodes[n] for n in row])
    meta = {"case": "L2", "variant": pt["id"], "point": pt, "level": level, "h": h_root, "div": div,
            "element_types": element_types(mesh, elem), "coord_requested": coord,
            "Ft_per_b": Ft_b, "Fn_per_b": Fn, "m": m, "load_point": pl, "load_dir": [-n_out[0], -n_out[1]],
            "load_patch_length": Lp, "den_mm": sc["den"], "eps_alpha_pair": sc["eps_alpha"],
            "geometry_check": {"sFn_30deg_mm": crit["sFn"], "rhoF_30deg_mm": rhoF, "point_30deg": crit["point"],
                               "rf": g.rf, "R_form": g.info["R_form"], "sa_mm": g.info["sa"]},
            "root_surface_points": surf_pts,
            "h_check": h_check(mesh, "T0_R_FIL", h_root),
            "root_element_nodes": {str(e): [mesh.nodes[n] for n in mesh.elements[e][1]] for e in root_el}}
    return finish(job_dir, f"L2_{pt['id']}_d{div}", deck, meta, mesh)


def post_L2(meta, blocks):
    from ccx_io import nodal, ip_table
    out, warn = {}, []
    S = ip_table(blocks, "stresses", "ROOTT")
    C = ip_table(blocks, "coord", "ROOTT")
    if not S:
        return out, ["未读到齿根积分点应力"]
    by_el = {}
    for (e, ip), v in S.items():
        by_el.setdefault(e, {})[ip] = v
    ip_max = max(post.principal_max(v) for v in S.values())
    out["sigma1_ip_max_MPa"] = ip_max
    best = None
    if C:
        meth = set()
        for e, ips in by_el.items():
            keys = sorted(ips)
            xy = [(C[(e, k)][0], C[(e, k)][1]) for k in keys if (e, k) in C]
            if len(xy) != len(keys):
                continue
            targets = meta["root_surface_points"].get(str(e), [])
            if not targets:
                continue
            vals, kind, npts = post.extrapolate_element(xy, [ips[k] for k in keys], targets)
            meth.add(f"{kind}/{npts}pts")
            for t, v in zip(targets, vals):
                s1 = post.principal_max(v)
                if best is None or s1 > best[0]:
                    best = (s1, t, e)
        out["extrapolation"] = sorted(meth)
    if best:
        out["sigma1_surface_peak_MPa"] = best[0]
        out["peak_point_mm"] = best[1]
        out["sigma_root_MPa"] = best[0]
        out["sigma_root_method"] = "gauss_point_polynomial_extrapolation_to_fillet_surface_no_nodal_smoothing"
        p30 = meta["geometry_check"]["point_30deg"]
        out["peak_offset_from_30deg_point_mm"] = math.dist(best[1], p30)
        R = math.hypot(*best[1])
        out["peak_radius_mm"] = R
    else:
        out["sigma_root_MPa"] = ip_max
        out["sigma_root_method"] = "gauss_point_max_no_extrapolation"
        warn.append("无积分点坐标（COORD），σ取积分点最大值，偏低约数个百分点")
    out["YFS_FE"] = out["sigma_root_MPa"] * meta["m"] / meta["Ft_per_b"]   # b = 1 mm
    RF = nodal(blocks, "forces", "FIXED")
    if RF:
        fx, fy = sum(v[0] for v in RF.values()), sum(v[1] for v in RF.values())
        Fx, Fy = meta["load_dir"][0] * meta["Fn_per_b"], meta["load_dir"][1] * meta["Fn_per_b"]
        out["force_balance_rel"] = math.hypot(fx + Fx, fy + Fy) / meta["Fn_per_b"]
    return out, warn


# ================================================================== L3 直齿副
class PairGeo:
    def __init__(self, case):
        p = case["pair"]
        self.p = p
        a = math.radians(p["alpha_deg"])
        m = p["m_mm"]
        asn = p.get("thickness_allowance_Asn_in_m", 0.0)
        xg = lambda x: x + asn / (2 * math.tan(a))
        self.g1 = SpurGear(p["z1"], m, p["x1"], p["alpha_deg"], p["haP"], p["hfP"], p["rhofP"], x_gen=xg(p["x1"]))
        self.g2 = SpurGear(p["z2"], m, p["x2"], p["alpha_deg"], p["haP"], p["hfP"], p["rhofP"], x_gen=xg(p["x2"]))
        sc = single_contact_diameter(p["z1"], p["z2"], m, p["alpha_deg"], p["x1"], p["x2"], p["haP"])
        self.aw, self.alw, self.pb, self.eps = sc["a_w"], sc["alpha_w"], sc["pb"], sc["eps_alpha"]
        self.rw1 = self.aw * p["z1"] / (p["z1"] + p["z2"])
        self.rw2 = self.aw - self.rw1
        self.O2 = (0.0, self.aw)
        g1, g2 = self.g1, self.g2
        self.sA = self.rw2 * math.sin(self.alw) - math.sqrt(g2.ra ** 2 - g2.rb ** 2)
        self.sE = math.sqrt(g1.ra ** 2 - g1.rb ** 2) - self.rw1 * math.sin(self.alw)
        self.phiC = -g1.theta_involute(self.rw1)          # 0 号齿右齿面过节点时的小轮转角

    def loa(self, s):
        return (s * math.cos(self.alw), self.rw1 + s * math.sin(self.alw))

    def phase(self, s_ref):
        """参考齿对（小轮 0 号齿）位于啮合线坐标 s_ref 时：小轮转角 phi1、大轮转角 psi2、各在啮齿对坐标。"""
        g1, g2, z1, z2 = self.g1, self.g2, self.g1.z, self.g2.z
        phi1 = self.phiC + s_ref / g1.rb
        P = self.loa(s_ref)
        R2 = math.dist(P, self.O2)
        ang = math.atan2(P[0] - self.O2[0], P[1] - self.O2[1])
        psi2 = ang - math.pi - g2.theta_involute(R2)
        pitch2 = 2 * math.pi / z2
        psi2 = (psi2 + pitch2 / 2) % pitch2 - pitch2 / 2
        pairs = []
        for k in range(-4, 5):
            s = s_ref + k * self.pb
            if self.sA - 1e-9 <= s <= self.sE + 1e-9:
                pairs.append({"k": k, "s": s, "point": self.loa(s)})
        # 自检：所有在啮点同时落在两轮右齿面上
        for pr in pairs:
            q = pr["point"]
            R1 = math.hypot(*q)
            t1 = math.atan2(q[0], q[1])
            d1 = (t1 - (g1.theta_involute(R1) + phi1)) / (2 * math.pi / z1)
            R2 = math.dist(q, self.O2)
            t2 = math.atan2(q[0] - self.O2[0], q[1] - self.O2[1])
            d2 = (t2 - (math.pi + g2.theta_involute(R2) + psi2)) / pitch2
            if abs(d1 - round(d1)) > 1e-7 or abs(d2 - round(d2)) > 1e-7:
                raise AssertionError("啮合位置计算不自洽")
            pr["k2"] = int(round(d2))
        return phi1, psi2, pairs


def build_L3(case, job_dir, *, s_ref, div, alpha, contact, tag):
    pg = PairGeo(case)
    g1, g2 = pg.g1, pg.g2
    p, mat, ms = case["pair"], case["material"], case["mesh"]
    E, nu, m = mat["E_MPa"], mat["nu"], p["m_mm"]
    phi1, psi2, pairs = pg.phase(s_ref)
    ref = case["_ref"]
    a_ref = ref["hertz_half_width_C_mm"]
    hc = a_ref / div
    T = ref["T1_per_b_Nmm_per_mm"]
    Fn = T / g1.rb
    rbore1, rbore2 = p["bore_diameter_ratio"] * g1.r, p["bore_diameter_ratio"] * g2.r
    def xf1(R, th):
        t = th + phi1
        return (R * math.sin(t), R * math.cos(t))
    def xf2(R, th):
        t = math.pi + th + psi2
        return (pg.O2[0] + R * math.sin(t), pg.O2[1] + R * math.cos(t))
    near1 = set(range(-2, 3))
    def nm1(k, part):
        kk = (k + g1.z // 2) % g1.z - g1.z // 2
        if kk in near1 and part in ("R_INV", "TIP"):
            return "P_FLANK"
        return "P_OTHER"
    # 大轮：与小轮在啮齿相对的齿号
    k2s = {pr["k2"] for pr in pairs}
    k2c = round(sum(k2s) / len(k2s))
    near2 = set(range(k2c - 2, k2c + 3))
    def nm2(k, part):
        if k in near2 and part in ("R_INV", "TIP"):
            return "W_FLANK"
        return "W_OTHER"
    kk1 = list(range(-(g1.z // 2), g1.z - g1.z // 2))
    kk2 = list(range(k2c - g2.z // 2, k2c - g2.z // 2 + g2.z))
    def full(g, xf, nmf, kk, rbore, cx, name):
        pcs = tooth_pieces(g, kk, xf, nmf)
        # 首尾相接：最右齿的右齿槽中心 = 最左齿的左齿槽中心 + 2π（同一点，坐标完全一致）
        first, last = pcs[0]["pts"][0], pcs[-1]["pts"][-1]
        if math.dist(first, last) > 1e-7:
            raise AssertionError("齿圈未闭合")
        pcs[-1]["pts"][-1] = first
        c = cx
        bore = [{"kind": "arc", "pts": [(c[0] + rbore, c[1]), (c[0], c[1] + rbore)], "center": c, "name": name + "_BORE"},
                {"kind": "arc", "pts": [(c[0], c[1] + rbore), (c[0] - rbore, c[1])], "center": c, "name": name + "_BORE"},
                {"kind": "arc", "pts": [(c[0] - rbore, c[1]), (c[0], c[1] - rbore)], "center": c, "name": name + "_BORE"},
                {"kind": "arc", "pts": [(c[0], c[1] - rbore), (c[0] + rbore, c[1])], "center": c, "name": name + "_BORE"}]
        return {"name": name, "outer": pcs, "holes": [bore]}
    surfs = [full(g1, xf1, nm1, kk1, rbore1, (0.0, 0.0), "PINION"), full(g2, xf2, nm2, kk2, rbore2, pg.O2, "WHEEL")]
    fields = [{"kind": "curve", "curves": ["P_FLANK", "W_FLANK"], "h_min": m * ms["h_flank_in_m"], "d_min": 0.0,
               "d_max": 2 * m}]
    for pr in pairs:
        fields.append({"kind": "disk", "center": pr["point"], "h_in": hc, "r_in": ms["refine_radius_in_a"] * a_ref,
                       "r_out": ms["refine_radius_in_a"] * a_ref + ms["grade_length_in_m"] * m})
    mesh = mesh_2d(surfs, fields, m * ms["h_max_in_m"], quads=False)
    deck = Deck(f"M37 L3 {case['id']} s={s_ref:.5f} div {div} {contact} alpha {alpha}")
    bodies = deck.mesh(mesh)
    deck.material(E, nu, bodies)
    K = alpha * E / hc
    deck.surface("PFL", mesh.edges["P_FLANK"])
    deck.surface("WFL", mesh.edges["W_FLANK"])
    deck.contact("PFL", "WFL", contact, K)
    # 小轮内孔刚性转动（*EQUATION，主节点在 (rbore,0)）；大轮内孔固定
    pb_nodes = mesh.edge_nodes("PINION_BORE")
    mnode = min(pb_nodes, key=lambda n: math.dist(mesh.nodes[n], (rbore1, 0.0)))
    if math.dist(mesh.nodes[mnode], (rbore1, 0.0)) > 1e-9:
        raise AssertionError("主节点不在 (rbore,0)")
    extra_fixed = []
    for n in pb_nodes:
        if n == mnode:
            continue
        x, y = mesh.nodes[n]
        for dof, coef in ((1, y / rbore1), (2, -x / rbore1)):
            if abs(coef) < 1e-12:
                extra_fixed.append((n, dof, dof))
            else:
                deck.equation([(n, dof, 1.0), (mnode, 2, coef)])
    wb = mesh.edge_nodes("WHEEL_BORE")
    deck.nset("WBORE", wb)
    deck.nset("PMASTER", [mnode])
    fixed = [("WBORE", 1, 2), (mnode, 1, 1)] + extra_fixed
    deck.boundary(fixed)
    c_iso = ref["c_prime_th_CB_N_per_mm_um"]
    d0 = 0.3 * Fn / c_iso * 1e-3                 # mm，沿啮合线
    th0 = d0 / g1.rb
    deck.add("*STEP,INC=300", "*STATIC", "0.25,1,1e-7,0.5")
    deck.boundary([(mnode, 2, 2, -th0 * rbore1)])
    deck.add("*END STEP", "*STEP,INC=300", "*STATIC", "0.25,1,1e-7,0.5")
    deck.boundary(fixed, op_new=True)
    deck.cload({(mnode, 2): -T / rbore1})
    deck.add("*NODE PRINT,NSET=PMASTER", "U", "*NODE PRINT,NSET=WBORE", "RF")
    deck.add("*CONTACT PRINT,SLAVE=PFL,MASTER=WFL", "CDIS,CSTR,CF")
    deck.add("*END STEP")
    meta = {"case": "L3", "variant": contact, "tag": tag, "s_ref": s_ref, "div": div, "alpha": alpha, "h": hc,
            "penalty": K if contact == "penalty" else None, "pairs_in_contact": len(pairs),
            "pairs": [{"k": pr["k"], "s": pr["s"], "point": pr["point"]} for pr in pairs],
            "phi1": phi1, "psi2": psi2, "T_per_b": T, "Fn_per_b": Fn, "rb1": g1.rb, "rb2": g2.rb,
            "rbore1": rbore1, "O2": pg.O2, "wbore_xy": {str(n): mesh.nodes[n] for n in wb},
            "element_types": element_types(mesh, "CPE8"),
            "h_check": h_check(mesh, "P_FLANK", hc, near=[pr["point"] for pr in pairs], radius=1.5 * a_ref)}
    return finish(job_dir, tag, deck, meta, mesh)


def post_L3(meta, blocks):
    from ccx_io import nodal, contact_tables
    out, warn = {}, []
    U = nodal(blocks, "displacements", "PMASTER")
    if not U:
        return out, ["未读到小轮主节点位移"]
    v = list(U.values())[0][1]
    theta = -v / meta["rbore1"]
    delta_um = meta["rb1"] * theta * 1e3
    out["theta_rad"] = theta
    out["delta_LOA_um"] = delta_um
    out["mesh_stiffness_N_per_mm_um"] = meta["Fn_per_b"] / delta_um
    ct = contact_tables(blocks)
    p = pressure_col(ct["stress_rows"])
    if p:
        out["p_max_MPa"] = max(abs(x) for x in p)
    else:
        warn.append("未读到接触应力表")
    if ct["area_normal_shear"]:
        out["contact_normal_force_rel_err"] = abs(abs(ct["area_normal_shear"][1]) - meta["Fn_per_b"]) / meta["Fn_per_b"]
    RF = nodal(blocks, "forces", "WBORE")
    if RF:
        cx, cy = meta["O2"]
        Mz = sum((meta["wbore_xy"][str(n)][0] - cx) * f[1] - (meta["wbore_xy"][str(n)][1] - cy) * f[0]
                 for n, f in RF.items() if str(n) in meta["wbore_xy"])
        expect = meta["T_per_b"] * meta["rb2"] / meta["rb1"]
        out["wheel_torque_rel_err"] = abs(abs(Mz) - expect) / expect
    return out, warn
