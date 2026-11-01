"""ISO/TS 6336-20:2022 胶合承载能力——闪温法（骨架）：θBmax = θMi + θflmax，SB = (θS − θoil)/(θBmax − θoil)。

资料与核对口径（用户私有 PDF，本机逐式渲染原图核对；代码只写条款号、式号、页码）：
  - 文件 "ISO TS 6336-20-2022.pdf"（42 页扫描），SHA256=SOURCE_SHA256；PDF 页 = 印刷页 + 6（PDF15 = 印9）。
  - 证据等级：测试内独立重写不构成外部参照；v0.14 起 KISSsoft 2026 P3 K01（直齿）可追溯字段逐位一致者登记 E5
    （文末 EXTERNAL_EVIDENCE），θfl 式(5) 在 KISSsoft 最大点有 −6,2 % 未归因差异，仍为 null。
    v0.15：μm 链式(23)(24)(26) 由 KISSsoft M39-K01-runin0（关闭跑合，原 Ra）逐位一致升 E5。

本版闭合范围（窄）：外啮合直齿、未修形齿廓（9.2，XΓ 式(38)–(40)）；
  θfl 沿啮合线 Γy 取样（式(5)–(8)、(27)–(33)），XJ 式(34)–(37)（Ceff 用附录 B 式(B.1)），
  μm 方法 C 式(23)–(26)，wBt 式(11)–(13)(17)（Kmp 显式给出，式(14)–(16) 另列），
  θMi 显式或式(19)，粗略 θM 式(20)–(22)，θS 显式或式(72)（表3 XW），SB 式(78)。
阻断/TODO：斜齿与修形齿廓的 XΓ（9.3–9.9）、Péclet 数检查式(9)(10) 所需材料数据（只提供函数）、
  10.3 接触时间修正式(73)–(76)、10.4 式(77)（其 XL 引用"式(26)"而式(26) 为 XR，无法确认取哪一个 XL）、
  附录 A 热弹系数 XM 的一般式（XM 显式输入，条文给常用钢 50 K·N^−3/4·s^1/2·m^−1/2·mm，PDF15/印9）。
"""
from __future__ import annotations

import math

from .tribology_common import (EXTERNAL_LEVEL_KISSSOFT, KISSSOFT_V014_BASIS, OutOfDomain, Unconfirmed, choice,
                               formula_registry, missing_keys, nonneg, num, pos, MissingInput, TribError)
from .tribology_common import grant_external_evidence as _grant

P = "ISO/TS 6336-20:2022"
SOURCE_FILE = "ISO TS 6336-20-2022.pdf"
SOURCE_SHA256 = "f2b70cb1b15f46e0b9d739317718ea23d8cba14e75aca1bde4dbc460e51978c1"
EVIDENCE_NULL_REASON = "无外部算例：测试为测试内独立重写，不构成外部参照"
FORMULAS: dict = {}
_formula = formula_registry(FORMULAS, P, EVIDENCE_NULL_REASON)

# 6.4 式(25) XL 系数（乘 ηoil^−0,05；PDF19/印13 原图已核）
X_L_COEF = {"mineral": 1.0, "polyglycol_water_soluble": 0.6, "polyglycol_non_water_soluble": 0.7,
            "polyalfaolefin": 0.8, "phosphate_ester": 1.3, "traction_fluid": 1.5}
# 5.5 式(20) XS（PDF17/印11 原图已核）
X_S = {"spray": 1.2, "dip": 1.0, "dip_with_cooling_spray": 1.0, "submerged_sufficient_cooling": 0.2}
# 10.2 表3 结构系数 XW（PDF29/印23 原图已核）
X_W_TABLE3 = {"through_hardened": 1.00, "phosphated": 1.25, "copper_plated": 1.50, "nitrided_bath_gas": 1.50,
              "carburized_austenite_below_average": 1.15, "carburized_austenite_average_10_20": 1.00,
              "carburized_austenite_above_average": 0.85, "austenitic_stainless": 0.45}


