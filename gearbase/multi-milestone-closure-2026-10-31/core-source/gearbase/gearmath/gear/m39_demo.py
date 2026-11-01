"""M39 端到端演示：K01（KISSsoft 厂商示例 01 直齿）齿轮输入 → ISO/TS 6336-21 积分温度法 SintS。

两种模式：
  strict     —— 只用 K01 证据文件（data/kisssoft/K01-spur.json）与 gearmath 现有几何/载荷模型输出；缺的输入不补，
                rate() 返回 blocked 并列出全部缺项。
  supplement —— 在 strict 基础上用 SUPPLEMENT 中逐项标注来源的"演示补充输入"闭合计算。补充项不是 K01 证据，
                数值仅演示流程闭环，须由 KISSsoft 运行（见 REPORT"KISSsoft 运行请求"）确认后才能对拍。
证据等级 null；本模块不判定产品胶合合格与否。

v0.14：另有 P3 适配（p3_integral_inputs / p3_flash_inputs / p3_micropitting_inputs）——用 data/kisssoft_v014
（KISSsoft 2026 原生油品/工况）的实际输入驱动 -21/-20/-22，供 tests/test_m39_kisssoft_v014.py 外部对拍。
注意：KISSsoft 证据显示 K01 油品 Klüberoil GEM 1-220 N 为 FZG A LS14（ZS.Oil.FZGtestA=14）、小轮主动、跑合
（Scoring_RunIn=1）；上面 supplement 的"LS12"等仍为演示假设，未改（保持既有演示输出不变）。
"""
from __future__ import annotations

import json
import math
import pathlib
import re

from ..kernel import units as U
from . import kisssoft_case as KC
from . import micropitting as MP
from . import scuffing_integral as SI

# 从 gearmath K01 模型取的量（canonical → 显示单位）
_MODEL_QTY = {"a_w": "mm", "alpha_t": "rad", "alpha_wt": "rad", "alpha_n": "rad", "beta": "rad", "beta_b": "rad",
              "da_1": "mm", "da_2": "mm", "db_1": "mm", "db_2": "mm", "eps_beta": "1", "b": "mm", "z_1": "1",
              "z_2": "1", "F_t": "N", "v": "m/s", "K_A": "1", "K_V": "1", "K_Hbeta": "1", "K_Halpha": "1",
              "c_s": "N/(mm*um)", "eps_alpha": "1", "m_t": "mm"}

# 演示补充输入：每项 (值, 来源/理由)。均非 K01 证据。
SUPPLEMENT = {
    "lambda_M": (50.0, "ISO/TS 6336-21 5.3 渗碳钢典型值 λM=50 N/(s·K)（PDF15/印9）；K01 未给材料热物性"),
    "c_v": (3.8, "ISO/TS 6336-21 5.3 渗碳钢典型值 cv=3,8 N/(mm²·K)（PDF15/印9）"),
    "material_XW": ("case_carburized_austenite_10_20", "假设：残余奥氏体 10–20 %（表4 XW=1,00）；K01 未给"),
    "phi_E": (1.0, "假设：完全跑合 φE=1；K01 未给跑合状态"),
    "driver": ("pinion", "假设：小轮主动；K01 证据未记录功率流向"),
    "T1T_or_load_stage": ({"load_stage": 12}, "假设：FZG A/8,3/90 失效载荷级 12；K01 只给油名 Klüberoil GEM 1-220 N，"
                                             "未给 FZG 等级（须油品数据表或 KISSsoft 油库确认）"),
    "eta_oil": (None, "由 ISO/TS 6336-22 式(17)–(19)(20)(21)(16) 在 θoil 处由 ν40/ν100 计算（跨部分借用，-21 未规定 ηoil 的求法；"
                      "矿物油 ρ15 用式(21) 近似）"),
}


def _k01_model_values():
    m, _ = KC.build_model("K01-spur")
    names = sorted(_MODEL_QTY)
    res = m.evaluate(names)
    if res.status != "ok":
        raise RuntimeError(f"K01 模型求值未完成：{res.status} {res.missing}")
    return {k: U.from_canonical(res.values[k], u) for k, u in _MODEL_QTY.items()}, m


