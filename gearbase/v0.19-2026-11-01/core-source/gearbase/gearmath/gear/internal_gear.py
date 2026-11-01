"""内齿轮（大轮 i=2 为内齿）全强度分支：ISO 6336 系列带符号约定下与外齿不同的规则。

约定（ISO 6336-1/-2/-3:2019 符号表注 a、TR30 4.2.13）：内齿啮合中 a、d2、da2、z2 为负，所有派生直径为负。
逐条出处（均已渲染原图核对，PDF 页为证据包页码）：
- 齿数比 u=z2/z1 为负：ISO 6336-2:2019 5.1（PDF19 正文 "for internal gears u is negative"）。
- Z_D=1：ISO 6336-2:2019 6.2（PDF23/印15 "For internal gears, ZD shall be taken as equal to 1,0"）；
  Z_B 仍按式(17)（PDF23–24，带符号 z2）。
- 单齿刚度：ISO 6336-1:2019 9.3.2 b)（PDF84/印76）以 zn2→∞ 代入式(83)(84)。
- 齿根当量齿轮外界点直径 den：ISO 6336-3:2019 6.2.2 式(22)（PDF26/印18），含 z/|z| 与 |z|。
- 内齿齿根弦齿厚/圆角/力臂：ISO 6336-3:2019 6.2.5（PDF32/印24）按插齿刀式(33)–(61)（PDF28–31/印20–23），
  直径与加工中心距 a0 取负号，切线角 θ=60°。6.1 e)（PDF22）：内齿只用插齿刀数据。
- 插齿刀齿顶高 haP0：原表未给，按 ISO 6336-3:2019 6.1 d)（PDF22）"刀具基本齿条尺寸与齿轮对偶齿条相同"
  取 haP0=hfP·mn（派生输入，已在模型输入中注明）。
- 内齿轮缘系数 YB：ISO 6336-3:2019 9.3.2 式(70)（PDF36/印28）sR/mn≥3.5 时 YB=1；原表 Solid 且未给外径，
  sR/mn≥3.5 作为显式假设输入。
- 寿命循环数 N_L2 用 |u|（u 为负号约定，转速比取绝对值）。
- 内齿量棒距反求产形变位（直齿）：按渐开线几何的带符号统一式（与外齿同式，z、d 取负），
  ISO 21771 原文不在证据包，状态 source_not_in_evidence_pack。
"""
from __future__ import annotations

from ..kernel.graph import Formula, InputSpec

F, S = Formula, InputSpec
R1, R2, R3 = "ISO 6336-1:2019", "ISO 6336-2:2019", "ISO 6336-3:2019"