@_formula("iso6336_20.eq11", f"{P} 5.3 式(11)–(13) wBt = KA·Kv·KBβ·KBα·Kmp·Ft/b，KBβ=KHβ，KBα=KHα（PDF16/印10 原图已核）")
def w_Bt(*, K_A, K_v, K_Hbeta, K_Halpha, K_mp, F_t, b):
    return (pos("K_A", K_A) * pos("K_v", K_v) * pos("K_Hbeta", K_Hbeta) * pos("K_Halpha", K_Halpha)
            * pos("K_mp", K_mp) * pos("F_t", F_t) / pos("b", b))


@_formula("iso6336_20.eq14", f"{P} 5.3 式(14) 行星轮系 Kmp = 1 + 0,25·√(np − 3)，np ≥ 3（PDF16/印10 原图已核）",
          note="条文为'无相关分析时可用'；其它情形（式17）Kmp = 1 由调用方显式给出")
def K_mp_planetary(*, n_planets):
    n = num("n_planets", n_planets)
    if n < 3:
        raise OutOfDomain("n_planets", "式(14) 要求 np ≥ 3")
    return 1.0 + 0.25 * math.sqrt(n - 3.0)


@_formula("iso6336_20.eq15", f"{P} 5.3 式(15) 双联串列 Kmp = 1 + 0,2/Φ（Φ 满载扭转角，度；PDF16/印10 原图已核）")
def K_mp_dual_tandem(*, quill_twist_deg):
    return 1.0 + 0.2 / pos("quill_twist_deg", quill_twist_deg)


@_formula("iso6336_20.eq16", f"{P} 5.3 式(16) 带外加轴向力的人字齿 Kmp = 1 + Fex/(Ft·tanβ)（PDF16/印10 原图已核）")
def K_mp_double_helical(*, F_ex, F_t, beta):
    return 1.0 + nonneg("F_ex", F_ex) / (pos("F_t", F_t) * math.tan(pos("beta", beta)))


@_formula("iso6336_20.eq24", f"{P} 6.4 式(24) vgΣC = 2·vt·sinαwt，vt>50 m/s 时以 50 代入（PDF19/印13 原图已核）")
def v_gSumC(*, v_t, alpha_wt):
    return 2.0 * min(pos("v_t", v_t), 50.0) * math.sin(pos("alpha_wt", alpha_wt))


@_formula("iso6336_20.eq25", f"{P} 6.4 式(25) XL = 系数·ηoil^−0,05（矿物油 1,0 …；ηoil mPa·s；PDF19/印13 原图已核）")
def X_L(*, lubricant, eta_oil):
    return X_L_COEF[choice("lubricant", lubricant, X_L_COEF)] * pos("eta_oil", eta_oil) ** -0.05


@_formula("iso6336_20.eq26", f"{P} 6.4 式(26) XR = ((Ra1+Ra2)/2)^0,25（µm；PDF19/印13 原图已核）")
def X_R(*, Ra1, Ra2):
    return (0.5 * (pos("Ra1", Ra1) + pos("Ra2", Ra2))) ** 0.25


@_formula("iso6336_20.eq23", f"{P} 6.4 式(23) 方法 C μm = 0,060·(wBt/(vgΣC·ρrelC))^0,2·XL·XR（PDF19/印13 原图已核）")
def mu_m_C(*, w_Bt, v_gSumC, rho_relC, X_L, X_R):
    return 0.060 * (pos("w_Bt", w_Bt) / (pos("v_gSumC", v_gSumC) * pos("rho_relC", rho_relC))) ** 0.2 \
        * pos("X_L", X_L) * pos("X_R", X_R)


@_formula("iso6336_20.eq6_8", f"{P} 5.2 式(6)–(8) ρy1 = (1+Γy)/(1+u)·a·sinαwt，ρy2 = (u−Γy)/(1+u)·a·sinαwt，"
                              "ρrely = ρy1·ρy2/(ρy1+ρy2)（PDF15/印9 原图已核）")
