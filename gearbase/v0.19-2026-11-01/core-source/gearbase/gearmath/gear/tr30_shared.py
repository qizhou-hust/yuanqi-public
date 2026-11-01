"""TR30 例1–4 与例5–8 两套适配器共用的公式：附录A A.6 的 dFf/dNf、fsh0、fHβ5。

- A.6（ISO/TR 6336-30:2022 PDF50/印45 与 PDF51/印46，原图已核）：
  dFf_i = √{[d_i·sinα_t − 2(h_aP0 − x_Ei·m_n − ρ_aP0(1 − sinα_n))/sinα_t]² + d_bi²}，
  原文前提"in this case there is no undercut or protuberance"（齿条型刀具展成）；
  dNf1 = √{(2|a|sinα_wt − √(d_Fa2² − d_b2²))² + d_b1²}，
  dNf2 = z2/|z2| · √{(2a·sinα_wt − √(d_Fa1² − d_b1²))² + d_b2²}（原式带符号，内齿亦适用）。
  h_aP0、ρ_aP0 为刀具（基本齿条）量，按 ISO 6336-3 约定 h_aP0 = h_fP、ρ_aP0 = ρ_fP，均以 m_n 为单位。
  d_Fa 取 d_a：原表声明齿顶倒角 0（例5–8）或未声明倒角（例1–4，见 note）。
- fsh0：ISO 6336-1:2019 附录F 表F.1（PDF137/印129，原图已核）定义为"shaft deformation under specific
  load"，单位 µm·mm/N；式(59)（PDF65/印57）fsh = (F_m/b)·k_unit·[…]·(b/d1)² 对 F_m/b 线性，
  故 fsh0 = fsh/(F_m/b)。该量没有编号公式，定义依据为符号表名称与单位。双斜齿式(60) 的
  "specific load" 取 F_m/b 还是 F_m/b_B 原文未定义：双斜齿须显式选择 FSH0_DOUBLE_HELICAL 的口径（无默认），
  不选即不给 fsh0（not_implemented）。
- 插齿刀展成内齿的 dFf（shaper_root_form）与啮合线不缩短前提（contact_path_formula）见各函数说明。
- fHβ5：见 iso1328.py（ISO 1328-1:2013 式(10) + 5.2.3，PDF32–33 原图已核）。
"""
from __future__ import annotations

from ..kernel.graph import Formula

TR = "ISO/TR 6336-30:2022"


def a6_root_form(i, *, note=""):
    """A.6 齿根形状圆 dFf_i（无根切、无凸台）。负方括号即根切，域外。"""
    inner = f"d_{i}*sin(alpha_t) - 2*m_n*(hfP_{i} - xE_{i} - rhofP_{i}*(1 - sin(alpha_n)))/sin(alpha_t)"
    return Formula(f"tr30.A6.d_Ff.{i}", f"d_Ff_{i}", "mm", f"sqrt(({inner})**2 + db_{i}**2)",
                   f"{TR} Annex A.6 root form diameter from generating shift xE, PDF50/printed45",
                   (f"{inner} >= 0*root_mm",),
                   note=note or "A.6 前提：齿条型刀具、无根切、无凸台；负方括号即根切 → out_of_domain")


def a6_sap(i, *, check_form=True, note="", internal=False):
    """A.6 有效啮合起始圆 dNf_i（原式带符号，外啮合/内啮合通用）。d_Fa 取 d_a。

    干涉核查（check_form）：外齿 |dNf| ≥ |dFf|（SAP 在齿根形状圆之外）；内齿（internal=True，z_i<0）
    齿根在大直径侧，条件反向为 |dNf| ≤ |dFf|。外齿表达式与 v0.8 相同（模型哈希不变）。
    """
    j = 2 if i == 1 else 1
    if i == 1:
        expr = "sqrt((2*abs(a_w)*sin(alpha_wt) - sqrt(da_2**2 - db_2**2))**2 + db_1**2)"
    else:
        expr = "z_2/abs(z_2)*sqrt((2*a_w*sin(alpha_wt) - sqrt(da_1**2 - db_1**2))**2 + db_2**2)"
    domain = (f"da_{j}**2 - db_{j}**2 >= 0*root_mm**2",)
    if check_form:
        domain += ((f"abs(d_Nf_{i}) <= abs(d_Ff_{i})", f"z_{i} < 0") if internal
                   else (f"abs(d_Nf_{i}) >= abs(d_Ff_{i})",))
    return Formula(f"tr30.A6.d_Nf.{i}", f"d_Nf_{i}", "mm", expr,
                   f"{TR} Annex A.6 SAP diameter, signed form, PDF51/printed46", domain,
                   note=note or "d_Fa 取 d_a（无齿顶倒角）；|dNf|<|dFf| 为干涉，out_of_domain")


