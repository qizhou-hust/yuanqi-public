"""ISO/TS 6336-21:2022 胶合承载能力——积分温度法（圆柱齿轮，外啮合）：θint = θM + C2·θfla,int，SintS = θintS/θint。

资料与核对口径（用户私有 PDF，本机逐式渲染原图核对；代码中只写条款号、式号、页码，不复制原文）：
  - 文件 "ISO TS 6336-21-2022.pdf"（44 页扫描，Second edition 2022-05），SHA256=SOURCE_SHA256；
    PDF 页 = 印刷页 + 6（PDF11 = 印5）。OCR 只用于检索，所列式子均为 pdftoppm -r 150 渲染后看图逐式核对。
  - 证据等级：附录 A 为资料性算例且输入不全（未给 ηoil、XM、精度等级），不作外部参照；v0.14 起以 KISSsoft 2026 P3
    K01–K05（原生油品/工况）同输入逐中间量对拍（tests/test_m39_kisssoft_v014.py，门限 1e-12），通过的公式见文末
    EXTERNAL_EVIDENCE（E5），其余仍为 null。

主流程（rate）：
  μmC 式(1)–(7)（XL 列表 5.1）→ XE 式(9) → XM 式(12)(13)（两轮同材料）→ Xαβ 式(14)（方法 A）
  → XBE 式(23)–(25) → XQ 式(26)–(32) → XCa 式(33)–(39) → θflaE 式(20) → Xε 式(40)–(46) → θfla,int 式(19)
  → θM 方法 C 式(21)(22)（或方法 A 显式输入；方法 B 按 6.1.6.3 不用于积分温度法 → 阻断）→ θint 式(18)（C2 = 1,5）
  → θintS 式(47)、FZG A/8,3/90 式(48)(49) + T1T（式(50) 近似 / 图7 标注值 LS3..12 / 显式）、FZG L-42 式(52)(53)、
    XWrelT 式(54) + 表4 → SintS 式(15)。XM 可由式(13) λM、cv 求 BM，或显式 BM（式(12) 直接代入）。
阻断（Unconfirmed / TODO）：两轮不同材料的 XM 式(10)（-21 未规定取哪一点 Γ）；内齿轮（XBE 负值约定未做）；
Ryder 试验的 θflaintT（图8 无近似式）；式(8) 替代摩擦系数；附录 B 接触时间修正；θM 方法 A 的热网络（只收显式值）。
几何/载荷量（a、αt、α′t、β、βb、da、db、εβ、Ft、v、KA、Kv、KHβ、KHα、c′/cγ）由调用方显式给出，
可由 gearmath.gear 现有几何/载荷模型输出（见 examples_k01_inputs）；ISO/TS 6336-21 表2：KBβ = KHβ、KBα = KHα。
"""
from __future__ import annotations

import math

from .tribology_common import (EXTERNAL_LEVEL_KISSSOFT, KISSSOFT_V014_BASIS, MissingInput, OutOfDomain, TribError,
                               Unconfirmed, choice, formula_registry, missing_keys, nonneg, num, pos)
from .tribology_common import grant_external_evidence as _grant

P = "ISO/TS 6336-21:2022"
SOURCE_FILE = "ISO TS 6336-21-2022.pdf"
SOURCE_SHA256 = "3a5b2761fab3f70b64fe7903e011d5f093c071bd3cacb23e656abfd2026f8888"
EVIDENCE_NULL_REASON = ("无外部算例对拍：附录 A 算例输入不全（无 ηoil、XM、精度等级）且为资料性；"
                        "测试为测试内独立重写与附录 A 表内自洽核对，不构成外部参照")
FORMULAS: dict = {}
_formula = formula_registry(FORMULAS, P, EVIDENCE_NULL_REASON)

C1 = 0.7    # 6.1.6.4 式(21) 下文（PDF18/印12 原图已核）
C2 = 1.5    # 6.1.4 式(18) 下文、6.2.2.2 式(47) 下文（PDF17/印11、PDF24/印18 原图已核）

# 5.1 式(1) 润滑油系数 XL（PDF13/印7 原图已核）
X_L_EQ1 = {"mineral": 1.0, "polyalfaolefin": 0.8, "polyglycol_non_water_soluble": 0.7,
           "polyglycol_water_soluble": 0.6, "traction_fluid": 1.5, "phosphate_ester": 1.3}
# 6.1.6.4 式(21) 润滑方式系数 XS（PDF18/印12 原图已核）
X_S = {"spray": 1.2, "dip": 1.0, "submerged": 0.2}
# 6.2.3 表4 焊合系数 XW（PDF28/印22 原图已核）
X_W_TABLE4 = {"through_hardened": 1.00, "phosphated": 1.25, "copper_plated": 1.50, "nitrided_bath_gas": 1.50,
              "case_carburized_austenite_lt10": 1.15, "case_carburized_austenite_10_20": 1.00,
              "case_carburized_austenite_gt20_30": 0.85, "austenitic_stainless": 0.45}
# 5.4 表3 方法 B 的 Xαβ-B（PDF15/印9 原图已核）：键 (α′t 度, β 度)；表外不插值（条文未规定插值）
X_ALPHABETA_B_TABLE3 = {
    (19, 0): 0.963, (19, 10): 0.960, (19, 20): 0.951, (19, 30): 0.938,
    (20, 0): 0.978, (20, 10): 0.975, (20, 20): 0.966, (20, 30): 0.952,
    (21, 0): 0.992, (21, 10): 0.989, (21, 20): 0.981, (21, 30): 0.966,
    (22, 0): 1.007, (22, 10): 1.004, (22, 20): 0.995, (22, 30): 0.981,
    (23, 0): 1.021, (23, 10): 1.018, (23, 20): 1.009, (23, 30): 0.995,
    (24, 0): 1.035, (24, 10): 1.032, (24, 20): 1.023, (24, 30): 1.008,
    (25, 0): 1.049, (25, 10): 1.046, (25, 20): 1.037, (25, 30): 1.012,
}


