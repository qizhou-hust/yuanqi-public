"""ISO/TS 6336-22:2018 微点蚀承载能力（方法 B 骨架）：λGF,Y = hY/Ra，Sλ = λGF,min/λGFP。

资料与核对口径（用户私有 PDF，本机逐式渲染原图核对；代码只写条款号、式号、页码）：
  - 文件 "ISO_TS 6336-22-2018.pdf"（48 页扫描），SHA256=SOURCE_SHA256；PDF 页 = 印刷页 + 8（PDF14 = 印6）。
  - 证据等级：ISO/TR 6336-31 算例本机未提供；v0.14 起 KISSsoft 2026 P3 K01/K02 七点（θM、θfl,Y 显式）逐位一致者
    登记 E5（文末 EXTERNAL_EVIDENCE），其余 null。

本版闭合范围（窄）：
  Er 式(6)(7)、αθ 式(8)/(28)、α38 式(9)–(11)、GM 式(5)、ν(θ) 式(17)–(19)/(30)、ρ(θ) 式(20)/(31)、ρ15 式(21)、
  η = 10⁻⁶·ν·ρ 式(16)/(29)、vΣ,Y 式(13)–(15)、UY 式(12)、WY 式(22)、pdyn,Y,A 式(23)、SGF,Y 式(27)、
  hY 式(4)、λGF,Y 式(2)(3)、接触点 gY 式(32)–(38)、dY 与 ρn,Y 式(39)–(43)、Sλ 式(1)、λGFP 附录 A 式(A.1)+表 A.1；
  v0.14 增：方法 B pdyn,Y 式(24)–(26)、直齿 XY 式(44)–(46)（未修形）与式(47)–(49)（图4 两轮修形），
  p_dyn_points_method_B_spur 七点组装（可作 rate() 的 local[点]["p_dyn"]）。
阻断/TODO（调用方须显式给出，或待后续核对）：
  斜齿 XY（11.4–11.9，含 εβ 插值）与直齿图5/图6 修形 XY（式(50)–(59)）、局部闪温 θfl,Y（第 13 章式(79)–(82)
  未收录）、本体温度 θM（第 14 章式(83)–(98) 未收录）、gα 与 pet（-22 未给式，取 ISO 21771 几何，调用方给出）、
  λGFP 方法 B 图 A.1/附录 B 曲线（只收式(A.1)，λGFT 显式给出）。
单位：η N·s/m²（Pa·s）；α m²/N；ν mm²/s；ρ kg/m³；Er N/mm²；ρn mm；v m/s；hY µm（表2，PDF10–12）。
式(17)–(19) 中 log 未注底：两点拟合的双对数式对底数取 10 或 e 结果相同（仿射等价），本模块用 log10。
"""
from __future__ import annotations

import math

from .tribology_common import (EXTERNAL_LEVEL_KISSSOFT, KISSSOFT_V014_BASIS, MissingInput, OutOfDomain, Unconfirmed,
                               choice, formula_registry, missing_keys, nonneg, num, pos)
from .tribology_common import grant_external_evidence as _grant

P = "ISO/TS 6336-22:2018"
SOURCE_FILE = "ISO_TS 6336-22-2018.pdf"
SOURCE_SHA256 = "8646d115b82c1d6547be077e66d2698284517dc4548cf3abc3f46e55d8da1941"
EVIDENCE_NULL_REASON = "无外部算例：ISO/TR 6336-31 算例本机未提供；测试为测试内独立重写，不构成外部参照"
FORMULAS: dict = {}
_formula = formula_registry(FORMULAS, P, EVIDENCE_NULL_REASON)

ALPHA38_COEF = {"mineral": (2.657e-8, 0.1348), "pao_non_vi_improved": (1.466e-8, 0.0507), "pag": (1.392e-8, 0.1572)}
W_W_TABLE_A1 = {"case_carburized_austenite_lt25": 1.0, "case_carburized_austenite_gt25": 0.95,
                "gas_nitrided_hv_gt850": 1.5, "induction_flame_hardened": 0.65, "through_hardened": 0.5}
POINTS = ("A", "AB", "B", "C", "D", "DE", "E")


