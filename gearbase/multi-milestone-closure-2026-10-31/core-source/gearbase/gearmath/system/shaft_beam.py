"""轴的梁模型：多支承（含超静定三支承）支反力、挠度、截面转角、扭转角 —— 直接刚度法（梁理论）。

模型（工程力学，非标准条文；证据等级 null，见 tests/test_m36_shaft_beam.py 的闭式解独立重写）：
  - 直轴，轴线 x（mm）；分段等截面（实心/空心圆截面，segments 同 shaft_line）；材料 E、G（N/mm²）显式给出。
  - 支承：n ≥ 2 个刚性点支承（径向位移 = 0，转角自由）；仅一个定位支承承受全部轴向力（调用方显式指定）。
    n = 2 时与 shaft_line.solve 静力结果相同；n ≥ 3 为超静定，由刚度法求解（等价于力法的变形协调）。
  - 载荷：shaft_line 的集中载荷（point_load / mesh_point_load / torque_load）与均布横向线载荷（shaft_line.line_load）。
    偏心轴向力与集中力偶产生的弯矩按 r×F + C 计入节点力偶。
  - 两个横向平面（x–y、x–z）分别求解；单元为两节点梁单元：
      shear_model = "euler_bernoulli"：Φ = 0；
      shear_model = "timoshenko"：Φ = 12·E·I·α_s/(G·A·L²)，α_s 为剪切修正系数（γ = α_s·Q/(G·A)，实心圆约 1,1），调用方显式给出。
    均布载荷按固端力等效为节点力（对等截面单元节点位移精确）；全部载荷/支承/轴段分界/线载荷端点/eval_points 都是节点，
    节点位移、转角为梁理论精确值；节点之间不插值（deflection_at 只接受节点）。
  - 转角为截面转角 ψ（Timoshenko 下不含剪切角 γ）；轴承"倾斜"取支承节点 ψ。
  - 扭转角：∫ T(x)/(G·Ip(x)) dx，T 来自截面内力（集中扭矩 → 分段常数），逐段精确求和。
未收录（TODO）：轴承径向/角刚度与游隙、壳体变形、轴向变形、离心/陀螺效应、临界转速、非均布线载荷、分布扭矩。
本模块不 import gearmath.gear；送 KHβ 的齿宽方向变形只留接口桩（mesh_width_deflection_stub），不做 ISO 6336 f_sh 换算。
单位：长度 mm；力 N；力矩 N·mm；应力/模量 N/mm²；转角 rad。
"""
from __future__ import annotations

import math

from . import shaft_line
from ._base import MissingInput, OutOfDomain, Unconfirmed, bad, choice, make_registry, num, pos

FORMULAS, _formula = make_registry("", "工程力学梁理论（非标准条文）；测试为闭式解与数值积分独立重写对拍")
SHEAR_MODELS = ("euler_bernoulli", "timoshenko")
_TOL = 1e-9


def _section(d, di):
    I = math.pi * (d ** 4 - di ** 4) / 64.0
    A = math.pi * (d ** 2 - di ** 2) / 4.0
    return I, A, 2.0 * I


@_formula("mech.beam_element", "工程力学：两节点梁单元刚度 k = EI/(L³(1+Φ))·[[12, 6L, −12, 6L], [6L, (4+Φ)L², −6L, (2−Φ)L²], …]，"
          "Φ = 12EIα_s/(GAL²)（Timoshenko；Euler–Bernoulli 时 Φ = 0）；均布载荷固端力 (qL/2, qL²/12, qL/2, −qL²/12)",
          basis="mechanics")
def element_stiffness(*, EI, GA_over_alpha, L):
    """返回 4×4 单元刚度（自由度 v1、ψ1、v2、ψ2）。GA_over_alpha 为 None 表示 Euler–Bernoulli（调用方显式）。"""
    EI, L = pos("EI", EI), pos("L", L)
    phi = 0.0 if GA_over_alpha is None else 12.0 * EI / (pos("GA_over_alpha", GA_over_alpha) * L * L)
    c = EI / (L ** 3 * (1.0 + phi))
    return [[c * 12, c * 6 * L, -c * 12, c * 6 * L],
            [c * 6 * L, c * (4 + phi) * L * L, -c * 6 * L, c * (2 - phi) * L * L],
            [-c * 12, -c * 6 * L, c * 12, -c * 6 * L],
            [c * 6 * L, c * (2 - phi) * L * L, -c * 6 * L, c * (4 + phi) * L * L]]


