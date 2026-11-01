"""轴系子系统统一核算入口（v0.15 EXTM36）："齿轮副输出 → 轴（梁模型，含挠度）→ DIN 743 截面 → ISO 281 轴承 → 键 → 过盈"。

定位与口径：
  - 只负责轴系子系统；全局报告（多级、齿轮强度汇总）由 SYS 路负责。接口为纯 dict 输入、纯 dict 输出（可 JSON 序列化）。
  - 输入全显式：齿轮副只以数值进入（工作节圆切向力 F_tw、α_wt、β_w、r_w、啮合点方位与符号），本模块不 import 齿轮包；
    缺任何键 → MissingInput；不设隐式默认（不做的子项须显式给空列表或 None）。
  - 计算全部调用已登记模块：shaft_line.run_beam（shaft_beam 刚度法 + section_check + ISO 281）、din743（截面系数）、
    din6892 / din6892_b（键）、din7190（过盈）。本模块不新增公式（FORMULAS 为空），只做编排、证据汇总与判定汇总。
  - 每个子项输出所用公式 id 及其 evidence_level_effective（E4 标准算例 / E5 KISSsoft 同输入逐字段一致 / None 未评估），
    并汇总"未验证项清单"（无外部证据的公式、超出 E5 覆盖分支的取值、模型层未收录项）。正式等级以 data/registry 为准。
spec 结构见 check() 文档。单位：mm、N、N·mm、N/mm²、r/min。
"""
from __future__ import annotations

from . import din743, din6892, din6892_b, din7190, iso281, shaft_beam, shaft_line
from ._base import MissingInput, OutOfDomain, Unconfirmed, bad, choice, make_registry, num, pos

FORMULAS, _formula = make_registry("", "编排模块，不含公式")
SCHEMA = "gearbase.drivetrain_check/1"
_E5_FATIGUE_BRANCHES = ("eq10", "eq11", "eq12", "zero_amplitude")      # din743_1.eq10_19_tabA1 外部 E5 覆盖分支
_KINDS = ("zd", "b", "t")
_NOTCH_FORMS = ("plain", "shoulder", "round_groove")

_DIN743_COMMON = ("din743_1.table1.section", "din743_1.table1.stress", "din743_2.eq10_14", "din743_2.eq15_16",
                  "din743_2.eq18", "din743_2.eq19", "din743_1.eq8_9", "din743_1.eq31_32", "din743_1.table2", "din743_1.table3")
_DIN743_FATIGUE = ("din743_1.eq23_24", "din743_1.eq5_7", "din743_1.eq20_22", "din743_1.eq10_19_tabA1", "din743_1.eq2",
                   "din743_1.eq1")
_DIN743_STATIC = ("din743_1.table4.stress", "din743_1.eq25", "din743_1.eq1")
_DIN743_NOTCH = ("din743_2.eq9", "din743_2.table2", "din743_2.eq4_6")
_ISO281_BASIC = ("iso281.table3.radial_contact", "iso281.eq3_14", "iso281.eq4_16", "iso281.table12")
_ISO281_ROLLER = ("iso281.table8", "iso281.eq3_14", "iso281.eq4_16", "iso281.table12")
_ISO281_AISO = ("iso281.eq31_36", "iso281.eq23")
_KEY_C = ("din6892.eq31", "din6892.eq33", "din6892.eq32", "din6892.eq32_pressure", "din6892.eq34")
_KEY_B = ("din6892b.eq1", "din6892b.eq2_3", "din6892b.eq4", "din6892b.eq5", "din6892b.eq11", "din6892b.eq12_13",
          "din6892b.eq15_16", "din6892b.eq9_10", "din6892b.eq19_20", "din6892b.eq21_23", "din6892b.eq24_29", "din6892b.eq17_18")