def k01_strict_inputs():
    """K01 证据 + gearmath 模型可得的积分温度法输入（缺项保持 None）。返回 (inputs, sources)。"""
    mv, _ = _k01_model_values()
    d = KC.load("K01-spur")
    rep, com, txt = d["report"], d["com"], d["report_text"]
    src = {}

    def put(k, v, s):
        inp[k] = v
        src[k] = s
    inp = {}
    for k, mk in (("z1", "z_1"), ("z2", "z_2"), ("a", "a_w"), ("alpha_n", "alpha_n"), ("alpha_t", "alpha_t"),
                  ("alpha_wt", "alpha_wt"), ("beta", "beta"), ("beta_b", "beta_b"), ("d_a1", "da_1"), ("d_a2", "da_2"),
                  ("d_b1", "db_1"), ("d_b2", "db_2"), ("eps_beta", "eps_beta"), ("b", "b"), ("F_t", "F_t"), ("v", "v"),
                  ("K_A", "K_A"), ("K_v", "K_V"), ("K_Hbeta", "K_Hbeta"), ("K_Halpha", "K_Halpha")):
        put(k, mv[mk], f"gearmath K01 模型输出 {mk}")
    put("mesh_stiffness", mv["c_s"], "直齿取 c′：gearmath K01 模型 c_s（报告 [c'] 第 865 行）")
    put("C_a1", com["ZR[0].Ca"], "COM ZR[0].Ca（报告：仅跑合修缘）")
    put("C_a2", com["ZR[1].Ca"], "COM ZR[1].Ca")
    put("tolerance_class", rep["Q_grade_1"]["value"], "报告 Q-ISO 1328:2013 A6（两轮同级）")
    put("same_material", com["ZR[0].mat.E"] == com["ZR[1].mat.E"] and com["ZR[0].mat.ny"] == com["ZR[1].mat.ny"]
        and txt["material"]["text"] != "", "COM 两轮 E/ν 相同，报告材料 18CrNiMo7-6 两轮同")
    put("E", com["ZR[0].mat.E"], "COM ZR[0].mat.E")
    put("nu", com["ZR[0].mat.ny"], "COM ZR[0].mat.ny")
    put("lambda_M", None, "K01 未给")
    put("c_v", None, "K01 未给")
    put("material_XW", None, "K01 未给残余奥氏体含量")
    put("lubricant", "mineral" if "mineral" in txt["lubrication"]["text"] else None, f"报告润滑：{txt['lubrication']['text']}")
    put("eta_oil", None, "K01 未给油温下动力黏度（-21 未规定求法）")
    put("Ra1", rep["Ra_H"]["value"], "报告 [RAH] 齿面 Ra（单值，两轮同）")
    put("Ra2", rep["Ra_H"]["value"], "报告 [RAH] 齿面 Ra（单值，两轮同）")
    put("phi_E", None, "K01 未给跑合状态")
    put("theta_oil", rep["T_oil"]["value"], "报告油温")
    put("lubrication", "dip" if "oil bath" in txt["lubrication"]["text"] else None, "报告 'oil bath' → 浸油 XS=1,0")
    put("n_p", 1, "单级一对齿轮：小轮啮合齿轮数 1")
    put("driver", None, "K01 证据未记录主动轮")
    put("X_alphabeta_method", "A", "演示选择：式(14) 方法 A")
    put("theta_M_method", "C", "演示选择：6.1.6.4 方法 C")
    put("scuffing_test", "FZG_A8390", "演示选择：FZG A/8,3/90")
    put("nu_40", rep["nu_40"]["value"], "报告 ν40")
    put("T1T_or_load_stage", None, "K01 未给 FZG 载荷级")
    put("X_WT", 1.0, "ISO/TS 6336-21 6.2.3：FZG 试验 XWT = 1")
    return inp, src