# =================================================================== 5.1 平均摩擦系数
@_formula("iso6336_21.eq2", f"{P} 5.1 式(2) vΣC = 2·v·tanα′t·cosαt（PDF12/印6 原图已核）")
def v_sum_C(*, v, alpha_wt, alpha_t):
    """节点切向速度和 vΣC（m/s）。v 为分度圆线速度（m/s）；角度为弧度。"""
    return 2.0 * pos("v", v) * math.tan(pos("alpha_wt", alpha_wt)) * math.cos(pos("alpha_t", alpha_t))


@_formula("iso6336_21.eq3", f"{P} 5.1 式(3) ρredC = u/(1+u)²·a·sinα′t/cosβb（PDF12/印6 原图已核）")
def rho_redC(*, u, a, alpha_wt, beta_b):
    u, a = pos("u", u), pos("a", a)
    return u / (1.0 + u) ** 2 * a * math.sin(pos("alpha_wt", alpha_wt)) / math.cos(nonneg("beta_b", beta_b))


@_formula("iso6336_21.eq4", f"{P} 5.1 式(4) wBt = KA·Kv·KBβ·KBα·Ft/b（PDF12/印6 原图已核）；表2 KBβ=KHβ、KBα=KHα（PDF8/印2）")
def w_Bt(*, K_A, K_v, K_Bbeta, K_Balpha, F_t, b):
    return (pos("K_A", K_A) * pos("K_v", K_v) * pos("K_Bbeta", K_Bbeta) * pos("K_Balpha", K_Balpha)
            * pos("F_t", F_t) / pos("b", b))


@_formula("iso6336_21.eq5", f"{P} 5.1 式(5) 及上下两段 KBγ（εγ≤2 取 1；2<εγ<3,5 式(5)；≥3,5 取 1,3；PDF12–13/印6–7 原图已核）")
def K_Bgamma(*, eps_gamma):
    e = pos("eps_gamma", eps_gamma)
    if e <= 2.0:
        return 1.0
    if e < 3.5:
        return 1.0 + 0.2 * math.sqrt((e - 2.0) * (5.0 - e))
    return 1.3


@_formula("iso6336_21.eq6_7", f"{P} 5.1 式(6)(7) XR = 2,2·(Ra/ρredC)^0,25，Ra = 0,5·(Ra1+Ra2)（PDF13/印7 原图已核）",
          note="Ra 为新加工齿面测量值（µm），ρredC 为 mm：式中 Ra/ρredC 按条文单位直接相除（条文未写换算）")
def X_R(*, Ra1, Ra2, rho_redC):
    Ra = 0.5 * (pos("Ra1", Ra1) + pos("Ra2", Ra2))
    return 2.2 * (Ra / pos("rho_redC", rho_redC)) ** 0.25


@_formula("iso6336_21.XL_eq1", f"{P} 5.1 式(1) 下 XL 列表（PDF13/印7 原图已核）")
def X_L(*, lubricant):
    return X_L_EQ1[choice("lubricant", lubricant, X_L_EQ1)]


@_formula("iso6336_21.eq1", f"{P} 5.1 式(1) μmC = 0,045·(wBt·KBγ/(vΣC·ρredC))^0,2·ηoil^−0,05·XR·XL；"
                            "适用 1≤v≤50 m/s（v>50 取 v=50 时的 vΣC），wBt<150 N/mm 时以 150 代入（PDF11–12/印5–6 原图已核）")
def mu_mC(*, w_Bt, K_Bgamma, v_sum_C, v, rho_redC, eta_oil, X_R, X_L):
    """ηoil：油温下动力黏度，mPa·s（表2 PDF9/印3）。v<1 m/s 条文只说"摩擦系数更高"，无式 → 越域阻断。"""
    v = pos("v", v)
    if v < 1.0:
        raise OutOfDomain("v", "ISO/TS 6336-21 5.1 式(1) 适用 v ≥ 1 m/s；v<1 时条文未给值")
    vs = pos("v_sum_C", v_sum_C)
    if v > 50.0:
        vs = vs * 50.0 / v          # vΣC ∝ v（式(2)），取 v = 50 m/s 时的 vΣC
    w = max(pos("w_Bt", w_Bt), 150.0)
    return (0.045 * (w * pos("K_Bgamma", K_Bgamma) / (vs * pos("rho_redC", rho_redC))) ** 0.2
            * pos("eta_oil", eta_oil) ** -0.05 * pos("X_R", X_R) * pos("X_L", X_L))


# =================================================================== 5.2 跑合系数
@_formula("iso6336_21.eq9", f"{P} 5.2 式(9) XE = 1 + (1−φE)·30·Ra/ρredC，φE=1 完全跑合、0 新加工（PDF14/印8 原图已核）")
def X_E(*, phi_E, Ra1, Ra2, rho_redC):
    phi = num("phi_E", phi_E)
    if not 0.0 <= phi <= 1.0:
        raise OutOfDomain("phi_E", "φE ∈ [0, 1]")
    Ra = 0.5 * (pos("Ra1", Ra1) + pos("Ra2", Ra2))
    return 1.0 + (1.0 - phi) * 30.0 * Ra / pos("rho_redC", rho_redC)


# =================================================================== 5.3 热闪系数
@_formula("iso6336_21.eq13", f"{P} 5.3 式(13) BM = √(λM·cv)（PDF15/印9 原图已核）")
def B_M(*, lambda_M, c_v):
    """λM N/(s·K)，cv N/(mm²·K) → BM N/(mm·s^½·K)（表2 PDF7/印1）。"""
    return math.sqrt(pos("lambda_M", lambda_M) * pos("c_v", c_v))


@_formula("iso6336_21.eq12", f"{P} 5.3 式(12) XM = E^0,25/((1−ν²)^0,25·BM)，两轮同材料（PDF15/印9 原图已核）",
          note="E N/mm²、BM N/(mm·s^½·K) 代入得 K·N^−0,75·s^0,5·mm^0,5，乘 √1000 换为条文单位 K·N^−0,75·s^0,5·m^−0,5·mm；"
               "条文典型值 λM=50、cv=3,8、E=206000、ν=0,3 → XM=50,0（同页原图已核，测试复核）")
