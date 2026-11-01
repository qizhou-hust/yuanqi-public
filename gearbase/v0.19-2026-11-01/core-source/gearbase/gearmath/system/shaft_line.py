"""最小轴系载荷传递模型："齿轮啮合力 → 轴 → 支承（轴承）/截面（DIN 743）"。

模型（静定，工程力学，非标准条文；证据等级 null）：
  - 直轴，轴线为 x（mm）；两个点支承 A、B（简支，静定）；只有一个定位支承承受全部轴向力（调用方显式指定 A 或 B）。
  - 载荷：作用点 (x, y, z) 处的集中力 F = (Fx, Fy, Fz)（N）与集中力偶 C = (Cx, Cy, Cz)（N·mm）；
    齿轮啮合力由 mesh_point_load() 按啮合点方位角、节圆半径换成三维力，轴向力偏心产生的弯矩、切向力产生的扭矩由叉积自动计入。
  - 扭矩须自平衡（ΣMx = 0，输入与输出扭矩都须显式给出），否则阻断。
  - 截面内力：取截面左侧隔离体，N（拉为正）、扭矩 T、合成弯矩 Mb = √(My² + Mz²)、合成剪力 Q。
  - 截面恰在集中载荷/支承/轴段分界处时内力或直径不唯一 → 阻断（调用方把截面放在相邻一侧）。
  - 均布线载荷（line_load，仅横向力，如按齿宽分布的啮合力）：v0.14 EXTC 起支持；静力求解按合力，截面内力按左侧实际分布段。
  - 超静定（三支承及以上）与挠度/转角：见 shaft_beam.py（刚度法梁理论）；其模型可直接交给本模块 section_check；
    端到端 run_beam()（v0.15 EXTM36）= solve_beam → section_check → ISO 281，并给出挠度/支承转角/扭转角。
  - 临界转速、剪切应力、轴承刚度：未实现（TODO）。
与标准的衔接（不复制公式，调用已登记模块）：
  - 截面名义应力与 DIN 743 疲劳/静强度：gearmath.system.din743（working_stresses、fatigue_proof、maximum_stresses、safety_static）。
  - 支反力 → ISO 281：gearmath.system.iso281.bearing_life。
应力状态：本轮只支持 'rotating_shaft_stationary_loads'（轴旋转、载荷方向固定、载荷恒定）：
  弯曲为完全对称循环 σba = Mb/Wb、σbm = 0；扭转与轴力恒定 τta = 0、τtm = T/Wt、σzda = 0、σzdm = N/A。
  其它载荷谱/变扭矩须调用方另行给出（TODO）。
本模块不 import gearmath.gear；齿轮输出（F_t 等）由调用方取出后显式传入。
"""
from __future__ import annotations

import math

from . import din743, iso281
from ._base import MissingInput, OutOfDomain, Unconfirmed, bad, choice, make_registry, nonneg, num, pos

FORMULAS, _formula = make_registry("", "工程力学通用关系（非标准条文）；测试为独立重写与平衡自洽检查")
STRESS_STATES = ("rotating_shaft_stationary_loads",)


# ------------------------------------------------------------------ 载荷构造
@_formula("mech.mesh_forces", "工程力学：节圆处 F_r = F_tw·tan α_wt、F_a = F_tw·tan β_w（F_tw 为工作节圆切向力）", basis="mechanics",
          note="对 ISO 6336 的 F_t = 2T/d（分度圆）：直齿变位或中心距变动时 F_tw ≠ F_t，调用方须给工作节圆值；斜齿 F_tw·tanβ_w = F_t·tanβ")
def mesh_forces(*, F_tw, alpha_wt_deg, beta_w_deg):
    Ft = pos("F_tw", F_tw)
    a, b = num("alpha_wt_deg", alpha_wt_deg), num("beta_w_deg", beta_w_deg)
    if not 0 < a < 90 or not 0 <= b < 90:
        raise OutOfDomain("angles", "须 0 < α_wt < 90°、0 ≤ β_w < 90°")
    return {"F_t": Ft, "F_r": Ft * math.tan(math.radians(a)), "F_a": Ft * math.tan(math.radians(b))}


