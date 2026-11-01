"""DIN 3967:1978-08 齿轮配合制（侧隙链接口骨架）：齿厚上偏差 Asne（表1）、齿厚公差 Tsn（表2）、下偏差 Asni = Asne − Tsn（3.2）。

资料与核对口径（用户私有 PDF，本机渲染原图核对；只写条款、表号、页码）：
  - 文件 "DIN 3967：1978.pdf"（24 页，英译本 "System of Gear Fits ... August 1978"），SHA256=SOURCE_SHA256；
    PDF 页 = 印刷页。表1/表2 数值逐格对照 PDF2 原图转录；3.2/3.4 文字与示例 "27cd，d=100 mm → Asne=−70 µm、
    Asni=−170 µm" 见 PDF3 原图。
  - 证据等级 null。旁证：K01（KISSsoft，报告"DIN 3967 cd25"）d1=150/d2=456 mm 的 Asne/Asni 与本表一致（测试核对）。
直径分档：表头 "over … up to"，按 (下限, 上限] 取档；d ≤ 0 或 > 10 000 mm 越域。
TODO（未收录）：附录 A 侧隙计算（温升、中心距公差、轴线平行度、单项偏差、膨胀、弹性的侧隙变化 Δj 各式）、
  附录 B 测量尺寸换算（公法线、跨球/跨棒、双啮中心距）、与 ISO 21771/DIN 3960 的 xE 换算链。
"""
from __future__ import annotations

from .tribology_common import OutOfDomain, TribError, Unconfirmed, choice, formula_registry, pos

P = "DIN 3967:1978"
SOURCE_FILE = "DIN 3967：1978.pdf"
SOURCE_SHA256 = "bc5c2245cf12cb8708d98041108d62a021c7eab743b6288bc2fe0a07219b322e"
EVIDENCE_NULL_REASON = "无独立外部算例；条文示例与 K01 报告值仅作一致性旁证"
FORMULAS: dict = {}
_formula = formula_registry(FORMULAS, P, EVIDENCE_NULL_REASON)

D_LIMITS = (10, 50, 125, 280, 560, 1000, 1600, 2500, 4000, 6300, 10000)     # 上限（mm），下限为前一档上限
ALLOWANCE_SERIES = ("a", "ab", "b", "bc", "c", "cd", "d", "e", "f", "g", "h")
# 表1 Asne（µm），行 = 直径档，列 = ALLOWANCE_SERIES（PDF2 原图已核）
TABLE1_ASNE = (
    (-100, -85, -70, -58, -48, -40, -33, -22, -10, -5, 0),
    (-135, -110, -95, -75, -65, -54, -44, -30, -14, -7, 0),
    (-180, -150, -125, -105, -85, -70, -60, -40, -19, -9, 0),
    (-250, -200, -170, -140, -115, -95, -80, -56, -26, -12, 0),
    (-330, -280, -230, -190, -155, -130, -110, -75, -35, -17, 0),
    (-450, -370, -310, -260, -210, -175, -145, -100, -48, -22, 0),
    (-600, -500, -420, -340, -290, -240, -200, -135, -64, -30, 0),
    (-820, -680, -560, -460, -390, -320, -270, -180, -85, -41, 0),
    (-1100, -920, -760, -620, -520, -430, -360, -250, -115, -56, 0),
    (-1500, -1250, -1020, -840, -700, -580, -480, -330, -155, -75, 0),
    (-2000, -1650, -1350, -1150, -940, -780, -640, -450, -210, -100, 0),
)
TOLERANCE_SERIES = tuple(range(21, 31))
# 表2 Tsn（µm），列 = 21..30（PDF2 原图已核）
TABLE2_TSN = (
    (3, 5, 8, 12, 20, 30, 50, 80, 130, 200),
    (5, 8, 12, 20, 30, 50, 80, 130, 200, 300),
    (6, 10, 16, 25, 40, 60, 100, 160, 250, 400),
    (8, 12, 20, 30, 50, 80, 130, 200, 300, 500),
    (10, 16, 25, 40, 60, 100, 160, 250, 400, 600),
    (12, 20, 30, 50, 80, 130, 200, 300, 500, 800),
    (16, 25, 40, 60, 100, 160, 250, 400, 600, 1000),
    (20, 30, 50, 80, 130, 200, 300, 500, 800, 1300),
    (25, 40, 60, 100, 160, 250, 400, 600, 1000, 1600),
    (30, 50, 80, 130, 200, 300, 500, 800, 1300, 2000),
    (40, 60, 100, 160, 250, 400, 600, 1000, 1600, 2400),
)