def X_M_same_material(*, E, nu, lambda_M, c_v):
    nu = num("nu", nu)
    if not 0.0 <= nu < 0.5:
        raise OutOfDomain("nu", "泊松比须在 [0, 0.5)")
    return pos("E", E) ** 0.25 / ((1.0 - nu * nu) ** 0.25 * B_M(lambda_M=lambda_M, c_v=c_v)) * math.sqrt(1000.0)


@_formula("iso6336_21.eq12_BM", f"{P} 5.3 式(12) XM = E^0,25/((1−ν²)^0,25·BM)，两轮同材料、BM 显式给出（PDF15/印9 原图已核）",
          note="与 X_M_same_material 同一式(12)，只是不经式(13) 由 λM、cv 求 BM（外部工具/材料数据直接给 BM 时用）")
def X_M_from_B_M(*, E, nu, B_M):
    nu = num("nu", nu)
    if not 0.0 <= nu < 0.5:
        raise OutOfDomain("nu", "泊松比须在 [0, 0.5)")
    return pos("E", E) ** 0.25 / ((1.0 - nu * nu) ** 0.25 * pos("B_M", B_M)) * math.sqrt(1000.0)


def X_M_different_materials(**_):
    """式(10) 需线上点 Γ（式(11)），ISO/TS 6336-21 未规定积分温度法取哪一点 → 无法确认，阻断。"""
    raise Unconfirmed("X_M", "ISO/TS 6336-21 式(10)（PDF14）为任意点 Γ 的表达式，积分温度法未规定取值点；两轮不同材料暂不支持")


# =================================================================== 5.4 压力角系数
@_formula("iso6336_21.eq14", f"{P} 5.4 式(14) 方法 A Xαβ-A = 1,22·(sinα′t)^0,25·(cosαn)^0,25·(cosβ)^0,25/((cosα′t)^0,5·(cosαt)^0,5)（PDF15/印9 原图已核）")
def X_alphabeta_A(*, alpha_wt, alpha_n, beta, alpha_t):
    return (1.22 * math.sin(pos("alpha_wt", alpha_wt)) ** 0.25 * math.cos(pos("alpha_n", alpha_n)) ** 0.25
            * math.cos(nonneg("beta", beta)) ** 0.25
            / (math.cos(alpha_wt) ** 0.5 * math.cos(pos("alpha_t", alpha_t)) ** 0.5))


@_formula("iso6336_21.table3", f"{P} 5.4 表3 方法 B Xαβ-B（αn=20° 基本齿条；PDF15/印9 原图已核）；表外不插值")
def X_alphabeta_B(*, alpha_wt_deg, beta_deg):
    key = (num("alpha_wt_deg", alpha_wt_deg), num("beta_deg", beta_deg))
    for (a, b), val in X_ALPHABETA_B_TABLE3.items():
        if abs(a - key[0]) < 1e-9 and abs(b - key[1]) < 1e-9:
            return val
    raise Unconfirmed("X_alphabeta_B", "表3 只列 α′t=19..25°、β=0/10/20/30° 的格点，条文未规定插值")


# =================================================================== 6.1.11 几何系数
@_formula("iso6336_21.eq24_25", f"{P} 6.1.11 式(24)(25) ρE1 = 0,5·√(da1²−db1²)，ρE2 = a·sinα′t − ρE1（PDF18/印12 原图已核）")
def rho_E(*, d_a1, d_b1, a, alpha_wt):
    da, db = pos("d_a1", d_a1), pos("d_b1", d_b1)
    if da <= db:
        raise OutOfDomain("d_a1", "齿顶圆须大于基圆")
    r1 = 0.5 * math.sqrt(da * da - db * db)
    r2 = pos("a", a) * math.sin(pos("alpha_wt", alpha_wt)) - r1
    if r2 <= 0:
        raise OutOfDomain("rho_E2", f"ρE2 = {r2} ≤ 0（小轮齿顶超出啮合线极限点）")
    return {"rho_E1": r1, "rho_E2": r2}


@_formula("iso6336_21.eq23", f"{P} 6.1.11 式(23) XBE = 0,51·√(|z2|/z2·(u+1))·(√ρE1 − √(ρE2/u))/(ρE1·|ρE2|)^0,25（PDF18/印12 原图已核）",
          note="仅外啮合：内齿轮按 6.1.11 需以负值代入 z2、u、a 与各直径，本版未实现（阻断）")
def X_BE(*, z2, u, rho_E1, rho_E2):
    z2, u = num("z2", z2), pos("u", u)
    if z2 <= 0:
        raise Unconfirmed("z2", "内齿轮负值约定（6.1.11）本版未实现")
    r1, r2 = pos("rho_E1", rho_E1), pos("rho_E2", rho_E2)
    return 0.51 * math.sqrt(abs(z2) / z2 * (u + 1.0)) * (math.sqrt(r1) - math.sqrt(r2 / u)) / (r1 * abs(r2)) ** 0.25


# =================================================================== 6.1.12 啮入系数
@_formula("iso6336_21.eq31_32", f"{P} 6.1.12 式(31)(32) ε1 = z1/(2π)·[√((da1/db1)²−1) − tanα′t]，ε2 同（|z2|）（PDF19/印13 原图已核）",
          note="齿顶倒角/倒圆时以有效齿顶圆 dNa 代入（调用方给出）")