def radii(*, Gamma_y, u, a, alpha_wt):
    g, u = num("Gamma_y", Gamma_y), pos("u", u)
    k = pos("a", a) * math.sin(pos("alpha_wt", alpha_wt)) / (1.0 + u)
    r1, r2 = (1.0 + g) * k, (u - g) * k
    if r1 <= 0 or r2 <= 0:
        raise OutOfDomain("Gamma_y", f"Γy={g} 超出 (−1, u)")
    return {"rho_y1": r1, "rho_y2": r2, "rho_rely": r1 * r2 / (r1 + r2)}


@_formula("iso6336_20.eq27_33", f"{P} 7 式(27)–(33) 啮合线参数 ΓA、ΓB、ΓD、ΓE 与 tanαa1/2（PDF20–21/印14–15 原图已核）",
          note="式(30) 中间式的 tanα 下标印作 α2，按同式右端 ΓD = ΓA + 2π/(z1·tanαwt) 实现")
def gamma_points(*, z1, z2, d_a1, d_a2, d1, d2, alpha_t, alpha_wt):
    z1, z2 = pos("z1", z1), pos("z2", z2)
    t = math.tan(pos("alpha_wt", alpha_wt))
    ca = math.cos(pos("alpha_t", alpha_t))
    tan_a1 = math.sqrt((pos("d_a1", d_a1) / (pos("d1", d1) * ca)) ** 2 - 1.0)
    tan_a2 = math.sqrt((pos("d_a2", d_a2) / (pos("d2", d2) * ca)) ** 2 - 1.0)
    GA = -z2 / z1 * (tan_a2 / t - 1.0)
    GE = tan_a1 / t - 1.0
    GB = tan_a1 / t - 1.0 - 2.0 * math.pi / (z1 * t)
    GD = GA + 2.0 * math.pi / (z1 * t)
    return {"Gamma_A": GA, "Gamma_B": GB, "Gamma_D": GD, "Gamma_E": GE, "tan_alpha_a1": tan_a1, "tan_alpha_a2": tan_a2}


@_formula("iso6336_20.eqB1", f"{P} 附录 B 式(B.1) Ceff = KA·Kmp·Ft/(b·cosαt·cγ)（PDF37/印31 原图已核）")
def C_eff_optimal(*, K_A, K_mp, F_t, b, alpha_t, c_gamma):
    return pos("K_A", K_A) * pos("K_mp", K_mp) * pos("F_t", F_t) / (pos("b", b) * math.cos(pos("alpha_t", alpha_t))
                                                                      * pos("c_gamma", c_gamma))


@_formula("iso6336_20.eq34_37", f"{P} 8 式(34)–(37) 啮入系数 XJ（小轮主动 Γy<0 段、大轮主动 Γy>0 段；XJ ≥ 1；PDF21/印15 原图已核）")
def X_J(*, Gamma_y, Gamma_A, Gamma_E, C_eff, C_a1, C_a2, driver):
    g = num("Gamma_y", Gamma_y)
    span = num("Gamma_E", Gamma_E) - num("Gamma_A", Gamma_A)
    if span <= 0:
        raise OutOfDomain("Gamma_E", "ΓE 须大于 ΓA")
    Ce = pos("C_eff", C_eff)
    if choice("driver", driver, ("pinion", "wheel")) == "pinion":
        if g >= 0:
            return 1.0
        return max(1.0, 1.0 + (Ce - nonneg("C_a2", C_a2)) / 50.0 * (-g / span) ** 3)
    if g <= 0:
        return 1.0
    return max(1.0, 1.0 + (Ce - nonneg("C_a1", C_a1)) / 50.0 * (g / span) ** 3)


