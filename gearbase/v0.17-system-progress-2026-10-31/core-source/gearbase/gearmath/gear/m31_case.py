"""从 M31 案例与收据（data/m31/）装配数学模型：输入只来自数据文件，不在代码里写数。

案例（gears.benchmark.case/1）提供几何、刀具、材料、工况；收据（python-gearbox）提供尚未公式化的证据系数。
证据系数逐个公式化后（M33），从 RECEIPT_EVIDENCE 中删除对应行即可。
"""
from __future__ import annotations

import json
import pathlib
import re

from .dynamic import set_dynamic_inputs
from .rating import SELECTOR_REQUIRES, pair_model

DATA = pathlib.Path(__file__).resolve().parents[2] / "data" / "m31"

# 模型输入名 → 收据字段（section, key）
RECEIPT_EVIDENCE = {
    "K_V": ("contact", "dynamic_factor"), "K_Hbeta": ("contact", "face_load_factor"),
    "K_Halpha": ("contact", "transverse_load_factor"), "K_Falpha": ("root", "transverse_load_factor"),
    "Z_L": ("contact", "lubricant_factor"), "Z_V": ("contact", "velocity_factor"), "Z_R": ("contact", "roughness_factor"),
    "Z_W": ("contact", "work_hardening_factor_pinion"), "Z_X": ("contact", "size_factor"),
    "Z_NT_1": ("contact", "life_factor_pinion"), "Z_NT_2": ("contact", "life_factor_wheel"),
    "Y_ST": ("root", "stress_correction_factor_reference"),
    "Y_NT_1": ("root", "life_factor_pinion"), "Y_NT_2": ("root", "life_factor_wheel"),
    "Y_drelT_1": ("root", "relative_notch_sensitivity_pinion"), "Y_drelT_2": ("root", "relative_notch_sensitivity_wheel"),
    "Y_RrelT_1": ("root", "relative_surface_factor_pinion"), "Y_RrelT_2": ("root", "relative_surface_factor_wheel"),
    "Y_X": ("root", "size_factor_pinion"), "Y_B": ("root", "rim_thickness_factor_pinion"), "Y_DT": ("root", "deep_tooth_factor"),
}


# M31 案例未声明 ISO 21771 版次；装配时显式补充并记录来源（可由调用方覆盖）
EDITION_SUPPLEMENT = {"ISO 21771": "2007"}


def load(rel):
    if isinstance(rel, dict):          # 允许直接传入已解析的案例/收据（测试、工具调用）
        return rel
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


def parse_editions(text):
    """"ISO6336-1/-2/-3:2019" → {"ISO 6336-1": "2019", "ISO 6336-2": "2019", "ISO 6336-3": "2019"}；无法解析返回 {}。"""
    m = re.fullmatch(r"\s*(ISO)\s*(\d+)((?:/?-\d+)+):(\d{4})\s*", text or "")
    if not m:
        return {}
    return {f"{m.group(1)} {m.group(2)}{p}": m.group(4) for p in re.findall(r"-\d+", m.group(3))}


class _Setter:
    """缺字段时不设置该输入（交给 rate 以 blocked_missing_inputs 报告），不抛 KeyError、不用默认值。"""

    def __init__(self, model):
        self.m, self.absent = model, []

    def __call__(self, name, get, unit, prov, src):
        try:
            v = get()
        except (KeyError, IndexError, TypeError):
            v = None
        if v is None:
            self.absent.append(name)
        else:
            self.m.set(name, v, unit, prov, src)
        return self


# M31 对拍契约（复现 python-gearbox@c005e4d 收据）的口径选择；均为标准允许的选项，来源记入模型
M31_CONTRACT_SELECTORS = {
    "method.m_red": ("eq30", "M31 对拍契约：python-gearbox 用 ISO 6336-1:2019 式(30)"),
    "method.f_pb": ("fpt", "M31 对拍契约：表2 以 fpt 代替 fpb（python-gearbox 取 max(fpt, ffα)，C001 两者相等，见接续文档）"),
    "method.K_Hbeta": ("external", "M31 对拍契约：K_Hβ 取收据值（案例无方法C 所需轴系输入）"),
    "method.K_Halpha": ("external", "M31 对拍契约：K_Hα/K_Fα 取收据值"),
    "method.root_shift": ("nominal", "M31 对拍契约：案例无齿厚公差，python-gearbox 用名义变位"),
}


def case_selectors(op, selectors=None):
    """方法选择器的取值与来源。K_V：调用方未给 selectors 时，案例 dynamic_factor_method = METHOD_B 且无实测值 → B；
    调用方给出 selectors（含空 {}）时 K_V 只取调用方的值。其余选择器取 M31 对拍契约值（来源记入），调用方可覆盖；
    method.m_red/f_pb 只在 K_V=B 时加入。不能确定的选择器留空（模型求值阻断，列出可选项），不用隐含默认值。"""
    sel, src = {}, {}
    if selectors is None and op.get("dynamic_factor_method") == "METHOD_B" and op.get("measured_dynamic_factor") is None:
        sel["method.K_V"] = "B"
        src["method.K_V"] = "M31 案例 engineering.operating.dynamic_factor_method = METHOD_B（案例数据）"
    sel.update(selectors or {})
    src.update({k: "调用方指定" for k in (selectors or {})})
    for k, (v, why) in M31_CONTRACT_SELECTORS.items():
        dep = SELECTOR_REQUIRES.get(k)
        if k in sel or (dep and sel.get(dep[0]) not in (None, dep[1])):
            continue
        sel[k], src[k] = v, why
    return sel, src