def addendum_contact_ratios(*, z1, z2, d_a1, d_b1, d_a2, d_b2, alpha_wt):
    t = math.tan(pos("alpha_wt", alpha_wt))
    out = {}
    for i, (z, da, db) in enumerate(((z1, d_a1, d_b1), (z2, d_a2, d_b2)), 1):
        z, da, db = abs(num(f"z{i}", z)), pos(f"d_a{i}", da), pos(f"d_b{i}", db)
        if da <= db:
            raise OutOfDomain(f"d_a{i}", "齿顶圆须大于基圆")
        out[f"eps_{i}"] = z / (2.0 * math.pi) * (math.sqrt((da / db) ** 2 - 1.0) - t)
        if out[f"eps_{i}"] <= 0:
            raise OutOfDomain(f"eps_{i}", f"齿顶重合度 {out[f'eps_{i}']} ≤ 0")
    out["eps_alpha"] = out["eps_1"] + out["eps_2"]       # 式(46)
    return out


@_formula("iso6336_21.eq26_30", f"{P} 6.1.12 式(26)–(30) XQ（εf/εa ≤1,5 取 1；1,5<·<3 取 1,40−4/15·εf/εa；≥3 取 0,60；"
                                "小轮主动 εf=ε2、εa=ε1，大轮主动 εf=ε1、εa=ε2；PDF19/印13 原图已核）")
def X_Q(*, eps_1, eps_2, driver):
    e1, e2 = pos("eps_1", eps_1), pos("eps_2", eps_2)
    ef, ea = (e2, e1) if choice("driver", driver, ("pinion", "wheel")) == "pinion" else (e1, e2)
    r = ef / ea
    if r <= 1.5:
        return 1.0
    if r < 3.0:
        return 1.40 - 4.0 / 15.0 * r
    return 0.60


# =================================================================== 6.1.13 齿顶修缘系数
@_formula("iso6336_21.eq38_39", f"{P} 6.1.13 式(38)(39) Ceff = KA·Ft/(b·c′)（直齿）、KA·Ft/(b·cγ)（斜齿）（PDF21/印15 原图已核）")
def C_eff(*, K_A, F_t, b, stiffness):
    """stiffness：直齿给 c′、斜齿给 cγ，单位 N/(mm·µm)；返回 µm。b 取两轮较小齿宽（同页）。"""
    return pos("K_A", K_A) * pos("F_t", F_t) / (pos("b", b) * pos("stiffness", stiffness))


@_formula("iso6336_21.eq34_37", f"{P} 6.1.13 式(34)–(37) 名义修缘量 Ca 的选取（PDF20–21/印14–15 原图已核）")
def C_a_nominal(*, C_a1, C_a2, C_eff, eps_1, eps_2, driver):
    Ca1, Ca2, Ce = nonneg("C_a1", C_a1), nonneg("C_a2", C_a2), pos("C_eff", C_eff)
    e1, e2 = pos("eps_1", eps_1), pos("eps_2", eps_2)
    drv = choice("driver", driver, ("pinion", "wheel"))
    use_pinion = (e1 > 1.5 * e2) if drv == "pinion" else (e1 > (2.0 / 3.0) * e2)
    Ca = Ca1 if use_pinion else Ca2
    return min(Ca, Ce)


@_formula("iso6336_21.eq33", f"{P} 6.1.13 式(33) XCa = 1 + [0,06+0,18·(Ca/Ceff)]·εmax + [0,02+0,69·(Ca/Ceff)]·εmax²；"
                             "ISO 1328-1 精度等级劣于 6 级时 XCa = 1（PDF20–21/印14–15 原图已核）")
def X_Ca(*, C_a, C_eff, eps_1, eps_2, tolerance_class):
    q = int(num("tolerance_class", tolerance_class))
    if q > 6:
        return 1.0
    r = nonneg("C_a", C_a) / pos("C_eff", C_eff)
    em = max(pos("eps_1", eps_1), pos("eps_2", eps_2))
    return 1.0 + (0.06 + 0.18 * r) * em + (0.02 + 0.69 * r) * em * em


# =================================================================== 6.1.14 重合度系数
@_formula("iso6336_21.eq40_46", f"{P} 6.1.14 式(40)–(46) Xε 分段（PDF21/印15 原图已核）")
def X_eps(*, eps_1, eps_2):
    e1, e2 = pos("eps_1", eps_1), pos("eps_2", eps_2)
    ea = e1 + e2
    k = 1.0 / (2.0 * ea * e1)
    if ea < 1.0:
        return k * (e1 ** 2 + e2 ** 2)                                                      # (40)
    if ea < 2.0:
        if e1 < 1.0 and e2 < 1.0:
            return k * (0.70 * (e1 ** 2 + e2 ** 2) - 0.22 * ea + 0.52 - 0.60 * e1 * e2)     # (41)
        if e1 >= 1.0 and e2 < 1.0:
            return k * (0.18 * e1 ** 2 + 0.70 * e2 ** 2 + 0.82 * e1 - 0.52 * e2 - 0.30 * e1 * e2)   # (42)
        if e1 < 1.0 and e2 >= 1.0:
            return k * (0.70 * e1 ** 2 + 0.18 * e2 ** 2 - 0.52 * e1 + 0.82 * e2 - 0.30 * e1 * e2)   # (43)
    if 2.0 <= ea < 3.0:
        if e1 >= e2:
            return k * (0.44 * e1 ** 2 + 0.59 * e2 ** 2 + 0.30 * e1 - 0.30 * e2 - 0.15 * e1 * e2)   # (44)
        return k * (0.59 * e1 ** 2 + 0.44 * e2 ** 2 - 0.30 * e1 + 0.30 * e2 - 0.15 * e1 * e2)       # (45)
    raise OutOfDomain("eps_alpha", f"εα = {ea}：式(40)–(45) 只覆盖 εα < 3")


# =================================================================== 6.1.4/6.1.5 温度
@_formula("iso6336_21.eq20", f"{P} 6.1.5 式(20) θflaE = μmC·XM·XBE·Xαβ·(KBγ·wBt)^0,75·v^0,5/|a|^0,25·XE/(XQ·XCa)（PDF17/印11 原图已核）",
          note="v 为分度圆线速度 m/s（式中印为 v，不是 vΣC）；wBt 用实际值（150 N/mm 下限只用于式(1)）")