@_formula("iso6336_22.eq6_7", f"{P} 6.2 式(6) Er = 2·((1−ν1²)/E1 + (1−ν2²)/E2)^−1；式(7) 同材料 Er = E/(1−ν²)（PDF18/印10 原图已核）")
def E_r(*, E1, E2, nu1, nu2):
    return 2.0 / ((1.0 - num("nu1", nu1) ** 2) / pos("E1", E1) + (1.0 - num("nu2", nu2) ** 2) / pos("E2", E2))


@_formula("iso6336_22.eq9_11", f"{P} 6.3 式(9)–(11) α38 = k·η38^n（矿物油 2,657e−8·η38^0,1348；PAO 1,466e−8·η38^0,0507；"
                               "PAG 1,392e−8·η38^0,1572；η38 N·s/m²；PDF18/印10 原图已核）")
def alpha_38(*, eta_38, oil_type):
    k, n = ALPHA38_COEF[choice("oil_type", oil_type, ALPHA38_COEF)]
    return k * pos("eta_38", eta_38) ** n


@_formula("iso6336_22.eq8_28", f"{P} 6.3 式(8)、9.2 式(28) αθ = α38·[1 + 516·(1/(θ+273) − 1/311)]（PDF18/印10、PDF23/印15 原图已核）",
          note="原图为线性方括号形式（非指数），按原图收录")
def alpha_theta(*, alpha_38, theta):
    return pos("alpha_38", alpha_38) * (1.0 + 516.0 * (1.0 / (num("theta", theta) + 273.0) - 1.0 / 311.0))


@_formula("iso6336_22.eq5", f"{P} 6.1 式(5) GM = 10⁶·αθM·Er（PDF17/印9 原图已核）")
def G_M(*, alpha_thetaM, E_r):
    return 1.0e6 * pos("alpha_thetaM", alpha_thetaM) * pos("E_r", E_r)


@_formula("iso6336_22.eq17_19", f"{P} 7.3.2 式(17)–(19)、9.3.2 式(30) log[log(νθ+0,7)] = A·log(θ+273) + B，"
                                "A = log[log(ν40+0,7)/log(ν100+0,7)]/log(313/373)，B = log[log(ν40+0,7)] − A·log(313)（PDF20/印12、PDF24/印16 原图已核）",
          note="θ>140 °C 外推条文要求实测确认 → 越域阻断")
def nu_theta(*, nu_40, nu_100, theta):
    n40, n100, th = pos("nu_40", nu_40), pos("nu_100", nu_100), num("theta", theta)
    if n100 >= n40:
        raise OutOfDomain("nu_100", "ν100 须小于 ν40")
    if th > 140.0:
        raise OutOfDomain("theta", "7.3.2/9.3.2：高于 140 °C 的外推须实测确认")
    lg = math.log10
    A = lg(lg(n40 + 0.7) / lg(n100 + 0.7)) / lg(313.0 / 373.0)
    B = lg(lg(n40 + 0.7)) - A * lg(313.0)
    return 10.0 ** (10.0 ** (A * lg(th + 273.0) + B)) - 0.7


@_formula("iso6336_22.eq21", f"{P} 7.3.3 式(21) 矿物油 ρ15 = 43,37·log ν40 + 805,5（PDF21/印13 原图已核）",
          note="仅矿物油；油品数据表有 ρ15 时应优先用数据表值")
def rho_15_mineral(*, nu_40):
    return 43.37 * math.log10(pos("nu_40", nu_40)) + 805.5


@_formula("iso6336_22.eq20_31", f"{P} 7.3.3 式(20)、9.3.3 式(31) ρθ = ρ15·[1 − 0,7·((θ+273) − 288)/ρ15]（PDF20/印12、PDF24/印16 原图已核）")
def rho_theta(*, rho_15, theta):
    r15 = pos("rho_15", rho_15)
    return r15 * (1.0 - 0.7 * ((num("theta", theta) + 273.0) - 288.0) / r15)


@_formula("iso6336_22.eq16_29", f"{P} 7.3.1 式(16)、9.3.1 式(29) η = 10⁻⁶·ν·ρ（N·s/m²；PDF20/印12、PDF23/印15 原图已核）")
def eta_dynamic(*, nu, rho):
    return 1.0e-6 * pos("nu", nu) * pos("rho", rho)