def eta_oil_from_22(*, nu_40, nu_100, theta_oil):
    """跨部分借用 ISO/TS 6336-22 式(17)–(21)(16)：矿物油 ηoil（mPa·s）。"""
    rho15 = MP.rho_15_mineral(nu_40=nu_40)
    eta = MP.eta_dynamic(nu=MP.nu_theta(nu_40=nu_40, nu_100=nu_100, theta=theta_oil),
                         rho=MP.rho_theta(rho_15=rho15, theta=theta_oil))
    return eta * 1000.0


def k01_integral_demo(mode):
    """mode：'strict' | 'supplement'。返回 {"mode", "result", "sources", "supplement_used"}。"""
    if mode not in ("strict", "supplement"):
        raise ValueError("mode 应为 'strict' 或 'supplement'")
    inp, src = k01_strict_inputs()
    used = {}
    if mode == "supplement":
        d = KC.load("K01-spur")
        for k, (v, why) in SUPPLEMENT.items():
            if inp.get(k) is not None:
                continue
            if k == "eta_oil":
                v = eta_oil_from_22(nu_40=d["report"]["nu_40"]["value"], nu_100=d["report"]["nu_100"]["value"],
                                    theta_oil=d["report"]["T_oil"]["value"])
            inp[k] = v
            src[k] = "【演示补充】" + why
            used[k] = v
    return {"mode": mode, "result": SI.rate(inp), "sources": src, "supplement_used": used}


# =================================================================== KISSsoft v0.14 P3（K01–K05 原生油品/工况）适配
P3_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "kisssoft_v014"
P3_CASES = ("P3-K01-spur", "P3-K02-helical", "P3-K03-premachining", "P3-K04-EV-stage1", "P3-K05-EV-stage2")
# KISSsoft 的 XWrelT（ZP[0].XWrelT）是式(47) 的实际输入；残余奥氏体含量不在证据中 → 按 XWrelT 输出值选表4 行（输入对齐，非独立证据）
P3_MATERIAL_XW = {"P3-K01-spur": "case_carburized_austenite_10_20", "P3-K02-helical": "nitrided_bath_gas",
                  "P3-K03-premachining": "case_carburized_austenite_10_20",
                  "P3-K04-EV-stage1": "case_carburized_austenite_10_20", "P3-K05-EV-stage2": "case_carburized_austenite_10_20"}
# 精度等级：报告 A6/A6、6/6；K03 为 A6/A7 混合，KISSsoft 未按"劣于 6 级取 XCa=1"处理 → 取 6（输入对齐）
P3_TOLERANCE_CLASS = {c: 6 for c in P3_CASES}


def load_p3(case):
    if case not in P3_CASES:
        raise ValueError(f"未知 P3 案例 {case!r}")
    return json.loads((P3_DIR / f"{case}.json").read_text(encoding="utf-8"))


def _p3_ca_actual(d):
    """报告 [Ca L/R]（最终加工信息节）：小轮 L、R、大轮 L、R → (Ca1, Ca2)。"""
    nums = [float(x) for x in re.findall(r"[0-9]+(?:\.[0-9]+)?", d["inputs"]["Ca_LR_text"]["v"])]
    if len(nums) != 4 or nums[0] != nums[1] or nums[2] != nums[3]:
        raise ValueError(f"{d['id']}：无法解析或左右齿面 Ca 不同 {nums}")
    return nums[0], nums[2]


