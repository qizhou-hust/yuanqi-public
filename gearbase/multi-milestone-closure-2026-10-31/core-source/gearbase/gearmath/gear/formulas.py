"""圆柱齿轮公式库（数据）。所有校核都从这里取公式，不在别处手写。

每条公式 = 输出名 + 单位 + 表达式 + 标准条款编号 + 适用域。
条款编号只做引用，不复制标准原文。下标 _1 = 小轮，_2 = 大轮。
"""
from __future__ import annotations

from ..kernel.graph import Formula

F = Formula


def _pair(fid, out, unit, expr, ref, domain=(), **kw):
    """为小轮(1)、大轮(2)各生成一条；{i} 为本轮，{j} 为配对轮。"""
    rows = []
    for i, j in (("1", "2"), ("2", "1")):
        sub = lambda s: s.replace("{i}", i).replace("{j}", j)
        rows.append(F(f"{fid}.{i}", sub(out), unit, sub(expr), ref, tuple(sub(d) for d in domain), **kw))
    return rows


GEOMETRY = [
    F("geo.alpha_t", "alpha_t", "rad", "atan(tan(alpha_n)/cos(beta))", "ISO 21771:2007 端面压力角"),
    F("geo.m_t", "m_t", "mm", "m_n/cos(beta)", "ISO 21771:2007 端面模数"),
    F("geo.beta_b", "beta_b", "rad", "atan(tan(beta)*cos(alpha_t))", "ISO 21771:2007 基圆螺旋角"),
    *_pair("geo.d", "d_{i}", "mm", "z_{i}*m_t", "ISO 21771:2007 分度圆直径", ("z_{i} >= 5",)),
    *_pair("geo.db", "db_{i}", "mm", "d_{i}*cos(alpha_t)", "ISO 21771:2007 基圆直径"),
    *_pair("geo.da", "da_{i}", "mm", "d_{i} + 2*m_n*(haP + x_{i})", "ISO 21771:2007 齿顶圆直径（不含齿顶缩短）"),
    *_pair("geo.df", "df_{i}", "mm", "d_{i} - 2*m_n*(hfP - x_{i})", "ISO 21771:2007 齿根圆直径"),
    *_pair("geo.h", "h_{i}", "mm", "(da_{i} - df_{i})/2", "ISO 21771:2007 全齿高"),
    *_pair("geo.zn", "zn_{i}", "1", "z_{i}/(cos(beta_b)**2*cos(beta))", "ISO 21771:2007 当量齿数"),
    F("geo.u", "u", "1", "z_2/z_1", "ISO 21771:2007 齿数比", ("z_2 >= z_1",)),
    F("geo.alpha_wt", "alpha_wt", "rad", "inv_inverse(inv(alpha_t) + 2*(x_1 + x_2)*tan(alpha_n)/(z_1 + z_2)*rad)",
      "ISO 21771:2007 无侧隙啮合方程（变位求工作压力角）"),
    F("geo.a", "a", "mm", "(d_1 + d_2)/2", "ISO 21771:2007 标准中心距"),
    F("geo.a_w", "a_w", "mm", "a*cos(alpha_t)/cos(alpha_wt)", "ISO 21771:2007 工作中心距"),
    F("geo.eps_alpha", "eps_alpha", "1",
      "(sqrt(da_1**2 - db_1**2) + sqrt(da_2**2 - db_2**2) - 2*a_w*sin(alpha_wt))/(2*pi*m_t*cos(alpha_t))",
      "ISO 21771:2007 端面重合度", ("eps_alpha >= 1",)),
    F("geo.eps_beta", "eps_beta", "1", "b*sin(beta)/(pi*m_n)", "ISO 21771:2007 纵向重合度"),
    F("geo.volume", "V_blank", "mm^3", "pi/4*b*(d_1**2 + d_2**2)", "近似齿坯体积（优化目标用，非标准）"),
]

LOAD = [
    F("load.F_t", "F_t", "N", "2*T_1/d_1", "ISO 6336-1:2019 名义切向力"),
    F("load.v", "v", "m/s", "pi*d_1*n_1", "ISO 6336-1:2019 分度圆线速度"),
    *_pair("load.bh", "bh_{i}", "1", "b/h_{i}", "ISO 6336-1:2019 7.6 式(72) 齿宽齿高比 b_i/h_i（本库两轮齿宽同为 b；PDF 73 页）"),
    F("load.bh_NF", "bh_NF", "1", "max(min(bh_1, bh_2), 3)",
      "ISO 6336-1:2019 7.6 式(72) 取 b1/h1、b2/h2 中较小者；b/h<3 时以 3 代入（PDF 73 页核图）"),
    F("load.N_F", "N_F", "1", "bh_NF**2/(1 + bh_NF + bh_NF**2)", "ISO 6336-1:2019 7.6 式(72) KFβ 指数 NF（PDF 73 页）"),
    F("load.K_Fbeta", "K_Fbeta", "1", "exp(N_F*log(K_Hbeta))", "ISO 6336-1:2019 7.6 式(71) KFβ = KHβ^NF（PDF 73 页）"),
]

