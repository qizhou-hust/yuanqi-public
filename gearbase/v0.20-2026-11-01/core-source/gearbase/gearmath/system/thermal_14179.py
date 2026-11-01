"""ISO/TR 14179-1:2001 齿轮箱热容量（热平衡骨架）：PV = PL + PN，PQ = Ac·k·ΔT，热平衡 PQ − PN − f(PA) = 0。

资料与核对口径（用户私有 PDF，本机逐式渲染原图核对；代码只写条款号、式号、页码）：
  - 文件 "ISO-TR 14179-1-2001.pdf"（34 页扫描），SHA256=SOURCE_SHA256；PDF 页 = 印刷页 + 4（PDF15 = 印11）。
    另有来源合编本 "ISO-TR-14179-1_WITH_SOURCED_PAGE_ii.pdf" 只补版权页 ii，不用于正文公式。
  - ISO/TR 14179-1 为技术报告（资料性）；证据等级一律 null（无外部算例）。
  - ISO/TR 14179-2 工程阅读本：按 standards/KNOWN_ISSUES.md（公式错乱、式 1–24 未完整重建、部分系数未确认）
    以及 09-repair-evidence/工程修复说明.md，本模块不收录其任何公式；part2() 直接阻断。

收录（均为 14179-1 方法 B）：式(1)(2)(5)(6)(7)(8)、轴承式(9)(10)(11)(13)(14)、啮合式(15)–(21)、
  油封式(22)+图2 两条直线、风阻搅油式(23)–(26)（Ag = 0,200）、轴承搅油式(27)–(29)(31)、散热式(35)。
TODO：表2/3/4 轴承系数（SKF 来源，调用方显式给 f1、P1、a、b）、式(12)(30) 与表5/6 的查表、油泵式(32)–(34)、
  第 8 章修正系数式(36) 与表8–12、热平衡迭代 solve（本版给残差函数 heat_balance_residual，由调用方迭代）。
单位：功率 kW；扭矩 N·m；转速 r/min；长度 mm；ν mm²/s（cSt）；k kW/(m²·°C)；Ac m²。
本模块只从 gearmath.gear 引入 tribology_common（通用输入校验/登记，无齿轮公式），不放在 gearmath/kernel/。
"""
from __future__ import annotations

import math

from gearmath.gear.tribology_common import (MissingInput, OutOfDomain, Unconfirmed, choice, formula_registry,
                                           nonneg, num, pos)

P = "ISO/TR 14179-1:2001"
SOURCE_FILE = "ISO-TR 14179-1-2001.pdf"
SOURCE_SHA256 = "19085bec7d8e91c52dc558062ab3c070011b2c7dc1b2ccdc32dd186c542156ee"
EVIDENCE_NULL_REASON = "技术报告（资料性），无外部算例；测试为测试内独立重写"
FORMULAS: dict = {}
_formula = formula_registry(FORMULAS, P, EVIDENCE_NULL_REASON)

A_G = 0.200              # 7.9 Ag 取 0,200（PDF19/印15 原图已核）
MESH_FRICTION = {"j": -0.223, "g": -0.40, "h": 0.70, "C1": 3.239}   # 7.4 式(20) 下（PDF18/印14 原图已核）
SEAL_TORQUE_COEF = {"viton": 3.737e-3, "buna_n": 2.429e-3}          # 图2 键 1/2（PDF19/印15 原图已核）


@_formula("iso14179_1.eq2", f"{P} 7.1 式(2) PV = PL + PN（PDF10/印6 原图已核）")
def P_V(*, P_L, P_N):
    return nonneg("P_L", P_L) + nonneg("P_N", P_N)


@_formula("iso14179_1.eq7", f"{P} 7.2 式(7) PL = ΣPB + ΣPM（PDF11/印7 原图已核）")
def P_L(*, bearing_losses, mesh_losses):
    return sum(nonneg("P_B", x) for x in bearing_losses) + sum(nonneg("P_M", x) for x in mesh_losses)