def stage_model(case="golden/C001/derived-candidate.json", receipt="golden/C001/gear-rating.json", stage=0, model=None,
                editions=None, selectors=None):
    """装配 M31 案例的一级模型。selectors：如 {"method.K_V": "B" | "external"}；
    external = 回放收据（K_V 取自收据，evidence）；B = 方法B 公式（K_V 派生）。
    不传时由案例数据决定（见 case_selectors，来源记入模型）；案例数据也不能确定时返回的模型求值阻断
    （blocked_missing_selectors），不使用默认方法。"""
    c, r = load(case), load(receipt)
    st, rs = c["stages"][stage], r["stages"][stage]
    if stage != 0:
        raise NotImplementedError("原型只装配第一级；后续级的输入转速与扭矩需由传动链公式（L2）推出")
    if st.get("module_basis") != "normal" or st.get("kind") != "spur":
        raise NotImplementedError(f"原型只装配法向模数直齿级，收到 {st.get('kind')}/{st.get('module_basis')}")
    eng = c.get("engineering", {})
    tool, mat, op = eng.get("tool", {}), eng.get("material", {}), eng.get("operating", {})
    src = f"M31 {case if isinstance(case, str) else '案例'} stages[{stage}]"
    sel, sel_src = case_selectors(op, selectors)
    m = model or pair_model(selectors=sel, selector_sources=sel_src)
    kv = m.selectors.get("method.K_V")
    m.set_editions(parse_editions(eng.get("standard")), "M31 engineering.standard")
    m.set_editions({k: v for k, v in EDITION_SUPPLEMENT.items() if k not in m.editions},
                   "装配补充：M31 案例未声明该分册版次，按本公式库版次")
    if editions:
        m.set_editions(editions, "调用方指定")
    put = _Setter(m)
    put("z_1", lambda: st["driver_teeth"], "1", "user", src)("z_2", lambda: st["driven_teeth"], "1", "user", src)
    put("m_n", lambda: st["module_mm"], "mm", "user", src)("alpha_n", lambda: st["pressure_angle_deg"], "deg", "user", src)
    m.set("beta", 0, "deg", "user", src + "（直齿）")
    put("b", lambda: st["face_width_mm"], "mm", "user", src)
    put("x_1", lambda: st["profile_shift_driver"], "1", "user", src)("x_2", lambda: st["profile_shift_driven"], "1", "user", src)
    put("haP", lambda: tool["addendum_coefficient"], "1", "user", "M31 engineering.tool")
    put("hfP", lambda: tool["dedendum_coefficient"], "1", "user", "M31 engineering.tool")
    put("rhofP", lambda: tool["root_fillet_radius_coefficient"], "1", "user", "M31 engineering.tool")
    put("T_1", lambda: c["input"]["torque_Nm"], "N*m", "user", "M31 input")
    put("n_1", lambda: c["input"]["speed_rpm"], "rpm", "user", "M31 input")
    put("E", lambda: mat["elastic_modulus_MPa"], "MPa", "evidence", "M31 engineering.material")
    put("nu", lambda: mat["poissons_ratio"], "1", "evidence", "M31 engineering.material")
    for i in (1, 2):
        put(f"sigma_Hlim_{i}", lambda: mat["contact_stress_limit_MPa"], "MPa", "assumption", "M31 engineering.material（假设材料）")
        put(f"sigma_Flim_{i}", lambda: mat["bending_stress_limit_MPa"], "MPa", "assumption", "M31 engineering.material（假设材料）")
    put("K_A", lambda: op["application_factor"], "1", "user", "M31 engineering.operating")
    for name, (sec, key) in RECEIPT_EVIDENCE.items():
        if name in m.formulas or (name == "K_V" and kv != "external"):
            continue                 # K_V：B 路径为派生量；未选择时不预填，避免暗示默认
        put(name, lambda: rs[sec][key], "1", "evidence", f"M31 {receipt if isinstance(receipt, str) else '收据'} stages[{stage}].{sec}.{key}（python-gearbox）")
    put("S_Hmin", lambda: op["min_safety_pitting"], "1", "user", "M31 engineering.operating")
    put("S_Fmin", lambda: op["min_safety_bending"], "1", "user", "M31 engineering.operating")
    m.set("eps_alpha_min", 1.2, "1", "user", "设计规则（示例）")
    if kv == "B":
        set_dynamic_inputs(m, c, stage, case if isinstance(case, str) else "案例")
    return m, rs