PITTING = [
    F("pit.Z_H", "Z_H", "1", "sqrt(2*cos(beta_b)*cos(alpha_wt)/(cos(alpha_t)**2*sin(alpha_wt)))", "ISO 6336-2:2019 节点区域系数"),
    F("pit.Z_E", "Z_E", "sqrt(MPa)", "sqrt(E/(2*pi*(1 - nu**2)))", "ISO 6336-2:2019 弹性系数（同材料）"),
    F("pit.Z_eps", "Z_eps", "1", "sqrt((4 - eps_alpha)/3*(1 - min(eps_beta, 1)) + min(eps_beta, 1)/eps_alpha)",
      "ISO 6336-2:2019 重合度系数"),
    F("pit.Z_beta", "Z_beta", "1", "1/sqrt(cos(beta))", "ISO 6336-2:2019 螺旋角系数"),
    F("pit.M_1", "M_1", "1",
      "tan(alpha_wt)/sqrt((sqrt(da_1**2/db_1**2 - 1) - 2*pi/z_1)*(sqrt(da_2**2/db_2**2 - 1) - (eps_alpha - 1)*2*pi/z_2))",
      "ISO 6336-2:2019 单对齿啮合系数中间量 M1"),
    F("pit.M_2", "M_2", "1",
      "tan(alpha_wt)/sqrt((sqrt(da_2**2/db_2**2 - 1) - 2*pi/z_2)*(sqrt(da_1**2/db_1**2 - 1) - (eps_alpha - 1)*2*pi/z_1))",
      "ISO 6336-2:2019 单对齿啮合系数中间量 M2"),
    F("pit.Z_B", "Z_B", "1", "max(1, M_1 - min(eps_beta, 1)*(M_1 - 1))",
      "ISO 6336-2:2019 小轮单对齿啮合系数；斜齿时等价式(19)–(21)取表3 fZCa=1.0（3D分析），"
      "其他表3分支须用 factor_selectors['method.Z_BD'] 显式选择"),
    F("pit.Z_D", "Z_D", "1", "max(1, M_2 - min(eps_beta, 1)*(M_2 - 1))",
      "ISO 6336-2:2019 大轮单对齿啮合系数；斜齿时等价式(19)(22)(23)取表3 fZCa=1.0（3D分析），"
      "其他表3分支须用 factor_selectors['method.Z_BD'] 显式选择"),
    F("pit.sigma_H0", "sigma_H0", "MPa", "Z_H*Z_E*Z_eps*Z_beta*sqrt(F_t/(d_1*b)*(u + 1)/u)", "ISO 6336-2:2019 名义接触应力"),
    F("pit.sigma_H_1", "sigma_H_1", "MPa", "Z_B*sigma_H0*sqrt(K_A*K_V*K_Hbeta*K_Halpha)", "ISO 6336-2:2019 小轮接触应力"),
    F("pit.sigma_H_2", "sigma_H_2", "MPa", "Z_D*sigma_H0*sqrt(K_A*K_V*K_Hbeta*K_Halpha)", "ISO 6336-2:2019 大轮接触应力"),
    *_pair("pit.sigma_HG", "sigma_HG_{i}", "MPa", "sigma_Hlim_{i}*Z_NT_{i}*Z_L*Z_V*Z_R*Z_W*Z_X", "ISO 6336-2:2019 接触极限应力"),
    *_pair("pit.S_H", "S_H_{i}", "1", "sigma_HG_{i}/sigma_H_{i}", "ISO 6336-2:2019 接触安全系数"),
]