def mesh_point_load(*, name, x, F_t, F_r, F_a, r_w, theta_deg, tangential_sign, axial_sign):
    """啮合点集中力：啮合点位于 (x, r_w·cosθ, r_w·sinθ)。
    径向力指向本轴轴线（外啮合）；切向力沿 tangential_sign·(−sinθ, cosθ)；轴向力沿 axial_sign·x。
    tangential_sign / axial_sign ∈ {+1, −1} 由调用方按主/从动与旋向显式给出（不推断）。"""
    th = math.radians(num("theta_deg", theta_deg))
    ts, as_ = choice("tangential_sign", tangential_sign, (1, -1)), choice("axial_sign", axial_sign, (1, -1))
    Ft, Fr, Fa, r = nonneg("F_t", F_t), nonneg("F_r", F_r), nonneg("F_a", F_a), pos("r_w", r_w)
    c, s = math.cos(th), math.sin(th)
    F = (as_ * Fa, -Fr * c + ts * Ft * (-s), -Fr * s + ts * Ft * c)
    return {"name": name, "x": num("x", x), "y": r * c, "z": r * s, "F": F, "C": (0.0, 0.0, 0.0), "kind": "mesh"}


def point_load(*, name, x, y, z, F, C):
    """一般集中载荷；F、C 为三元组（缺省请显式传 (0,0,0)）。"""
    if F is None:
        raise MissingInput("F")
    if C is None:
        raise MissingInput("C")
    if len(F) != 3 or len(C) != 3:
        raise bad("F/C", "须为三元组")
    return {"name": name, "x": num("x", x), "y": num("y", y), "z": num("z", z),
            "F": tuple(num("F", v) for v in F), "C": tuple(num("C", v) for v in C), "kind": "point"}


def line_load(*, name, x0, x1, F):
    """均布线载荷：在 [x0, x1] 上均匀分布的横向合力 F = (0, Fy, Fz)（N），作用线过轴线（无偏心、无力偶）。
    轴向分量须为 0（分布轴向力未收录 → 阻断）。静力等效于作用在中点的集中力。"""
    a, b = num("x0", x0), num("x1", x1)
    if b <= a:
        raise OutOfDomain("x1", "须 x1 > x0")
    if F is None:
        raise MissingInput("F")
    if len(F) != 3:
        raise bad("F", "须为三元组")
    Fv = tuple(num("F", v) for v in F)
    if Fv[0] != 0.0:
        raise Unconfirmed("F", "分布轴向力未收录（仅横向线载荷）")
    return {"name": name, "x": 0.5 * (a + b), "x0": a, "x1": b, "y": 0.0, "z": 0.0, "F": Fv, "C": (0.0, 0.0, 0.0), "kind": "line"}


def torque_load(*, name, x, T):
    """纯扭矩（如联轴器输入/输出），Cx = T（右手定则，沿 +x 为正）。"""
    return {"name": name, "x": num("x", x), "y": 0.0, "z": 0.0, "F": (0.0, 0.0, 0.0), "C": (num("T", T), 0.0, 0.0), "kind": "torque"}


# ------------------------------------------------------------------ 求解
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _segments(segs):
    if not segs:
        raise MissingInput("segments")
    out = []
    for i, s in enumerate(segs):
        for k in ("x0", "x1", "d", "d_i"):
            if s.get(k) is None:
                raise MissingInput(f"segments[{i}].{k}")
        x0, x1, d, di = num("x0", s["x0"]), num("x1", s["x1"]), pos("d", s["d"]), nonneg("d_i", s["d_i"])
        if x1 <= x0 or di >= d:
            raise OutOfDomain(f"segments[{i}]", "须 x1 > x0 且 d_i < d")
        out.append((x0, x1, d, di))
    out.sort()
    for a, b in zip(out, out[1:]):
        if abs(a[1] - b[0]) > 1e-9:
            raise OutOfDomain("segments", f"轴段不连续或重叠：{a[1]} vs {b[0]}")
    return out


@_formula("mech.two_support_statics", "工程力学：简支双支承静力平衡 ΣF = 0、ΣM_A = 0（支反力），定位支承承受全部轴向力；扭矩自平衡检查",
          basis="mechanics")