@_formula("iso6336_22.eq13_15", f"{P} 7.2 式(13)–(15) vΣ,Y = vr1,Y + vr2,Y，vr1,Y = 2π·n1/60·dw1/2000·sinαwt·√((dY1²−db1²)/(dw1²−db1²))，"
                                "vr2,Y 同（n1/(u·60)、dw2、dY2、db2）（PDF19/印11 原图已核）")
def v_sum_Y(*, n1, u, d_w1, d_w2, d_b1, d_b2, d_Y1, d_Y2, alpha_wt):
    n1, u, s = pos("n1", n1), pos("u", u), math.sin(pos("alpha_wt", alpha_wt))
    dw1, dw2, db1, db2 = pos("d_w1", d_w1), pos("d_w2", d_w2), pos("d_b1", d_b1), pos("d_b2", d_b2)
    dY1, dY2 = pos("d_Y1", d_Y1), pos("d_Y2", d_Y2)
    if dY1 < db1 or dY2 < db2:
        raise OutOfDomain("d_Y", "Y 圆直径不得小于基圆")
    v1 = 2 * math.pi * n1 / 60.0 * dw1 / 2000.0 * s * math.sqrt((dY1 ** 2 - db1 ** 2) / (dw1 ** 2 - db1 ** 2))
    v2 = 2 * math.pi * n1 / (u * 60.0) * dw2 / 2000.0 * s * math.sqrt((dY2 ** 2 - db2 ** 2) / (dw2 ** 2 - db2 ** 2))
    return {"v_r1": v1, "v_r2": v2, "v_sum": v1 + v2}


@_formula("iso6336_22.eq12", f"{P} 7.1 式(12) UY = ηθM·vΣ,Y/(2000·Er·ρn,Y)（PDF19/印11 原图已核）")
def U_Y(*, eta_thetaM, v_sum_Y, E_r, rho_nY):
    return pos("eta_thetaM", eta_thetaM) * pos("v_sum_Y", v_sum_Y) / (2000.0 * pos("E_r", E_r) * pos("rho_nY", rho_nY))


@_formula("iso6336_22.eq22", f"{P} 8.1 式(22) WY = 2π·pdyn,Y²/Er²（PDF21/印13 原图已核）")
def W_Y(*, p_dyn_Y, E_r):
    return 2.0 * math.pi * pos("p_dyn_Y", p_dyn_Y) ** 2 / pos("E_r", E_r) ** 2


@_formula("iso6336_22.eq23", f"{P} 8.2 式(23) 方法 A pdyn,Y,A = pH,Y,A·√(KA·Kv)（PDF21/印13 原图已核）",
          note="pH,Y,A 由三维载荷分布程序给出；若该程序已含 KA/Kv，条文注释要求相应取 1,0（调用方显式给出）")
def p_dyn_A(*, p_H_Y_A, K_A, K_v):
    return pos("p_H_Y_A", p_H_Y_A) * math.sqrt(pos("K_A", K_A) * pos("K_v", K_v))


@_formula("iso6336_22.eq27", f"{P} 9.1 式(27) SGF,Y = αθB,Y·ηθB,Y/(αθM·ηθM)（PDF23/印15 原图已核）")
def S_GF(*, alpha_thetaB, eta_thetaB, alpha_thetaM, eta_thetaM):
    return pos("alpha_thetaB", alpha_thetaB) * pos("eta_thetaB", eta_thetaB) / (pos("alpha_thetaM", alpha_thetaM)
                                                                                 * pos("eta_thetaM", eta_thetaM))


@_formula("iso6336_22.eq4", f"{P} 5.3 式(4) hY = 1600·ρn,Y·GM^0,6·UY^0,7·WY^−0,13·SGF,Y^0,22（PDF14/印6 原图已核）")
def h_Y(*, rho_nY, G_M, U_Y, W_Y, S_GF_Y):
    return (1600.0 * pos("rho_nY", rho_nY) * pos("G_M", G_M) ** 0.6 * pos("U_Y", U_Y) ** 0.7
            * pos("W_Y", W_Y) ** -0.13 * pos("S_GF_Y", S_GF_Y) ** 0.22)