_FIT = ("din7190.eq7", "din7190.eq10_11", "din7190.eq12", "din7190.eq13_14", "din7190.eq20_23", "din7190.eq24_25", "din7190.eq1")
_REGISTRIES = (din743.FORMULAS, iso281.FORMULAS, din6892.FORMULAS, din6892_b.FORMULAS, din7190.FORMULAS,
               shaft_line.FORMULAS, shaft_beam.FORMULAS)


# ------------------------------------------------------------------ 小工具
def _get(d, key, where):
    if d is None:
        raise MissingInput(where)
    if not isinstance(d, dict):
        raise bad(where, "须为 dict")
    if key not in d or d[key] is None:
        raise MissingInput(f"{where}.{key}")
    return d[key]


def _list(d, key, where):
    if d is None or key not in d or d[key] is None:
        raise MissingInput(f"{where}.{key}（无此子项时显式给空列表）")
    if not isinstance(d[key], list):
        raise bad(f"{where}.{key}", "须为 list")
    return d[key]


def _meta(fid):
    for reg in _REGISTRIES:
        if fid in reg:
            return reg[fid]
    raise AssertionError(f"未登记的公式 id：{fid}")


def _evidence(fids):
    out = []
    for fid in dict.fromkeys(fids):
        m = _meta(fid)
        out.append({"id": fid, "level_effective": m.get("evidence_level_effective", m.get("evidence_level")),
                    "evidence_level": m.get("evidence_level"), "external_level": m.get("external_evidence_level"),
                    "basis": m.get("basis", "standard")})
    return out


# ------------------------------------------------------------------ 载荷
def _mesh_loads(mesh, torques):
    dist = choice("mesh.distribution", _get(mesh, "distribution", "mesh"), ("point", "uniform"))
    mf = shaft_line.mesh_forces(F_tw=_get(mesh, "F_tw", "mesh"), alpha_wt_deg=_get(mesh, "alpha_wt_deg", "mesh"),
                                beta_w_deg=_get(mesh, "beta_w_deg", "mesh"))
    pl = shaft_line.mesh_point_load(name=_get(mesh, "name", "mesh"), x=_get(mesh, "x", "mesh"), F_t=mf["F_t"], F_r=mf["F_r"],
                                    F_a=mf["F_a"], r_w=_get(mesh, "r_w", "mesh"), theta_deg=_get(mesh, "theta_deg", "mesh"),
                                    tangential_sign=_get(mesh, "tangential_sign", "mesh"), axial_sign=_get(mesh, "axial_sign", "mesh"))
    notes = []
    if dist == "point":
        if mesh.get("x0") is not None or mesh.get("x1") is not None:
            raise bad("mesh.x0/x1", "distribution = 'point' 时须为 None")
        loads = [pl]
    else:
        if mf["F_a"] != 0.0:
            raise Unconfirmed("mesh.distribution", "带轴向力（偏心力偶）的均布啮合载荷未收录")
        x0, x1 = num("mesh.x0", _get(mesh, "x0", "mesh")), num("mesh.x1", _get(mesh, "x1", "mesh"))
        Tx = pl["y"] * pl["F"][2] - pl["z"] * pl["F"][1]                     # (r × F)_x
        loads = [shaft_line.line_load(name=pl["name"], x0=x0, x1=x1, F=(0.0, pl["F"][1], pl["F"][2])),
                 shaft_line.torque_load(name=pl["name"] + " torque", x=pl["x"], T=Tx)]
        notes.append("均布啮合载荷：横向力按 [x0, x1] 均布；啮合扭矩按集中扭矩作用于啮合点 x（分布扭矩未收录）")
    for i, t in enumerate(torques):
        loads.append(shaft_line.torque_load(name=_get(t, "name", f"torques[{i}]"), x=_get(t, "x", f"torques[{i}]"),
                                            T=_get(t, "T", f"torques[{i}]")))
    return mf, loads, notes