@_formula("iso6336_20.eq38_40", f"{P} 9.2 式(38)–(40) 直齿未修形 XΓ；A = 7（精度≤7 级）或精度等级（8..11）（PDF22/印16 原图已核）",
          note="式(40) 适用区间印为 ΓD<Γy≤ΓB，按同页图4/图5 的 D–E 段（ΓD<Γy≤ΓE）实现")
def X_Gamma_spur_unmodified(*, Gamma_y, Gamma_A, Gamma_B, Gamma_D, Gamma_E, tolerance_class):
    q = int(num("tolerance_class", tolerance_class))
    if q > 11:
        raise OutOfDomain("tolerance_class", "9.2 图5 只覆盖 A ≤ 11")
    A = 7 if q <= 7 else q
    g = num("Gamma_y", Gamma_y)
    GA, GB, GD, GE = (num(k, v) for k, v in (("Gamma_A", Gamma_A), ("Gamma_B", Gamma_B), ("Gamma_D", Gamma_D),
                                               ("Gamma_E", Gamma_E)))
    if not GA <= g <= GE:
        raise OutOfDomain("Gamma_y", "Γy 不在啮合线 [ΓA, ΓE] 内")
    if g < GB:
        return (A - 3) / 12.0 + (g - GA) / (3.0 * (GB - GA))
    if g <= GD:
        return 1.0
    return (A - 3) / 12.0 + (GE - g) / (3.0 * (GE - GD))


@_formula("iso6336_20.eq5", f"{P} 5.2 式(5) θfl = 2,52·μm·XM/50·XJ·(XΓ·wBt)^0,75·√(n1/60)·|√ρy1 − √(ρy2/u)|/ρrely^0,25（PDF15/印9 原图已核）",
          note="XM 单位 K·N^−3/4·s^1/2·m^−1/2·mm，常用钢 50（同页）；n1 min^−1")
def theta_fl(*, mu_m, X_M, X_J, X_Gamma, w_Bt, n1, rho_y1, rho_y2, u):
    r1, r2, u = pos("rho_y1", rho_y1), pos("rho_y2", rho_y2), pos("u", u)
    rel = r1 * r2 / (r1 + r2)
    return (2.52 * pos("mu_m", mu_m) * pos("X_M", X_M) / 50.0 * pos("X_J", X_J)
            * (pos("X_Gamma", X_Gamma) * pos("w_Bt", w_Bt)) ** 0.75 * math.sqrt(pos("n1", n1) / 60.0)
            * abs(math.sqrt(r1) - math.sqrt(r2 / u)) / rel ** 0.25)


@_formula("iso6336_20.eq19", f"{P} 5.4 式(19) θMi = (θM1+θM2)/2（PDF17/印11 原图已核）")
def theta_Mi(*, theta_M1, theta_M2):
    return 0.5 * (num("theta_M1", theta_M1) + num("theta_M2", theta_M2))


@_formula("iso6336_20.eq20_22", f"{P} 5.5 式(20)–(22) 粗略本体温度 θM = θoil + 0,47·XS·Xmp·θflm，Xmp=(1+np)/2，"
                                "θflm = ∫θfl dΓ/(ΓE−ΓA)（PDF17–18/印11–12 原图已核）")
def theta_M_rough(*, theta_oil, lubrication, n_p, theta_flm):
    n = num("n_p", n_p)
    if n < 1 or n != int(n):
        raise OutOfDomain("n_p", "np 须为 ≥1 的整数")
    return num("theta_oil", theta_oil) + 0.47 * X_S[choice("lubrication", lubrication, X_S)] * (1 + n) / 2.0 \
        * nonneg("theta_flm", theta_flm)


@_formula("iso6336_20.eq2", f"{P} 5.1 式(2) θBmax = θMi + θflmax（PDF14/印8 原图已核）")
def theta_Bmax(*, theta_Mi, theta_flmax):
    return num("theta_Mi", theta_Mi) + nonneg("theta_flmax", theta_flmax)