@_formula("iso6336_22.eq2_3", f"{P} 5.3 式(2)(3) λGF,Y = hY/Ra，Ra = 0,5·(Ra1+Ra2)（PDF14/印6 原图已核）")
def lambda_GF_Y(*, h_Y, Ra1, Ra2):
    return pos("h_Y", h_Y) / (0.5 * (pos("Ra1", Ra1) + pos("Ra2", Ra2)))


@_formula("iso6336_22.eq1", f"{P} 5.2 式(1) Sλ = λGF,min/λGFP（PDF14/印6 原图已核）")
def S_lambda(*, lambda_GF_min, lambda_GFP):
    return pos("lambda_GF_min", lambda_GF_min) / pos("lambda_GFP", lambda_GFP)


@_formula("iso6336_22.eqA1", f"{P} 附录 A 式(A.1) λGFP = 1,4·WW·λGFT，表 A.1 WW（PDF42/印34 原图已核）",
          note="式右端下标原图印作 λGFP，按同页 where 列表的 λGFT（试验得比油膜厚度）实现")
def lambda_GFP_A1(*, material, lambda_GFT):
    return 1.4 * W_W_TABLE_A1[choice("material", material, W_W_TABLE_A1)] * pos("lambda_GFT", lambda_GFT)


@_formula("iso6336_22.eq32_38", f"{P} 10 式(32)–(38) 方法 B 七个接触点 gY（自 A 点起量；PDF24–25/印16–17 原图已核）")
def contact_points(*, g_alpha, p_et, d_a1, d_b1, alpha_wt):
    ga, pe = pos("g_alpha", g_alpha), pos("p_et", p_et)
    if pe >= ga:
        raise OutOfDomain("p_et", "pet 须小于 gα（εα > 1）")
    da1, db1 = pos("d_a1", d_a1), pos("d_b1", d_b1)
    gC = db1 / 2.0 * math.tan(pos("alpha_wt", alpha_wt)) - math.sqrt(da1 ** 2 / 4.0 - db1 ** 2 / 4.0) + ga
    return {"A": 0.0, "AB": (ga - pe) / 2.0, "B": ga - pe, "C": gC, "D": pe, "DE": (ga - pe) / 2.0 + pe, "E": ga}


@_formula("iso6336_22.eq39_43", f"{P} 10 式(39)–(43) dY1、dY2，ρt1,2,Y = √((dY²−db²)/4)，ρt,Y = ρt1·ρt2/(ρt1+ρt2)，"
                                "ρn,Y = ρt,Y/cosβb（PDF26/印18 原图已核）")
def local_geometry(*, g_Y, g_alpha, d_a1, d_a2, d_b1, d_b2, beta_b):
    gY, ga = nonneg("g_Y", g_Y), pos("g_alpha", g_alpha)
    da1, da2, db1, db2 = pos("d_a1", d_a1), pos("d_a2", d_a2), pos("d_b1", d_b1), pos("d_b2", d_b2)
    t1 = math.sqrt(da1 ** 2 / 4 - db1 ** 2 / 4) - ga + gY
    t2 = math.sqrt(da2 ** 2 / 4 - db2 ** 2 / 4) - gY
    if t1 <= 0 or t2 <= 0:
        raise OutOfDomain("g_Y", "接触点超出啮合线（到切点距离 ≤ 0）")
    dY1 = 2.0 * math.sqrt(db1 ** 2 / 4 + t1 ** 2)
    dY2 = 2.0 * math.sqrt(db2 ** 2 / 4 + t2 ** 2)
    r1 = math.sqrt((dY1 ** 2 - db1 ** 2) / 4)
    r2 = math.sqrt((dY2 ** 2 - db2 ** 2) / 4)
    rt = r1 * r2 / (r1 + r2)
    return {"d_Y1": dY1, "d_Y2": dY2, "rho_t1": r1, "rho_t2": r2, "rho_tY": rt,
            "rho_nY": rt / math.cos(nonneg("beta_b", beta_b))}