@_formula("iso14179_1.eq8", f"{P} 7.2 式(8) PN = ΣPS + ΣPW + ΣPWB + ΣPP（PDF11/印7 原图已核）")
def P_N(*, seal_losses, windage_losses, bearing_churning_losses, pump_losses):
    return sum(nonneg("loss", x) for grp in (seal_losses, windage_losses, bearing_churning_losses, pump_losses)
               for x in grp)


@_formula("iso14179_1.eq5", f"{P} 7.1 式(5) η = 100 − (PL+PN)/PA·100（%；PDF11/印7 原图已核）")
def efficiency(*, P_L, P_N, P_A):
    return 100.0 - (nonneg("P_L", P_L) + nonneg("P_N", P_N)) / pos("P_A", P_A) * 100.0


@_formula("iso14179_1.eq6", f"{P} 7.1 式(6) PT = PQ/(1 − η/100)（PDF11/印7 原图已核）")
def thermal_rating(*, P_Q, eta_percent):
    e = num("eta_percent", eta_percent)
    if not 0.0 <= e < 100.0:
        raise OutOfDomain("eta_percent", "效率须在 [0, 100)")
    return pos("P_Q", P_Q) / (1.0 - e / 100.0)


@_formula("iso14179_1.eq35", f"{P} 7.12 式(35) PQ = Ac·k·ΔT（PDF24/印20 原图已核）",
          note="k 典型 0,017–0,020 kW/(m²·°C)（大型室内）；风扇冷却见表7 —— 均由调用方显式给出")
def P_Q(*, A_c, k, delta_T):
    return pos("A_c", A_c) * pos("k", k) * num("delta_T", delta_T)


@_formula("iso14179_1.eq1_4", f"{P} 7.1 式(1)(4) 热平衡 PQ = PV，残差 PQ − PN − f(PA)（PDF10–11/印6–7 原图已核）",
          note="迭代求 PT 由调用方完成（变 PA 使残差为 0）；PQ ≤ PN（空载）时无热容量")
def heat_balance_residual(*, P_Q, P_N, P_L):
    return num("P_Q", P_Q) - nonneg("P_N", P_N) - nonneg("P_L", P_L)


# ------------------------------------------------------------------ 轴承
@_formula("iso14179_1.eq10", f"{P} 7.3.1 式(10) dm = (di + do)/2（PDF12/印8 原图已核）")
def bearing_mean_diameter(*, d_i, d_o):
    return 0.5 * (pos("d_i", d_i) + pos("d_o", d_o))


@_formula("iso14179_1.eq9", f"{P} 7.3.1 式(9) M1 = f1·P1^a·dm^b/1000（N·m；PDF12/印8 原图已核）",
          note="f1、P1（表2）与 a、b（表3）为 SKF 来源数据，本版未收录表格，须显式给出")
def bearing_load_torque(*, f1, P1, a, b, d_m):
    return pos("f1", f1) * nonneg("P1", P1) ** num("a", a) * pos("d_m", d_m) ** num("b", b) / 1000.0


@_formula("iso14179_1.eq11", f"{P} 7.3.1 式(11) PBi = (M1+M2)·n/9549（kW；PDF12/印8 原图已核）")
def bearing_load_loss(*, M1, M2, n):
    return (nonneg("M1", M1) + nonneg("M2", M2)) * nonneg("n", n) / 9549.0


@_formula("iso14179_1.eq13_14", f"{P} 7.3.3 式(13)(14) 单列圆锥滚子轴承当量动载 P = Fr 或 0,4·Fr + Y·Fa（PDF15/印11 原图已核）",
          note="原图两式条件均印作 Fa/Fr ≤ e；按常规理解式(14) 应为 Fa/Fr > e —— 无法确认，故按 Fa/Fr ≤ e 取式(13)，"
               "Fa/Fr > e 时阻断（调用方按轴承样本给 P）")
def tapered_equivalent_load(*, F_r, F_a, e, Y):
    Fr, Fa = pos("F_r", F_r), nonneg("F_a", F_a)
    pos("Y", Y)
    if Fa / Fr <= pos("e", e):
        return Fr
    raise Unconfirmed("F_a", "式(14) 适用条件原图印作 Fa/Fr ≤ e（与式(13) 相同），无法确认")