def solve(*, x_A, x_B, axial_support, loads, segments):
    """返回模型 dict：reactions（A、B 的三向反力，N）、bearing_loads（径向合力与轴向力）、loads、segments。"""
    xA, xB = num("x_A", x_A), num("x_B", x_B)
    if xB <= xA:
        raise OutOfDomain("x_B", "须 x_B > x_A")
    ax = choice("axial_support", axial_support, ("A", "B"))
    if not loads:
        raise MissingInput("loads")
    segs = _segments(segments)
    lo, hi = segs[0][0], segs[-1][1]
    for ld in loads + [{"name": "A", "x": xA}, {"name": "B", "x": xB}]:
        for xx in (ld["x"], ld.get("x0", ld["x"]), ld.get("x1", ld["x"])):
            if not lo <= xx <= hi:
                raise OutOfDomain(ld["name"], f"x = {xx} 不在轴段范围 [{lo}, {hi}] 内")
    SF = [0.0, 0.0, 0.0]
    MA = [0.0, 0.0, 0.0]
    absT = 0.0
    for ld in loads:
        r = (ld["x"] - xA, ld["y"], ld["z"])
        m = _cross(r, ld["F"])
        for k in range(3):
            SF[k] += ld["F"][k]
            MA[k] += m[k] + ld["C"][k]
        absT += abs(m[0] + ld["C"][0])
    if abs(MA[0]) > 1e-9 * max(absT, 1.0):
        raise OutOfDomain("torque_balance", f"扭矩不平衡 ΣMx = {MA[0]} N·mm：输入/输出扭矩须全部显式给出")
    L = xB - xA
    B = [0.0, -MA[2] / L, MA[1] / L]
    A = [0.0, -SF[1] - B[1], -SF[2] - B[2]]
    if ax == "A":
        A[0] = -SF[0]
    else:
        B[0] = -SF[0]
    reac = {"A": tuple(A), "B": tuple(B)}
    bl = {k: {"F_r": math.hypot(v[1], v[2]), "F_a": abs(v[0])} for k, v in reac.items()}
    return {"x_A": xA, "x_B": xB, "axial_support": ax, "loads": list(loads), "segments": segs,
            "reactions": reac, "bearing_loads": bl,
            "transmitted_torque": max(abs(ld["C"][0] + _cross((0.0, ld["y"], ld["z"]), ld["F"])[0]) for ld in loads)}


def _support_points(model):
    """两支承模型（solve）用 x_A/x_B；多支承模型（shaft_beam.solve_beam）用 support_points。"""
    if "support_points" in model:
        return [(sp["x"], sp["name"]) for sp in model["support_points"]]
    return [(model["x_A"], "A"), (model["x_B"], "B")]


@_formula("mech.section_resultants", "工程力学：截面左侧隔离体合力/合力矩，N = −ΣFx、M = −Σ(r − x_s)×F − ΣC，Mb = √(My²+Mz²)；"
          "均布线载荷取截面左侧部分的合力（作用于该部分中点）",
          basis="mechanics")
def internal_forces(*, model, x):
    xs = num("x", x)
    items = []
    for ld in model["loads"]:
        if ld.get("kind") == "line":
            if ld["x0"] < xs:
                b = min(xs, ld["x1"])
                frac = (b - ld["x0"]) / (ld["x1"] - ld["x0"])
                xm = 0.5 * (ld["x0"] + b)
                items.append((xm, (xm, 0.0, 0.0), tuple(frac * f for f in ld["F"]), (0.0, 0.0, 0.0), ld["name"], False))
            continue
        items.append((ld["x"], (ld["x"], ld["y"], ld["z"]), ld["F"], ld["C"], ld["name"], True))
    items += [(xp, (xp, 0.0, 0.0), model["reactions"][nm], (0.0, 0.0, 0.0), f"support {nm}", True)
              for xp, nm in _support_points(model)]
    for xi, _, _, _, nm, concentrated in items:
        if concentrated and abs(xi - xs) < 1e-9:
            raise OutOfDomain("x", f"截面 x = {xs} 与 {nm} 重合，内力不唯一：请把截面放在相邻一侧")
    F = [0.0, 0.0, 0.0]
    M = [0.0, 0.0, 0.0]
    for xi, r, f, c, _, _ in items:
        if xi < xs:
            m = _cross((r[0] - xs, r[1], r[2]), f)
            for k in range(3):
                F[k] += f[k]
                M[k] += m[k] + c[k]
    N, Qy, Qz = -F[0], -F[1], -F[2]
    T, My, Mz = -M[0], -M[1], -M[2]
    return {"x": xs, "N": N, "Q": math.hypot(Qy, Qz), "T": T, "M_y": My, "M_z": Mz, "M_b": math.hypot(My, Mz)}