# =================================================================== 方法 B 局部赫兹应力与载荷分配系数（直齿）
@_formula("iso6336_22.eq44_46", f"{P} 11.2 式(44)–(46) 直齿未修形 XY：gA≤gY<gB 取 (A−2)/15 + gY/(3·gB)；gB≤gY≤gD 取 1,0；"
                                "gD<gY≤gE 取 (A−2)/15 + (gα−gY)/(3·(gα−gD))；A = 7（精度 ≤7 级）或精度等级（≥8 级）"
                                "（PDF27–28/印19–20 原图已核）",
          note="gY 自 A 点起量（式(32)–(38)），gB = gα − pet，gD = pet；图3 只画到 A = 11，A > 11 越域阻断")
def X_Y_spur_unmodified(*, g_Y, g_B, g_D, g_alpha, tolerance_class):
    q = int(num("tolerance_class", tolerance_class))
    if q > 11:
        raise OutOfDomain("tolerance_class", "11.2 图3 只覆盖 A ≤ 11")
    A = 7 if q <= 7 else q
    g, gB, gD, ga = nonneg("g_Y", g_Y), pos("g_B", g_B), pos("g_D", g_D), pos("g_alpha", g_alpha)
    if not gB <= gD < ga or g > ga:
        raise OutOfDomain("g_Y", "须 0 ≤ gY ≤ gα 且 gB ≤ gD < gα")
    if g < gB:
        return (A - 2) / 15.0 + g / (3.0 * gB)
    if g <= gD:
        return 1.0
    return (A - 2) / 15.0 + (ga - g) / (3.0 * (ga - gD))


@_formula("iso6336_22.eq47_49", f"{P} 11.3 式(47)–(49) 直齿两轮均有适当齿廓修形（图4）XY：gY/gB；1,0；(gα−gY)/(gα−gD)"
                                "（PDF28/印20 原图已核）",
          note="只收图4 情形；图5/图6（仅大轮齿顶或小轮齿根修形，式(50)–(59)）未收录")
def X_Y_spur_modified_both(*, g_Y, g_B, g_D, g_alpha):
    g, gB, gD, ga = nonneg("g_Y", g_Y), pos("g_B", g_B), pos("g_D", g_D), pos("g_alpha", g_alpha)
    if not gB <= gD < ga or g > ga:
        raise OutOfDomain("g_Y", "须 0 ≤ gY ≤ gα 且 gB ≤ gD < gα")
    if g <= gB:
        return g / gB
    if g < gD:
        return 1.0
    return (ga - g) / (ga - gD)


@_formula("iso6336_22.eq25_26", f"{P} 8.3.2 式(25)(26) pH,Y,B = ZE·√(Ft·XY/(b·ρn,Y·cosαt))，ZE = √(Er/(2π))（PDF22/印14 原图已核）",
          note="式(25) 原图分母为 cosαt（同页 where 列出 βb 但式中未出现，按原图实现）；Ft 为分度圆端面切向力")
def p_H_Y_B(*, F_t, X_Y, b, rho_nY, alpha_t, E_r):
    ZE = math.sqrt(pos("E_r", E_r) / (2.0 * math.pi))
    return ZE * math.sqrt(pos("F_t", F_t) * pos("X_Y", X_Y) / (pos("b", b) * pos("rho_nY", rho_nY)
                                                              * math.cos(pos("alpha_t", alpha_t))))


@_formula("iso6336_22.eq24", f"{P} 8.3.1 式(24) pdyn,Y,B = pH,Y,B·√(KA·Kγ·Kv·KHα·KHβ)（PDF22/印14 原图已核）",
          note="同页注：εα > 2 只能用方法 A → 越域阻断")
def p_dyn_B(*, p_H_Y_B, K_A, K_gamma, K_v, K_Halpha, K_Hbeta, eps_alpha):
    if pos("eps_alpha", eps_alpha) > 2.0:
        raise OutOfDomain("eps_alpha", "8.3.1 注：εα > 2 只能按方法 A 计算")
    return pos("p_H_Y_B", p_H_Y_B) * math.sqrt(pos("K_A", K_A) * pos("K_gamma", K_gamma) * pos("K_v", K_v)
                                               * pos("K_Halpha", K_Halpha) * pos("K_Hbeta", K_Hbeta))