# ------------------------------------------------------------------ 啮合（直齿/斜齿）
@_formula("iso14179_1.eq17_18", f"{P} 7.4 式(17)(18) Hs = (u+1)·[√(ro2²/rw2² − cos²αw) − sinαw]，"
                                "Ht = ((u+1)/u)·[√(ro1²/rw1² − cos²αw) − sinαw]（外齿轮；PDF17/印13 原图已核）")
def sliding_ratios(*, u, r_o1, r_w1, r_o2, r_w2, alpha_w):
    u, aw = pos("u", u), pos("alpha_w", alpha_w)
    Hs = (u + 1.0) * (math.sqrt((pos("r_o2", r_o2) / pos("r_w2", r_w2)) ** 2 - math.cos(aw) ** 2) - math.sin(aw))
    Ht = (u + 1.0) / u * (math.sqrt((pos("r_o1", r_o1) / pos("r_w1", r_w1)) ** 2 - math.cos(aw) ** 2) - math.sin(aw))
    return {"H_s": Hs, "H_t": Ht}


@_formula("iso14179_1.eq16", f"{P} 7.4 式(16) M = 2·cosαw·(Hs+Ht)/(Hs²+Ht²)（PDF17/印13 原图已核）")
def mechanical_advantage(*, alpha_w, H_s, H_t):
    hs, ht = pos("H_s", H_s), pos("H_t", H_t)
    return 2.0 * math.cos(pos("alpha_w", alpha_w)) * (hs + ht) / (hs * hs + ht * ht)


@_formula("iso14179_1.eq21", f"{P} 7.4 式(21) K = 1000·T1·(z1+z2)/(2·bw·rw1²·z2)（N/mm²；PDF18/印14 原图已核）")
def load_intensity(*, T1, z1, z2, b_w, r_w1):
    return 1000.0 * pos("T1", T1) * (pos("z1", z1) + pos("z2", z2)) / (2.0 * pos("b_w", b_w) * pos("r_w1", r_w1) ** 2
                                                                       * z2)


@_formula("iso14179_1.eq20", f"{P} 7.4 式(20) fm = ν^j·K^g/(C1·V^h)，j=−0,223、g=−0,40、h=0,70、C1=3,239；"
                             "适用 2 < V ≤ 25 m/s、1,4 < K ≤ 14 N/mm²（PDF17–18/印13–14 原图已核）",
          note="ν 为工作油池温度下运动黏度（cSt）；适用范围外条文要求按经验确定 → 越域阻断")
def mesh_friction(*, nu, K, V):
    nu, K, V = pos("nu", nu), pos("K", K), pos("V", V)
    if not 2.0 < V <= 25.0:
        raise OutOfDomain("V", "式(20) 适用 2 m/s < V ≤ 25 m/s")
    if not 1.4 < K <= 14.0:
        raise OutOfDomain("K", "式(20) 适用 1,4 N/mm² < K ≤ 14 N/mm²")
    c = MESH_FRICTION
    return nu ** c["j"] * K ** c["g"] / (c["C1"] * V ** c["h"])


@_formula("iso14179_1.eq15", f"{P} 7.4 式(15) PMi = fm·T1·n1·cos²βw/(9549·M)（kW；PDF15/印11 原图已核）")
def mesh_loss(*, f_m, T1, n1, beta_w, M):
    return pos("f_m", f_m) * pos("T1", T1) * nonneg("n1", n1) * math.cos(nonneg("beta_w", beta_w)) ** 2 / (9549.0 * pos("M", M))


# ------------------------------------------------------------------ 油封、风阻搅油
@_formula("iso14179_1.fig2", f"{P} 7.8 图2 油封摩擦扭矩 TS = 3,737e−3·Ds（VITON）、2,429e−3·Ds（BUNA N）（PDF19/印15 原图已核）")
def seal_torque(*, seal_material, D_s):
    return SEAL_TORQUE_COEF[choice("seal_material", seal_material, SEAL_TORQUE_COEF)] * pos("D_s", D_s)


