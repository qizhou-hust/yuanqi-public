"""双斜齿专用规则：ISO 6336-1:2019 7.5.3.5.2 式(60)、ISO 6336-2:2019 式(40) 与 TR30 4.2.8–4.2.11。

- 式(60)（PDF65/印57 原图已核）：fsh = Fm/b·2·k_unit·[|B* + K′·l·s/d1²·(d1/dsh)⁴ − 0.3| + 0.3]·(bB/d1)²，
  单一啮合时 B* = 1.5，k_unit = 0.023 mm·µm/N。
- ISO 6336-2:2019 式(40)（PDF33）与 TR30 4.2.9：εβ 只按一个半齿宽 bB（tr30_examples58 的 b_overlap 已实现）。
- ISO 6336-1:2019 7.6 式(72) 下文：KFβ 指数 NF 的 b/h 对双斜齿用 bB。
- ISO 6336-2:2019 5.1：σH0 中 b = 2bB（原表 b_eff 即总宽）。
- TR30 4.2.10/4.2.11（PDF13/印8）：fHβ5 按 ISO 1328-1:2013 式(10) 5 级计算（PDF33 原图已核）并按 5.2.3 舍入，双斜齿用 bB
  （图内实现见 iso1328.py；本模块 fhbeta_class5_iso1328 仅为图外参考实现）。
"""
from __future__ import annotations

import math

from ..kernel.graph import Formula, InputSpec

DOUBLE_HELICAL_FSH = Formula(
    "dh.f_sh", "f_sh", "um",
    "2*0.023*Fm_b/c_unit*(abs(B_star + K_prime*l_sh*s_sh/d_1**2*(d_1/d_sh)**4 - 0.3) + 0.3)*(b_B/d_1)**2",
    "ISO 6336-1:2019 7.5.3.5.2 式(60) 双斜齿 fsh（B*=1.5 单一啮合；PDF65/印57 原图已核）",
    ("B_star >= 1.5",))

def double_helical_bh(i):
    """ISO 6336-1:2019 7.6 式(72) 下文（PDF73/印65）：双斜齿 b/h 用 bB 代替 b。"""
    return Formula(f"dh.bh.{i}", f"bh_{i}", "1", f"b_B/h_{i}",
                   "ISO 6336-1:2019 7.6 式(72)：双斜齿以 bB 代替 b（PDF73/印65 原文）")


DOUBLE_HELICAL_INPUTS = [InputSpec("b_B", "mm", "双斜齿单个半齿宽 bB", ("b_B > 0",))]


def _round_1328(value):
    """ISO 1328-1:2013 5.2.3 舍入（PDF32/印26 原图已核）：>10 µm 取整；5.0–10 µm 取 0.5；<5.0 µm 取 0.1。"""
    from .dynamic import _round_iso1328
    return _round_iso1328(value)


def fhbeta_class5_iso1328(model, raw, double):
    """fHβ5：ISO 1328-1:2013 式(10) fHβT=(0.05√d+0.35√b+4)·√2^(A−5)，A=5（PDF33/印27 原图已核），
    5.2.3 舍入，两轮取大；双斜齿 b 用 bB（TR30 4.2.11）。适用范围按第1章（PDF7/印1）检查，5.2.1 不得外推。

    返回 (值 µm, 来源说明)。v0.8-Q1 起 fHβ5 已由 iso1328.fhbeta5_formulas 在公式图内计算（kernel round_to）；
    本函数只保留为图外参考实现，供测试逐例交叉核对，不再写入任何模型。
    """
    mn = raw["m_n"]["values"][0]
    beta_deg = raw["beta"]["values"][0]
    beta = math.radians(beta_deg)
    values = []
    for i in (1, 2):
        z = abs(raw["z"]["values"][i-1])
        d = z * mn / math.cos(beta)
        b = raw["b_per_helix"]["values"][i-1] if double else raw["b"]["values"][i-1]
        if not (5 <= z <= 1000 and 5 <= d <= 15000 and 0.5 <= mn <= 70 and 4 <= b <= 1200 and abs(beta_deg) <= 45):
            raise ValueError(f"ISO 1328-1:2013 第1章适用范围外（5.2.1 不得外推）：z={z}, d={d}, mn={mn}, b={b}, β={beta_deg}")
        values.append(_round_1328(0.05*math.sqrt(d) + 0.35*math.sqrt(b) + 4))
    note = ("ISO 1328-1:2013 式(10) 5 级 fHβT=(0.05√d+0.35√b+4)（PDF33/印27 原图已核），5.2.3 舍入（PDF32/印26），"
            "第1章适用范围已查（PDF7/印1），两轮取大；TR30 4.2.10/4.2.11 PDF14；舍入为阶跃，作派生输入")
    return max(values), note