def p_dyn_points_method_B_spur(*, profile, g_alpha, p_et, d_a1, d_a2, d_b1, d_b2, alpha_wt, alpha_t, F_t, b, E_r,
                               K_A, K_gamma, K_v, K_Halpha, K_Hbeta, eps_alpha, beta_b, tolerance_class):
    """直齿方法 B 七点 pdyn,Y：gY 式(32)–(38) → ρn,Y 式(39)–(43) → XY 式(44)–(46)/(47)–(49) → 式(25)(26) → 式(24)。

    profile：'unmodified'（11.2）| 'modified_both'（11.3 图4）。斜齿 XY（11.5–11.9）未收录 → 阻断。
    返回 {点名: {"g_Y", "X_Y", "rho_nY", "p_H", "p_dyn"}}，可直接作为 rate() 的 local[点]["p_dyn"]。"""
    if nonneg("beta_b", beta_b) != 0.0:
        raise Unconfirmed("beta_b", "斜齿 XY（11.4–11.9，含 XY 在 εβ=0,8/1,2 间插值）本版未收录")
    choice("profile", profile, ("unmodified", "modified_both"))
    gY = contact_points(g_alpha=g_alpha, p_et=p_et, d_a1=d_a1, d_b1=d_b1, alpha_wt=alpha_wt)
    gB, gD = gY["B"], gY["D"]
    out = {}
    for name in POINTS:
        geo = local_geometry(g_Y=gY[name], g_alpha=g_alpha, d_a1=d_a1, d_a2=d_a2, d_b1=d_b1, d_b2=d_b2, beta_b=beta_b)
        if profile == "unmodified":
            xy = X_Y_spur_unmodified(g_Y=gY[name], g_B=gB, g_D=gD, g_alpha=g_alpha, tolerance_class=tolerance_class)
        else:
            xy = X_Y_spur_modified_both(g_Y=gY[name], g_B=gB, g_D=gD, g_alpha=g_alpha)
        if xy <= 0.0:
            raise OutOfDomain(f"X_Y[{name}]", "XY = 0（该点不承载）：pdyn,Y = 0 时式(22)(4) 无定义，条文未给处理")
        pH = p_H_Y_B(F_t=F_t, X_Y=xy, b=b, rho_nY=geo["rho_nY"], alpha_t=alpha_t, E_r=E_r)
        out[name] = {"g_Y": gY[name], "X_Y": xy, "rho_nY": geo["rho_nY"], "p_H": pH,
                     "p_dyn": p_dyn_B(p_H_Y_B=pH, K_A=K_A, K_gamma=K_gamma, K_v=K_v, K_Halpha=K_Halpha,
                                      K_Hbeta=K_Hbeta, eps_alpha=eps_alpha)}
    return out


# =================================================================== 主流程（方法 B 七点；pdyn,Y 与 θfl,Y 显式）
REQUIRED = ("n1", "u", "d_w1", "d_w2", "d_a1", "d_a2", "d_b1", "d_b2", "alpha_wt", "beta_b", "g_alpha", "p_et",
            "E1", "E2", "nu1", "nu2", "oil_type", "nu_40", "nu_100", "density", "theta_M", "Ra1", "Ra2",
            "alpha_38_source", "local", "lambda_GFP_source")


def _required(inp):
    req = list(REQUIRED)
    req += ["rho_15"] if inp.get("density") == "rho_15" else []
    req += ["alpha_38"] if inp.get("alpha_38_source") == "explicit" else []
    req += ["lambda_GFP"] if inp.get("lambda_GFP_source") == "explicit" else ["material_WW", "lambda_GFT"]
    return req


