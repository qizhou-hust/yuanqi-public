"""TR30 例5–8 全强度链诊断（K/Z/Y → σH/σF → 许用 → SH/SF）。

与例1–4 同一套公式图：rating.pair_model 选择器特化 + tr30_geometry 补丁 + tr30_examples58.build_probe
的输入几何，再按每例原表输入声明选择分支（逐轮材料、内齿、双斜齿、残余凸台）。从不读取 raw_outputs
建图；原表输出只在建模后比较。新增的标准公式在 material_branches / protuberance / double_helical /
internal_gear 模块，各自注明条款、式号、PDF 页。

比较判据：原表为舍入显示值（TR30 4.2.14，PDF14），采用显示量子规则
|Δ| ≤ q/2 + min(0.01, 0.005·|r|)，q 为原表显示末位单位；旧的 4.2.15 严格双门另列诊断列。
本诊断从不授予验收：accepted=false、evidence_level=not_assessed。
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import re

from ..kernel.graph import Formula, InputSpec, Model
from ..kernel import units as U
from .rating import pair_model, LIBRARY_EDITIONS
from .inputs import full_input_table, input_specs
from .dynamic import CONSTANTS
from .load_distribution import LD_CONSTANTS, _y_group
from .life_factors import LIFE_CYCLES, CYCLE_INPUTS
from .root_factors import ROOT_AUX_FACTORS, ROOT_AUX_INPUTS, ROOT_FACTOR_INPUTS, set_root_constants
from .tr30_geometry import patch_tr30_geometry, TR30_GEOMETRY_INPUTS
from .tr30_examples58 import build_probe, load_cases
from .surface_factors import (SURFACE_REFERENCE_ENDPOINTS, SURFACE_PER_GEAR_FACTORS, SURFACE_INPUTS,
                              PER_GEAR_SURFACE_INPUTS, CONTACT_STRESS_NO_PITTING, CONTACT_STRESS_INPUTS,
                              set_surface_constants, ZV_VELOCITY_VARIANTS)
from .contact_factors import ZBD_VARIANTS, ZBD_INPUTS, set_contact_method_evidence
from .material_branches import gear_branch, parse_hardness, RAW_MATERIAL, BRANCH_INPUTS
from .protuberance import protuberance_rack, PROTUBERANCE_INPUTS
from .double_helical import DOUBLE_HELICAL_FSH, double_helical_bh, DOUBLE_HELICAL_INPUTS
from .iso1328 import fhbeta5_formulas
from .tr30_shared import a6_root_form, a6_sap, FSH0, FSH0_DOUBLE_HELICAL, shaper_root_form, contact_path_formula
from . import internal_gear as IG

F, S = Formula, InputSpec
TR = "ISO/TR 6336-30:2022"


def _word(expr, old, new):
    return re.sub(r"\b" + re.escape(old) + r"\b", new, expr)


def _rows(case, field="raw_inputs"):
    return {r["key"]: r for r in case[field]}


def _num(raw, key, index=0):
    value = raw[key]["values"][index]
    if type(value) not in (int, float):
        raise ValueError(f"缺少独立数值输入 {key}[{index}]")
    return value


def _cite(row):
    c = row["citation"]
    return f"{c['source']} PDF {c['pdf_page']}: {c['location']}"


# 原表文字 → 方法码（只认原表声明）
HELIX_MOD = {"None (No. 1)": 1, "Helix + Crowning (No. 5)": 5}
ARRANGEMENT = {"a": 1, "b": 2}


RZ_SOURCES = {
    "ra_times_6": f"{TR} 4.2.7（PDF13/印8 原图已核）Rz = 6·Ra，由原表 Ra 计算",
    "printed_rz": f"{TR} 原表括号内印刷 Rz（显示值；例8 印 2,3，而 6·Ra = 2,28）",
}


def rz_discriminates(case):
    """原表括号 Rz 与 6·Ra 不完全相等（只在显示精度内一致）时，Rz 来源须显式选择。"""
    raw = _rows(case)
    return any(abs(_num(raw, "Rz_H", i) - 6*_num(raw, "Ra_H", i)) > 1e-9 for i in (0, 1))


FSH0_BASES = {
    "total_width": "ISO 6336-1:2019 7.5.1（PDF58/印50）b=2b_B：specific load = F_m/b（总宽）",
    "per_helix": "ISO 6336-1:2019 式(60)（PDF65/印57）2F_m/b = F_m/b_B：specific load = F_m/b_B",
}


# 例8 凸台刀预加工+磨削的有效 dFf（显式选择器 method.d_Ff_protuberance，无默认）。用户决定 2026-10-30（第 7 项）：
# 同意把 protuberance.protuberance_dff_converged 数值包络接入主图。按 kernel.methods 的设计，数值方法结果以输入节点
# 进入公式图：provenance="derived"（证据等级上限 E1，见 kernel.evidence.PROVENANCE_CAP），收敛记录随模型保存在
# model.tr30_numerical_nodes。不选时原路径不变（d_Ff 未实现，啮合线前提退回显式 assumption）。
PROTUBERANCE_DFF_METHODS = {
    "numerical_envelope": "protuberance.protuberance_dff_converged：ISO 6336-3 式(26) 预加工圆角 + TR30 A.6 展成原理 + "
                          "ISO 21771-1 式(249)(250) xEV（数值包络，三级加密收敛；dFf 定义原图无法确认）",
}


def protuberance_dff_inputs(raw, i, xE, xEV):
    """凸台 dFf 数值方法的输入（全部取原表行与图内 xE/xEV；缺项即 KeyError/ValueError，不设默认）。"""
    p = {"z": _num(raw, "z", i-1), "m_n": _num(raw, "m_n"), "alpha_n": math.radians(_num(raw, "alpha_n")),
         "beta": math.radians(_num(raw, "beta")), "hfP_cut": _num(raw, "h_fP_pre", i-1),
         "rhofP": _num(raw, "rho_fP", i-1), "pr_cut": _num(raw, "pr", i-1),
         "alpha_pr": math.radians(_num(raw, "tool_pr_angle", i-1)), "x_cut": xEV, "x_fin": xE}
    if abs((p["x_cut"] - p["x_fin"]) * p["m_n"] * math.sin(p["alpha_n"]) - _num(raw, "q", i-1)) > 1e-9:
        raise ValueError("xEV−xE 与原表 q 不一致")
    return p


def build_model(case, *, zv_velocity, hardness_conversion=None, rz_source=None, fsh0_basis=None, protuberance_dff=None,
                _contact_path=None):
    """由原表输入建全强度图。hardness_conversion：'ISO18265_A1_linear'（ISO 18265 表A.1）、'HB_div_0.95_assumption'（近似，仅对比）
    或 'HV_external_readback'（HV 作为外部证据输入 mat_hv_ext_i，见 material_branches；仅三方对拍用，非正式口径）。

    rz_source（齿面 Rz 来源，显式选择器 method.Rz_H_source，无默认）：'ra_times_6'（TR30 4.2.7）或
    'printed_rz'（原表括号印刷值）。两者相同（例5–7）时可不选；不同（例8：2,28 / 2,3）时不选即阻断。

    fsh0_basis（双斜齿 fsh0 的 specific load 口径，显式选择器 method.f_sh0_specific_load，无默认）：
    'total_width'（F_m/b）或 'per_helix'（F_m/b_B），见 tr30_shared.FSH0_DOUBLE_HELICAL。不选则双斜齿不给 fsh0。

    啮合线不缩短前提（ISO 6336-2 6.3）：两轮 dFf 均可在图内计算时，由 A.6 dFf/dNf 公式判定
    （tr30_shared.contact_path_formula）；否则（例8 凸台 dFf 未实现）退回显式 assumption 并在
    model.tr30_premise_audit 记录原因。_contact_path 仅供内部两遍构建使用。

    protuberance_dff（显式选择器 method.d_Ff_protuberance，无默认）：'numerical_envelope' 时，残余凸台轮的 d_Ff_i 由
    数值包络给出并以 derived 输入接入主图（见 PROTUBERANCE_DFF_METHODS）；此时 A.6 dNf 干涉核查与啮合线前提可在图内判定。
    """
    if _contact_path is None:
        first = build_model(case, zv_velocity=zv_velocity, hardness_conversion=hardness_conversion,
                            rz_source=rz_source, fsh0_basis=fsh0_basis, protuberance_dff=protuberance_dff,
                            _contact_path="A6_formula")
        if "contact_path_not_shortened" in first.formulas:
            check = first.evaluate(["contact_path_not_shortened"])
            if check.status == "ok":
                return first
            reason = f"A.6 判定不可用：{check.status} {check.domain_violations or check.errors}"
        else:
            reason = "两轮 dFf 未全部实现（如例8 凸台），A.6 判定不可用"
        second = build_model(case, zv_velocity=zv_velocity, hardness_conversion=hardness_conversion,
                             rz_source=rz_source, fsh0_basis=fsh0_basis, protuberance_dff=protuberance_dff,
                             _contact_path="assumption")
        second.tr30_premise_audit["contact_path_not_shortened"]["fallback_reason"] = reason
        return second
    if type(case) is int:
        case = next(c for c in load_cases() if c["example_number"] == case)
    raw = _rows(case)
    number = case["example_number"]
    if raw["K_V_method"]["values"] != ["Method B"] or raw["K_Hbeta_method"]["values"] != ["Method C"]:
        raise NotImplementedError("需原表显式选择 K_V 方法B / K_Hβ 方法C")
    if raw["blank_type"]["values"] != ["Solid", "Solid"] or raw["reverse_bending"]["values"] != ["No", "No"]:
        raise NotImplementedError("仅支持原表声明的实心轮坯、无反向弯曲")
    if raw["shot_peen"]["values"] != ["No", "No"]:
        raise NotImplementedError("喷丸分支未实现")
    internal = min(raw["z"]["values"]) < 0
    double = "double" in " ".join(str(v) for v in raw["hand"]["values"]).lower()
    beta = _num(raw, "beta")
    if beta == 0:
        contact = "spur"
    else:
        label = raw["f_ZCa_input"]["values"][0]
        if label != "manufacturers experience":
            raise NotImplementedError(f"未映射的 fZCa 声明 {label!r}")
        contact = "helical_manufacturer"
    pitting = raw["limited_pitting"]["values"]
    if len(set(pitting)) != 1:
        raise NotImplementedError("两轮点蚀许可声明不同的组合未实现")
    limited = pitting[0] == "Yes"
    if rz_source is not None and rz_source not in RZ_SOURCES:
        raise ValueError(f"rz_source 须为 {sorted(RZ_SOURCES)} 之一")
    if rz_source is None and rz_discriminates(case):
        raise ValueError("原表括号 Rz 与 TR30 4.2.7 的 6·Ra 不同：须显式选择 rz_source（ra_times_6 / printed_rz），不设默认")
    probe = build_probe(case)
    selectors = {"method.K_V": "B", "method.m_red": "exact", "method.f_pb": "fpbT",
                 "method.K_Hbeta": "C", "method.K_Halpha": "B", "method.root_shift": "generating"}
    fs = patch_tr30_geometry(pair_model(selectors=selectors).formulas.values(),
                             shift_source="span", mass_root="nominal_annex_a", kfbeta_root="nominal_annex_a")
    formulas = {f.output: f for f in fs}
    for f in probe.formulas.values():
        formulas[f.output] = f
    for name in probe.inputs:
        formulas.pop(name, None)
    # 例8 精加工余量 q_i（mm）与 ISO 6336-1 式(32) 轮坯质量比 q_i 同名：余量改名 q_fin_i，避免冲突
    probe_inputs = dict(probe.inputs)
    probe_specs = dict(probe.specs)
    for i in (1, 2):
        if f"xEV_{i}" in formulas:
            formulas[f"xEV_{i}"] = replace(formulas[f"xEV_{i}"], expr=_word(formulas[f"xEV_{i}"].expr, f"q_{i}", f"q_fin_{i}"))
            probe_inputs[f"q_fin_{i}"] = probe_inputs.pop(f"q_{i}")
            probe_specs[f"q_fin_{i}"] = replace(probe_specs.pop(f"q_{i}"), name=f"q_fin_{i}")
    # 逐轮基本齿条量与残余凸台（ISO 6336-3:2019 式(26)，s_pr=pr−q）
    formulas.pop("rack_E")
    for i in (1, 2):
        formulas[f"rack_E_{i}"] = protuberance_rack(i)
    for name, f in list(formulas.items()):
        expr = f.expr
        for i in (1, 2):
            if name.endswith(f"_{i}") and f.id.startswith("root."):
                for old, new in (("hfP", f"hfP_{i}"), ("rhofP", f"rhofP_{i}"), ("rack_E", f"rack_E_{i}")):
                    expr = _word(expr, old, new)
            if name in (f"bh_{i}", f"sigma_F_{i}"):
                expr = _word(expr, "b", f"b_{i}")
            if name == f"sigma_F_{i}":
                expr = _word(expr, "Y_B", f"Y_B_{i}")
            if name == f"sigma_FG_{i}":
                expr = _word(expr, "Y_X", f"Y_X_{i}")
            if name == f"sigma_HG_{i}":
                for q in ("Z_L", "Z_V", "Z_R", "Z_W", "Z_X"):
                    expr = _word(expr, q, f"{q}_{i}")
        if name == "C_B":
            expr = _word(expr, "hfP", "((hfP_1+hfP_2)/2)")
        formulas[name] = replace(f, expr=expr)
    formulas["b"] = F("tr58.b", "b", "mm", "b_eff",
                      f"{TR} 原表接触齿宽 b_eff（双斜齿为两半宽之和，ISO 6336-2:2019 5.1 b=2bB）")
    formulas["C_R"] = F("tr58.CR.solid", "C_R", "1", "1", "ISO 6336-1:2019 9.3.2 实心轮坯分支")
    for i in (1, 2):
        formulas[f"q_{i}"] = F(f"tr58.q.solid.{i}", f"q_{i}", "1", "0", "ISO 6336-1:2019 式(32)，原表声明实心轮坯")
    formulas["B_k"] = F("tr58.B_k.relief", "B_k", "1",
                        "where(Q_grade >= 6, 1, abs(1-c_s*min(C_a_1+C_f_2,C_a_2+C_f_1)/line_load))",
                        "ISO 6336-1:2019 式(17)，原表齿顶/齿根修缘与精度等级规则")
    formulas.pop("C_a", None)
    for stem, base in (("p", "f_pb"), ("f", "f_falpha")):
        for i in ("1", "2"):
            q = f"y_{stem}_{i}"
            formulas[q] = F(f"tr58.{q}", q, "um", _y_group(i, 160, 12800, 6400, .275, 22, 11, .075, 3, base),
                            "ISO 6336-1:2019 6.5.4 与 8.3.6.2 式(77)–(80)，逐轮材料组")
        formulas[f"y_{stem}"] = F(f"tr58.y_{stem}", f"y_{stem}", "um", f"(y_{stem}_1+y_{stem}_2)/2",
                                  "ISO 6336-1:2019 式(80) 两轮跑合量均值")
    # 两轮弹性模量不同：ISO 6336-2:2019 7.2 式(25)（一般式）与 ISO 6336-1:2019 9.3.2 c) 式(90)(91)
    formulas["Z_E"] = F("tr58.Z_E.general", "Z_E", "sqrt(MPa)",
                        "sqrt(1/(pi*((1-nu_1**2)/E_1+(1-nu_2**2)/E_2)))",
                        "ISO 6336-2:2019 第7章 式(24)（PDF25/印17 原图已核）：两轮 E、ν 可不同的一般式")
    formulas["E"] = F("tr58.E.pair", "E", "MPa", "2*E_1*E_2/(E_1+E_2)",
                      "ISO 6336-1:2019 9.3.2 c) 式(91)（PDF84/印76）：c′ 材料修正 E/E_St 中的 E")
    if double:
        formulas["f_sh"] = DOUBLE_HELICAL_FSH
        for i in (1, 2):
            formulas[f"bh_{i}"] = double_helical_bh(i)
    # 材料分支（逐轮）
    added, mat_specs, metas = [], [], {}
    for i in (1, 2):
        family = RAW_MATERIAL.get(raw["material"]["values"][i-1])
        if family is None:
            raise NotImplementedError(f"未支持的原表材料 {raw['material']['values'][i-1]!r}")
        value, scale = parse_hardness(raw["case_hardness"]["values"][i-1])
        fsi, spi, meta = gear_branch(i, family, raw["material_quality"]["values"][i-1], scale,
                                     limited_pitting=limited, znt_end=_num(raw, "Z_NT_end", i-1),
                                     ynt_end=_num(raw, "Y_NT_end", i-1), hardness_conversion=hardness_conversion)
        meta["hardness"] = value
        added += fsi
        mat_specs += spi
        metas[i] = meta
    added += LIFE_CYCLES + ROOT_AUX_FACTORS + SURFACE_REFERENCE_ENDPOINTS + SURFACE_PER_GEAR_FACTORS + ZBD_VARIANTS[contact]
    added += [F("tr58.surface_ref_material", "sigma_Hlim_surface", "MPa", "min(sigma_Hlim_1, sigma_Hlim_2)",
                "ISO 6336-2:2019 12.3.1（PDF33/印25 原图已核）：软硬配对时 Z_L/Z_V/Z_R 按较软材料确定；"
                "例5–8 中较软者即 σHlim 较小者（同材同硬时两者相同）"),
              F("tr58.YST", "Y_ST", "1", "2", "ISO 6336-3:2019 标准试验齿轮应力修正系数 YST=2.0")]
    for i in (1, 2):
        added.append(F(f"tr58.sigma_F0.{i}", f"sigma_F0_{i}", "MPa", f"F_t/(b_{i}*m_n)*Y_F_{i}*Y_S_{i}*Y_beta*Y_B_{i}*Y_DT",
                       "ISO 6336-3:2019 5.2 名义齿根应力"))
        for end in ("static", "ref"):
            added.append(F(f"tr58.ZW.{end}.{i}", f"Z_W_{end}_{i}", "1", "1",
                           f"{TR} 4.2.6 PDF14/印8：例5 大轮保守取 ZW2=1，其余两轮同为调质或表面硬化，ZW1,2=1"))
        nref = metas[i]["n_ref"]
        added += [F(f"tr58.Href.{i}", f"sigma_HG_ref_{i}", "MPa", f"sigma_Hlim_{i}*Z_L_ref*Z_V_ref*Z_R_ref*Z_W_ref_{i}*Z_X_{i}",
                    "ISO 6336-2:2019 5.4.4.3 参考端点"),
                  F(f"tr58.Hstatic.{i}", f"sigma_HG_static_{i}", "MPa", f"1.6*sigma_Hlim_{i}*Z_W_static_{i}",
                    "ISO 6336-2:2019 表5 静强度端点 ZNT=1.6 与式(57)"),
                  F(f"tr58.HP.{i}", f"sigma_HP_{i}", "MPa", f"sigma_HG_life_{i}/S_Hmin", "ISO 6336-2:2019 许用接触应力"),
                  F(f"tr58.FP.{i}", f"sigma_FP_{i}", "MPa", f"sigma_FG_{i}/S_Fmin", "ISO 6336-3:2019 许用齿根应力"),
                  F(f"tr58.Z_N.{i}", f"Z_N_{i}", "1", f"sigma_HG_life_{i}/sigma_HG_ref_{i}",
                    f"{TR} 4.2.5：整应力寿命系数 Z_N，与 Z_NT 区分"),
                  F(f"tr58.Y_N.{i}", f"Y_N_{i}", "1", f"Y_NT_{i}", "ISO 6336-3:2019 参考/长寿命段：Y_N 与 Y_NT 相同",
                    (f"N_L_{i} >= 3e6",))]
        if limited:
            # 曲线1：参考点 1e9 之后的长寿命段；1e9 以下的有限寿命整应力插值未实现（适用域阻断）
            added.append(F(f"tr58.HG.limited.{i}", f"sigma_HG_life_{i}", "MPa", f"sigma_HG_ref_{i}*Z_NT_long_{i}",
                           "ISO 6336-2:2019 表5 曲线1（允许有限点蚀）参考点 1e9 后长寿命段",
                           (f"N_L_{i} >= {nref}",)))
    if not limited:
        added += CONTACT_STRESS_NO_PITTING
    if internal:
        added += IG.internal_formulas(formulas, raw["z"]["values"][1])
    # fHβ5：ISO 1328-1:2013 式(10)+5.2.3 图内分档取整（TR30 4.2.10/4.2.11，双斜齿用 bB）
    added += fhbeta5_formulas((lambda i: "b_B") if double else (lambda i: f"b_{i}"),
                              width_note="；双斜齿按 TR30 4.2.11（PDF13/印8）用半齿宽 bB" if double else "")
    # fsh0：ISO 6336-1 表F.1；双斜齿 specific load 基准原文未定义 → 须显式选择口径，不选不给（not_implemented）
    if fsh0_basis is not None and fsh0_basis not in FSH0_BASES:
        raise ValueError(f"fsh0_basis 须为 {sorted(FSH0_BASES)} 之一")
    if not double:
        added.append(FSH0)
    elif fsh0_basis is not None:
        added.append(FSH0_DOUBLE_HELICAL[fsh0_basis])
    # 附录A A.6 dFf：只在原表声明满足 A.6 前提（外齿、齿条型刀具展成即有跨齿测量、无凸台 pr=s_pr=0）时给出
    if protuberance_dff is not None and protuberance_dff not in PROTUBERANCE_DFF_METHODS:
        raise ValueError(f"protuberance_dff 须为 {sorted(PROTUBERANCE_DFF_METHODS)} 之一")
    numerical_ff = []          # 由数值方法以 derived 输入接入主图的 d_Ff_i（轮号）
    for i in (1, 2):
        rack_generated = raw["z"]["values"][i-1] > 0 and raw["W_k"]["values"][i-1] is not None \
            and raw["z_0"]["values"][i-1] is None
        no_protuberance = raw["pr"]["values"][i-1] == 0 and raw["s_pr"]["values"][i-1] == 0
        if rack_generated and no_protuberance:
            added.append(a6_root_form(i))
        elif rack_generated and protuberance_dff is not None:
            numerical_ff.append(i)
        # 内齿插齿刀展成（直齿、无凸台）：A.6 SAP 原理用于加工啮合 + ISO 6336-3 式(37)(40)–(43)（tr30_shared.shaper_root_form）
        shaper_internal = raw["z"]["values"][i-1] < 0 and type(raw["z_0"]["values"][i-1]) in (int, float) \
            and beta == 0
        if shaper_internal and no_protuberance and internal:
            added.append(shaper_root_form(i))
    # A.6 dNf（带符号原式，内外啮合通用）：d_Fa 取 d_a，原表齿顶倒角声明须为 0
    if raw["tip_chamfer"]["values"] == [0.0, 0.0] or raw["tip_chamfer"]["values"] == [0, 0]:
        have_ff = {f.output for f in added} | {f"d_Ff_{i}" for i in numerical_ff}
        for i in (1, 2):
            check = f"d_Ff_{i}" in have_ff
            inner = raw["z"]["values"][i-1] < 0
            added.append(a6_sap(i, check_form=check, internal=inner,
                                note="d_Fa 取 d_a（原表齿顶倒角 0）" + (
                                    ("；内齿 |dNf|>|dFf| 为干涉，out_of_domain" if inner else "；|dNf|<|dFf| 为干涉，out_of_domain")
                                    if check else "；dFf 不在已核前提内未实现，干涉核查未做")))
    if protuberance_dff is not None and not numerical_ff:
        raise ValueError("protuberance_dff 只适用于齿条展成且有残余凸台（pr>0）的轮；本例不适用，不得选择")
    have = {f.output for f in added} | {f"d_Ff_{i}" for i in numerical_ff}
    if _contact_path == "A6_formula" and {"d_Ff_1", "d_Ff_2", "d_Nf_1", "d_Nf_2"} <= have:
        added.append(contact_path_formula(internal=tuple(z < 0 for z in raw["z"]["values"])))
    for f in added:
        formulas[f.output] = f
    # Z_V 速度口径（显式选择，不设默认）：用主库选择器 method.Z_V_velocity 的变体（surface_factors.ZV_VELOCITY_VARIANTS）。
    # ISO 6336-2:2019 式(47) 用 v_w；TR30 附录A A.9.2 式(47)（PDF59/印53 原图已核）用参考圆速度 v。
    if zv_velocity not in ZV_VELOCITY_VARIANTS:
        raise ValueError("zv_velocity 须显式选择 v_ref（TR30 A.9.2）或 v_w（ISO 6336-2 式47）")
    zv = ZV_VELOCITY_VARIANTS[zv_velocity]
    formulas[zv.output] = zv
    for i in (1, 2):
        fp = formulas[f"sigma_HG_{i}"]
        formulas[f"sigma_HG_factor_{i}"] = replace(fp, id=fp.id + ".factor_path", output=f"sigma_HG_factor_{i}")
        formulas[f"sigma_HG_{i}"] = F(f"tr58.HG.whole.{i}", f"sigma_HG_{i}", "MPa", f"sigma_HG_life_{i}",
                                      f"{TR} 4.2.5 PDF13/印7：安全系数用整应力寿命插值")
    specs = list(probe_specs.values()) + full_input_table() + TR30_GEOMETRY_INPUTS + mat_specs + BRANCH_INPUTS
    specs += CYCLE_INPUTS + ROOT_AUX_INPUTS + ROOT_FACTOR_INPUTS + SURFACE_INPUTS + PER_GEAR_SURFACE_INPUTS
    specs += CONTACT_STRESS_INPUTS + ZBD_INPUTS + PROTUBERANCE_INPUTS + DOUBLE_HELICAL_INPUTS + IG.INTERNAL_INPUTS
    for i in (1, 2):
        specs += [S(f"b_{i}", "mm", "原表逐轮齿宽", (f"b_{i} > 0",)),
                  S(f"rhofP_{i}", "1", "原表逐轮齿条齿根圆角系数", (f"rhofP_{i} >= 0",)),
                  S(f"C_a_{i}", "um", "原表齿顶修缘", (f"C_a_{i} >= 0",)),
                  S(f"E_{i}", "MPa", "原表弹性模量", (f"E_{i} > 0",)),
                  S(f"nu_{i}", "1", "原表泊松比", (f"nu_{i} > 0", f"nu_{i} < 0.5"))]
    for i in numerical_ff:
        specs.append(S(f"d_Ff_{i}", "mm", f"第{i}轮凸台刀预加工+磨削有效齿根形状圆（数值方法节点，method.d_Ff_protuberance）",
                       (f"d_Ff_{i} > 0",)))
    if internal:
        # 内齿：原表输入声明（带符号 z、a、da）覆盖基础表的外齿正值域
        specs += list(probe_specs.values())
    editions = {**LIBRARY_EDITIONS, "ISO/TR 6336-30": "2022", "ISO 6336-5": "2016", "ISO 1328-1": "2013"}
    if hardness_conversion == "ISO18265_A1_linear":
        editions["ISO 18265"] = "2013"
    model = Model(list(formulas.values()), inputs=input_specs(list(formulas.values()), specs), editions=editions)
    for name, value in probe_inputs.items():
        if name in model.specs:
            model.set(name, U.from_canonical(value.value, value.unit), value.unit, value.provenance, value.source)

    def put(name, value, unit, provenance="user", source=""):
        if name in model.specs:
            model.set(name, value, unit, provenance, source)

    def inp(name, key, index=0, unit=None):
        row = raw[key]
        value = _num(raw, key, index)
        chosen = unit or row["unit"]
        if row["unit"] == "h":
            value *= 3600
            chosen = "s"
        put(name, value, chosen, "user", _cite(row))

    for name, key in (("K_A", "K_A"), ("K_gamma", "K_gamma"), ("nu_40", "nu_40"), ("life_duration", "life_hours"),
                      ("l_sh", "bearing_span"), ("s_sh", "bearing_offset"), ("d_sh", "shaft_diameter"),
                      ("S_Hmin", "S_Hmin"), ("S_Fmin", "S_Fmin")):
        inp(name, key)
    put("nu", _num(raw, "nu"), "1", "user", _cite(raw["nu"]))
    if _num(raw, "nu", 0) != _num(raw, "nu", 1):
        raise NotImplementedError("两轮泊松比不同：C_B/c′ 的单一 ν 输入需另行处理")
    for i in (1, 2):
        for name, key in ((f"b_{i}", "b"), (f"rhofP_{i}", "rho_fP"), (f"C_a_{i}", "C_a"), (f"C_f_{i}", "C_f"),
                          (f"f_falpha_{i}", "f_falpha"), (f"f_Hbeta_{i}", "f_Hbeta"), (f"rho_{i}", "rho"),
                          (f"DT_grade_{i}", "Q"), (f"cycles_per_rev_{i}", "N_M"), (f"E_{i}", "E"), (f"nu_{i}", "nu")):
            if raw[key]["values"][i-1] is None and internal and i == 2:
                continue
            inp(name, key, i-1)
        put(f"hfP_{i}", _num(raw, "h_fP", i-1), "1", "user", _cite(raw["h_fP"]))
        put(f"mat_hardness_{i}", metas[i]["hardness"], "1", "user", _cite(raw["case_hardness"]))
        put(f"mat_group_{i}", metas[i]["mat_group"], "1", "user", f"原表材料 {metas[i]['family']}：ISO 6336-1 跑合材料组")
        put(f"d_inner_{i}", 0, "mm", "derived", "原表声明 Solid 实心轮坯")
        ra = _num(raw, "Ra_H", i-1)
        rz_printed = _num(raw, "Rz_H", i-1)
        if abs(rz_printed - 6*ra) > 0.05 + 1e-12:
            raise ValueError("原表括号 Rz 与 4.2.7 Rz=6Ra 在显示精度内不符")
        if rz_source == "printed_rz":
            put(f"Rz_H_{i}", rz_printed, "um", "user", f"{RZ_SOURCES['printed_rz']}；{_cite(raw['Rz_H'])}")
        else:
            put(f"Rz_H_{i}", 6*ra, "um", "derived", f"{TR} 4.2.7 Rz=6Ra；原表括号值 {rz_printed} 仅显示核对")
        raf = _num(raw, "Ra_F", i-1)
        put(f"Rz_F_{i}", 6*raf, "um", "derived", f"{TR} 4.2.7 Rz=6Ra（齿根）")
        put(f"root_surface_intact_{i}", 1, "1", "assumption", "ISO 6336-3 14.1 适用前提：无 >2Rz 划痕、无有害化学/氧化影响")
        ys = raw["yield_stress"]["values"][i-1]
        if type(ys) in (int, float):
            put(f"yield_strength_{i}", ys, "MPa", "user", _cite(raw["yield_stress"]))
        put(f"s_pr_{i}", _num(raw, "s_pr", i-1), "mm", "user", _cite(raw["s_pr"]))
        if abs(_num(raw, "s_pr", i-1) - (_num(raw, "pr", i-1) - _num(raw, "q", i-1))) > 1e-9:
            raise ValueError("原表 s_pr 与 pr−q 不一致（ISO 6336-3 式(26) 下注）")
    grades = raw["Q"]["values"]
    if not (all(q <= 5 for q in grades) or all(q >= 6 for q in grades)):
        raise NotImplementedError("两轮精度等级跨 B_k 分支，需逐轮实现")
    put("Q_grade", min(grades), "1", "derived", "两轮精度等级位于同一 B_k 分支")
    put("k_pb", .5 if raw["profile_compensated"]["values"] == ["Yes"] else 1, "1", "user", _cite(raw["profile_compensated"]))
    arrangement = ARRANGEMENT.get(raw["arrangement"]["values"][0])
    helix = HELIX_MOD.get(raw["helix_modification"]["values"][0])
    if arrangement is None or helix is None:
        raise NotImplementedError("未映射的布置或齿向修形声明")
    favourable = raw["favourable_contact"]["values"]
    if len(set(favourable)) != 1:
        raise NotImplementedError("两轮接触斑点声明不一致")
    for name, value, source in [("pinion_arrangement", arrangement, f"原表布置 {raw['arrangement']['values'][0]}"),
                                ("pinion_stiffening", 1, "原表实心小轮轴；图13 注a 按 d1/dsh 判定"),
                                ("B_star", 1.5 if double else 1, "ISO 6336-1:2019 式(59)/(60)：单一啮合功率路径"),
                                ("helix_mod", helix, f"原表 {raw['helix_modification']['values'][0]}"),
                                ("contact_favourable", 1 if favourable[0] == "Yes" else 0, "原表接触斑点位置"),
                                ("DT_profile_modified", 0, "原表齿廓修形不补偿变形")]:
        put(name, value, "1", "user", source)
    for name, value, source in [("surface_oil_mineral", 1, "按矿物油黏度关系；原表只给 ν40"),
                                ("surface_nu40_vi95", 1, "VI95 近似；原表只给 ν40"),
                                ("contact_path_not_shortened", 1, "无根切缩短有效啮合线（式17/18 前提）")]:
        put(name, value, "1", "assumption", source)   # 已由公式给出时 put 自动跳过（不在 specs）
    if not limited:
        put("contact_no_pitting_steel", 1, "1", "user", "原表 limited pitting=No，材料 St/V/Eh/IF")
    for name, value, unit, source in CONSTANTS + LD_CONSTANTS:
        put(name, value, unit, "standard_constant", source)
    for name, value, unit, source in (("root_MPa", 1, "MPa", "1 MPa 单位"), ("material_stress_unit", 1.0, "MPa", "式(2) 单位尺度")):
        put(name, value, unit, "standard_constant", source)
    set_root_constants(model)
    set_surface_constants(model)
    if double:
        put("b_B", _num(raw, "b_per_helix"), "mm", "user", _cite(raw["b_per_helix"]))
    if internal:
        IG.set_internal_inputs(model, raw, put)
    model.tr30_numerical_nodes = {}
    if numerical_ff:
        from .protuberance import protuberance_dff_converged
        for i in numerical_ff:
            xs = model.evaluate([f"xE_{i}", f"xEV_{i}"])
            if xs.status != "ok":
                raise ValueError(f"凸台 dFf 数值方法所需 xE/xEV 不可算：{xs.status}")
            p = protuberance_dff_inputs(raw, i, xs.values[f"xE_{i}"], xs.values[f"xEV_{i}"])
            result, detail = protuberance_dff_converged(p)
            put(f"d_Ff_{i}", result.value, "mm", "derived",
                f"数值方法 {PROTUBERANCE_DFF_METHODS[protuberance_dff]}；用户决定 2026-10-30 接入主图")
            model.tr30_numerical_nodes[f"d_Ff_{i}"] = {
                "method": protuberance_dff, "value_mm": result.value, "convergence": result.convergence,
                "inputs": {k: p[k] for k in sorted(p)}, "branch": detail["branch"],
                "sources": detail["sources"], "evidence_nature": detail["evidence_nature"],
                "provenance": "derived", "evidence_cap": "E1"}
    model.selectors = {**selectors, "method.Z_BD": contact, "method.Z_W": "TR30_4.2.6", "method.Z_V_velocity": zv_velocity,
                       "method.material_limits": "ISO6336-5_2016_table1_per_gear",
                       "method.Rz_H_source": rz_source or "not_discriminating(6Ra=printed)",
                       **({"method.f_sh0_specific_load": fsh0_basis or "not_selected(f_sh0 not_implemented)"} if double else {}),
                       **({"method.d_Ff_protuberance": protuberance_dff} if numerical_ff else {}),
                       "method.contact_life_stress": "curve1_long_life" if limited else "TR30_4.2.5_whole_stress_0.3705"}
    set_contact_method_evidence(model, contact, _cite(raw["f_ZCa_input"]))
    model.selector_sources.update({k: "TR30 原表输入声明与显式诊断范围" for k in model.selectors if k not in model.selector_sources})
    model.tr30_case = case["id"]
    model.tr30_assumptions = [a for i in (1, 2) for a in metas[i]["assumptions"]]
    model.tr30_internal = internal
    model.tr30_double = double
    model.tr30_premise_audit = premise_audit(model)
    cp = model.tr30_premise_audit.get("contact_path_not_shortened")
    if cp is not None and cp["status"] == "eliminated_by_formula" and numerical_ff:
        cp["via_numerical_inputs"] = [f"d_Ff_{i}" for i in numerical_ff]
    return model


def premise_audit(model):
    """逐项列出适用性前提状态（与例1–4 共用 tr30_rating.PREMISE_BASIS）。"""
    from .tr30_rating import premise_audit as _audit
    return _audit(model)


# ---------------- 比较 ----------------
_OUTPUT_ALIASES = {
    "d": "d", "d_a": "da", "d_b": "db", "d_f": "df", "x_E": "xE", "x_EV": "xEV", "d_w": "dw", "v_w": "v_w",
    "c_prime": "c_s", "F_bx": "F_bx", "F_by": "F_by", "f_e": "f_eps",
}
_STAGES = ("geometry", "load", "K", "Z/Y", "stress", "safety")


def _stage(key):
    if key.startswith("S_"):
        return "safety"
    if key.startswith("sigma_"):
        return "stress"
    if key.startswith(("Y_", "Z_", "f_e")):
        return "Z/Y"
    if key in ("F_t", "v", "v_w"):
        return "load"
    if key.startswith(("K_", "c_", "f_", "F_b", "y_", "N_res", "m_red")):
        return "K"
    return "geometry"


def display_quantum(display):
    """原表显示末位单位 q（'1 338'→1，'0,022 9'→1e-4，'2,457'→1e-3）。"""
    text = str(display).replace(" ", "").replace(" ", "").replace(",", ".")
    text = text.strip("()")
    return 10.0 ** (-len(text.split(".", 1)[1])) if "." in text else 1.0


def quantum_tolerance(display, reference):
    """显示量子判据：q/2 + min(0.01, 0.005·|r|)（与 P1 形式化口径一致的本地实现）。"""
    return display_quantum(display) / 2 + min(0.01, 0.005 * abs(reference))


def compare_full(case, *, zv_velocity="v_ref", hardness_conversion="ISO18265_A1_linear", rz_source=None, fsh0_basis=None,
                 extra_inputs=None, protuberance_dff=None):
    """逐个参考量独立求值；保留全部阻断与未实现项。rz_source 见 build_model（例8 必须显式给出）。

    extra_inputs：{名称: (值, 单位, provenance, 来源)}，建图后写入（如 hardness_conversion='HV_external_readback'
    所需的 mat_hv_ext_i，provenance 须为 evidence）；名称不在模型输入声明中即报错，不静默忽略。"""
    if type(case) is int:
        case = next(c for c in load_cases() if c["example_number"] == case)
    head = {"id": case.get("id"), "example_number": case.get("example_number"), "accepted": False,
            "evidence_level": "not_assessed", "product_strength": "not_assessed", "numerical_complete": False,
            "scope": "TR30 例5–8 全强度诊断；来源/适用性验收独立"}
    try:
        model = build_model(case, zv_velocity=zv_velocity, hardness_conversion=hardness_conversion, rz_source=rz_source,
                            fsh0_basis=fsh0_basis, protuberance_dff=protuberance_dff)
    except (KeyError, ValueError, NotImplementedError) as error:
        return {**head, "status": "blocked_unsupported_or_missing_inputs", "errors": [str(error)], "rows": [],
                "first_divergence": None, "counts": {}}
    for name, (value, unit, provenance, source) in (extra_inputs or {}).items():
        if name not in model.specs:
            raise ValueError(f"extra_inputs 中的 {name} 不是该模型声明的输入")
        model.set(name, value, unit, provenance, source)
    rows = []
    for ref in case["raw_outputs"]:
        key = ref["key"]
        prefix = _OUTPUT_ALIASES.get(key, key)
        for i, expected in enumerate(ref["values"]):
            name = f"{prefix}_{i+1}" if len(ref["values"]) == 2 else prefix
            row = {"quantity": name, "source_quantity": key, "stage": _stage(key), "reference": expected,
                   "unit": ref["unit"], "display": ref["display"][i], "citation": ref["citation"]}
            if type(expected) not in (int, float):
                rows.append({**row, "status": "reference_not_applicable"})
                continue
            if name in model.tr30_numerical_nodes:
                # 数值方法节点（主图内 derived 输入）：按与公式行相同的量子判据比较，另标 numerical_method
                value = model.inputs[name]
                actual = U.from_canonical(value.value, value.unit)
                status = None
                row["numerical_method"] = model.tr30_numerical_nodes[name]["method"]
            elif name in model.inputs:
                value = model.inputs[name]
                actual = U.from_canonical(value.value, value.unit)
                status = "derived_input" if value.provenance == "derived" else "input_not_formula"
            elif name not in model.formulas:
                rows.append({**row, "status": "not_implemented"})
                continue
            else:
                result = model.evaluate([name])
                if result.status != "ok":
                    rows.append({**row, "status": "blocked", "model_status": result.status,
                                 "missing": result.missing, "errors": result.errors,
                                 "domain_violations": result.domain_violations})
                    continue
                # TR30 表 fsh0 单位栏印 µm；ISO 6336-1 表F.1（PDF137）为 µm·mm/N（数值相同）
                unit = "N/(mm*um)" if ref["unit"] == "N/mm/um" else "um*mm/N" if name == "f_sh0" else ref["unit"]
                actual = U.from_canonical(result.values[name], unit)
                status = None
            diff = actual - expected
            tol = quantum_tolerance(ref["display"][i], expected)
            ok = abs(diff) <= tol + 1e-12
            strict = abs(diff) <= .01 + 1e-12 and abs(diff) <= .005 * abs(expected) + 1e-12
            rows.append({**row, "actual": actual, "difference": diff, "quantum_tolerance": tol,
                         "quantum_match": ok, "strict_both_gates": strict,
                         "status": status or ("pass" if ok else "fail")})
    rows.sort(key=lambda r: _STAGES.index(r["stage"]))
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    first = next((r for r in rows if r["status"] in ("fail", "blocked")), None)
    assumptions = {n: {"value": U.from_canonical(v.value, v.unit), "source": v.source}
                   for n, v in model.inputs.items() if v.provenance == "assumption"}
    return {**head, "status": "full_rating_diagnostic", "model_sha256": model.sha256(),
            "selectors": model.selectors, "rows": rows, "counts": counts, "first_divergence": first,
            "assumptions": assumptions, "branch_assumptions": model.tr30_assumptions,
            "premise_audit": model.tr30_premise_audit,
            "numerical_nodes": {k: {kk: v[kk] for kk in ("method", "value_mm", "branch", "provenance", "evidence_cap")}
                                for k, v in model.tr30_numerical_nodes.items()}}


def ex8_root_stress_analysis(*, rz_source="ra_times_6"):
    """例8 σF0_1/σF_2 偏高约 0.1% 的逐段排查（不调任何输入去追平）。

    1. 按 版次方法→输入单位→几何→载荷→K/Z/Y→应力 排序找首分歧；
    2. 由四个 σF 行（σF0_1/2、σF_1/2）的显示量子界求"公共乘子 k"可行区间：若 TR 与本库只差一个两轮共有的因子，
       k 必须同时落在四个区间内；
    3. 对每个候选根因给出数值结论（排除/不能排除）。
    """
    case = next(c for c in load_cases() if c["example_number"] == 8)
    report = compare_full(case, rz_source=rz_source)
    rows = {r["quantity"]: r for r in report["rows"]}
    first = report["first_divergence"]
    upstream = [r["quantity"] for r in report["rows"] if r["stage"] in ("geometry", "load", "K", "Z/Y")
                and r["status"] not in ("pass", "input_not_formula", "not_implemented", "reference_not_applicable")]
    lo, hi = 0.0, float("inf")
    for q in ("sigma_F0_1", "sigma_F0_2", "sigma_F_1", "sigma_F_2"):
        r = rows[q]
        lo = max(lo, (r["reference"] - r["quantum_tolerance"]) / r["actual"])
        hi = min(hi, (r["reference"] + r["quantum_tolerance"]) / r["actual"])
    model = build_model(case, zv_velocity="v_ref", rz_source=rz_source)
    v = model.evaluate(["F_t", "f_eps", "Y_beta", "m_n", "alpha_n", "b_1", "b_2", "eps_beta", "beta", "beta_b"]).values
    raw = _rows(case)
    mn, an = v["m_n"], v["alpha_n"]
    hfp_pre, hfp, q = _num(raw, "h_fP_pre"), _num(raw, "h_fP"), _num(raw, "q")
    checks = {
        "F_t_display": {"max_factor_from_rounding": (rows["F_t"]["reference"] + .5) / rows["F_t"]["actual"],
                        "verdict": "excluded"},
        "facewidth_iso6336_3_note": {"b_1": v["b_1"], "b_1_limit": min(v["b_1"], v["b_2"] + 2*mn),
                                     "verdict": "excluded（ISO 6336-3:2019 5.2 NOTE：宽轮承载宽 ≤ 窄轮 + 每端 1 m_n，85,2 mm > 78,74 mm）"},
        "pre_finishing_vs_finishing_rack": {
            "difference_mm": (hfp_pre - hfp)*mn*math.tan(an) - q/math.cos(an),
            "verdict": "excluded（(hfP_pre−hfP)·m_n·tanα_n 与 q/cosα_n 只差原表舍入；G、E 两种装配等价）"},
        "f_eps": {"actual": v["f_eps"], "required_upper": v["f_eps"]*hi, "printed": rows["f_eps"]["reference"],
                  "verdict": "excluded" if v["f_eps"]*hi < rows["f_eps"]["reference"] - .005 else "not_excluded"},
        "Y_beta": {"actual": v["Y_beta"], "required_range": (v["Y_beta"]*lo, v["Y_beta"]*hi),
                   "printed": rows["Y_beta"]["reference"],
                   # 两种常见实现偏差（非标准式）：εβ 不截断为 1；cos³ 用 βb 代替 β
                   "variant_k": {"eps_beta_uncapped": (1 - v["eps_beta"]*v["beta"]/(2*math.pi/3))/math.cos(v["beta"])**3/v["Y_beta"],
                                 "cos3_beta_b": (1 - min(v["eps_beta"], 1)*v["beta"]/(2*math.pi/3))/math.cos(v["beta_b"])**3/v["Y_beta"]},
                   "verdict": "显示 0,96 容许所需值，但无对应的式变体：上列两种实现偏差的 k 都在区间外（库内式见 formulas.py root.Y_beta，本轮未重新核图）"},
    }
    spr_fit = []
    for spr in (0.0, 0.01, 0.02, 0.03, 0.035, 0.04, 0.045, 0.047, 0.05, 0.06):
        m = build_model(case, zv_velocity="v_ref", rz_source=rz_source)
        for i in (1, 2):
            m.set(f"s_pr_{i}", spr, "mm", "user", "排查扫描（不进模型）")
        keys = ("sigma_F0_1", "sigma_F0_2", "sigma_F_1", "sigma_F_2")
        vals = m.evaluate(list(keys)).values
        ok = all(abs(vals[k] - rows[k]["reference"]) <= rows[k]["quantum_tolerance"] + 1e-12 for k in keys)
        spr_fit.append((spr, ok))
    checks["s_pr_single_value"] = {"scan": spr_fit,
                                   "verdict": "excluded" if not any(ok for _, ok in spr_fit) else "not_excluded"}
    return {"first_divergence": first and first["quantity"], "first_divergence_stage": first and first["stage"],
            "upstream_non_pass": upstream, "common_factor_interval": (lo, hi), "candidates": checks,
            "conclusion": ("根因无法确认：几何/载荷/K/Z/Y 全部在显示量子内，首分歧在应力段 σF0_1；四个 σF 行可由两轮共有乘子 "
                           f"k∈[{lo:.5f}, {hi:.5f}]（约 −0.1%）同时消除，单参数候选均已排除；剩余可能为凸台分支 Y_F/Y_S 的"
                           "逐轮细节（原表只给 3 位有效数字，无附录级未舍入值可对拍）。未调整任何输入。")}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"schema": "gearmath.tr30_full58_diagnostic/v1",
              "cases": [compare_full(c, rz_source="ra_times_6" if rz_discriminates(c) else None) for c in load_cases()],
              "example8_printed_rz": compare_full(8, rz_source="printed_rz"),
              "example8_root_stress_analysis": ex8_root_stress_analysis()}
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    for r in report["cases"]:
        fd = r["first_divergence"]
        print(r["example_number"], r["counts"], fd and (fd["quantity"], fd.get("actual"), fd["reference"]))
    raise SystemExit(2)