def _row(d):
    d = pos("d", d)
    for i, hi in enumerate(D_LIMITS):
        if d <= hi:
            return i
    raise OutOfDomain("d", "表1/表2 只覆盖分度圆直径 ≤ 10 000 mm")


@_formula("din3967.table1", f"{P} 3.1 表1 齿厚上偏差 Asne（µm），按分度圆直径与偏差系列（PDF2/印2 原图已核）")
def upper_allowance(*, d, series):
    return float(TABLE1_ASNE[_row(d)][ALLOWANCE_SERIES.index(choice("series", series, ALLOWANCE_SERIES))])


@_formula("din3967.table2", f"{P} 3.3 表2 齿厚公差 Tsn（µm），按分度圆直径与公差系列 21–30（PDF2/印2 原图已核）")
def tooth_thickness_tolerance(*, d, tolerance_series):
    return float(TABLE2_TSN[_row(d)][TOLERANCE_SERIES.index(choice("tolerance_series", tolerance_series, TOLERANCE_SERIES))])


@_formula("din3967.3_2", f"{P} 3.2 下偏差 = 上偏差 − 公差（均为负值）；3.4 代号 = 公差系列号 + 上偏差系列字母（PDF3/印3 原图已核）")
def allowances(*, d, series, tolerance_series):
    """返回 {"A_sne": µm, "T_sn": µm, "A_sni": µm}。"""
    e = upper_allowance(d=d, series=series)
    t = tooth_thickness_tolerance(d=d, tolerance_series=tolerance_series)
    return {"A_sne": e, "T_sn": t, "A_sni": e - t}


def parse_designation(code):
    """解析代号：DIN 3967 3.4 写法 '27cd'（数字在前）；KISSsoft 报告写法 'cd25'（字母在前）同样接受。"""
    if not isinstance(code, str) or not code.strip():
        raise TribError("code", "bad_input", "代号应为非空字符串")
    s = code.strip().lower()
    digits = "".join(ch for ch in s if ch.isdigit())
    letters = "".join(ch for ch in s if ch.isalpha())
    if not digits or not letters or (s != digits + letters and s != letters + digits):
        raise TribError("code", "bad_input", f"无法解析代号 {code!r}")
    tol = int(digits)
    choice("tolerance_series", tol, TOLERANCE_SERIES)
    choice("series", letters, ALLOWANCE_SERIES)
    return {"series": letters, "tolerance_series": tol}


def backlash_chain(*, d1, d2, code1, code2):
    """侧隙链接口骨架：两轮齿厚偏差（法向，µm）。附录 A 的侧隙计算未收录，backlash() 阻断。"""
    c1, c2 = parse_designation(code1), parse_designation(code2)
    g1 = allowances(d=d1, **c1)
    g2 = allowances(d=d2, **c2)
    return {"gear1": g1, "gear2": g2, "sum_A_sne": g1["A_sne"] + g2["A_sne"], "sum_A_sni": g1["A_sni"] + g2["A_sni"],
            "TODO": "附录 A：jt,min/jt,max 由 ΣAsne/ΣAsni 与 Δjϑ、Δja、Δjβ、ΔjF、Δjq、ΔjE 等修正得到，未实现"}


def backlash(**_):
    raise Unconfirmed("backlash", "DIN 3967 附录 A（PDF7 起）侧隙与修正项 Δj 各式本版未核对收录（TODO）")