def rate(inputs):
    """inputs["local"]：{点名: {"p_dyn": N/mm², "theta_fl": K}}，须覆盖 A、AB、B、C、D、DE、E 七点。
    density：'rho_15'（给数据表 ρ15）| 'mineral_eq21'（矿物油式(21)）。alpha_38_source：'explicit' | 'eq9_11'。"""
    inp = dict(inputs)
    miss = missing_keys(inp, _required(inp))
    if miss:
        return {"status": "blocked", "missing": miss, "unconfirmed": []}
    try:
        choice("density", inp["density"], ("rho_15", "mineral_eq21"))
        choice("alpha_38_source", inp["alpha_38_source"], ("explicit", "eq9_11"))
        choice("lambda_GFP_source", inp["lambda_GFP_source"], ("explicit", "A1"))
        loc = inp["local"]
        lack = [p for p in POINTS if not isinstance(loc, dict) or p not in loc
                or loc[p].get("p_dyn") is None or loc[p].get("theta_fl") is None]
        if lack:
            return {"status": "blocked", "missing": [f"local[{p}].p_dyn/theta_fl" for p in lack], "unconfirmed": []}
        r = {"E_r": E_r(E1=inp["E1"], E2=inp["E2"], nu1=inp["nu1"], nu2=inp["nu2"])}
        r["rho_15"] = (pos("rho_15", inp["rho_15"]) if inp["density"] == "rho_15"
                       else rho_15_mineral(nu_40=inp["nu_40"]))

        def eta_at(th):
            return eta_dynamic(nu=nu_theta(nu_40=inp["nu_40"], nu_100=inp["nu_100"], theta=th),
                               rho=rho_theta(rho_15=r["rho_15"], theta=th))
        if inp["alpha_38_source"] == "explicit":
            r["alpha_38"] = pos("alpha_38", inp["alpha_38"])
        else:
            r["alpha_38"] = alpha_38(eta_38=eta_at(38.0), oil_type=inp["oil_type"])
        r["eta_thetaM"] = eta_at(num("theta_M", inp["theta_M"]))
        r["alpha_thetaM"] = alpha_theta(alpha_38=r["alpha_38"], theta=inp["theta_M"])
        r["G_M"] = G_M(alpha_thetaM=r["alpha_thetaM"], E_r=r["E_r"])
        r["g_Y"] = contact_points(g_alpha=inp["g_alpha"], p_et=inp["p_et"], d_a1=inp["d_a1"], d_b1=inp["d_b1"],
                                  alpha_wt=inp["alpha_wt"])
        pts = {}
        for name in POINTS:
            g = local_geometry(g_Y=r["g_Y"][name], g_alpha=inp["g_alpha"], d_a1=inp["d_a1"], d_a2=inp["d_a2"],
                               d_b1=inp["d_b1"], d_b2=inp["d_b2"], beta_b=inp["beta_b"])
            vs = v_sum_Y(n1=inp["n1"], u=inp["u"], d_w1=inp["d_w1"], d_w2=inp["d_w2"], d_b1=inp["d_b1"],
                         d_b2=inp["d_b2"], d_Y1=g["d_Y1"], d_Y2=g["d_Y2"], alpha_wt=inp["alpha_wt"])
            thB = num("theta_M", inp["theta_M"]) + nonneg(f"local[{name}].theta_fl", loc[name]["theta_fl"])   # 式(78)
            row = dict(g, **vs, theta_B=thB)
            row["U_Y"] = U_Y(eta_thetaM=r["eta_thetaM"], v_sum_Y=vs["v_sum"], E_r=r["E_r"], rho_nY=g["rho_nY"])
            row["W_Y"] = W_Y(p_dyn_Y=loc[name]["p_dyn"], E_r=r["E_r"])
            row["S_GF"] = S_GF(alpha_thetaB=alpha_theta(alpha_38=r["alpha_38"], theta=thB), eta_thetaB=eta_at(thB),
                               alpha_thetaM=r["alpha_thetaM"], eta_thetaM=r["eta_thetaM"])
            row["h_Y"] = h_Y(rho_nY=g["rho_nY"], G_M=r["G_M"], U_Y=row["U_Y"], W_Y=row["W_Y"], S_GF_Y=row["S_GF"])
            row["lambda_GF"] = lambda_GF_Y(h_Y=row["h_Y"], Ra1=inp["Ra1"], Ra2=inp["Ra2"])
            pts[name] = row
        r["points"] = pts
        r["point_min"] = min(pts, key=lambda k: pts[k]["lambda_GF"])
        r["lambda_GF_min"] = pts[r["point_min"]]["lambda_GF"]
        r["lambda_GFP"] = (pos("lambda_GFP", inp["lambda_GFP"]) if inp["lambda_GFP_source"] == "explicit"
                           else lambda_GFP_A1(material=inp["material_WW"], lambda_GFT=inp["lambda_GFT"]))
        r["S_lambda"] = S_lambda(lambda_GF_min=r["lambda_GF_min"], lambda_GFP=r["lambda_GFP"])
    except Unconfirmed as e:
        return {"status": "blocked", "missing": [], "unconfirmed": [str(e)]}
    except MissingInput as e:
        return {"status": "blocked", "missing": [e.name], "unconfirmed": []}
    r["status"] = "ok"
    return r