def theta_flaE(*, mu_mC, X_M, X_BE, X_alphabeta, K_Bgamma, w_Bt, v, a, X_E, X_Q, X_Ca):
    return (pos("mu_mC", mu_mC) * pos("X_M", X_M) * pos("X_BE", X_BE) * pos("X_alphabeta", X_alphabeta)
            * (pos("K_Bgamma", K_Bgamma) * pos("w_Bt", w_Bt)) ** 0.75 * pos("v", v) ** 0.5
            / abs(num("a", a)) ** 0.25 * pos("X_E", X_E) / (pos("X_Q", X_Q) * pos("X_Ca", X_Ca)))


@_formula("iso6336_21.eq19", f"{P} 6.1.4 式(19) θfla,int = θflaE·Xε（PDF17/印11 原图已核）")
def theta_flaint(*, theta_flaE, X_eps):
    return nonneg("theta_flaE", theta_flaE) * pos("X_eps", X_eps)


@_formula("iso6336_21.eq22", f"{P} 6.1.6.4 式(22) Xmp = (1+np)/2（PDF18/印12 原图已核）")
def X_mp(*, n_p):
    n = num("n_p", n_p)
    if n < 1 or n != int(n):
        raise OutOfDomain("n_p", "啮合齿轮数 np 须为 ≥1 的整数")
    return (1.0 + n) / 2.0


@_formula("iso6336_21.eq21", f"{P} 6.1.6.4 式(21) θM-C = θoil + C1·Xmp·θfla,int·XS，C1 = 0,7，XS 喷油 1,2/浸油 1,0/全浸 0,2（PDF17–18/印11–12 原图已核）")
def theta_M_C(*, theta_oil, X_mp, theta_flaint, lubrication):
    return (num("theta_oil", theta_oil) + C1 * pos("X_mp", X_mp) * nonneg("theta_flaint", theta_flaint)
            * X_S[choice("lubrication", lubrication, X_S)])


@_formula("iso6336_21.eq18", f"{P} 6.1.4 式(18) θint = θM + C2·θfla,int，C2 = 1,5（PDF17/印11 原图已核）")
def theta_int(*, theta_M, theta_flaint):
    return num("theta_M", theta_M) + C2 * nonneg("theta_flaint", theta_flaint)


@_formula("iso6336_21.eq15", f"{P} 6.1.2 式(15) SintS = θintS/θint（PDF16/印10 原图已核）")
def S_intS(*, theta_intS, theta_int):
    return pos("theta_intS", theta_intS) / pos("theta_int", theta_int)


@_formula("iso6336_21.eq16", f"{P} 6.1.2 式(16) SSl ≈ (θintS − θoil)/(θint − θoil)（PDF16/印10 原图已核）")
def S_Sl(*, theta_intS, theta_int, theta_oil):
    den = num("theta_int", theta_int) - num("theta_oil", theta_oil)
    if den <= 0:
        raise OutOfDomain("theta_int", "θint 须高于 θoil")
    return (num("theta_intS", theta_intS) - theta_oil) / den


@_formula("iso6336_21.eq17", f"{P} 6.1.3 式(17) θintP = θintS/SSmin（PDF16/印10 原图已核）")
def theta_intP(*, theta_intS, S_Smin):
    return pos("theta_intS", theta_intS) / pos("S_Smin", S_Smin)


# =================================================================== 6.2 胶合积分温度
@_formula("iso6336_21.eq50", f"{P} 6.2.2.3 式(50) T1T = 3,726·(FZG 载荷级)²（PDF24/印18 原图已核）",
          note="近似式：图7 横轴标注 LS11/12 为 450,1/534,5 N·m，式(50) 得 450,8/536,5 N·m；直接给 T1T 时不经式(50)")
def T1T_from_load_stage(*, load_stage):
    s = num("load_stage", load_stage)
    if s < 1 or s > 14 or s != int(s):
        raise OutOfDomain("load_stage", "FZG 载荷级应为 1..14 的整数")
    return 3.726 * s * s


# 6.2.2.3 图7 横轴：FZG A/8,3/90 载荷级 → 小轮试验扭矩 T1T（N·m）。PDF25/印19 原图已核（300 dpi 渲染逐个读刻度）：
# 载荷级 1、2 的刻度线无数值标注，载荷级 13、14 不在图内 → 不收（阻断，不外推）。
T1T_FIGURE7 = {3: 35.3, 4: 60.8, 5: 94.1, 6: 135.3, 7: 183.4, 8: 239.3, 9: 302.0, 10: 372.6, 11: 450.1, 12: 534.5}


@_formula("iso6336_21.fig7", f"{P} 6.2.2.3 图7 横轴 FZG A/8,3/90 载荷级 3..12 的 T1T 标注值（PDF25/印19 原图已核）",
          note="式(50) 为图7 的近似式（LS12：536,5 vs 图值 534,5）；KISSsoft 2026 对 LS12 用图值 534,5（K02–K05 θintS 逐位一致）")
def T1T_from_figure7(*, load_stage):
    s = num("load_stage", load_stage)
    if s != int(s):
        raise OutOfDomain("load_stage", "FZG 载荷级应为整数")
    if int(s) not in T1T_FIGURE7:
        raise Unconfirmed("load_stage", f"图7（PDF25）只标注了载荷级 3..12 的扭矩；载荷级 {int(s)} 无原图数值")
    return T1T_FIGURE7[int(s)]


@_formula("iso6336_21.eq48_49", f"{P} 6.2.2.3 a) 式(48)(49) FZG A/8,3/90：θMT = 80 + 0,23·T1T·XL，"
                                "θflaintT = 0,2·T1T·(100/ν40)^0,02·XL（PDF24/印18 原图已核）")
def fzg_A8390(*, T1T, nu_40, X_L):
    T, xl = pos("T1T", T1T), pos("X_L", X_L)
    return {"theta_MT": 80.0 + 0.23 * T * xl, "theta_flaintT": 0.2 * T * (100.0 / pos("nu_40", nu_40)) ** 0.02 * xl}