def distribution(*, model, xs):
    """沿轴各点内力；xs 中与载荷点重合者阻断（见 internal_forces）。"""
    if not xs:
        raise MissingInput("xs")
    return [internal_forces(model=model, x=x) for x in xs]


def section_geometry(*, model, x):
    xs = num("x", x)
    for x0, x1, d, di in model["segments"]:
        if abs(xs - x0) < 1e-9 or abs(xs - x1) < 1e-9:
            raise OutOfDomain("x", f"截面 x = {xs} 恰在轴段分界，直径不唯一")
        if x0 < xs < x1:
            return {"d": d, "d_i": di}
    raise OutOfDomain("x", f"截面 x = {xs} 不在任何轴段内")


# ------------------------------------------------------------------ 衔接 DIN 743 / ISO 281
_DIN743_KEYS = ("load_case", "S_min", "sigma_zdW_dB", "sigma_bW_dB", "tau_tW_dB", "sigma_B_dB", "sigma_B_d", "K1_deff",
                "K_sigma_zd", "K_sigma_b", "K_tau", "sigma_zdFK", "sigma_bFK", "tau_tFK", "sigma_dFK")


def _req(spec, key, where):
    if spec is None:
        raise MissingInput(where)
    if spec.get(key) is None:
        raise MissingInput(f"{where}.{key}")
    return spec[key]


def section_check(*, model, x, stress_state, checks, fatigue, static):
    """一个截面：内力 → DIN 743-1 表1 名义应力 → 疲劳（fatigue_proof）/静强度（式25 + 式1）。

    checks：('fatigue', 'static') 的非空子集（显式列出）。
    fatigue：_DIN743_KEYS 全部键（含义同 din743.fatigue_proof）；不做疲劳时须为 None。
    static：{"load_factor": 最大载荷/名义载荷（显式，如 K_A 或峰值比）, "S_min": ≥1,2, "sigma_zdFK", "sigma_bFK", "tau_tFK"}；
            不做静强度时须为 None。
    """
    choice("stress_state", stress_state, STRESS_STATES)
    if not checks or any(c not in ("fatigue", "static") for c in checks):
        raise bad("checks", "须为 ('fatigue', 'static') 的非空子集")
    g = section_geometry(model=model, x=x)
    f = internal_forces(model=model, x=x)
    ws = din743.working_stresses(d=g["d"], d_i=g["d_i"], F_zda=0.0, F_zdm=f["N"], M_ba=f["M_b"], M_bm=0.0,
                                 M_ta=0.0, M_tm=abs(f["T"]))
    out = {"x": f["x"], **g, "internal": f, "stresses": ws}
    if "fatigue" in checks:
        args = {k: _req(fatigue, k, "fatigue") for k in _DIN743_KEYS}
        out["fatigue"] = din743.fatigue_proof(sigma_zda=ws["sigma_zda"], sigma_zdm=ws["sigma_zdm"], sigma_ba=ws["sigma_ba"],
                                              sigma_bm=ws["sigma_bm"], tau_ta=ws["tau_ta"], tau_tm=ws["tau_tm"], **args)
    elif fatigue is not None:
        raise bad("fatigue", "checks 未含 'fatigue' 时须为 None")
    if "static" in checks:
        kf = pos("static.load_factor", _req(static, "load_factor", "static"))
        mx = din743.maximum_stresses(d=g["d"], d_i=g["d_i"], F_zdmax=kf * f["N"], M_bmax=kf * f["M_b"], M_tmax=kf * abs(f["T"]))
        S = din743.safety_static(sigma_zdmax=mx["sigma_zdmax"], sigma_zdFK=_req(static, "sigma_zdFK", "static"),
                                 sigma_bmax=mx["sigma_bmax"], sigma_bFK=_req(static, "sigma_bFK", "static"),
                                 tau_tmax=mx["tau_tmax"], tau_tFK=_req(static, "tau_tFK", "static"))
        Smin = _req(static, "S_min", "static")
        out["static"] = {**mx, "load_factor": kf, "S": S, "S_min": Smin, "ok": din743.check_safety(S=S, S_min=Smin)}
    elif static is not None:
        raise bad("static", "checks 未含 'static' 时须为 None")
    return out