# =================================================================== 外部证据（KISSsoft 2026 P3 K01/K02 七点，tests/test_m39_kisssoft_v014.py）
# θM、θfl,Y 取 KISSsoft 值作显式输入（隔离第 13/14 章）；K01 七点全比，K02 只比 AB–DE（A/E 点 KISSsoft pdyn=0，
# 已知差异）。未列入（null）：式(21) ρ15 近似（KISSsoft 用数据表 ρ15）、式(23) 方法 A、式(47)–(49) 修形直齿 XY（未被案例覆盖）。
# K03–K05 KISSsoft 未计算（缺油品微点蚀试验数据），不构成任何证据。
EXTERNAL_EVIDENCE = {
    "iso6336_22.eq6_7": "Er = 226373,626 N/mm²（报告 [Er]）K01/K02",
    "iso6336_22.eq9_11": "α38（ZS.Oil.alfa38，mm²/N）K01/K02 逐位一致（矿物油）",
    "iso6336_22.eq8_28": "αθM（ZS.Oil.alfa）与各点 αθB（chain，SGF,Y）K01/K02 逐位一致",
    "iso6336_22.eq5": "GM 在 hY 求值链上（chain）",
    "iso6336_22.eq17_19": "ν(θ) 在 ηoil（-21 FIT.etaOil，K01–K05）与 ηθM 链上逐位一致",
    "iso6336_22.eq20_31": "ρ(θ)（数据表 ρ15）在 ηoil（K01–K05）与 ηθM 链上逐位一致",
    "iso6336_22.eq16_29": "η = 1e−6·ν·ρ：-21 FIT.etaOil K01–K05、-22 ηθM K01/K02 逐位一致",
    "iso6336_22.eq13_15": "vΣ,Y 与 ZPP[0].vrY+ZPP[1].vrY 七点（K01）/五点（K02）逐位一致",
    "iso6336_22.eq12": "UY（analysisPoints.UY）逐位一致",
    "iso6336_22.eq22": "WY（analysisPoints.WY）逐位一致（pdyn>0 点）",
    "iso6336_22.eq27": "SGF,Y（analysisPoints.SGFY）逐位一致",
    "iso6336_22.eq4": "hY（analysisPoints.hY）逐位一致",
    "iso6336_22.eq2_3": "λGF,Y（analysisPoints.lamGFY）逐位一致",
    "iso6336_22.eq1": "Sλ（ZP[0].MP_ISO.SlamB）K01（含本库 pdyn 路线）/K02 逐位一致",
    "iso6336_22.eqA1": "λGFP = 1,4·WW·λGFT（ZP[0].RefMP.lamGFP，WW 取 KISSsoft 打印 1,0）K01/K02 逐位一致",
    "iso6336_22.eq32_38": "gY（analysisPoints.gY）K01 七点、K02 五点逐位一致",
    "iso6336_22.eq39_43": "dY1、dY2、ρn,Y（ZPP[i].dY、ronY）逐位一致",
    "iso6336_22.eq44_46": "直齿未修形 XY（A=7）K01 七点与 analysisPoints.XY 逐位一致",
    "iso6336_22.eq25_26": "pH,Y,B（pHYB）K01 七点（本库 XY）、K02 五点（KISSsoft XY）逐位一致",
    "iso6336_22.eq24": "pdyn,Y,B（phidynYB）K01 七点、K02 五点逐位一致",
}
_grant(FORMULAS, globals(), EXTERNAL_EVIDENCE, level=EXTERNAL_LEVEL_KISSSOFT, basis=KISSSOFT_V014_BASIS)
