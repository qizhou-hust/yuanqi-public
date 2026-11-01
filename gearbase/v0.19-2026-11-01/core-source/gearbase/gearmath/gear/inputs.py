"""圆柱齿轮模型的输入声明表（数据）：每个输入的期望单位（只比较量纲）、含义、取值域、角色。

规则：
  - 公式库中每个自由变量都必须在此声明，否则装配模型时报错（不按公式用法猜量纲）；
  - Model.set 拒绝未声明的名字、量纲不符的单位、取值域之外的数值；
  - role="limit" 的输入只被校核使用（安全系数限值等），也是必需输入；
  - 取值域谓词按规范单位（mm、N、s、rad）书写，只表达物理有效性，不表达标准符合性。
下标 _1 = 小轮，_2 = 大轮。
"""
from __future__ import annotations

from ..kernel.expr import FormulaError
from ..kernel.graph import InputSpec, compile_expr

S = InputSpec


def _pair(name, unit, desc, domain=(), **kw):
    return [S(name.replace("{i}", i), unit, f"{desc}（{w}）", tuple(d.replace("{i}", i) for d in domain), **kw)
            for i, w in (("1", "小轮"), ("2", "大轮"))]


GEOMETRY_INPUTS = [
    *_pair("z_{i}", "1", "齿数", ("z_{i} >= 1",)),
    S("m_n", "mm", "法向模数", ("m_n > 0",)),
    S("alpha_n", "deg", "法向压力角", ("alpha_n > 0", "alpha_n < pi/2")),
    S("beta", "deg", "分度圆螺旋角（取绝对值，旋向另行声明）", ("beta >= 0", "beta < pi/2")),
    *_pair("x_{i}", "1", "法向变位系数"),
    S("b", "mm", "齿宽", ("b > 0",)),
    S("haP", "1", "基本齿条齿顶高系数", ("haP > 0",)),
    S("hfP", "1", "基本齿条齿根高系数", ("hfP > 0",)),
    S("rhofP", "1", "基本齿条齿根圆角半径系数", ("rhofP >= 0",)),
    *_pair("A_sn_i_{i}", "mm", "法向齿厚下偏差 Asn,i（带符号，减薄为负；method.root_shift=generating 时求 xE,min）",
           ("A_sn_i_{i} <= 0",)),
]

LOAD_INPUTS = [
    S("T_1", "N*m", "小轮名义扭矩", ("T_1 > 0",)),
    S("n_1", "rpm", "小轮转速", ("n_1 > 0",)),
    S("E", "MPa", "弹性模量（同材料）", ("E > 0",)),
    S("nu", "1", "泊松比（同材料）", ("nu > 0", "nu < 0.5")),
    *_pair("sigma_Hlim_{i}", "MPa", "接触疲劳极限", ("sigma_Hlim_{i} > 0",)),
    *_pair("sigma_Flim_{i}", "MPa", "弯曲疲劳极限", ("sigma_Flim_{i} > 0",)),
]

_FACTORS = [
    ("K_A", "使用系数"), ("K_V", "动载系数"), ("K_Hbeta", "接触齿向载荷系数"), ("K_Halpha", "接触齿间载荷系数"),
    ("K_Falpha", "弯曲齿间载荷系数"), ("Z_L", "润滑剂系数"), ("Z_V", "速度系数"), ("Z_R", "粗糙度系数"),
    ("Z_W", "工作硬化系数"), ("Z_X", "接触尺寸系数"), ("Y_ST", "试验齿轮应力修正系数"), ("Y_X", "弯曲尺寸系数"),
    ("Y_B", "轮缘厚度系数"), ("Y_DT", "深齿系数"),
]
_PAIR_FACTORS = [("Z_NT_{i}", "接触寿命系数"), ("Y_NT_{i}", "弯曲寿命系数"),
                 ("Y_drelT_{i}", "相对缺口敏感系数"), ("Y_RrelT_{i}", "相对表面状况系数")]

FACTOR_INPUTS = [S(n, "1", d, (f"{n} > 0",)) for n, d in _FACTORS] + \
                [row for n, d in _PAIR_FACTORS for row in _pair(n, "1", d, (f"{n} > 0",))]

LIMIT_INPUTS = [
    S("S_Hmin", "1", "最小接触安全系数（限值）", ("S_Hmin > 0",), role="limit"),
    S("S_Fmin", "1", "最小弯曲安全系数（限值）", ("S_Fmin > 0",), role="limit"),
    S("eps_alpha_min", "1", "最小端面重合度（设计规则限值）", ("eps_alpha_min > 0",), role="limit"),
]

CYLINDRICAL_PAIR_INPUTS = GEOMETRY_INPUTS + LOAD_INPUTS + FACTOR_INPUTS + LIMIT_INPUTS


def free_names(formulas):
    """公式（表达式与适用域）中出现、但不由任何公式输出的名字。"""
    outs = {f.output for f in formulas}
    names = set()
    for f in formulas:
        names |= set(compile_expr(f.expr).names)
        for d in f.domain:
            names |= set(compile_expr(d).names)
    return names - outs


def full_input_table():
    """圆柱齿轮副的全部输入声明：基础表 + 动载系数方法B 新增输入（gear/dynamic.py:DYNAMIC_INPUTS）
    + K_Hβ 方法C / K_Hα 方法B 输入（gear/load_distribution.py:LD_INPUTS）。
    只有被所选公式集引用的自由变量才会进入模型（K_V 选 external 时方法B 的输入不会出现）。"""
    from .dynamic import DYNAMIC_INPUTS    # 延迟导入：dynamic 模块本身依赖本模块
    from .load_distribution import LD_INPUTS
    return CYLINDRICAL_PAIR_INPUTS + DYNAMIC_INPUTS + LD_INPUTS


def input_specs(formulas, table=None):
    """给定公式集需要的输入声明：自由变量 + 限值。自由变量未声明时报错，不猜量纲。
    table 缺省为 full_input_table()（基础表 + 方法B 输入）。"""
    rows = {s.name: s for s in (full_input_table() if table is None else table)}
    free = free_names(formulas)
    undeclared = sorted(free - set(rows))
    if undeclared:
        raise FormulaError(f"公式库中以下自由变量没有输入声明（gear/inputs.py）：{undeclared}")
    return [s for s in rows.values() if s.name in free or s.role == "limit"]