def internal_formulas(formulas, z2):
    """返回替换/新增公式（大轮为内齿）。formulas 为当前图，用于确认被替换项存在。"""
    for need in ("u", "q_s", "den_2", "sFn_2", "rhoF_2", "hFe_2", "df_2", "df_nominal_2"):
        if need not in formulas:
            raise KeyError(f"内齿补丁缺少基础公式 {need}")
    odd = int(round(abs(z2))) % 2 == 1
    fs = [
        internal_shift_from_balls(odd),
        F("int.df.2", "df_2", "mm", "d_2 - 2*m_n*(hfP_2 - xE_2)",
          "ISO/TR 6336-30:2022 4.2.12/4.2.13：齿根圆用产形变位，内齿直径带负号（与外齿同式，去掉正值域）"),
        F("int.df_nominal.2", "df_nominal_2", "mm", "d_2 - 2*m_n*(hfP_2 - x_2)",
          "ISO/TR 6336-30:2022 附录A 名义齿根圆口径；内齿直径带负号"),
        F("int.u", "u", "1", "z_2/z_1", f"{R2} 5.1：内齿啮合 u 为负（PDF19）", ("z_2 < 0",)),
        F("int.rho_red", "rho_red", "mm", "0.5*db_1*db_2*tan(alpha_wt)/(db_1 + db_2)",
          f"{R2} 12.3.2.3 式(51)(52) 及脚注1（PDF36/印28）：ρred 同样适用于内齿副（带符号 db2<0）",
          ("db_1 > 0", "db_2 < 0", "rho_red > 0")),
        F("int.Z_D", "Z_D", "1", "1", f"{R2} 6.2：内齿 Z_D=1.0（PDF23/印15）", ("z_2 < 0",)),
        F("int.q_s", "q_s", "1",
          "0.04723 + 0.15551/zn_c_1 - 0.00635*x_1 - 0.11654*x_1/zn_c_1 - 0.00193*x_2 + 0.00529*x_1**2 + 0.00182*x_2**2",
          f"{R1} 9.3.2 b)（PDF84/印76）：内齿以 zn2→∞ 代入式(84)，含 1/zn2 的项为零", ("z_2 < 0",)),
        F("int.N_L_2", "N_L_2", "1", "n_1/abs(u)*life_duration*cycles_per_rev_2",
          "ISO 6336-2/-3 寿命循环数；内齿 u 为负号约定，转速比取 |u|"),
        F("int.Y_B_2", "Y_B_2", "1", "1", f"{R3} 9.3.2 式(70)（PDF36/印28）：sR/mn≥3.5 时 YB=1",
          ("internal_rim_ge_3p5 >= 1", "internal_rim_ge_3p5 <= 1")),
        # ISO 6336-3 式(22)：通用（带符号）外界点直径；对外齿与库内式相同
        F("int.den.2", "den_2", "mm",
          "2*z_2/abs(z_2)*sqrt((sqrt((dan_2/2)**2 - (dbn_2/2)**2) - pi*d_2*cos(beta)*cos(alpha_n)/abs(z_2)*(eps_alphan - 1))**2 + (dbn_2/2)**2)",
          f"{R3} 6.2.2 式(22)（PDF26/印18 原图已核）：z/|z| 与 |z| 带符号写法"),
        # 插齿刀加工内齿：式(33)–(61)
        F("int.z0v", "z0v_2", "1", "z0_2/(cos(beta)*cos(beta_b)**2)", f"{R3} 6.2.4 式(33)（PDF29/印21）"),
        F("int.xi", "xi0_2", "1", "2*(x0_2 + xE_2)/(z0v_2 + zn_2)*tan(alpha_n) + inv(alpha_n)/rad",
          f"{R3} 式(34)：加工啮合 inv αw0（PDF29/印21）；x 取产形变位 xE（6.1）"),
        F("int.aw0", "aw0_2", "rad", "aw0_2 + (xi0_2*rad - inv(aw0_2))/tan(aw0_2)**2",
          f"{R3} 式(35)(36) 牛顿迭代 αw0（PDF29/印21）", kind="fixed_point", start=0.3),
        F("int.a0", "a0_2", "mm", "m_n*(z0v_2 + zn_2)/2*cos(alpha_n)/cos(aw0_2)",
          f"{R3} 式(37) 加工中心距（内齿为负，6.2.5；PDF29/32）"),
        F("int.u0", "u0_2", "1", "z0v_2/zn_2", f"{R3} 式(38)"),
        F("int.rw", "rw_2", "mm", "a0_2/(1 + u0_2)", f"{R3} 式(39) 齿轮加工节圆半径（内齿为负）"),
        F("int.rw0", "rw0_2", "mm", "rw_2*u0_2", f"{R3} 式(39) 刀具加工节圆半径"),
        F("int.rb0", "rb0_2", "mm", "0.5*m_n*z0v_2*cos(alpha_n)", f"{R3} 式(40) 刀具基圆半径（PDF29/印21）"),
        F("int.rM", "rM_2", "mm", "m_n*(z0v_2/2 + haP0_2/m_n + x0_2 - rhoa0_2/m_n)",
          f"{R3} 式(41)(42) 刀尖圆角中心半径（PDF30/印22）"),
        F("int.aM", "aM_2", "rad", "acos(rb0_2/rM_2)", f"{R3} 式(43)"),
        F("int.dalpha", "dalpha_2", "rad",
          "((0.5*pi + 2*x0_2*tan(alpha_n))/z0v_2 - (rhoa0_2 - s_pr_2)/rb0_2)*rad + inv(alpha_n) - inv(aM_2)",
          f"{R3} 式(44) M 点半齿厚角（PDF30/印22）"),
        F("int.XM", "XM_2", "mm", "rM_2*sin(dalpha_2)", f"{R3} 式(45)"),
        F("int.YM", "YM_2", "mm", "rM_2*cos(dalpha_2)", f"{R3} 式(45)"),
        F("int.psi0", "psi0_2", "rad", "pi/zn_2*rad + theta0_2", f"{R3} 式(46)（PDF30/印22）"),
        F("int.psi", "psi_2", "rad",
          "psi_2 - (psi_2 - acos(rw0_2/rM_2*cos(psi_2)) + dalpha_2 + (psi_2 - psi0_2)/u0_2)"
          "/(1 + 1/u0_2 - rw0_2/rM_2*sin(psi_2)/sqrt(1 - (rw0_2/rM_2*cos(psi_2))**2))",
          f"{R3} 式(47)–(51) 辅助角 ψ 牛顿迭代（PDF31/印23）", kind="fixed_point", start=1.0),
        F("int.delta", "delta_2", "rad", "acos(rw0_2/rM_2*cos(psi_2))", f"{R3} 式(53)"),
        F("int.omega0", "omega0_2", "rad", "delta_2 - psi_2 - dalpha_2", f"{R3} 式(52)"),
        F("int.dhp", "dhp_2", "mm", "YM_2 - rw0_2*cos(omega0_2)", f"{R3} 式(54)"),
        F("int.dh", "dh_2", "mm", "dhp_2*sin(psi_2)/sin(psi_2 + omega0_2)", f"{R3} 式(55)"),
        F("int.K", "Kc_2", "mm", "dh_2/sin(psi_2)", f"{R3} 式(56)"),
        F("int.X", "Xc_2", "mm", "rw_2*sin(psi_2 - theta0_2) - (Kc_2 + rhoa0_2)*cos(theta0_2)", f"{R3} 式(57)"),
        F("int.Y", "Yc_2", "mm", "rw_2*cos(psi_2 - theta0_2) - (Kc_2 + rhoa0_2)*sin(theta0_2)", f"{R3} 式(58)"),
        F("int.sFn", "sFn_2", "mm", "2*Xc_2", f"{R3} 式(59) 齿根弦齿厚（PDF31/印23）"),
        F("int.rhoF", "rhoF_2", "mm", "Kc_2**2/((rw0_2*rw_2/(rw0_2 + rw_2))*sin(psi_2) + Kc_2) + rhoa0_2", f"{R3} 式(60)"),
        F("int.hFe", "hFe_2", "mm", "(cos(gamma_e_2) - sin(gamma_e_2)*tan(alpha_Fen_2))*den_2/2 - Yc_2", f"{R3} 式(61) 弯曲力臂"),
    ]
    return fs