# ------------------------------------------------------------------ DIN 743 截面系数（DIN 743-2/-1 已登记函数）
def section_coefficients(*, d, material, notch, Rz, K_V, hard_surface, sigma_dFK, sigma_dFK_equals_sigma_zdFK):
    """由材料、缺口几何、表面显式输入求截面 DIN 743 全部系数（K1、K2、KF、α、G'、n、β、K、σWK 所需、K2F、γF、FK）。

    material：{"sigma_B_dB", "sigma_S_dB", "sigma_zdW_dB", "sigma_bW_dB", "tau_tW_dB", "K1_curve_B", "K1_curve_S", "d_eff"}；
    notch：{"form": "plain"}（光轴 α = β = 1）或 {"form": "shoulder"|"round_groove", "r", "t", "D"}；
    sigma_dFK_equals_sigma_zdFK：True 时表A.1 的 σdFK 以 σzdFK 代（标准表注允许，须调用方显式选择），此时 sigma_dFK 须为 None。"""
    d = pos("d", d)
    m = {k: _get(material, k, "material") for k in ("sigma_B_dB", "sigma_S_dB", "sigma_zdW_dB", "sigma_bW_dB", "tau_tW_dB",
                                                    "K1_curve_B", "K1_curve_S", "d_eff")}
    form = choice("notch.form", _get(notch, "form", "notch"), _NOTCH_FORMS)
    hard = hard_surface
    if hard is None:
        raise MissingInput("hard_surface")
    if hard is not False:
        raise Unconfirmed("hard_surface", "本入口只收录无硬化表层（硬化表层 K_V、式(6)、式(28) 由调用方另算）")
    if not isinstance(sigma_dFK_equals_sigma_zdFK, bool):
        raise MissingInput("sigma_dFK_equals_sigma_zdFK")
    K1B = din743.K1(curve=m["K1_curve_B"], d_eff=m["d_eff"])
    K1S = din743.K1(curve=m["K1_curve_S"], d_eff=m["d_eff"])
    sBd, sSd = K1B * pos("sigma_B_dB", m["sigma_B_dB"]), K1S * pos("sigma_S_dB", m["sigma_S_dB"])
    KFs = din743.KF_sigma(Rz=Rz, sigma_B_d=sBd)
    KFt = din743.KF_tau(KF_sigma=KFs)
    alpha, G, n, beta = {}, {}, {}, {}
    for k in _KINDS:
        if form == "plain":
            alpha[k], G[k], n[k], beta[k] = 1.0, None, None, 1.0
            continue
        g = {x: _get(notch, x, "notch") for x in ("r", "t", "D")}
        f2 = "absatz" if form == "shoulder" else "rundnut"
        alpha[k] = din743.alpha_groove_shoulder(form=f2, kind=k, r=g["r"], t=g["t"], d=d, D=g["D"])
        G[k] = din743.stress_gradient(form=f2, kind=k, r=g["r"], t=g["t"], d=d, D=g["D"])
        bb = din743.beta_from_alpha(alpha=alpha[k], G_prime=G[k], sigma_S_d=sSd, hard_surface=False)
        n[k], beta[k] = bb["n"], bb["beta"]
    K2 = {k: din743.K2(kind=k, d=d) for k in _KINDS}
    K = {k: din743.total_influence_factor(kind="tau" if k == "t" else "sigma", beta=beta[k], K2_d=K2[k],
                                          K_F=KFt if k == "t" else KFs, K_V=K_V) for k in _KINDS}
    K2F = {k: din743.K2F(kind=k, hollow=False, hard_surface=False) for k in _KINDS}
    gF = {k: din743.gamma_F(kind=k, alpha_or_beta=alpha[k], hard_surface=False, circumferential_notch=(form != "plain"))
          for k in _KINDS}
    FK = {k: din743.component_yield_point(kind=k, K1_deff=K1S, K2F=K2F[k], gamma_F=gF[k], sigma_S_dB=m["sigma_S_dB"])
          for k in _KINDS}
    if sigma_dFK_equals_sigma_zdFK:
        if sigma_dFK is not None:
            raise bad("sigma_dFK", "已选择以 σzdFK 代 σdFK，sigma_dFK 须为 None")
        dFK = FK["zd"]
    else:
        dFK = pos("sigma_dFK", sigma_dFK)
    return {"K1_sigmaB": K1B, "K1_sigmaS": K1S, "sigma_B_d": sBd, "sigma_S_d": sSd, "KF_sigma": KFs, "KF_tau": KFt,
            "alpha": alpha, "G_prime": G, "n": n, "beta": beta, "K2": K2, "K": K, "K2F": K2F, "gamma_F": gF, "FK": FK,
            "sigma_dFK": dFK, "notch_form": form, "material": m}