def shaper_root_form(i):
    """插齿刀展成（内齿，直齿）的齿根形状圆 dFf_i：A.6 同一啮合几何原理用于加工啮合（刀具↔齿轮）。

    依据（均已渲染原图核对）：
    - TR30 A.6（补页阅读副本 PDF51/印45、PDF52/印46）：齿条展成时 dFf 即"刀具齿顶形状线"在展成啮合中
      对应的齿轮直径；dNf 的带符号式 z2/|z2|·√{(2a·sinα_wt − √(d_Fa1² − d_b1²))² + d_b2²} 对内啮合成立。
    - ISO 6336-3:2019 式(33)–(43)（PDF29–30/印21–22）：插齿刀加工啮合 α_w0、加工中心距 a0（内齿为负，6.2.5）、
      刀具基圆 r_b0、刀尖圆角中心半径 r_M = r_a0 − ρ_a0；式(43)/(44) 把 M 当作渐开线（等距线）上的点
      （α_M = arccos(r_b0/r_M)），故刀具渐开线与刀尖圆角的切点 F 在同一法线上，展开长度
      √(r_F² − r_b0²) = √(r_M² − r_b0²) + ρ_a0（渐开线等距线性质）。
    组合式：dFf_i = z_i/|z_i|·√{(2·a0_i·sin α_w0,i − 2(√(r_M,i² − r_b0²) + ρ_a0,i))² + d_b,i²}。
    证据性质：两条原文式的组合（非原文直接给出的 dFf 插齿式）；仅直齿（ISO 6336-3 用法截面当量齿数，
    斜齿的端面换算未核）。
    """
    expr = (f"z_{i}/abs(z_{i})*sqrt((2*a0_{i}*sin(aw0_{i}) - 2*(sqrt(rM_{i}**2 - rb0_{i}**2) + rhoa0_{i}))**2"
            f" + db_{i}**2)")
    return Formula(f"tr30.shaper.d_Ff.{i}", f"d_Ff_{i}", "mm", expr,
                   f"{TR} Annex A.6 SAP 原理（PDF51–52/印45–46）用于插齿刀加工啮合，ISO 6336-3:2019 式(37)(40)–(43)"
                   "（PDF29–30/印21–22）给 a0、α_w0、r_b0、r_M",
                   (f"rM_{i} > rb0_{i}", "beta <= 0*rad", "beta >= 0*rad"),
                   note="组合式（两条已核原文式按同一展成几何组合），证据性质记为 composition_of_verified_formulas；"
                        "插齿刀齿顶高 h_aP0 取 ISO 6336-3 6.1 d) 的 h_fP·m_n（派生输入）")


def contact_path_formula(internal=(False, False)):
    """ISO 6336-2:2019 6.3（PDF24/印16，原图已核）"Formula (17) and (18) are not valid, if undercut shortens
    the path of contact" 的前提，由 A.6 的 dFf/dNf 在图内判定（取代 assumption 输入）：
    dFf 公式本身的域（方括号 ≥ 0）即 A.6 原文"no undercut"前提；外齿 |dNf| ≥ |dFf|、内齿 |dNf| ≤ |dFf|
    表示有效啮合段全落在渐开线上，未被缩短。任一 dFf 不可算（根切、凸台未实现）即 out_of_domain，
    调用方须退回显式 assumption 并记录原因。"""
    dom = []
    for i, inner in zip((1, 2), internal):
        dom.append(f"abs(d_Nf_{i}) <= abs(d_Ff_{i})" if inner else f"abs(d_Nf_{i}) >= abs(d_Ff_{i})")
    return Formula("tr30.contact_path.A6", "contact_path_not_shortened", "1", "1",
                   "ISO 6336-2:2019 6.3 式(17)(18) 前提（PDF24/印16）由 ISO/TR 6336-30:2022 A.6 dFf/dNf（PDF51–52）判定",
                   tuple(dom),
                   note="值恒为 1；前提不成立或 dFf 不可算时 out_of_domain（不出数）")


FSH0 = Formula("tr30.f_sh0", "f_sh0", "um*mm/N", "f_sh/Fm_b",
               "ISO 6336-1:2019 Annex F Table F.1 (PDF137/printed129) f_sh0 shaft deformation under specific load, "
               "with Formula (59) (PDF65/printed57) linear in F_m/b",
               note="无编号公式：定义取符号表名称与单位 µm·mm/N；TR30 表的单位栏印作 µm。双斜齿须显式选 FSH0_DOUBLE_HELICAL")

# 双斜齿 fsh0 的"specific load"口径（显式选择器 method.f_sh0_specific_load，无默认）：
# - total_width：F_m/b，b = 2b_B。ISO 6336-1:2019 7.5.1（PDF58/印50，原图已核）"Throughout this clause, in the case
#   of double helical gears (b = 2b_B)"，式(60) 属 7.5.3.5.2，且其后"See 7.2.2 for F_m/b"（7.2.2 PDF52/印44：F_m/b
#   为横向单位载荷）。按字面即总宽。
# - per_helix：F_m/b_B（= 2F_m/b）。式(60)（PDF65/印57）写作 F_m/b·2·k_unit·[…]·(b_B/d1)²，其中 2F_m/b = F_m/b_B，
#   即与式(59) 同形、b→b_B；按"式(59) 的载荷无关因子"读法得 fsh0 = k_unit·[…]·(b_B/d1)²。
# 两种读法原文均未直接定义 fsh0（表F.1 只有名称与单位），属来源未定义；两者都报告，不按表值选。
FSH0_DOUBLE_HELICAL = {
    "total_width": Formula("tr30.f_sh0.dh.total", "f_sh0", "um*mm/N", "f_sh/Fm_b",
                           "ISO 6336-1:2019 表F.1（PDF137/印129）+ 7.5.1 b=2b_B（PDF58/印50）：specific load = F_m/b（总宽）",
                           note="双斜齿 fsh0 口径 total_width（显式选择）"),
    "per_helix": Formula("tr30.f_sh0.dh.per_helix", "f_sh0", "um*mm/N", "f_sh/(Fm_b*b/b_B)",
                         "ISO 6336-1:2019 表F.1（PDF137/印129）+ 式(60)（PDF65/印57）2F_m/b = F_m/b_B：specific load = F_m/b_B",
                         note="双斜齿 fsh0 口径 per_helix（显式选择）；b 为总接触宽 2b_B"),
}
