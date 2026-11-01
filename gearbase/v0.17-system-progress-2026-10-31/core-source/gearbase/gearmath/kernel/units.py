"""量纲与单位目录（全系统唯一一份）。

内部规范单位：长度 mm、力 N、时间 s、角度 rad、温度 K（绝对温度）。
量纲向量 (L, F, T, A, Θ)：长度、力、时间、角度、温度。角度单列，避免"度当弧度"这类错误。

温度约定（K9）：
  - 图内一律用开尔文 K（绝对温度），温度差也用 K；
  - degC 是仿射单位（K = degC + 273.15），只在 set/get 边界作为"绝对温度"的输入/输出单位，
    不允许用作公式声明单位，也不提供"摄氏度差"单位；
  - 换算一律走 to_canonical / from_canonical，不要直接乘 unit(name)[1]（对 degC 会漏掉偏移）。
质量用力系导出：kg = N·s²/m（本系统没有独立的质量维）。
"""
from __future__ import annotations

import math
from fractions import Fraction

Dim = tuple  # (L, F, T, A, Θ)，分量为 Fraction

NAMES = ("mm", "N", "s", "rad", "K")
ONE: Dim = (Fraction(0),) * len(NAMES)


def dim(L=0, F=0, T=0, A=0, Th=0) -> Dim:
    return (Fraction(L), Fraction(F), Fraction(T), Fraction(A), Fraction(Th))


def mul(a: Dim, b: Dim) -> Dim:
    return tuple(x + y for x, y in zip(a, b))


def div(a: Dim, b: Dim) -> Dim:
    return tuple(x - y for x, y in zip(a, b))


def power(a: Dim, p) -> Dim:
    return tuple(x * Fraction(p).limit_denominator(64) for x in a)


def show(d: Dim) -> str:
    parts = [f"{n}^{x}" if x != 1 else n for n, x in zip(NAMES, d) if x != 0]
    return "*".join(parts) or "1"


# 单位 -> (量纲, 换算到规范单位的倍数)
UNITS: dict[str, tuple[Dim, float]] = {
    "1": (ONE, 1.0),
    "mm": (dim(L=1), 1.0),
    "m": (dim(L=1), 1000.0),
    "um": (dim(L=1), 1e-3),
    "N": (dim(F=1), 1.0),
    "kN": (dim(F=1), 1000.0),
    "N*mm": (dim(L=1, F=1), 1.0),
    "N*m": (dim(L=1, F=1), 1000.0),
    "MPa": (dim(L=-2, F=1), 1.0),
    "N/mm": (dim(L=-1, F=1), 1.0),
    "s": (dim(T=1), 1.0),
    "h": (dim(T=1), 3600.0),
    "1/h": (dim(T=-1), 1.0 / 3600.0),
    "rpm": (dim(T=-1), 1.0 / 60.0),
    "m/s": (dim(L=1, T=-1), 1000.0),
    "mm/min": (dim(L=1, T=-1), 1.0 / 60.0),
    "W": (dim(L=1, F=1, T=-1), 1000.0),
    "kW": (dim(L=1, F=1, T=-1), 1.0e6),
    "rad": (dim(A=1), 1.0),
    "deg": (dim(A=1), math.pi / 180.0),
    "mm^2/s": (dim(L=2, T=-1), 1.0),
    "mm^2": (dim(L=2), 1.0),
    "m^2": (dim(L=2), 1e6),
    "mm^3": (dim(L=3), 1.0),
    "sqrt(MPa)": (dim(L=-1, F=Fraction(1, 2)), 1.0),
    # ---- K9：温度、热、黏度、质量 ----
    "K": (dim(Th=1), 1.0),
    "degC": (dim(Th=1), 1.0),                       # 仿射，见 OFFSETS
    "1/K": (dim(Th=-1), 1.0),
    "W/(m^2*K)": (dim(L=-1, F=1, T=-1, Th=-1), 1e-3),
    "W/(m*K)": (dim(F=1, T=-1, Th=-1), 1.0),
    "kg": (dim(L=-1, F=1, T=2), 1e-3),
    "kg/m^3": (dim(L=-4, F=1, T=2), 1e-12),
    "J/(kg*K)": (dim(L=2, T=-2, Th=-1), 1e6),
    "Pa*s": (dim(L=-2, F=1, T=1), 1e-6),
    "mPa*s": (dim(L=-2, F=1, T=1), 1e-9),
    # 刚度与质量（质量无独立量纲：kg = N·s²/m = 1e-3 N·s²/mm）
    "N/(mm*um)": (dim(L=-2, F=1), 1000.0),          # 啮合刚度 c'、cγ
    "um*mm/N": (dim(L=2, F=-1), 1e-3),              # 单位线载荷下的变形（柔度）
    "kg/mm^3": (dim(L=-4, F=1, T=2), 1.0e-3),       # 密度
    "kg/mm": (dim(L=-2, F=1, T=2), 1.0e-3),         # 单位齿宽诱导质量 m_red
}

# 仿射单位：规范值 = 数值 × 倍数 + 偏移
OFFSETS: dict[str, float] = {"degC": 273.15}


def unit(name: str) -> tuple[Dim, float]:
    if name not in UNITS:
        raise KeyError(f"未登记的单位：{name}")
    return UNITS[name]


def is_affine(name: str) -> bool:
    return name in OFFSETS


def to_canonical(value, name: str) -> float:
    """用户单位数值 → 规范单位数值（degC 加偏移）。"""
    return float(value) * unit(name)[1] + OFFSETS.get(name, 0.0)


def from_canonical(value, name: str) -> float:
    """规范单位数值 → 用户单位数值。"""
    return (float(value) - OFFSETS.get(name, 0.0)) / unit(name)[1]