@_formula("iso6336_21.eq52_53", f"{P} 6.2.2.3 c) 式(52)(53) FZG L-42 141/19,5/110：θMT = 110 + 0,02·T1T·XL，"
                                "θflaintT = 0,48·T1T·(100/ν40)^0,02·XL（PDF25/印19 原图已核）")
def fzg_L42(*, T1T, nu_40, X_L):
    T, xl = pos("T1T", T1T), pos("X_L", X_L)
    return {"theta_MT": 110.0 + 0.02 * T * xl, "theta_flaintT": 0.48 * T * (100.0 / pos("nu_40", nu_40)) ** 0.02 * xl}


@_formula("iso6336_21.eq51", f"{P} 6.2.2.3 b) 式(51) Ryder/FZG-Ryder R/46,5/74：θMT = 90 + 0,0125·(Fbt/b)T·XL，Fbt/b 以 lb/in 计（PDF24/印18 原图已核）",
          note="同条款未给 Ryder 的 θflaintT 近似式（图8 只有曲线）→ θintS 无法由本模块闭合")
def ryder_theta_MT(*, Fbt_b_lb_in, X_L):
    return 90.0 + 0.0125 * pos("Fbt_b_lb_in", Fbt_b_lb_in) * pos("X_L", X_L)


@_formula("iso6336_21.eq54", f"{P} 6.2.3 式(54) XWrelT = XW/XWT，FZG/Ryder/FZG L-42 试验 XWT = 1，XW 见表4（PDF28/印22 原图已核）")
def X_WrelT(*, material, X_WT):
    return X_W_TABLE4[choice("material", material, X_W_TABLE4)] / pos("X_WT", X_WT)


@_formula("iso6336_21.eq47", f"{P} 6.2.2.2 式(47) θintS = θMT + XWrelT·C2·θflaintT，C2 = 1,5（PDF24/印18 原图已核）")
def theta_intS(*, theta_MT, X_WrelT, theta_flaintT):
    return num("theta_MT", theta_MT) + pos("X_WrelT", X_WrelT) * C2 * nonneg("theta_flaintT", theta_flaintT)


# =================================================================== 主流程
GEOMETRY_KEYS = ("z1", "z2", "a", "alpha_n", "alpha_t", "alpha_wt", "beta", "beta_b", "d_a1", "d_a2", "d_b1", "d_b2",
                 "eps_beta", "b")
LOAD_KEYS = ("F_t", "v", "K_A", "K_v", "K_Hbeta", "K_Halpha", "driver")
TIP_KEYS = ("C_a1", "C_a2", "mesh_stiffness", "tolerance_class")
MATERIAL_KEYS = ("same_material", "E", "nu", "lambda_M", "c_v", "material_XW")
LUB_KEYS = ("lubricant", "eta_oil", "Ra1", "Ra2", "phi_E", "theta_oil", "lubrication", "n_p")
SELECTORS = {"X_alphabeta_method": ("A", "B_table"), "theta_M_method": ("C", "A_explicit", "B"),
             "scuffing_test": ("FZG_A8390", "FZG_L42", "explicit_theta_intS")}


def required_inputs(sel):
    """按方法选择返回所需输入键（不含默认值）。显式给出 "B_M"（热接触系数）时不再需要 λM、cv（式(13) 不用）。"""
    req = list(GEOMETRY_KEYS + LOAD_KEYS + TIP_KEYS + MATERIAL_KEYS + LUB_KEYS) + list(SELECTORS)
    if sel.get("B_M") is not None:
        req = [k for k in req if k not in ("lambda_M", "c_v")]
    if sel.get("theta_M_method") == "A_explicit":
        req += ["theta_M_A"]
    test = sel.get("scuffing_test")
    if test in ("FZG_A8390", "FZG_L42"):
        req += ["nu_40", "T1T_or_load_stage", "X_WT"]
    elif test == "explicit_theta_intS":
        req += ["theta_intS_explicit"]
    return req