@_formula("iso6336_20.eq72", f"{P} 10.2 式(72) θS = θMT + XW·θflmaxT，XW 见表3（PDF29/印23 原图已核）")
def theta_S_from_test(*, theta_MT, material, theta_flmaxT):
    return num("theta_MT", theta_MT) + X_W_TABLE3[choice("material", material, X_W_TABLE3)] * nonneg("theta_flmaxT", theta_flmaxT)


def theta_S_eq77(**_):
    raise Unconfirmed("theta_S", "ISO/TS 6336-20 10.4 式(77)（PDF31/印25）的 XL 指向式(26)，而式(26) 为 XR；"
                                 "无法确认应取哪一个 XL，阻断")


@_formula("iso6336_20.eq78", f"{P} 10.5 式(78) SB = (θS − θoil)/(θBmax − θoil)（PDF31/印25 原图已核）")
def S_B(*, theta_S, theta_Bmax, theta_oil):
    den = num("theta_Bmax", theta_Bmax) - num("theta_oil", theta_oil)
    if den <= 0:
        raise OutOfDomain("theta_Bmax", "θBmax 须高于 θoil")
    return (num("theta_S", theta_S) - theta_oil) / den


# =================================================================== 主流程（直齿、未修形）
REQUIRED = ("z1", "z2", "a", "alpha_t", "alpha_wt", "beta", "d1", "d2", "d_a1", "d_a2", "b", "F_t", "v", "n1",
            "K_A", "K_v", "K_Hbeta", "K_Halpha", "K_mp", "c_gamma", "C_a1", "C_a2", "driver", "tolerance_class",
            "profile_modified", "X_M", "mu_method", "bulk_method", "theta_oil", "theta_S_method")


def _required(inp):
    req = list(REQUIRED)
    req += ["lubricant", "eta_oil", "Ra1", "Ra2"] if inp.get("mu_method") == "C" else ["mu_m_explicit"]
    req += ["theta_M_explicit"] if inp.get("bulk_method") == "explicit" else ["lubrication", "n_p"]
    req += ["theta_S_explicit"] if inp.get("theta_S_method") == "explicit" else ["theta_MT", "theta_flmaxT", "material_XW"]
    return req