def p3_integral_inputs(case, *, t1t, ca_route):
    """P3 案例 → scuffing_integral.rate() 输入（全部来自 data/kisssoft_v014 的 KISSsoft 实际输入；ηoil 由本库 -22 式计算）。

    t1t：'figure7'（图7 标注值，LS 3..12）| 'eq50'（式(50) 近似）| {'T1T': N·m}（显式）。
    ca_route：'kisssoft'（报告"Ca 按最优取"=1 时进入式(33) 的 Ca = Ceff，否则用实际 Ca）| 'standard'（一律实际 Ca，式(34)–(37)）。
    返回 (inputs, notes)：notes 为逐项来源/对齐说明。"""
    d = load_p3(case)
    I = {k: x["v"] for k, x in d["inputs"].items()}
    helical = I["beta"] != 0.0
    notes = {}
    inp = {k: I[k] for k in ("z1", "z2", "a", "alpha_n", "alpha_t", "alpha_wt", "beta", "beta_b", "d_a1", "d_a2",
                             "d_b1", "d_b2", "eps_beta", "F_t", "v", "K_A", "K_v", "K_Hbeta", "K_Halpha", "Ra1",
                             "Ra2", "nu_40")}
    inp["b"] = I["b_min"]
    notes["b"] = "ZP[0].bMin（-21 6.1.13：两轮齿宽不同取小者；KISSsoft beff 同）"
    inp["mesh_stiffness"] = I["c_gamma_alpha"] if helical else I["c_prime"]
    notes["mesh_stiffness"] = "斜齿 cγα（ZP[0].KV.cg，式(39)）" if helical else "直齿 c′（ZP[0].KV.cStr，式(38)）"
    ca1, ca2 = _p3_ca_actual(d)
    if ca_route == "kisssoft" and I["Ca_taken_as_optimal"] == [1, 1]:
        inp["C_a1"] = inp["C_a2"] = I["C_eff"]
        notes["C_a"] = "KISSsoft 选项'Ca 按最优取'=1：进入式(33) 的 Ca = Ceff（ZP[0].Ceff）；非 -21 式(34)–(37) 路径"
    elif ca_route in ("kisssoft", "standard"):
        inp["C_a1"], inp["C_a2"] = ca1, ca2
        notes["C_a"] = "报告 [Ca L/R] 实际修缘量，按式(34)–(37) 选取"
    else:
        raise ValueError("ca_route 应为 'kisssoft' 或 'standard'")
    inp["tolerance_class"] = P3_TOLERANCE_CLASS[case]
    notes["tolerance_class"] = f"报告精度 {I['accuracy_grade']} → 6（见 P3_TOLERANCE_CLASS 说明）"
    inp["driver"] = I["driver"]
    notes["driver"] = "报告 Gear driving (+)/driven (-)：小轮 +"
    inp.update(same_material=I["E1"] == I["E2"] and I["nu1"] == I["nu2"] and I["B_M1"] == I["B_M2"],
               E=I["E1"], nu=I["nu1"], B_M=I["B_M1"], lambda_M=None, c_v=None)
    notes["B_M"] = "ZR[0].BM（KISSsoft 热接触系数；λM、cv 未导出，式(13) 不用）"
    notes["same_material"] = ("两轮 E、ν、BM 相同即按同材料（K02/K03 牌号不同但性能参数相同：式(10) 在 BM1=BM2、"
                              "E/ν 相同时与 Γ 无关，退化为式(12)）")
    inp["material_XW"], inp["X_WT"] = P3_MATERIAL_XW[case], 1.0
    notes["material_XW"] = f"对齐 KISSsoft XWrelT={I['X_WrelT']}（表4 行选择不是独立证据）"
    if "Mineral" not in I["lubricant_base"]:
        raise ValueError(f"{case}：润滑油基础 {I['lubricant_base']!r} 未映射")
    inp["lubricant"] = "mineral"
    inp["eta_oil"] = MP.eta_dynamic(nu=MP.nu_theta(nu_40=I["nu_40"], nu_100=I["nu_100"], theta=I["theta_oil"]),
                                    rho=MP.rho_theta(rho_15=I["rho_15"] * 1000.0, theta=I["theta_oil"])) * 1000.0
    notes["eta_oil"] = "本库 ISO/TS 6336-22 式(17)–(20)(16)：ν40、ν100、数据表 ρ15（ZS.Oil.roOil）在 θoil 处（跨部分借用）"
    if I["scoring_runin"] != 1.0:
        raise ValueError(f"{case}：RechSt.Scoring_RunIn={I['scoring_runin']} 未映射")
    inp["phi_E"] = 1.0
    notes["phi_E"] = "RechSt.Scoring_RunIn=1（报告'well run in'，XE=1）→ φE = 1"
    inp["theta_oil"] = I["theta_oil"]
    if I["lubrication_type"] != "Oil bath lubrication":
        raise ValueError(f"{case}：润滑方式 {I['lubrication_type']!r} 未映射")
    inp["lubrication"], inp["n_p"] = "dip", 1
    notes["lubrication"] = "报告 Oil bath → 浸油 XS=1,0；单对啮合 np=1（KISSsoft Xmp=1）"
    inp.update(X_alphabeta_method="A", theta_M_method="C", scuffing_test="FZG_A8390")
    stage = int(I["fzg_load_stage"])
    if t1t == "figure7":
        inp["T1T_or_load_stage"] = {"load_stage_fig7": stage}
    elif t1t == "eq50":
        inp["T1T_or_load_stage"] = {"load_stage": stage}
    elif isinstance(t1t, dict) and set(t1t) == {"T1T"}:
        inp["T1T_or_load_stage"] = dict(t1t)
    else:
        raise ValueError("t1t 应为 'figure7'、'eq50' 或 {'T1T': N·m}")
    notes["T1T"] = f"FZG A/8,3/90 载荷级 {stage}（ZS.Oil.FZGtestA），路线 {t1t}"
    return inp, notes