@_formula("iso14179_1.eq22", f"{P} 7.8 式(22) PSi = TS·n/9549（kW；PDF18/印14 原图已核）")
def seal_loss(*, T_S, n):
    return nonneg("T_S", T_S) * nonneg("n", n) / 9549.0


@_formula("iso14179_1.eq23", f"{P} 7.9 式(23) Rf = 7,93 − 4,648/mt（PDF19/印15 原图已核）")
def roughness_factor(*, m_t):
    return 7.93 - 4.648 / pos("m_t", m_t)


def _dip(f_g):
    f = num("f_g", f_g)
    if not 0.0 <= f <= 1.0:
        raise OutOfDomain("f_g", "浸油系数 fg ∈ [0, 1]（7.9）")
    return f


@_formula("iso14179_1.eq24", f"{P} 7.9 式(24) 光滑外圆 PGWi = 7,37·fg·ν·n³·D^4,7·L/(Ag·10^26)（PDF20/印16 原图已核）")
def windage_smooth_od(*, f_g, nu, n, D, L):
    return 7.37 * _dip(f_g) * pos("nu", nu) * nonneg("n", n) ** 3 * pos("D", D) ** 4.7 * pos("L", L) / (A_G * 1e26)


@_formula("iso14179_1.eq25", f"{P} 7.9 式(25) 光滑端面（两侧合计）PGWi = 1,474·fg·ν·n³·D^5,7/(Ag·10^26)（PDF20/印16 原图已核）")
def windage_disc_sides(*, f_g, nu, n, D):
    return 1.474 * _dip(f_g) * pos("nu", nu) * nonneg("n", n) ** 3 * pos("D", D) ** 5.7 / (A_G * 1e26)


@_formula("iso14179_1.eq26", f"{P} 7.9 式(26) 齿面 PGWi = 7,37·fg·ν·n³·D^4,7·F·(Rf/√tanβ)/(Ag·10^26)，β<10° 时取 10°（PDF20/印16 原图已核）")
def windage_teeth(*, f_g, nu, n, D, F, R_f, beta_deg):
    b = max(nonneg("beta_deg", beta_deg), 10.0)
    return (7.37 * _dip(f_g) * pos("nu", nu) * nonneg("n", n) ** 3 * pos("D", D) ** 4.7 * pos("F", F)
            * (pos("R_f", R_f) / math.sqrt(math.tan(math.radians(b)))) / (A_G * 1e26))


@_formula("iso14179_1.eq29", f"{P} 7.10 式(29) f0 = f0(min) + (f0(max) − f0(min))·H/DOR（PDF21/印17 原图已核）")
def bearing_dip_factor(*, f0_min, f0_max, H, D_OR):
    h = nonneg("H", H) / pos("D_OR", D_OR)
    if h > 1.0:
        raise OutOfDomain("H", "H/DOR ≤ 1")
    return pos("f0_min", f0_min) + (pos("f0_max", f0_max) - f0_min) * h


@_formula("iso14179_1.eq27_28", f"{P} 7.10 式(27)(28) M0 = 1,6e−8·f0·dm³（ν·n < 2000）或 1e−10·f0·(ν·n)^(2/3)·dm³（ν·n ≥ 2000）（PDF21/印17 原图已核）")
def bearing_no_load_torque(*, f0, nu, n, d_m):
    vn = pos("nu", nu) * nonneg("n", n)
    if vn < 2000.0:
        return 1.6e-8 * pos("f0", f0) * pos("d_m", d_m) ** 3
    return 1e-10 * pos("f0", f0) * vn ** (2.0 / 3.0) * pos("d_m", d_m) ** 3


@_formula("iso14179_1.eq31", f"{P} 7.10 式(31) PWBi = (M0+M3)·n/9549（kW；PDF23/印19 原图已核）")
def bearing_churning_loss(*, M0, M3, n):
    return (nonneg("M0", M0) + nonneg("M3", M3)) * nonneg("n", n) / 9549.0


def part2(**_):
    raise Unconfirmed("ISO/TR 14179-2", "工程阅读本公式存在错乱、式 1–24 未完整重建、部分系数未确认"
                                        "（standards/KNOWN_ISSUES.md、09-repair-evidence/工程修复说明.md），不收录")