def _solve_linear(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for k in range(n):
        piv = max(range(k, n), key=lambda r: abs(M[r][k]))
        if abs(M[piv][k]) < 1e-300:
            raise OutOfDomain("supports", "刚度矩阵奇异（支承不足以约束刚体位移）")
        M[k], M[piv] = M[piv], M[k]
        for r in range(k + 1, n):
            f = M[r][k] / M[k][k]
            if f:
                for cidx in range(k, n + 1):
                    M[r][cidx] -= f * M[k][cidx]
    x = [0.0] * n
    for k in range(n - 1, -1, -1):
        x[k] = (M[k][n] - sum(M[k][j] * x[j] for j in range(k + 1, n))) / M[k][k]
    return x


def _unique_sorted(xs):
    out = []
    for x in sorted(xs):
        if not out or abs(x - out[-1]) > _TOL:
            out.append(x)
    return out


def _node_index(nodes, x):
    for i, xn in enumerate(nodes):
        if abs(xn - x) <= _TOL:
            return i
    return None


@_formula("mech.beam_stiffness_method", "工程力学：直接刚度法 K·u = f + R，刚性点支承处径向位移为 0；R = K·u − f（支反力）；"
          "n ≥ 3 支承为超静定（与力法变形协调等价）；轴向力全部由定位支承承担；扭矩须自平衡",
          basis="mechanics")
def solve_beam(*, supports, axial_support, loads, segments, E, G, shear_model, shear_factor, eval_points):
    """supports：[{"name", "x"}]（≥ 2，名称、位置互异）；axial_support：定位支承名称。
    shear_model ∈ SHEAR_MODELS；timoshenko 时 shear_factor（α_s）必需，euler_bernoulli 时须为 None。
    eval_points：需要输出挠度/转角的附加节点位置列表（可为空列表，不可为 None）。
    返回模型 dict（可直接交给 shaft_line.section_check / internal_forces）。"""
    if not supports or len(supports) < 2:
        raise MissingInput("supports（至少 2 个刚性点支承）")
    sp = []
    for i, s in enumerate(supports):
        if s.get("name") is None or s.get("x") is None:
            raise MissingInput(f"supports[{i}].name/x")
        sp.append({"name": s["name"], "x": num(f"supports[{i}].x", s["x"])})
    names = [s["name"] for s in sp]
    if len(set(names)) != len(names):
        raise bad("supports", "支承名称须互异")
    sp.sort(key=lambda s: s["x"])
    if any(b["x"] - a["x"] <= _TOL for a, b in zip(sp, sp[1:])):
        raise OutOfDomain("supports", "支承位置须互异")
    ax = choice("axial_support", axial_support, tuple(names))
    if not loads:
        raise MissingInput("loads")
    segs = shaft_line._segments(segments)
    E, G = pos("E", E), pos("G", G)
    sm = choice("shear_model", shear_model, SHEAR_MODELS)
    if sm == "timoshenko":
        alpha = pos("shear_factor", shear_factor)
    else:
        if shear_factor is not None:
            raise bad("shear_factor", "euler_bernoulli 不用剪切修正系数，须为 None")
        alpha = None
    if eval_points is None:
        raise MissingInput("eval_points（无附加点时传空列表）")
    lo, hi = segs[0][0], segs[-1][1]
    xs = [lo, hi] + [s[0] for s in segs] + [s["x"] for s in sp] + [num("eval_points", e) for e in eval_points]
    for ld in loads:
        xs += [ld["x0"], ld["x1"]] if ld.get("kind") == "line" else [ld["x"]]
    for x in xs:
        if not lo - _TOL <= x <= hi + _TOL:
            raise OutOfDomain("x", f"x = {x} 不在轴段范围 [{lo}, {hi}] 内")
    nodes = _unique_sorted(xs)

    # 扭矩自平衡与轴向力（与 shaft_line.solve 同口径）
    SF = [0.0, 0.0, 0.0]
    Mx, absT = 0.0, 0.0
    for ld in loads:
        m = shaft_line._cross((0.0, ld["y"], ld["z"]), ld["F"])
        for k in range(3):
            SF[k] += ld["F"][k]
        Mx += m[0] + ld["C"][0]
        absT += abs(m[0] + ld["C"][0])
    if abs(Mx) > 1e-9 * max(absT, 1.0):
        raise OutOfDomain("torque_balance", f"扭矩不平衡 ΣMx = {Mx} N·mm：输入/输出扭矩须全部显式给出")

    n = len(nodes)
    ndof = 2 * n
    planes = {}
    for plane in ("y", "z"):
        K = [[0.0] * ndof for _ in range(ndof)]
        f = [0.0] * ndof
        for e in range(n - 1):
            xa, xb = nodes[e], nodes[e + 1]
            xm = 0.5 * (xa + xb)
            g = next(s for s in segs if s[0] - _TOL <= xm <= s[1] + _TOL)
            I, A, _ = _section(g[2], g[3])
            k = element_stiffness(EI=E * I, GA_over_alpha=None if alpha is None else G * A / alpha, L=xb - xa)
            dofs = (2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3)
            for i in range(4):
                for j in range(4):
                    K[dofs[i]][dofs[j]] += k[i][j]
            for ld in loads:   # 均布线载荷固端力
                if ld.get("kind") == "line" and ld["x0"] - _TOL <= xa and xb <= ld["x1"] + _TOL:
                    q = ld["F"][1 if plane == "y" else 2] / (ld["x1"] - ld["x0"])
                    L = xb - xa
                    for dof, val in zip(dofs, (q * L / 2, q * L * L / 12, q * L / 2, -q * L * L / 12)):
                        f[dof] += val
        for ld in loads:
            if ld.get("kind") == "line":
                continue
            i = _node_index(nodes, ld["x"])
            m = shaft_line._cross((0.0, ld["y"], ld["z"]), ld["F"])
            My, Mz = m[1] + ld["C"][1], m[2] + ld["C"][2]
            if plane == "y":
                f[2 * i] += ld["F"][1]
                f[2 * i + 1] += Mz                 # ψ 与 dv/dx 同向，共轭力偶为 Mz
            else:
                f[2 * i] += ld["F"][2]
                f[2 * i + 1] += -My                # θy = −dw/dx，与 dw/dx 共轭的力偶为 −My
        fixed = [2 * _node_index(nodes, s["x"]) for s in sp]
        free = [d for d in range(ndof) if d not in fixed]
        u_free = _solve_linear([[K[i][j] for j in free] for i in free], [f[i] for i in free])
        u = [0.0] * ndof
        for d, v in zip(free, u_free):
            u[d] = v
        R = {s["name"]: sum(K[d][j] * u[j] for j in range(ndof)) - f[d] for s, d in zip(sp, fixed)}
        planes[plane] = {"u": u, "R": R}
    reac = {}
    for s in sp:
        reac[s["name"]] = (-SF[0] if s["name"] == ax else 0.0, planes["y"]["R"][s["name"]], planes["z"]["R"][s["name"]])
    defl = [{"x": x, "v": planes["y"]["u"][2 * i], "w": planes["z"]["u"][2 * i],
             "psi_y_plane": planes["y"]["u"][2 * i + 1], "psi_z_plane": planes["z"]["u"][2 * i + 1]} for i, x in enumerate(nodes)]
    for dd in defl:
        dd["radial"] = math.hypot(dd["v"], dd["w"])
        dd["rotation"] = math.hypot(dd["psi_y_plane"], dd["psi_z_plane"])
    return {"support_points": sp, "axial_support": ax, "loads": list(loads), "segments": segs, "reactions": reac,
            "bearing_loads": {k: {"F_r": math.hypot(v[1], v[2]), "F_a": abs(v[0])} for k, v in reac.items()},
            "nodes": nodes, "deflection": defl, "E": E, "G": G, "shear_model": sm, "shear_factor": alpha,
            "statically_indeterminate": len(sp) > 2,
            "force_residual": tuple(SF[k] + sum(r[k] for r in reac.values()) for k in range(3))}


def deflection_at(*, model, x):
    """节点处挠度/截面转角（x 须为节点，否则阻断：请把 x 放进 eval_points）。"""
    xs = num("x", x)
    i = _node_index(model["nodes"], xs)
    if i is None:
        raise OutOfDomain("x", f"x = {xs} 不是求解节点：请在 eval_points 中给出后重新求解（节点之间不插值）")
    return dict(model["deflection"][i])


@_formula("mech.beam_max_deflection", "工程力学：节点径向挠度 √(v² + w²) 的最大值及位置（节点精确值）", basis="mechanics")
def max_deflection(*, model):
    d = max(model["deflection"], key=lambda r: r["radial"])
    return {"x": d["x"], "radial": d["radial"]}


def support_misalignment(*, model):
    """各支承节点的截面转角（rad）：两平面分量与合成值（刚性支承，未计轴承游隙/刚度）。"""
    out = {}
    for s in model["support_points"]:
        d = deflection_at(model=model, x=s["x"])
        out[s["name"]] = {"psi_y_plane": d["psi_y_plane"], "psi_z_plane": d["psi_z_plane"], "rotation": d["rotation"]}
    return out


@_formula("mech.torsion_angle", "工程力学：扭转角 φ = ∫ T(x)/(G·Ip(x)) dx，Ip = π(d⁴ − d_i⁴)/32；T 由截面内力分段常数逐段精确求和",
          basis="mechanics")
def torsion_angle(*, model, x_from, x_to):
    """x_from → x_to 的相对扭转角（rad，按 shaft_line.internal_forces 的 T 符号）。"""
    a, b = num("x_from", x_from), num("x_to", x_to)
    if b <= a:
        raise OutOfDomain("x_to", "须 x_to > x_from")
    cuts = [a, b] + [s[0] for s in model["segments"]] + [s[1] for s in model["segments"]]
    cuts += [ld["x"] for ld in model["loads"] if ld.get("kind") != "line"]
    cuts += [sp["x"] for sp in model["support_points"]] if "support_points" in model else [model["x_A"], model["x_B"]]
    pts = [x for x in _unique_sorted(cuts) if a - _TOL <= x <= b + _TOL]
    phi = 0.0
    for x0, x1 in zip(pts, pts[1:]):
        xm = 0.5 * (x0 + x1)
        g = shaft_line.section_geometry(model=model, x=xm)
        Ip = _section(g["d"], g["d_i"])[2]
        phi += shaft_line.internal_forces(model=model, x=xm)["T"] / (model["G"] * Ip) * (x1 - x0)
    return phi


def bearing_checks(*, model, bearings):
    """bearings：{支承名: iso281.bearing_life 除 F_r、F_a 外的全部关键字参数}；须覆盖全部支承。"""
    if not bearings:
        raise MissingInput("bearings")
    from . import iso281
    out = {}
    for s in model["support_points"]:
        spec = bearings.get(s["name"])
        if spec is None:
            raise MissingInput(f"bearings.{s['name']}")
        bl = model["bearing_loads"][s["name"]]
        out[s["name"]] = {"F_r": bl["F_r"], "F_a": bl["F_a"], **iso281.bearing_life(F_r=bl["F_r"], F_a=bl["F_a"], **spec)}
    return out


def mesh_width_deflection_stub(*, model, x0, x1, direction_deg):
    """【接口桩】齿宽范围 [x0, x1] 内各节点挠度在给定横向方向（y–z 平面内，与 +y 轴夹角 direction_deg）上的投影。

    供齿轮侧 KHβ（ISO 6336-1 的 f_sh 等）将来使用：本函数只给力学量（节点投影挠度、首尾差、线性端点连线的最大偏离），
    不做任何齿轮换算（啮合线方向、f_sh 定义、扭转变形叠加均由齿轮侧决定）。x0、x1 须为节点（经 eval_points 给出）。"""
    a, b = num("x0", x0), num("x1", x1)
    if b <= a:
        raise OutOfDomain("x1", "须 x1 > x0")
    for xx in (a, b):
        if _node_index(model["nodes"], xx) is None:
            raise OutOfDomain("x", f"x = {xx} 不是求解节点：请在 eval_points 中给出")
    th = math.radians(num("direction_deg", direction_deg))
    c, s = math.cos(th), math.sin(th)
    pts = [(d["x"], d["v"] * c + d["w"] * s) for d in model["deflection"] if a - _TOL <= d["x"] <= b + _TOL]
    (xa, ya), (xb, yb) = pts[0], pts[-1]
    dev = [y - (ya + (yb - ya) * (x - xa) / (xb - xa)) for x, y in pts]
    return {"status": "stub：未接 KHβ（ISO 6336-1 f_sh 换算未实现）", "points": pts, "end_difference": yb - ya,
            "max_deviation_from_chord": max(dev, key=abs), "n_points": len(pts)}


UNCONFIRMED = {
    "shaft_beam.bearing_stiffness": "轴承径向/角刚度、游隙、壳体刚度：未收录（支承为刚性点支承）→ 需要时阻断由调用方另建模",
    "shaft_beam.khbeta": "齿宽方向变形 → KHβ（ISO 6336-1 附录 f_sh、扭转叠加）：只留接口桩 mesh_width_deflection_stub",
    "shaft_beam.critical_speed": "临界转速、陀螺效应、离心：TODO",
    "shaft_beam.nonuniform_loads": "非均布线载荷、分布扭矩、自重：TODO",
    "shaft_beam.shear_factor": "剪切修正系数 α_s（实心圆约 1,1）由调用方显式给出，本库不默认",
}