def internal_shift_from_balls(odd):
    """直齿内齿量棒距 MdK → 产形变位 xE2（带符号统一式；odd 为原表齿数奇偶，由整数输入判定）。"""
    factor = "cos(pi/(2*z_2)*rad)" if odd else "1"
    return F("int.xE.balls", "xE_2", "1",
             f"z_2/(2*tan(alpha_n))*((inv(acos(db_2*{factor}/(M_dK_2 - D_M_2))) - inv(alpha_t))/rad"
             " - D_M_2/(m_n*z_2*cos(alpha_n)) + pi/(2*z_2))",
             "渐开线量棒距带符号统一式 inv αM = inv α + DM/(m z cosα) − π/(2z) + 2x tanα/z 的反解"
             "（内齿 z、d、MdK 取负；ISO 21771 原文不在证据包，source_not_in_evidence_pack）",
             ("beta <= 0*rad", "beta >= 0*rad", "z_2 < 0"))


INTERNAL_INPUTS = [
    S("M_dK_2", "mm", "内齿量棒距（带符号，取负）"), S("D_M_2", "mm", "量棒直径", ("D_M_2 > 0",)),
    S("z0_2", "1", "插齿刀齿数", ("z0_2 > 0",)), S("x0_2", "1", "插齿刀变位系数"),
    S("haP0_2", "mm", "插齿刀齿顶高（6.1 d) 取 hfP·mn）", ("haP0_2 > 0",)),
    S("rhoa0_2", "mm", "插齿刀齿顶圆角半径", ("rhoa0_2 >= 0",)),
    S("theta0_2", "rad", "内齿切线角 60°（6.2.4/6.2.5）"),
    S("internal_rim_ge_3p5", "1", "内齿轮缘 sR/mn≥3.5 的显式确认（式70 前提）"),
]


def set_internal_inputs(model, raw, put):
    """内齿原表输入：插齿刀、量棒距与显式假设。"""
    import math

    def cite(key):
        c = raw[key]["citation"]
        return f"{c['source']} PDF {c['pdf_page']}: {c['location']}"
    mn = raw["m_n"]["values"][0]
    put("M_dK_2", -abs(raw["M_dK"]["values"][1]), "mm", "user", cite("M_dK") + "；TR30 4.2.13 内齿取负号")
    put("D_M_2", raw["D_M"]["values"][1], "mm", "user", cite("D_M"))
    put("z0_2", raw["z_0"]["values"][1], "1", "user", cite("z_0"))
    put("x0_2", raw["x_0"]["values"][1], "1", "user", cite("x_0"))
    put("rhoa0_2", raw["rho_aP0"]["values"][1]*mn, "mm", "user", cite("rho_aP0") + "（系数×mn）")
    put("haP0_2", raw["h_fP"]["values"][1]*mn, "mm", "derived",
        "ISO 6336-3:2019 6.1 d)（PDF22）刀具齿条与齿轮对偶齿条相同：haP0=hfP·mn；原表未直接给出")
    put("theta0_2", math.radians(60), "rad", "standard_constant", "ISO 6336-3:2019 6.2.4/6.2.5 内齿切线角 60°")
    put("internal_rim_ge_3p5", 1, "1", "assumption", "原表 Solid、未给外径：假设 sR/mn≥3.5（式70 → YB=1）")