def rate(inputs):
    """ISO/TS 6336-21 积分温度法主流程。inputs：dict（单位见各函数）。

    返回 {"status": "ok", 各中间量…, "S_intS": …} 或 {"status": "blocked", "missing": [...], "unconfirmed": [...]}。
    "T1T_or_load_stage"：{"T1T": N·m} 或 {"load_stage": int}（式(50) 近似）或 {"load_stage_fig7": int}（图7 标注值，3..12）。
    "B_M"（可选）：显式热接触系数 N/(mm·s^½·K)，给出时 XM 用式(12) 直接代入、不经式(13)。
    theta_M_method="B"：6.1.6.3 规定方法 B 不用于积分温度法 → 阻断。"""
    inp = dict(inputs)
    missing = missing_keys(inp, required_inputs(inp))
    if missing:
        return {"status": "blocked", "missing": missing, "unconfirmed": []}
    for k, opts in SELECTORS.items():
        choice(k, inp[k], opts)
    if inp["theta_M_method"] == "B":
        return {"status": "blocked", "missing": [], "unconfirmed": [
            "θM 方法 B：ISO/TS 6336-21 6.1.6.3（PDF17/印11 原图已核）规定方法 B 不用于积分温度法（闪温法见 -20）"]}
    if inp["same_material"] is not True:
        try:
            X_M_different_materials()
        except Unconfirmed as e:
            return {"status": "blocked", "missing": [], "unconfirmed": [str(e)]}
    r = {}
    try:
        r["K_Bbeta"], r["K_Balpha"] = inp["K_Hbeta"], inp["K_Halpha"]         # 表2 定义
        r["u"] = pos("z2", inp["z2"]) / pos("z1", inp["z1"])
        r["v_sum_C"] = v_sum_C(v=inp["v"], alpha_wt=inp["alpha_wt"], alpha_t=inp["alpha_t"])
        r["rho_redC"] = rho_redC(u=r["u"], a=inp["a"], alpha_wt=inp["alpha_wt"], beta_b=inp["beta_b"])
        r["w_Bt"] = w_Bt(K_A=inp["K_A"], K_v=inp["K_v"], K_Bbeta=r["K_Bbeta"], K_Balpha=r["K_Balpha"],
                         F_t=inp["F_t"], b=inp["b"])
        r.update(addendum_contact_ratios(z1=inp["z1"], z2=inp["z2"], d_a1=inp["d_a1"], d_b1=inp["d_b1"],
                                         d_a2=inp["d_a2"], d_b2=inp["d_b2"], alpha_wt=inp["alpha_wt"]))
        if r["eps_alpha"] > 2.5:
            raise OutOfDomain("eps_alpha", "6.1.1：εα ≤ 2,5")
        r["eps_gamma"] = r["eps_alpha"] + nonneg("eps_beta", inp["eps_beta"])
        r["K_Bgamma"] = K_Bgamma(eps_gamma=r["eps_gamma"])
        r["X_R"] = X_R(Ra1=inp["Ra1"], Ra2=inp["Ra2"], rho_redC=r["rho_redC"])
        r["X_L"] = X_L(lubricant=inp["lubricant"])
        r["mu_mC"] = mu_mC(w_Bt=r["w_Bt"], K_Bgamma=r["K_Bgamma"], v_sum_C=r["v_sum_C"], v=inp["v"],
                           rho_redC=r["rho_redC"], eta_oil=inp["eta_oil"], X_R=r["X_R"], X_L=r["X_L"])
        r["X_E"] = X_E(phi_E=inp["phi_E"], Ra1=inp["Ra1"], Ra2=inp["Ra2"], rho_redC=r["rho_redC"])
        if inp.get("B_M") is not None:
            r["X_M"] = X_M_from_B_M(E=inp["E"], nu=inp["nu"], B_M=inp["B_M"])
        else:
            r["X_M"] = X_M_same_material(E=inp["E"], nu=inp["nu"], lambda_M=inp["lambda_M"], c_v=inp["c_v"])
        if inp["X_alphabeta_method"] == "A":
            r["X_alphabeta"] = X_alphabeta_A(alpha_wt=inp["alpha_wt"], alpha_n=inp["alpha_n"], beta=inp["beta"],
                                             alpha_t=inp["alpha_t"])
        else:
            r["X_alphabeta"] = X_alphabeta_B(alpha_wt_deg=math.degrees(inp["alpha_wt"]), beta_deg=math.degrees(inp["beta"]))
        r.update(rho_E(d_a1=inp["d_a1"], d_b1=inp["d_b1"], a=inp["a"], alpha_wt=inp["alpha_wt"]))
        r["X_BE"] = X_BE(z2=inp["z2"], u=r["u"], rho_E1=r["rho_E1"], rho_E2=r["rho_E2"])
        r["X_Q"] = X_Q(eps_1=r["eps_1"], eps_2=r["eps_2"], driver=inp["driver"])
        r["C_eff"] = C_eff(K_A=inp["K_A"], F_t=inp["F_t"], b=inp["b"], stiffness=inp["mesh_stiffness"])
        r["C_a"] = C_a_nominal(C_a1=inp["C_a1"], C_a2=inp["C_a2"], C_eff=r["C_eff"], eps_1=r["eps_1"],
                               eps_2=r["eps_2"], driver=inp["driver"])
        r["X_Ca"] = X_Ca(C_a=r["C_a"], C_eff=r["C_eff"], eps_1=r["eps_1"], eps_2=r["eps_2"],
                         tolerance_class=inp["tolerance_class"])
        r["theta_flaE"] = theta_flaE(mu_mC=r["mu_mC"], X_M=r["X_M"], X_BE=r["X_BE"], X_alphabeta=r["X_alphabeta"],
                                     K_Bgamma=r["K_Bgamma"], w_Bt=r["w_Bt"], v=inp["v"], a=inp["a"], X_E=r["X_E"],
                                     X_Q=r["X_Q"], X_Ca=r["X_Ca"])
        r["X_eps"] = X_eps(eps_1=r["eps_1"], eps_2=r["eps_2"])
        r["theta_flaint"] = theta_flaint(theta_flaE=r["theta_flaE"], X_eps=r["X_eps"])
        if inp["theta_M_method"] == "C":
            r["X_mp"] = X_mp(n_p=inp["n_p"])
            r["theta_M"] = theta_M_C(theta_oil=inp["theta_oil"], X_mp=r["X_mp"], theta_flaint=r["theta_flaint"],
                                     lubrication=inp["lubrication"])
        else:
            r["theta_M"] = num("theta_M_A", inp["theta_M_A"])
        r["theta_int"] = theta_int(theta_M=r["theta_M"], theta_flaint=r["theta_flaint"])
        test = inp["scuffing_test"]
        if test == "explicit_theta_intS":
            r["theta_intS"] = pos("theta_intS_explicit", inp["theta_intS_explicit"])
        else:
            tl = inp["T1T_or_load_stage"]
            if not isinstance(tl, dict) or len(tl) != 1 or not set(tl) <= {"T1T", "load_stage", "load_stage_fig7"}:
                raise TribError("T1T_or_load_stage", "bad_input",
                                "应为 {'T1T': N·m}、{'load_stage': int} 或 {'load_stage_fig7': int}")
            if "T1T" in tl:
                r["T1T"] = pos("T1T", tl["T1T"])
            elif "load_stage" in tl:
                r["T1T"] = T1T_from_load_stage(load_stage=tl["load_stage"])
            else:
                if test != "FZG_A8390":
                    raise Unconfirmed("load_stage_fig7", "图7 只适用于 FZG A/8,3/90")
                r["T1T"] = T1T_from_figure7(load_stage=tl["load_stage_fig7"])
            fz = (fzg_A8390 if test == "FZG_A8390" else fzg_L42)(T1T=r["T1T"], nu_40=inp["nu_40"], X_L=r["X_L"])
            r.update(fz)
            r["X_WrelT"] = X_WrelT(material=inp["material_XW"], X_WT=inp["X_WT"])
            r["theta_intS"] = theta_intS(theta_MT=r["theta_MT"], X_WrelT=r["X_WrelT"], theta_flaintT=r["theta_flaintT"])
        r["S_intS"] = S_intS(theta_intS=r["theta_intS"], theta_int=r["theta_int"])
    except Unconfirmed as e:
        return {"status": "blocked", "missing": [], "unconfirmed": [str(e)], "partial": r}
    except MissingInput as e:
        return {"status": "blocked", "missing": [e.name], "unconfirmed": [], "partial": r}
    r["status"] = "ok"
    return r