def p3_flash_inputs(case, *, ra_route):
    """P3 案例 → scuffing_flash.rate() 输入（-20 骨架只支持外啮合直齿未修形；斜齿由 rate() 阻断）。

    ra_route：'as_manufactured'（报告 Ra）| 'runin_60pct'（-20 式(26) 下注"充分跑合约降至 60 %"，Ra×0,6）。
    v0.15 说明：KISSsoft 有效 Ra 字段仍未导出，但 M39-K01-runin0（RechSt.Scoring_RunIn=0）μm 与 'as_manufactured' 逐位一致，
    且 RunIn 1/0 两运行 μm 之比 = 0,6^−0,25（逐位）→ "KISSsoft 跑合时按 0,6·Ra"已由开关对照证实为其实现，不再只是推断；
    0,6 来自标准下注"约 60 %"，属 KISSsoft 对"约"的取值，P3 跑合案例仍以推断路线比较（不作 E5 依据）。θS 用 KISSsoft 值显式输入（式(72) 所需 θMT、θflmaxT 未导出）。"""
    d = load_p3(case)
    I = {k: x["v"] for k, x in d["inputs"].items()}
    o = d["outputs"]["iso6336_20"]
    f = {"as_manufactured": 1.0, "runin_60pct": 0.6}[ra_route]
    inp, _ = p3_integral_inputs(case, t1t="eq50", ca_route="standard")
    return {"z1": I["z1"], "z2": I["z2"], "a": I["a"], "alpha_t": I["alpha_t"], "alpha_wt": I["alpha_wt"],
            "beta": I["beta"], "d1": I["d1"], "d2": I["d2"], "d_a1": I["d_a1"], "d_a2": I["d_a2"], "b": I["b_min"],
            "F_t": I["F_t"], "v": I["v"], "n1": I["n1"], "K_A": I["K_A"], "K_v": I["K_v"], "K_Hbeta": I["K_Hbeta"],
            "K_Halpha": I["K_Halpha"], "K_mp": 1.0, "c_gamma": I["c_gamma_alpha"], "C_a1": inp["C_a1"],
            "C_a2": inp["C_a2"], "driver": I["driver"], "tolerance_class": P3_TOLERANCE_CLASS[case],
            "profile_modified": not I["profile_modification"].startswith("none"),
            "X_M": SI.X_M_from_B_M(E=I["E1"], nu=I["nu1"], B_M=I["B_M1"]),
            "mu_method": "C", "lubricant": "mineral", "eta_oil": inp["eta_oil"], "Ra1": I["Ra1"] * f,
            "Ra2": I["Ra2"] * f, "bulk_method": "rough_eq20", "lubrication": "dip", "n_p": 1,
            "theta_oil": I["theta_oil"], "theta_S_method": "explicit", "theta_S_explicit": o["theta_S"]["v"]}