def rate(inputs, n_samples=None):
    """闪温法骨架。n_samples：沿 [ΓA, ΓE] 等分取样点数（显式给出，≥ 11）；另加 ΓB、ΓD 两点。"""
    inp = dict(inputs)
    miss = missing_keys(inp, _required(inp))
    if n_samples is None:
        miss.append("n_samples")
    if miss:
        return {"status": "blocked", "missing": miss, "unconfirmed": []}
    try:
        choice("mu_method", inp["mu_method"], ("C", "explicit"))
        choice("bulk_method", inp["bulk_method"], ("explicit", "rough_eq20"))
        choice("theta_S_method", inp["theta_S_method"], ("explicit", "test_eq72"))
        if num("beta", inp["beta"]) != 0.0:
            raise Unconfirmed("beta", "斜齿 XΓ（9.4–9.9）本版未核对/未实现")
        if inp["profile_modified"] is not False:
            raise Unconfirmed("profile_modified", "修形齿廓 XΓ（9.3）本版未实现")
        r = {"u": pos("z2", inp["z2"]) / pos("z1", inp["z1"])}
        r["w_Bt"] = w_Bt(K_A=inp["K_A"], K_v=inp["K_v"], K_Hbeta=inp["K_Hbeta"], K_Halpha=inp["K_Halpha"],
                         K_mp=inp["K_mp"], F_t=inp["F_t"], b=inp["b"])
        r.update(gamma_points(z1=inp["z1"], z2=inp["z2"], d_a1=inp["d_a1"], d_a2=inp["d_a2"], d1=inp["d1"],
                              d2=inp["d2"], alpha_t=inp["alpha_t"], alpha_wt=inp["alpha_wt"]))
        r["rho_relC"] = radii(Gamma_y=0.0, u=r["u"], a=inp["a"], alpha_wt=inp["alpha_wt"])["rho_rely"]
        if inp["mu_method"] == "C":
            r["v_gSumC"] = v_gSumC(v_t=inp["v"], alpha_wt=inp["alpha_wt"])
            r["X_L"] = X_L(lubricant=inp["lubricant"], eta_oil=inp["eta_oil"])
            r["X_R"] = X_R(Ra1=inp["Ra1"], Ra2=inp["Ra2"])
            r["mu_m"] = mu_m_C(w_Bt=r["w_Bt"], v_gSumC=r["v_gSumC"], rho_relC=r["rho_relC"], X_L=r["X_L"], X_R=r["X_R"])
        else:
            r["mu_m"] = pos("mu_m_explicit", inp["mu_m_explicit"])
        r["C_eff"] = C_eff_optimal(K_A=inp["K_A"], K_mp=inp["K_mp"], F_t=inp["F_t"], b=inp["b"],
                                   alpha_t=inp["alpha_t"], c_gamma=inp["c_gamma"])
        n = int(num("n_samples", n_samples))
        if n < 11:
            raise OutOfDomain("n_samples", "取样点数须 ≥ 11")
        GA, GE = r["Gamma_A"], r["Gamma_E"]
        pts = sorted(set([GA, GE] + [GA + (GE - GA) * i / (n - 1) for i in range(1, n - 1)] + [r["Gamma_B"], r["Gamma_D"]]))
        prof = []
        for g in pts:
            rr = radii(Gamma_y=g, u=r["u"], a=inp["a"], alpha_wt=inp["alpha_wt"])
            xj = X_J(Gamma_y=g, Gamma_A=GA, Gamma_E=GE, C_eff=r["C_eff"], C_a1=inp["C_a1"], C_a2=inp["C_a2"],
                     driver=inp["driver"])
            xg = X_Gamma_spur_unmodified(Gamma_y=g, Gamma_A=GA, Gamma_B=r["Gamma_B"], Gamma_D=r["Gamma_D"],
                                         Gamma_E=GE, tolerance_class=inp["tolerance_class"])
            th = theta_fl(mu_m=r["mu_m"], X_M=inp["X_M"], X_J=xj, X_Gamma=xg, w_Bt=r["w_Bt"], n1=inp["n1"],
                          rho_y1=rr["rho_y1"], rho_y2=rr["rho_y2"], u=r["u"])
            prof.append({"Gamma_y": g, "X_J": xj, "X_Gamma": xg, "theta_fl": th})
        r["profile"] = prof
        best = max(prof, key=lambda p: p["theta_fl"])
        r["theta_flmax"], r["Gamma_at_max"] = best["theta_fl"], best["Gamma_y"]
        if inp["bulk_method"] == "explicit":
            r["theta_M"] = num("theta_M_explicit", inp["theta_M_explicit"])
        else:
            area = sum(0.5 * (p0["theta_fl"] + p1["theta_fl"]) * (p1["Gamma_y"] - p0["Gamma_y"])
                       for p0, p1 in zip(prof, prof[1:]))          # 式(22) 梯形数值积分（XΓ 跳变处两侧均为取样点）
            r["theta_flm"] = area / (GE - GA)
            r["theta_M"] = theta_M_rough(theta_oil=inp["theta_oil"], lubrication=inp["lubrication"], n_p=inp["n_p"],
                                         theta_flm=r["theta_flm"])
        r["theta_Mi"] = theta_Mi(theta_M1=r["theta_M"], theta_M2=r["theta_M"])
        r["theta_Bmax"] = theta_Bmax(theta_Mi=r["theta_Mi"], theta_flmax=r["theta_flmax"])
        if inp["theta_S_method"] == "explicit":
            r["theta_S"] = num("theta_S_explicit", inp["theta_S_explicit"])
        else:
            r["theta_S"] = theta_S_from_test(theta_MT=inp["theta_MT"], material=inp["material_XW"],
                                             theta_flmaxT=inp["theta_flmaxT"])
        r["S_B"] = S_B(theta_S=r["theta_S"], theta_Bmax=r["theta_Bmax"], theta_oil=inp["theta_oil"])
    except Unconfirmed as e:
        return {"status": "blocked", "missing": [], "unconfirmed": [str(e)]}
    except MissingInput as e:
        return {"status": "blocked", "missing": [e.name], "unconfirmed": []}
    r["status"] = "ok"
    return r