# =================================================================== 外部证据（KISSsoft 2026 P3 K01–K05，tests/test_m39_kisssoft_v014.py 设门 1e-12）
# 输入：data/kisssoft_v014/P3-*.json 中 KISSsoft 实际输入（COM 全精度），ηoil 由本库 -22 式计算；逐中间量相对差 ≤ 1,9e-14。
# 未列入者保持 null：式(50)（KISSsoft 用图7 标注值，已知差异）、式(12)/(13) 的 λM·cv 路线（KISSsoft 只给 BM）、
# 式(9)（只有 φE=1 平凡分支且 φE 由跑合标志映射）、式(54)/表4（XW 行按 KISSsoft XWrelT 对齐，循环）、表3、式(17)(51)(52)(53)。
EXTERNAL_EVIDENCE = {
    "iso6336_21.eq1": "μmC（ZP[0].FIT.mym）K01–K05 逐位一致（wBt 均 ≥150 N/mm，v 1,9–23 m/s）",
    "iso6336_21.eq2": "vΣC 在 μmC 求值链上（chain），K01–K05",
    "iso6336_21.eq3": "ρredC 在 μmC/XE 求值链上（chain），K01–K05",
    "iso6336_21.eq4": "wBt = Scoring_wBT/Kbg K01–K05 逐位一致",
    "iso6336_21.eq5": "KBγ（ZP[0].Kbg）三段全覆盖：K01/K03 εγ≤2、K02/K05 2<εγ<3,5、K04 εγ≥3,5",
    "iso6336_21.eq6_7": "XR 在 μmC 求值链上（chain；Ra 0,6–3,0 µm）",
    "iso6336_21.XL_eq1": "矿物油 XL=1（报告 Mineral-oil base，FIT 节 XL=1,000）在 μmC 链上",
    "iso6336_21.eq12_BM": "XM（ZP[0].FIT.XM）以 KISSsoft BM=ZR[0].BM 代入，K01–K05 逐位一致",
    "iso6336_21.eq14": "Xαβ（FIT.Xalfbet）方法 A，K01–K05（β 0–29°）逐位一致",
    "iso6336_21.eq23": "XBE（FIT.XBE）K01–K05 逐位一致（仅外啮合）",
    "iso6336_21.eq24_25": "ρE1/ρE2 在 XBE 链上（chain）",
    "iso6336_21.eq26_30": "XQ（FIT.XQ）K01–K05 = 1；仅覆盖 εf/εa ≤ 1,5 分支",
    "iso6336_21.eq31_32": "ε1、ε2（ZPP[i].eps.nul）K01–K05 逐位一致",
    "iso6336_21.eq33": "XCa（FIT.XCa）K01–K05 逐位一致（K02/K04/K05 以 KISSsoft 选项 Ca=Ceff 为输入）；v0.15 回传关闭"
                       "'Ca 按最优取'后 K02（Ca/Ceff=0,803）、K05（Ca=0）按标准式以报告实际 Ca 逐位一致",
    "iso6336_21.eq34_37": "Ca 选取：K03 小轮主动 ε1>1,5ε2 取 Ca1=2,0（Ca2=3,2 可区分）、K01 两轮 2,0，XCa 逐位一致；"
                          "v0.15 K02 斜齿 ε1≤1,5ε2 式(36) Ca2=5,0≤Ceff、K05 Ca=0 逐位一致。截顶支式(35)(37) 只在 K04 出现，"
                          "KISSsoft 输入为含配对齿根修形的 Ceq（-20 附录 B 式(B.2)(B.3) 概念）而非 -21 条文的实际 Ca，未作依据（OPEN）",
    "iso6336_21.eq38_39": "Ceff（ZP[0].Ceff）直齿 c′（K01/K03）与斜齿 cγ（K02/K04/K05）逐位一致",
    "iso6336_21.eq40_46": "Xε（FIT.XE）式(41)（K01/K02/K03/K05）与式(44)（K04 εα=2,03）逐位一致",
    "iso6336_21.eq20": "θflaE 未独立导出；θfla,int = θflaE·Xε（FIT.theflaint）K01–K05 逐位一致（chain）",
    "iso6336_21.eq19": "θfla,int（FIT.theflaint）K01–K05 逐位一致",
    "iso6336_21.eq22": "Xmp（Scoring_Xmp）= 1，仅 np=1",
    "iso6336_21.eq21": "θM-C（FIT.theMC）K01–K05 逐位一致（浸油 XS=1）",
    "iso6336_21.eq18": "θint（FIT.theint）K01–K05 逐位一致",
    "iso6336_21.eq15": "SintS（FIT.SSint）K02–K05（图7 T1T）逐位一致",
    "iso6336_21.eq16": "SSl（FIT.SSL）K02–K05 逐位一致",
    "iso6336_21.fig7": "LS12 → 534,5 N·m：K02–K05 θintS 逐位一致（式(50) 的 536,5 不一致）",
    "iso6336_21.eq48_49": "θMT、θflaintT 未独立导出；θintS（FIT.theSint）K02–K05 一致，ν40=150/220/46 与 XWrelT=1/1,5 "
                          "的组合把两式分开约束（chain）",
    "iso6336_21.eq47": "θintS（FIT.theSint）K02–K05 逐位一致",
}
_grant(FORMULAS, globals(), EXTERNAL_EVIDENCE, level=EXTERNAL_LEVEL_KISSSOFT, basis=KISSSOFT_V014_BASIS)