def _section_inputs(s, i, model_segments):
    where = f"sections[{i}]"
    mode = choice(f"{where}.coefficients", _get(s, "coefficients", where), ("din743_2", "explicit"))
    checks = tuple(_get(s, "checks", where))
    out = {"name": _get(s, "name", where), "x": _get(s, "x", where), "stress_state": _get(s, "stress_state", where), "checks": checks}
    if mode == "explicit":
        out["fatigue"], out["static"] = s.get("fatigue"), s.get("static")
        return out, None
    d = None
    for x0, x1, dd, _ in model_segments:
        if x0 < out["x"] < x1:
            d = dd
    if d is None:
        raise OutOfDomain(f"{where}.x", "截面不在任何轴段内部（恰在分界或越界）")
    c = section_coefficients(d=d, material=_get(s, "material", where), notch=_get(s, "notch", where), Rz=_get(s, "Rz", where),
                             K_V=_get(s, "K_V", where), hard_surface=_get(s, "hard_surface", where),
                             sigma_dFK=s.get("sigma_dFK"), sigma_dFK_equals_sigma_zdFK=_get(s, "sigma_dFK_equals_sigma_zdFK", where))
    m = c["material"]
    out["fatigue"] = None if "fatigue" not in checks else {
        "load_case": _get(s, "load_case", where), "S_min": _get(s, "S_min_fatigue", where),
        "sigma_zdW_dB": m["sigma_zdW_dB"], "sigma_bW_dB": m["sigma_bW_dB"], "tau_tW_dB": m["tau_tW_dB"],
        "sigma_B_dB": m["sigma_B_dB"], "sigma_B_d": c["sigma_B_d"], "K1_deff": c["K1_sigmaB"],
        "K_sigma_zd": c["K"]["zd"], "K_sigma_b": c["K"]["b"], "K_tau": c["K"]["t"],
        "sigma_zdFK": c["FK"]["zd"], "sigma_bFK": c["FK"]["b"], "tau_tFK": c["FK"]["t"], "sigma_dFK": c["sigma_dFK"]}
    out["static"] = None if "static" not in checks else {
        "load_factor": _get(s, "static_load_factor", where), "S_min": _get(s, "S_min_static", where),
        "sigma_zdFK": c["FK"]["zd"], "sigma_bFK": c["FK"]["b"], "tau_tFK": c["FK"]["t"]}
    return out, c


def legacy_static_solve(*, x_A, x_B, axial_support, loads, segments):
    """Explicit two-support static compatibility route; no beam properties assumed."""
    return shaft_line.solve(x_A=x_A, x_B=x_B, axial_support=axial_support, loads=loads, segments=segments)


def legacy_section_check(*, model, x, stress_state, checks, fatigue, static):
    """Evaluate a section of the static compatibility model."""
    return shaft_line.section_check(model=model, x=x, stress_state=stress_state, checks=checks, fatigue=fatigue, static=static)


def legacy_bearing_life(*, bearing_kind, F_r, F_a, C_r, C_0r, xy, n, reliability_percent, a_ISO_inputs):
    """Evaluate ISO 281 life for explicit or static-model bearing reactions."""
    return iso281.bearing_life(bearing_kind=bearing_kind, F_r=F_r, F_a=F_a, C_r=C_r, C_0r=C_0r, xy=xy, n=n, reliability_percent=reliability_percent, a_ISO_inputs=a_ISO_inputs)