ROOT = [
    F("root.E", "rack_E", "mm", "pi/4*m_n - hfP*m_n*tan(alpha_n) - (1 - sin(alpha_n))*rhofP*m_n/cos(alpha_n)",
      "ISO 6336-3:2019 方法B 辅助量 E（无凸台）"),
    *_pair("root.G", "G_{i}", "1", "rhofP - hfP + x_{i}", "ISO 6336-3:2019 辅助量 G"),
    *_pair("root.H", "H_{i}", "rad", "(2/zn_{i}*(pi/2 - rack_E/m_n) - pi/3)*rad", "ISO 6336-3:2019 辅助量 H"),
    *_pair("root.theta", "theta_{i}", "rad", "2*G_{i}/zn_{i}*tan(theta_{i})*rad - H_{i}",
           "ISO 6336-3:2019 辅助角 θ（不动点迭代）", kind="fixed_point", start=0.5235987755982988),
    *_pair("root.sFn", "sFn_{i}", "mm", "m_n*(zn_{i}*sin(pi/3*rad - theta_{i}) + sqrt(3)*(G_{i}/cos(theta_{i}) - rhofP))",
           "ISO 6336-3:2019 危险截面齿根弦齿厚"),
    *_pair("root.rhoF", "rhoF_{i}", "mm", "m_n*(rhofP + 2*G_{i}**2/(cos(theta_{i})*(zn_{i}*cos(theta_{i})**2 - 2*G_{i})))",
           "ISO 6336-3:2019 危险截面齿根圆角半径"),
    *_pair("root.dn", "dn_{i}", "mm", "d_{i}/cos(beta_b)**2", "ISO 6336-3:2019 当量齿轮分度圆"),
    *_pair("root.dbn", "dbn_{i}", "mm", "dn_{i}*cos(alpha_n)", "ISO 6336-3:2019 当量齿轮基圆"),
    *_pair("root.dan", "dan_{i}", "mm", "dn_{i} + da_{i} - d_{i}", "ISO 6336-3:2019 当量齿轮齿顶圆"),
    F("root.eps_alphan", "eps_alphan", "1", "eps_alpha/cos(beta_b)**2", "ISO 6336-3:2019 当量齿轮重合度"),
    *_pair("root.den", "den_{i}", "mm",
           "2*sqrt((sqrt((dan_{i}/2)**2 - (dbn_{i}/2)**2) - pi*d_{i}*cos(beta)*cos(alpha_n)/z_{i}*(eps_alphan - 1))**2 + (dbn_{i}/2)**2)",
           "ISO 6336-3:2019 单齿啮合外界点直径"),
    *_pair("root.alpha_en", "alpha_en_{i}", "rad", "acos(dbn_{i}/den_{i})", "ISO 6336-3:2019 外界点压力角"),
    *_pair("root.gamma_e", "gamma_e_{i}", "rad", "(pi/2 + 2*tan(alpha_n)*x_{i})/zn_{i}*rad + inv(alpha_n) - inv(alpha_en_{i})",
           "ISO 6336-3:2019 γe"),
    *_pair("root.alpha_Fen", "alpha_Fen_{i}", "rad", "alpha_en_{i} - gamma_e_{i}", "ISO 6336-3:2019 载荷作用角"),
    *_pair("root.hFe", "hFe_{i}", "mm",
           "m_n/2*((cos(gamma_e_{i}) - sin(gamma_e_{i})*tan(alpha_Fen_{i}))*den_{i}/m_n - zn_{i}*cos(pi/3*rad - theta_{i}) - G_{i}/cos(theta_{i}) + rhofP)",
           "ISO 6336-3:2019 弯曲力臂"),
    F("root.f_eps", "f_eps", "1",
      "where(eps_beta <= 0, where(eps_alphan < 2, 1, 0.7), "
      "where(eps_beta < 1, where(eps_alphan < 2, sqrt(1 - eps_beta + eps_beta/eps_alphan), "
      "sqrt((1 - eps_beta)/2 + eps_beta/eps_alphan)), 1/sqrt(eps_alphan)))",
      "ISO 6336-3:2019 6.2.1 式(10)-(14) 齿根载荷分配系数，使用当量端面重合度εαn（PDF25/印刷17原图核实）",
      ("eps_beta >= 0", "eps_alphan >= 1"),
      note="εαn=2,0 原文矛盾：正文称直齿 εαn≤2,0 时 fε=1，式(10)/(11) 条件却为 εαn<2 → 1、εαn≥2 → 0,7；"
           "本库按式取，近折点由 f_eps_kink_warnings 告警"),
    *_pair("root.Y_F", "Y_F_{i}", "1", "6*hFe_{i}/m_n*cos(alpha_Fen_{i})/((sFn_{i}/m_n)**2*cos(alpha_n))*f_eps",
           "ISO 6336-3:2019 6.2.1 式(9) 齿形系数YF，含fε（PDF25/印刷17原图核实）"),
    *_pair("root.L", "L_{i}", "1", "sFn_{i}/hFe_{i}", "ISO 6336-3:2019 L"),
    *_pair("root.qs", "qs_{i}", "1", "sFn_{i}/(2*rhoF_{i})", "ISO 6336-3:2019 缺口参数 qs", ("qs_{i} >= 1",)),
    *_pair("root.Y_S", "Y_S_{i}", "1", "(1.2 + 0.13*L_{i})*exp(log(qs_{i})/(1.21 + 2.3/L_{i}))", "ISO 6336-3:2019 应力修正系数 YS"),
    F("root.Y_beta", "Y_beta", "1", "(1 - min(eps_beta, 1)*min(beta, pi/6*rad)/(2*pi/3*rad))/cos(min(beta, pi/6*rad))**3",
      "ISO 6336-3:2019 螺旋角系数（2019 版含 1/cos³β，与 M31 standard_rating_engine 口径一致）", ("beta <= pi/4*rad",)),
    *_pair("root.sigma_F", "sigma_F_{i}", "MPa", "F_t/(b*m_n)*Y_F_{i}*Y_S_{i}*Y_beta*Y_B*Y_DT*K_A*K_V*K_Fbeta*K_Falpha",
           "ISO 6336-3:2019 齿根应力"),
    *_pair("root.sigma_FG", "sigma_FG_{i}", "MPa", "sigma_Flim_{i}*Y_ST*Y_NT_{i}*Y_drelT_{i}*Y_RrelT_{i}*Y_X", "ISO 6336-3:2019 齿根极限应力"),
    *_pair("root.S_F", "S_F_{i}", "1", "sigma_FG_{i}/sigma_F_{i}", "ISO 6336-3:2019 弯曲安全系数"),
]