def p3_micropitting_inputs(case, *, p_dyn_source):
    """K01/K02（七点有效）→ micropitting.rate() 输入。θfl,Y 与 θM 用 KISSsoft 值（显式，隔离膜厚链）。

    p_dyn_source：'kisssoft'（KISSsoft pdyn,Y）| 'method_B_spur_unmodified'（本库式(24)–(26)(44)–(46)，仅直齿）。"""
    d = load_p3(case)
    mp = d["outputs"]["iso6336_22"]
    if not mp["valid"]:
        raise ValueError(f"{case}：{mp['reason']}")
    I = {k: x["v"] for k, x in d["inputs"].items()}
    pts = mp["points"]
    if p_dyn_source == "kisssoft":
        pdyn = {p: pts[p]["phidynYB"] for p in MP.POINTS}
    elif p_dyn_source == "method_B_spur_unmodified":
        er = MP.E_r(E1=I["E1"], E2=I["E2"], nu1=I["nu1"], nu2=I["nu2"])
        res = MP.p_dyn_points_method_B_spur(
            profile="unmodified", g_alpha=I["g_alpha"], p_et=I["p_et"], d_a1=I["d_a1"], d_a2=I["d_a2"], d_b1=I["d_b1"],
            d_b2=I["d_b2"], alpha_wt=I["alpha_wt"], alpha_t=I["alpha_t"], F_t=I["F_t"], b=I["b_min"], E_r=er,
            K_A=I["K_A"], K_gamma=I["K_gamma"], K_v=I["K_v"], K_Halpha=I["K_Halpha"], K_Hbeta=I["K_Hbeta"],
            eps_alpha=I["eps_alpha"], beta_b=I["beta_b"], tolerance_class=P3_TOLERANCE_CLASS[case])
        pdyn = {p: res[p]["p_dyn"] for p in MP.POINTS}
    else:
        raise ValueError("p_dyn_source 应为 'kisssoft' 或 'method_B_spur_unmodified'")
    inp = {"n1": I["n1"], "u": I["z2"] / I["z1"], "d_w1": I["d_w1"], "d_w2": I["d_w2"], "d_a1": I["d_a1"],
           "d_a2": I["d_a2"], "d_b1": I["d_b1"], "d_b2": I["d_b2"], "alpha_wt": I["alpha_wt"], "beta_b": I["beta_b"],
           "g_alpha": I["g_alpha"], "p_et": I["p_et"], "E1": I["E1"], "E2": I["E2"], "nu1": I["nu1"], "nu2": I["nu2"],
           "oil_type": "mineral", "nu_40": I["nu_40"], "nu_100": I["nu_100"], "density": "rho_15",
           "rho_15": I["rho_15"] * 1000.0, "theta_M": mp["scalars"]["theta_M"]["v"], "Ra1": I["Ra1"], "Ra2": I["Ra2"],
           "alpha_38_source": "eq9_11", "lambda_GFP_source": "A1", "material_WW": "case_carburized_austenite_lt25",
           "lambda_GFT": mp["scalars"]["lambda_GFT"]["v"],
           "local": {p: {"p_dyn": pdyn[p], "theta_fl": pts[p]["Theta_flY"]} for p in MP.POINTS}}
    return inp


def summary(demo):
    r = demo["result"]
    if r["status"] != "ok":
        return {"status": r["status"], "missing": r.get("missing"), "unconfirmed": r.get("unconfirmed")}
    keys = ("mu_mC", "X_M", "X_BE", "X_alphabeta", "X_Q", "X_Ca", "X_eps", "X_E", "K_Bgamma", "w_Bt", "theta_flaE",
            "theta_flaint", "theta_M", "theta_int", "T1T", "theta_MT", "theta_flaintT", "theta_intS", "S_intS")
    return {k: r[k] for k in keys if k in r}


if __name__ == "__main__":      # pragma: no cover
    for md in ("strict", "supplement"):
        dm = k01_integral_demo(md)
        print(md, summary(dm))
    print("eta_oil(80°C) mPa·s =", eta_oil_from_22(nu_40=220.0, nu_100=19.0, theta_oil=80.0), math.nan)