# ------------------------------------------------------------------ 梁路线（v0.17 SYSREG：产品 system-input shaft_model = "beam"）
def beam_solve(*, supports, axial_support, loads, segments, E, G, shear_model, shear_factor, eval_points):
    """Explicit beam route: shaft_beam stiffness method (n >= 2 rigid point supports, statically indeterminate allowed).

    E, G, shear_model and shear_factor are mandatory caller inputs (no defaults); see shaft_beam.solve_beam."""
    return shaft_beam.solve_beam(supports=supports, axial_support=axial_support, loads=loads, segments=segments, E=E, G=G,
                                 shear_model=shear_model, shear_factor=shear_factor, eval_points=eval_points)


def beam_section_inputs(*, section, index, model):
    """DIN 743 section input of the beam route: coefficients = "explicit" | "din743_2" (same contract as check())."""
    return _section_inputs(section, index, model["segments"])


def beam_section_check(*, model, x, stress_state, checks, fatigue, static):
    """DIN 743-1 section check on the beam model (internal forces from the stiffness solution)."""
    return shaft_line.section_check(model=model, x=x, stress_state=stress_state, checks=checks, fatigue=fatigue, static=static)


def beam_deflection_report(*, model, stubs):
    """Deflection, support rotation, torsion angle and KHβ interface-stub data of a solved beam model.

    stubs: [{"name", "x0", "x1", "direction_deg"}] (may be empty; x0/x1 must be solved nodes).
    The stub is mechanics only (shaft_beam.mesh_width_deflection_stub); no ISO 6336 f_sh conversion."""
    lo, hi = model["segments"][0][0], model["segments"][-1][1]
    rot = shaft_beam.support_misalignment(model=model)
    out = {"max": shaft_beam.max_deflection(model=model), "support_rotation": rot,
           "max_support_rotation_rad": max(v["rotation"] for v in rot.values()),
           "torsion_angle_rad": shaft_beam.torsion_angle(model=model, x_from=lo, x_to=hi),
           "statically_indeterminate": model["statically_indeterminate"], "force_residual": model["force_residual"],
           "khbeta_stub": {}}
    for i, s in enumerate(stubs):
        nm = _get(s, "name", f"stubs[{i}]")
        out["khbeta_stub"][nm] = shaft_beam.mesh_width_deflection_stub(
            model=model, x0=_get(s, "x0", f"stubs[{i}]"), x1=_get(s, "x1", f"stubs[{i}]"),
            direction_deg=_get(s, "direction_deg", f"stubs[{i}]"))
    return out