CYLINDRICAL_PAIR = GEOMETRY + LOAD + PITTING + ROOT

# 齿根计算所用变位（选择器 method.root_shift）。ISO 6336-3:2019 6.1（PDF 22 页核图）：有实测齿形时用实测；
# 否则"应"按齿厚公差取最小产形变位 xE,min（should，推荐）；同节 d) 又称齿厚余量"可以忽略"。两种口径均有原文依据，
# 故不设默认：nominal = 式(24)(27) 中 x 取名义变位（上面 ROOT 中的 G、γe，偏不安全）；
# generating = x 换成 xE,min（下面三组公式，需齿厚下偏差 Asn,i）。式(24)(25)(27) 见 PDF 26 页（核图）。
ROOT_SHIFT_OUTPUTS = ("G_1", "G_2", "gamma_e_1", "gamma_e_2")
ROOT_GENERATING = [
    *_pair("root.xE", "xE_{i}", "1", "x_{i} + A_sn_i_{i}/(2*m_n*tan(alpha_n))",
           "ISO 6336-3:2019 6.1 最小产形变位 xE,min = x + Asn,i/(2·mn·tanαn)（Asn,i 带符号，减薄为负；"
           "换算式已并核 ISO 21771-1:2024 9.4/9.5式(248)(251)(252)原图，"
           "限精加工q=0、Asn,i对应E_sni；未据此更改本库2007几何版次）"),
    *_pair("root.G.xE", "G_{i}", "1", "rhofP - hfP + xE_{i}", "ISO 6336-3:2019 6.2.3 式(27) 辅助量 G，x 取 xE,min（6.1；PDF 22/26 页）"),
    *_pair("root.gamma_e.xE", "gamma_e_{i}", "rad",
           "(pi/2 + 2*tan(alpha_n)*xE_{i})/zn_{i}*rad + inv(alpha_n) - inv(alpha_en_{i})",
           "ISO 6336-3:2019 6.2.2 式(24) γe，x 取 xE,min（6.1；PDF 22/26 页）"),
]


F_EPS_AMBIGUITY = ("ISO 6336-3:2019 6.2.1（PDF25/印刷17）：正文写直齿 εαn≤2,0 时 fε=1，式(10)/(11) 的条件却是 "
                   "εαn<2 → 1、εαn≥2 → 0,7（斜齿式(12)/(13)同界）；本库按式取，εαn 恰在 2,0 附近时两种读法相差约 30 %")


def f_eps_kink_warnings(model, result, rel_tol=1e-6):
    """fε 分段条件（εαn 与 2 比较、εβ 与 0/1 比较）在结果点附近时给出告警，不改变计算值。"""
    from ..kernel.expr import near_kinks
    if "f_eps" not in getattr(result, "values", {}) or "f_eps" not in model.formulas:
        return []
    return [{"code": "near_kink_f_eps", "quantity": "f_eps", "condition": row["text"],
             "margin": row["margin"], "branch": row["branch"], "message": F_EPS_AMBIGUITY}
            for row in near_kinks(model, result, rel_tol, names=["f_eps"])
            # 只报 εαn 与 2 的比较；直齿 εβ=0 是精确值，εβ=1 处式(13)(14)连续，不属该歧义
            if row["text"].startswith("where(eps_alphan")]