__all__ = ["rate", "FORMULAS", "TribError"]


# =================================================================== 外部证据（KISSsoft 2026 P3 K01 直齿，tests/test_m39_kisssoft_v014.py）
# 只登记以 KISSsoft 可追溯字段为输入、逐位一致者。未列入（null）：式(5) θfl（KISSsoft Γmax 处 −6,2 %，未归因）、
# 式(34)–(37) XJ 与附录 B Ceff
# （XJ 分布未导出）、式(14)–(16)、式(19)、式(72)。斜齿 K02/K04/K05 本骨架阻断。
EXTERNAL_EVIDENCE = {
    "iso6336_20.eq25": "XL = ηoil^−0,05（ZP[0].FBT.XLforPart1）K01 逐位一致（ηoil 由本库 -22 链计算）",
    "iso6336_20.eq27_33": "ΓA、ΓB、ΓD、ΓE 与 KISSsoft 七点 GamY（ZP[0].MP_ISO.analysisPoints[0/2/4/6].GamY）K01 逐位一致",
    "iso6336_20.eq6_8": "ρy1 在 A、C、E 与 ZP[0].EL.T1A/T1C/T1E K01 逐位一致",
    "iso6336_20.eq11": "wBt 与 ZP[0].Scoring_wBT K01 逐位一致（Kmp=1、KBγ=1 不可区分）",
    "iso6336_20.eq38_40": "XΓ 在 KISSsoft 最大温度点 Γ（FBT.Gamma，D–E 段）与 FBT.XGam 相对差 7,3e-10（门 1e-8）",
    "iso6336_20.eq20_22": "θMi = θoil + 0,47·XS·Xmp·θflm 以 KISSsoft θflm（Scoring_Theflm）代入与 FBT.them 逐位一致"
                          "（式(22) 积分本身未比较）",
    "iso6336_20.eq2": "θBmax = θMi + θflmax 以 KISSsoft 中间量代入与 FBT.theB 逐位一致",
    "iso6336_20.eq78": "SB 以 KISSsoft θS、θBmax 代入与 FBT.SB 逐位一致",
    # v0.15 回传 M39-K01-runin0（RechSt.Scoring_RunIn=0，只改此一项，读回与保存原件一致）：报告原 Ra 直接进入式(26)，
    # 输入身份可追溯（ZR[i].RAH=0,6），不再依赖推断。跑合（RunIn=1）时 KISSsoft 按 0,6·Ra 已由开关对照证实（比值 0,6^−0,25）。
    "iso6336_20.eq23": "μm 方法 C（FBT.mymy）K01 RunIn=0 以报告 Ra=0,6 µm 逐位一致（v0.15 回传 M39-K01-runin0，相对 9e-16）",
    "iso6336_20.eq24": "vgΣC 在 μm 求值链上（chain），K01 RunIn=0",
    "iso6336_20.eq26": "XR = ((Ra1+Ra2)/2)^0,25 在 μm 链上，K01 RunIn=0 原 Ra（ZR[i].RAH）逐位一致；RunIn 1/0 两运行 μm 比值 = 0,6^−0,25",
}
_grant(FORMULAS, globals(), EXTERNAL_EVIDENCE, level=EXTERNAL_LEVEL_KISSSOFT, basis=KISSSOFT_V014_BASIS)