# ------------------------------------------------------------------ 主入口
def check(*, spec):
    """轴系子系统核算。spec（dict，全部键必需；不做的子项给空列表/None）：
      mesh：{"name", "F_tw", "alpha_wt_deg", "beta_w_deg", "r_w", "x", "theta_deg", "tangential_sign", "axial_sign",
             "distribution": "point"|"uniform", "x0", "x1"（uniform 时必需，point 时为 None）}
      torques：[{"name", "x", "T"}]（与啮合扭矩平衡的输入/输出扭矩，显式）
      shaft：{"segments", "E", "G", "shear_model", "shear_factor", "supports", "axial_support", "eval_points"}
      sections：[{"name", "x", "stress_state", "checks", "coefficients": "din743_2"|"explicit", …}]
                din743_2：另需 material、notch、Rz、K_V、hard_surface、sigma_dFK、sigma_dFK_equals_sigma_zdFK、load_case、
                          S_min_fatigue（做疲劳时）、static_load_factor、S_min_static（做静强度时）；
                explicit：fatigue/static 同 shaft_line.section_check。
      bearings：{支承名: iso281.bearing_life 除 F_r/F_a 外的参数 + "bearing_kind"}（须覆盖全部支承）
      keys：[{"name", "method": "C"|"B", "args": din6892.method_c / din6892_b.method_b 全部参数}]
      fits：[{"name", "T_nom", "args": din7190.elastic_check_for_interference 全部参数}]
      deflection_limits：None（不判定，列入未验证项）或 {"max_radial_mm", "max_support_rotation_rad"}
    返回结构化结果（含 evidence、unverified、summary）。"""
    if not isinstance(spec, dict):
        raise MissingInput("spec")
    mesh = _get(spec, "mesh", "spec")
    torques = _list(spec, "torques", "spec")
    shaft = _get(spec, "shaft", "spec")
    sections = _list(spec, "sections", "spec")
    bearings = _get(spec, "bearings", "spec")
    keys = _list(spec, "keys", "spec")
    fits = _list(spec, "fits", "spec")
    if "deflection_limits" not in spec:
        raise MissingInput("spec.deflection_limits（不判定时显式给 None）")
    lim = spec["deflection_limits"]
    unverified = []

    mf, loads, notes = _mesh_loads(mesh, torques)
    segs = shaft_line._segments(_get(shaft, "segments", "shaft"))
    sec_in, coeffs = [], []
    for i, s in enumerate(sections):
        a, c = _section_inputs(s, i, segs)
        sec_in.append(a)
        coeffs.append(c)
    if "shear_factor" not in shaft:
        raise MissingInput("shaft.shear_factor（Euler–Bernoulli 时显式给 None）")
    r = shaft_line.run_beam(supports=_get(shaft, "supports", "shaft"), axial_support=_get(shaft, "axial_support", "shaft"),
                            loads=loads, segments=_get(shaft, "segments", "shaft"), E=_get(shaft, "E", "shaft"),
                            G=_get(shaft, "G", "shaft"), shear_model=_get(shaft, "shear_model", "shaft"),
                            shear_factor=shaft["shear_factor"], eval_points=_list(shaft, "eval_points", "shaft"),
                            sections=sec_in, bearings=bearings)
    model = r["model"]
    beam_ev = _evidence(("mech.beam_element", "mech.beam_stiffness_method", "mech.beam_max_deflection", "mech.torsion_angle",
                         "mech.section_resultants", "mech.mesh_forces"))
    unverified.append("轴梁模型（shaft_beam，工程力学）：KISSsoft W010 对拍仅近似一致（P4 挠度相对 3,3e-4；R1 支反力差来自 KISSsoft "
                      "力平衡残差 0,385 N，R3 OPEN），未提升证据；轴承刚度/游隙、壳体、临界转速未收录")
    unverified += notes

    # 挠度
    defl = r["deflection"]
    rot_max = max(v["rotation"] for v in defl["support_rotation"].values())
    shaft_out = {"reactions": model["reactions"], "bearing_loads": model["bearing_loads"], "force_residual": model["force_residual"],
                 "statically_indeterminate": model["statically_indeterminate"], "max_deflection": defl["max"],
                 "support_rotation": defl["support_rotation"], "max_support_rotation_rad": rot_max,
                 "torsion_angle_rad": defl["torsion_angle_rad"], "evidence": beam_ev}
    if lim is None:
        shaft_out["deflection_check"] = "not_requested"
        unverified.append("挠度/支承转角许用值未给出 → 未判定")
    else:
        mr, ma = pos("max_radial_mm", _get(lim, "max_radial_mm", "deflection_limits")), \
            pos("max_support_rotation_rad", _get(lim, "max_support_rotation_rad", "deflection_limits"))
        shaft_out["deflection_check"] = {"max_radial_mm": mr, "max_support_rotation_rad": ma,
                                         "ok": defl["max"]["radial"] <= mr and rot_max <= ma}

    # 截面
    sec_out = []
    for s, c, spec_s in zip(r["sections"], coeffs, sections):
        fids = list(_DIN743_COMMON) if c is not None else ["din743_1.table1.section", "din743_1.table1.stress"]
        if c is not None and c["notch_form"] != "plain":
            fids += _DIN743_NOTCH
        item = {"name": s["name"], "x": s["x"], "d": s["d"], "internal": s["internal"], "stresses": s["stresses"],
                "coefficients": None if c is None else {k: v for k, v in c.items() if k != "material"}}
        if "fatigue" in s:
            fids += _DIN743_FATIGUE
            f = s["fatigue"]
            item["fatigue"] = {"S": f["S"], "S_min": f["S_min"], "ok": f["ok"], "mean_branch": f["mean_branch"],
                               "branches": {k: f[k]["branch"] for k in _KINDS}, "detail": {k: f[k] for k in _KINDS},
                               "sigma_mv": f["sigma_mv"], "tau_mv": f["tau_mv"]}
            outside = [f"{k}:{b}" for k, b in item["fatigue"]["branches"].items() if b not in _E5_FATIGUE_BRANCHES]
            if f["mean_branch"] != "eq23":
                outside.append(f"mean:{f['mean_branch']}")
            if outside:
                unverified.append(f"截面 {s['name']}：DIN 743 分支 {outside} 超出 KISSsoft E5 覆盖范围")
        if "static" in s:
            fids += _DIN743_STATIC
            st = s["static"]
            item["static"] = {"S": st["S"], "S_min": st["S_min"], "ok": st["ok"], "load_factor": st["load_factor"],
                              "sigma_bmax": st["sigma_bmax"], "tau_tmax": st["tau_tmax"]}
        if c is None:
            unverified.append(f"截面 {s['name']}：系数由调用方显式给出（coefficients='explicit'），来源不在本入口核验范围")
        item["evidence"] = _evidence(fids)
        sec_out.append(item)

    # 轴承
    brg_out = {}
    for nm, b in r["bearings"].items():
        kind = bearings[nm]["bearing_kind"]
        fids = list(_ISO281_BASIC if kind == "radial_ball" else _ISO281_ROLLER)
        if b.get("Lnm") is not None:
            fids += _ISO281_AISO
        else:
            unverified.append(f"轴承 {nm}：修正寿命 Lnm 未计算（κ/ec/Cu 未给出）")
        if b["F_a"] != 0.0:
            unverified.append(f"轴承 {nm}：Fa ≠ 0，X/Y 分支超出 KISSsoft E5 覆盖（仅 Fa = 0）")
        brg_out[nm] = {**b, "evidence": _evidence(fids)}

    # 键
    key_out = []
    for i, k in enumerate(keys):
        where = f"keys[{i}]"
        meth = choice(f"{where}.method", _get(k, "method", where), ("C", "B"))
        args = _get(k, "args", where)
        if meth == "C":
            res = din6892.method_c(**args)
            fids = list(_KEY_C) + (["din6892.eq35_36"] if res.get("peak_check") not in (None, "not_requested") else [])
            ok = res["ok_eq"] and res.get("ok_peak", True)
            S = res["M_tzul"] / res["M_teq"]
            if res.get("peak_check") == "not_requested":
                unverified.append(f"键 {k['name']}：方法 C 峰值扭矩（式35/36）未核")
        else:
            res = din6892_b.method_b(**args)
            fids = list(_KEY_B)
            ok = res["ok"]
            S = min(c[w]["S"] for c in res["checks"].values() for w in ("eq", "max") if c[w] != "not_required")
            unverified.append(f"键 {k['name']}：方法 B 的 K_λe 为图4–6 读值（调用方给出）；f_W 与 KISSsoft（图7 端点插值）口径不同")
        key_out.append({"name": _get(k, "name", where), "method": meth, "S_min_found": S, "ok": ok, "result": res,
                        "evidence": _evidence(fids)})

    # 过盈
    fit_out = []
    for i, ft in enumerate(fits):
        where = f"fits[{i}]"
        args = _get(ft, "args", where)
        Tn = pos(f"{where}.T_nom", _get(ft, "T_nom", where))
        res = din7190.elastic_check_for_interference(**args)
        item = {"name": _get(ft, "name", where), "T_nom": Tn, "result": res}
        if res["p"] is None:
            item.update({"S_r_actual": None, "ok": False})
            unverified.append(f"过盈 {ft['name']}：超出纯弹性范围（4.3 弹塑性未收录）")
        else:
            T1 = din7190.transferable_torque(D_F=args["D_F"], l_F=args["l_F"], nu_ru=args["nu_ru"], p=res["p"], S_r=1.0)
            item.update({"S_r_actual": T1 / Tn, "ok": T1 / Tn >= args["S_r"]})
        item["evidence"] = _evidence(_FIT)
        fit_out.append(item)

    # 汇总
    every = [e for s in sec_out for e in s["evidence"]] + [e for b in brg_out.values() for e in b["evidence"]] \
        + [e for k in key_out for e in k["evidence"]] + [e for f in fit_out for e in f["evidence"]]
    levels = {}
    for e in every:
        levels[e["id"]] = e["level_effective"]
    unverified += [f"公式 {fid}：无外部/标准算例证据（evidence_level_effective = None）" for fid, lv in levels.items() if lv is None]
    flags = [("section", s["name"], kk, s[kk]["ok"]) for s in sec_out for kk in ("fatigue", "static") if kk in s]
    flags += [("key", k["name"], k["method"], k["ok"]) for k in key_out] + [("fit", f["name"], "slip", f["ok"]) for f in fit_out]
    if isinstance(shaft_out["deflection_check"], dict):
        flags.append(("shaft", "deflection", "limits", shaft_out["deflection_check"]["ok"]))
    fat = [(s["name"], s["fatigue"]["S"]) for s in sec_out if "fatigue" in s]
    sta = [(s["name"], s["static"]["S"]) for s in sec_out if "static" in s]
    summary = {"all_ok": all(f[3] for f in flags), "failed": [f[:3] for f in flags if not f[3]],
               "min_S_fatigue": min(fat, key=lambda t: t[1]) if fat else None,
               "min_S_static": min(sta, key=lambda t: t[1]) if sta else None,
               "min_L10h": min(((nm, b["L10h"]) for nm, b in brg_out.items()), key=lambda t: t[1]),
               "max_deflection_mm": defl["max"]["radial"], "bearing_life_not_judged": "L10h 无许用值输入，只报告不判定"}
    counts = {}
    for lv in levels.values():
        counts[str(lv)] = counts.get(str(lv), 0) + 1
    return {"schema": SCHEMA, "scope": "轴系子系统（齿轮副数值输出 → 轴 → DIN 743 → ISO 281 → 键 → 过盈）",
            "mesh_forces": mf, "shaft": shaft_out, "sections": sec_out, "bearings": brg_out, "keys": key_out, "fits": fit_out,
            "summary": summary, "evidence": {"formulas": levels, "counts": counts}, "unverified": list(dict.fromkeys(unverified))}


UNCONFIRMED = {
    "drivetrain.global_report": "多级/全局报告与齿轮强度汇总：由 SYS 路负责，本入口只出轴系子系统",
    "drivetrain.keyway_notch": "DIN 743-2 表1 键槽、花键、横孔缺口在本入口的系数自动化：TODO（可用 coefficients='explicit'）",
    "drivetrain.load_spectrum": "变扭矩/载荷谱（DIN 743-4）、Case 2 自动选择：TODO",
    "drivetrain.distributed_torque": "沿齿宽分布扭矩、非均布载荷（KHβ 形状）：TODO；均布时扭矩按集中处理",
    "drivetrain.khbeta_feedback": "轴挠度 → KHβ 回馈齿轮侧：只有 shaft_beam.mesh_width_deflection_stub 接口桩",
    "drivetrain.key_torque_consistency": "键/过盈的扭矩由调用方显式给出，未自动取自截面内力",
}