def bearing_checks(*, model, bearings):
    """bearings：{"A": {...}, "B": {...}}，每项为 iso281.bearing_life 除 F_r、F_a 外的全部关键字参数。
    F_r 取支反力径向合力，F_a 取定位支承轴向力（浮动支承为 0）。"""
    if not bearings:
        raise MissingInput("bearings")
    out = {}
    for k in ("A", "B"):
        spec = bearings.get(k)
        if spec is None:
            raise MissingInput(f"bearings.{k}")
        bl = model["bearing_loads"][k]
        out[k] = {"F_r": bl["F_r"], "F_a": bl["F_a"], **iso281.bearing_life(F_r=bl["F_r"], F_a=bl["F_a"], **spec)}
    return out


def run(*, x_A, x_B, axial_support, loads, segments, sections, bearings):
    """端到端：solve → 各截面 section_check → bearing_checks。sections：[{x, stress_state, checks, fatigue, static, name}]。"""
    m = solve(x_A=x_A, x_B=x_B, axial_support=axial_support, loads=loads, segments=segments)
    if not sections:
        raise MissingInput("sections")
    res = []
    for i, s in enumerate(sections):
        for k in ("x", "stress_state", "checks"):
            if s.get(k) is None:
                raise MissingInput(f"sections[{i}].{k}")
        r = section_check(model=m, x=s["x"], stress_state=s["stress_state"], checks=s["checks"],
                          fatigue=s.get("fatigue"), static=s.get("static"))
        res.append({"name": s.get("name", f"S{i + 1}"), **r})
    return {"model": m, "sections": res, "bearings": bearing_checks(model=m, bearings=bearings)}


def _section_runs(model, sections):
    if not sections:
        raise MissingInput("sections")
    res = []
    for i, s in enumerate(sections):
        for k in ("x", "stress_state", "checks"):
            if s.get(k) is None:
                raise MissingInput(f"sections[{i}].{k}")
        r = section_check(model=model, x=s["x"], stress_state=s["stress_state"], checks=s["checks"],
                          fatigue=s.get("fatigue"), static=s.get("static"))
        res.append({"name": s.get("name", f"S{i + 1}"), **r})
    return res


def run_beam(*, supports, axial_support, loads, segments, E, G, shear_model, shear_factor, eval_points, sections, bearings):
    """端到端（v0.15 EXTM36）：shaft_beam.solve_beam（n ≥ 2 刚性点支承、超静定、挠度/转角）→ 各截面 section_check → 各支承 ISO 281。
    参数含义同 shaft_beam.solve_beam 与 run；bearings 须覆盖全部支承名。返回 {"model", "sections", "bearings", "deflection"}。"""
    from . import shaft_beam                                   # 延迟导入：shaft_beam 依赖本模块
    m = shaft_beam.solve_beam(supports=supports, axial_support=axial_support, loads=loads, segments=segments, E=E, G=G,
                              shear_model=shear_model, shear_factor=shear_factor, eval_points=eval_points)
    lo, hi = m["segments"][0][0], m["segments"][-1][1]
    defl = {"max": shaft_beam.max_deflection(model=m), "support_rotation": shaft_beam.support_misalignment(model=m),
            "torsion_angle_rad": shaft_beam.torsion_angle(model=m, x_from=lo, x_to=hi)}
    return {"model": m, "sections": _section_runs(m, sections), "bearings": shaft_beam.bearing_checks(model=m, bearings=bearings),
            "deflection": defl}


UNCONFIRMED = {
    "shaft_line.statically_indeterminate": "本模块 solve 只接受 A、B 两支承；三支承及以上见 shaft_beam.solve_beam（刚性点支承）",
    "shaft_line.deflection": "挠度/转角见 shaft_beam；临界转速、轴承游隙/刚度、ISO/TS 16281：TODO",
    "shaft_line.load_spectrum": "变扭矩、载荷谱（DIN 743-4 衔接）、非'轴旋转-载荷方向固定'应力状态：TODO",
    "shaft_line.distributed_loads": "均布横向线载荷已支持（line_load）；非均布（齿宽方向载荷分布 KHβ 形状）、自重、分布轴向力/扭矩：TODO",
}
