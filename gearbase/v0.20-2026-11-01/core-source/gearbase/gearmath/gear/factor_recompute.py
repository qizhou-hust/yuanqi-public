"""M34 优化闭环（v0.14 OPT2）：随几何变化的系数在优化中重新计算，不再按 hold_evidence 原样保持。

背景：v0.14 OPT 路 K01 最优设计（z 23/68、m_n 6、b 28.3、x1 0.427）经 KISSsoft 2026 复核 S_H1=0.99497、S_F2=1.39453，
本库 1.0000/1.4004。逐项对账（gear/kisssoft_v014.py、docs/M34-系数对账-P2.md）：差异来自优化中保持不变的
Z_V、Z_R、Z_NT_2、Y_NT_2、Y_δrelT（证据区按旧几何取值）与轮坯内径 d_inner（作者输入按旧几何取值 → m_red → K_V），
以及齿顶缩短口径（ε_α，KISSsoft 自动 k·m_n=−0.015 mm，本库 geo.da 不含齿顶缩短）。

本模块只做装配，不新增、不修改标准公式：
  * 系数方法组：沿用 factor_methods.compile_factors（ISO 原图已核的 Z_L/Z_V/Z_R、Z_NT/Y_NT、Y_δrelT/Y_RrelT/Y_X、
    Z_W/Z_X、Y_B/Y_DT 子集），由文档 selectors 区显式选择（method.Z_LVR 等），不设默认；
  * 适配层 ADAPTERS（文档 selectors 区显式选择，键以 "adapter." 开头）：
      adapter.tolerances = iso1328_grade：f_pt_i、f_falpha_i、f_Hbeta_i、f_Hbeta5 由 iso1328.py 已有的 ISO 1328-1:2013
        式(5)(8)(10)+5.2.3（PDF32–33 原图已核）按精度等级 A1328_i 计算（原为按旧几何写死的作者输入）；b_i = b（两轮同宽）；
      adapter.blank_bore = rim_from_root_min：d_inner_i = d_i − 2·m_n·(h_fP − x_E,i) − 2·(s_R/m_n)·m_n，即保持作者给出的
        轮缘厚 s_R/m_n（同一文档已用于 C_R 式(87)），内径从最小根圆 d_f,i 量起；K01 原作者输入 77.58/377.5 mm 与本式
        相差 0.004 mm（< 报告末位半格 0.005），KISSsoft P2 在几何改动后给出的 67.726/329.496 mm 与本式逐位一致。
    适配层不是标准条文，是"让文档内已有的作者意图（精度等级、轮缘厚比）在几何改变时保持自洽"的装配；在选择器来源里写明。

hold：没有公式路径的系数仍须在声明 parameters.hold_evidence 中显式列出，并在 parameters.hold_rationale 中逐项给出
适用性理由；随几何变化但按作者意图保持的输入（如小轮轴 l/s/d_sh）在 parameters.geometry_coupled_held 中列出。
优化报告 coefficient_status 逐项给出"recomputed（公式输出）/ held（输入，未随几何更新）"。
"""
from __future__ import annotations

import copy
import hashlib
import json

from dataclasses import replace as dc_replace

from ..kernel import source_doc as SD
from ..kernel.graph import Formula, InputSpec, Model
from . import math_source as MS
from .factor_methods import FACTOR_OPTIONS

F, S = Formula, InputSpec
ROOT = MS.ROOT

ADAPTERS = {
    "adapter.tolerances": {
        "iso1328_grade": "f_pt_i/f_falpha_i/f_Hbeta_i/f_Hbeta5 按 ISO 1328-1:2013 式(5)(8)(10)+5.2.3 由精度等级 A1328_i 与当前几何计算",
    },
    "adapter.blank_bore": {
        "rim_from_root_min": "d_inner_i = d_i − 2 m_n (h_fP − x_E,i) − 2 (s_R/m_n) m_n：保持轮缘厚比 s_R/m_n，从最小根圆量起",
        "rim_from_root_min_wheel": "只对大轮：d_inner_2 = d_f,min,2 − 2 (s_R/m_n) m_n（K02–K05 链已有 df_min_i）；小轮内径（轴齿轮/轴孔）保持作者输入",
    },
    # v0.15 OPT3：齿顶缩短作为显式几何口径选择器（无默认；文档 selectors 区或问题声明 parameters.tip_shortening 必须显式给出）
    "adapter.tip_shortening": {
        "none": "k_X_i = 0：齿顶圆 d_a,i = d_i + 2 m_n (h_aP + x_i)，不做齿顶缩短（KISSsoft P5-A kFaktorFlag=true、kXmn=0 同口径）",
        "kisssoft_auto_equivalent": "k_X_i = a_w − a − (x_1 + x_2)·m_n（两轮相同，mm，带符号；保持标准顶隙）；d_a,i 加 2·k_X_i。"
                                    "口径来源：KISSsoft P2（kXmn=−0.015 mm）与 P5-B（/home/claude/private_ks15/cases/P5-B-auto/run.json "
                                    "ZR[i].kXmn=−0.019 mm、da 155.35/416.98）证据；ISO 21771 原文不在本环境，未对照原文核验；"
                                    "KISSsoft 将 kXmn 圆整到 0.001 mm，本式不圆整（|Δ(k·m_n)| ≤ 5e-4 mm）",
    },
    "adapter.face_widths": {
        "pinion_overhang": "b_1 = b_2 + b_overhang（作者输入，保持原设计小轮比大轮宽出的量；只用于两轮齿宽分列的 K02–K05 链）",
    },
    # v0.17 K02GAP：fHβ5 是 ISO 6336-1:2019 7.5.3.4 式(55) 的"5 级"螺旋线倾斜公差，与工件的精度等级/公差标准无关
    # （K02 工件精度按 DIN 3961:1978，本库未实现；但 fHβ5 不取自 DIN 3961）。只重算 fHβ5，其余公差保持作者输入。
    "adapter.f_Hbeta5": {
        "iso1328_grade5": "只 f_Hbeta5 按 ISO 1328-1:2013 式(10) A=5 + 5.2.3（iso1328.fhbeta5_formulas，PDF33/印27 原图已核）"
                          "由当前 d_i 与本轮齿宽 b_i 逐轮计算、两轮取大；f_pt/f_falpha/f_Hbeta_i 等工件公差仍为作者输入。"
                          "只用于两轮齿宽分列（b_1/b_2）的 K02–K05 链；与 adapter.tolerances=iso1328_grade 互斥（后者已含 fHβ5）",
    },
}
from .din3967_adapter import CODES as DIN3967_CODES
for _i in (1, 2):
    ADAPTERS[f"adapter.din3967_{_i}"] = {code: "DIN 3967 explicit tooth thickness designation" for code in DIN3967_CODES}
TIP_SHORTENING = tuple(ADAPTERS["adapter.tip_shortening"])
TIP_SHORTENING_SOURCE = ("口径来源为 KISSsoft 证据：P2（data/kisssoft_v014/P2-K01-opt.json，kXmn=−0.015 mm）与 P5-B "
                         "（/home/claude/private_ks15/cases/P5-B-auto/run.json，kXmn=−0.019 mm）；ISO 21771 原文不在本环境，未核原文")

# 状态报告关注的系数/几何耦合量（存在于模型中的才报告）
COEFFICIENTS = ("K_V", "K_Hbeta", "K_Fbeta", "K_Halpha", "K_Falpha",
                "Z_NT_1", "Z_NT_2", "Y_NT_1", "Y_NT_2", "Z_L", "Z_V", "Z_R", "Z_W", "Z_X",
                "Y_X", "Y_drelT_1", "Y_drelT_2", "Y_RrelT_1", "Y_RrelT_2", "Y_B", "Y_DT", "Y_ST",
                "f_pt_1", "f_pt_2", "f_falpha_1", "f_falpha_2", "f_Hbeta_1", "f_Hbeta_2", "f_Hbeta5",
                "d_inner_1", "d_inner_2", "q_1", "q_2", "C_R", "l_sh", "s_sh", "d_sh", "N_L_1", "N_L_2")

_ISO1328_KEEP = ("q1328_{i}", "fpT_raw_{i}", "fpT_{i}", "ffaT_raw_{i}", "ffaT_{i}", "fHbT_raw_{i}", "fHbT_{i}")


def split_selectors(doc):
    """文档 selectors -> (基础选择器, 系数选择器, 适配选择器, 来源)。"""
    sel = {k: r["value"] for k, r in doc.get("selectors", {}).items()}
    src = {k: r["source"] for k, r in doc.get("selectors", {}).items()}
    fsel = {k: v for k, v in sel.items() if k in FACTOR_OPTIONS}
    asel = {k: v for k, v in sel.items() if k.startswith("adapter.")}
    base = {k: v for k, v in sel.items() if k not in fsel and k not in asel}
    return base, fsel, asel, src


def uses_recompute(doc):
    _, fsel, asel, _ = split_selectors(doc)
    return bool(fsel or asel)


def _adapter_formulas(asel, base_formulas):
    """返回 (适配公式, 新增输入声明)。取值非法即 ValueError（不设默认）。"""
    bad = [f"{k}={v!r}" for k, v in asel.items() if k not in ADAPTERS or v not in ADAPTERS[k]]
    if bad:
        raise ValueError(f"适配选择器取值无效：{bad}；可选：{ADAPTERS}")
    fs, specs = [], []
    if asel.get("adapter.tolerances") == "iso1328_grade":
        from .iso1328 import fhbeta5_formulas, tolerance_formulas
        note = "适配层（adapter.tolerances=iso1328_grade）：本库 K 链/齿轮副模型两轮同宽 b"
        fs += [F(f"opt.b_width.{i}", f"b_{i}", "mm", "b", "适配：ISO 1328-1:2013 式(10) 的本轮齿宽 b_i = b（两轮同宽）", note=note)
               for i in ("1", "2")]
        for i in ("1", "2"):
            keep = {k.format(i=i) for k in _ISO1328_KEEP}
            fs += [f for f in tolerance_formulas(i) if f.output in keep]
        fs += [F(f"opt.f_pt.{i}", f"f_pt_{i}", "um", f"fpT_{i}",
                 "ISO 1328-1:2013 5.3.1 式(5)+5.2.3：单个齿距公差 fpT 作为 K_V/K_Hα 的 f_pt（适配）", note=note) for i in ("1", "2")]
        fs += [F(f"opt.f_falpha.{i}", f"f_falpha_{i}", "um", f"ffaT_{i}",
                 "ISO 1328-1:2013 5.3.3.2 式(8)+5.2.3：齿廓形状公差 ffαT 作为 f_falpha（适配）", note=note) for i in ("1", "2")]
        if any(f.output == "f_Hbeta" or "f_Hbeta_1" in f.expr for f in base_formulas):
            fs += [F(f"opt.f_Hbeta.{i}", f"f_Hbeta_{i}", "um", f"fHbT_{i}",
                     "ISO 1328-1:2013 5.3.4.1 式(10)+5.2.3：螺旋线倾斜公差 fHβT 作为 f_Hbeta（适配）", note=note) for i in ("1", "2")]
            fs += fhbeta5_formulas(lambda i: f"b_{i}")
        specs += [S(f"A1328_{i}", "1", f"ISO 1328-1:2013 齿面公差等级（第 {i} 轮）", (f"A1328_{i} >= 1", f"A1328_{i} <= 11"))
                  for i in ("1", "2")]
        specs += [S("root_mm", "mm", "Fixed length unit, 1 mm", ("root_mm >= 1", "root_mm <= 1")),
                  S("root_um", "um", "Fixed roughness unit, 1 um", ("root_um >= 0.001", "root_um <= 0.001"))]
    if asel.get("adapter.blank_bore") == "rim_from_root_min":
        fs += [F(f"opt.d_inner.{i}", f"d_inner_{i}", "mm", f"d_{i} - 2*m_n*(hfP - xE_{i}) - 2*sR_mn*m_n",
                 "适配：轮坯内径 = 最小根圆 d_f,i − 2·s_R，s_R = (s_R/m_n)·m_n（ISO 6336-1:2019 9.3.2.4 轮缘厚 s_R；"
                 "同一 s_R/m_n 已用于 C_R 式(87)）", (f"d_{i} - 2*m_n*(hfP - xE_{i}) > 2*sR_mn*m_n",),
                 note="适配层（adapter.blank_bore=rim_from_root_min）：不是标准条文；KISSsoft P2 di 逐位相同") for i in ("1", "2")]
    din_keys = ("adapter.din3967_1", "adapter.din3967_2")
    if any(k in asel for k in din_keys):
        if not all(k in asel for k in din_keys):
            raise ValueError("DIN 3967 requires explicit designations for both gears")
        by_output = {f.output: f for f in base_formulas}
        if not {"d_1", "d_2", "xE_1", "xE_2"} <= set(by_output) or any(
            f"A_sn_i_{i}" not in by_output[f"xE_{i}"].compiled().names for i in (1, 2)
        ):
            raise ValueError("DIN 3967 adapter requires generating-root geometry consuming A_sn_i for both gears")
        from .din3967_adapter import formulas
        dfs, dspecs = formulas({i: asel[f"adapter.din3967_{i}"] for i in (1,2)})
        fs += dfs
        specs += [s for s in dspecs if s.name not in {x.name for x in specs}]
    return fs, specs


def _geometry_adapters(asel, base):
    """v0.15 OPT3 几何口径适配：齿顶缩短、两轮齿宽。返回 (公式, 新增输入声明, 被替换的基础公式输出集合)。"""
    fs, specs, replaced = [], [], set()
    tip = asel.get("adapter.tip_shortening")
    if tip is not None:
        note = f"几何口径适配（adapter.tip_shortening={tip}）；{TIP_SHORTENING_SOURCE}"
        expr = "a_w - a - (x_1 + x_2)*m_n" if tip == "kisssoft_auto_equivalent" else "0*m_n"
        ref = ("齿顶缩短 k·m_n = a_w − a − (x_1 + x_2)·m_n（保持标准顶隙；KISSsoft 自动齿顶缩短等效口径）"
               if tip == "kisssoft_auto_equivalent" else "不做齿顶缩短：k·m_n = 0")
        fs += [F(f"opt.k_X.{tip}.{i}", f"k_X_{i}", "mm", expr, ref, note=note) for i in ("1", "2")]
        for f in base.formulas.values():
            for i in ("1", "2"):
                if f.output == f"da_{i}" and f"k_X_{i}" not in f.expr:
                    fs.append(dc_replace(f, id=f"opt.da_kX.{i}", expr=f"{f.expr} + 2*k_X_{i}",
                                         note=(f.note + "；" if f.note else "") + note))
                    replaced.add(f.output)
    if asel.get("adapter.blank_bore") == "rim_from_root_min_wheel":
        if "df_min_2" not in base.formulas:
            raise ValueError("adapter.blank_bore=rim_from_root_min_wheel 需要链中已有最小根圆 df_min_2（K02–K05 rim_thickness_root_circle）")
        fs.append(F("opt.d_inner.wheel", "d_inner_2", "mm", "df_min_2 - 2*sR_mn*m_n",
                    "适配：大轮轮坯内径 = 最小根圆 d_f,i − 2·s_R，s_R = (s_R/m_n)·m_n（ISO 6336-1:2019 9.3.2.4 轮缘厚 s_R）",
                    ("df_min_2 > 2*sR_mn*m_n",), note="适配层（adapter.blank_bore=rim_from_root_min_wheel）：不是标准条文"))
        if "sR_mn" not in base.specs:
            specs.append(S("sR_mn", "1", "轮缘厚/法向模数比 s_R/m_n（作者意图）", ("sR_mn > 0",)))
    if asel.get("adapter.face_widths") == "pinion_overhang":
        if "b_1" not in base.specs or "b_2" not in base.specs:
            raise ValueError("adapter.face_widths=pinion_overhang 只用于两轮齿宽 b_1/b_2 为作者输入的模型")
        fs.append(F("opt.b_1.overhang", "b_1", "mm", "b_2 + b_overhang",
                    "适配：小轮齿宽 = 大轮齿宽 + 作者给出的宽出量（保持原设计齿宽差；非标准条文）",
                    note="几何口径适配（adapter.face_widths=pinion_overhang）"))
        specs.append(S("b_overhang", "mm", "小轮比大轮宽出的量（作者意图，mm）", ("b_overhang >= 0",)))
    if asel.get("adapter.f_Hbeta5") == "iso1328_grade5":
        if asel.get("adapter.tolerances") == "iso1328_grade":
            raise ValueError("adapter.f_Hbeta5=iso1328_grade5 与 adapter.tolerances=iso1328_grade 互斥（后者已由 ISO 1328-1 给出 fHβ5）")
        names = set(base.specs) | set(base.formulas)
        if not {"b_1", "b_2", "d_1", "d_2", "z_1", "z_2", "f_Hbeta5"} <= names:
            raise ValueError("adapter.f_Hbeta5=iso1328_grade5 只用于两轮齿宽 b_1/b_2 分列且含 f_Hbeta5 的链（K02–K05）")
        from .iso1328 import fhbeta5_formulas
        fs += fhbeta5_formulas(lambda i: f"b_{i}",
                               width_note="；适配层 adapter.f_Hbeta5=iso1328_grade5：本轮齿宽 b_i（KISSsoft 2026 OPT3-3-K02 "
                                          "ZP[0].KHdat.fHb5=6.5 µm 与本式逐位一致，见 data/kisssoft_v017/OPT3-3-K02.json）")
        for n, u, t in (("root_mm", "mm", "Fixed length unit, 1 mm"), ("root_um", "um", "Fixed roughness unit, 1 um")):
            if n not in base.specs:
                specs.append(S(n, u, t, (f"{n} >= 1", f"{n} <= 1") if u == "mm" else (f"{n} >= 0.001", f"{n} <= 0.001")))
    return fs, specs, replaced


def _base_model(family, case, base_sel, fsel, src):
    if family == "kisssoft_chain" and case in _multi_cases():
        from . import kisssoft_multi as KM
        m, _ = KM.build_model(case)
        allowed = {"method.life": "nitrided_085_long_life", "method.root_factors": "nitrided_reference"}
        changed = {k: v for k, v in fsel.items() if m.selectors.get(k) != v}
        bad = [k for k, v in changed.items() if allowed.get(k) != v or m.selectors.get(k) != "external"]
        if bad:
            raise ValueError(f"{case} 文档系数方法选择器与 K 链契约不一致：{bad}")
        if not changed:
            return m
        from .factor_methods import FACTOR_OUTPUTS, compile_factors, validation_status
        from .inputs import input_specs
        selected = {k: fsel.get(k, v) for k, v in m.selectors.items() if k in FACTOR_OPTIONS}
        compiled, table, unresolved = compile_factors(selected)
        outputs = {q for k in changed for q in FACTOR_OUTPUTS[k]}
        # YX per-gear values are internal dependencies of the common YX output.
        if "method.root_factors" in changed:
            outputs.update(("Y_X_1", "Y_X_2"))
        replacements = [f for f in compiled if f.output in outputs]
        if not outputs <= {f.output for f in replacements}:
            raise ValueError("nitrided factor override has incomplete outputs")
        formulas = [f for f in m.formulas.values() if f.output not in outputs] + replacements
        declared = {s.name: s for s in m.specs.values() if s.name not in outputs}
        for spec in table:
            declared.setdefault(spec.name, spec)
        needed = input_specs(formulas, list(declared.values()))
        used = {s.name for s in needed}
        # Preserve existing source document inputs even if not used by a target.
        specs = [s for s in m.specs.values() if s.name not in outputs]
        have = {s.name for s in specs}
        specs += [s for s in needed if s.name in used and s.name not in have]
        updated = Model(formulas, inputs=specs)
        updated.required_evidence = {k: v for k, v in m.required_evidence.items() if k not in outputs}
        updated.unresolved = list(m.unresolved) + list(unresolved)
        updated.selectors = {**m.selectors, **changed}
        updated.selector_sources = {**m.selector_sources, **{k: src.get(k, "") for k in changed}}
        updated.factor_validation = validation_status(selected)
        return updated
    if family == "pair_model":
        from .rating import pair_model
        return pair_model(selectors=base_sel, selector_sources=src, factor_selectors=fsel or None,
                          factor_selector_sources=src if fsel else None)
    if family == "kisssoft_chain":
        from . import kisssoft_case as KC
        if case != "K01-spur":
            raise NotImplementedError(f"系数重算装配只支持 K01-spur（{case} 未建立契约）")
        m, _ = KC.build_model(case, factor_selectors=fsel or None)
        return m
    raise ValueError(f"未知模型族 {family}")


def _multi_cases():
    from .kisssoft_multi import CASES
    return CASES


def assemble(doc, family, case=None):
    """按文档选择器装配公式图（不设输入）。返回 Model。"""
    base_sel, fsel, asel, src = split_selectors(doc)
    base = _base_model(family, case, base_sel, fsel, src)
    afs, aspecs = _adapter_formulas(asel, list(base.formulas.values()))
    if case in _multi_cases():           # 两轮齿宽分列的链：b_i 是作者输入（或 face_widths 适配），不另设 b_i = b
        afs = [f for f in afs if not f.id.startswith("opt.b_width.")]
    gfs, gspecs, replaced = _geometry_adapters(asel, base)
    afs, aspecs = afs + gfs, aspecs + gspecs
    outs = {f.output for f in afs}
    have = set(base.specs)
    specs = [s for s in base.specs.values() if s.name not in outs]
    for s in aspecs:
        if s.name not in have:
            specs.append(s)
            have.add(s.name)
    m = Model([f for f in base.formulas.values() if f.output not in replaced] + afs, inputs=specs)
    m.required_evidence = dict(getattr(base, "required_evidence", {}))
    m.unresolved = list(getattr(base, "unresolved", []))
    if hasattr(base, "factor_validation"):
        m.factor_validation = base.factor_validation
    m.selectors = {k: r["value"] for k, r in doc["selectors"].items()}
    m.selector_sources = {k: r["source"] for k, r in doc["selectors"].items()}
    return m


def build_model(doc, family, case=None):
    """文档 -> 模型（系数方法组 + 适配层）。校验失败、输入被公式锁定/未声明 -> SourceError。"""
    errs = MS.validate(doc)
    if errs:
        raise SD.SourceError(errs)
    try:
        m = assemble(doc, family, case)
    except (ValueError, TypeError, NotImplementedError) as e:
        raise SD.SourceError([{"path": "$.selectors", "code": "invalid_selector", "message": str(e)}]) from e
    return SD.apply_sections(m, doc)


def coefficient_status(model, decl=None):
    """逐项：recomputed（公式输出，随设计变量重算）/ held（输入，未随几何更新；附理由）。"""
    p = (decl or {}).get("parameters") or {}
    why = {**(p.get("hold_rationale") or {}), **(p.get("geometry_coupled_held") or {})}
    rows = []
    for n in COEFFICIENTS:
        if n in model.formulas:
            rows.append({"name": n, "status": "recomputed", "formula": model.formulas[n].id})
        elif n in model.inputs:
            i = model.inputs[n]
            rows.append({"name": n, "status": "held", "provenance": i.provenance, "unit": i.unit,
                         "value_canonical": i.value, "reason": why.get(n, "未给出理由（旧声明：hold_evidence 只列名）")})
    return rows


# ---------------------------------------------------------------- 文档修订（父文档 -> 系数重算文档）
def derive_document(parent, family, case, *, selectors, inputs=(), evidence=(), editions=None, doc_id, title, extra_note=""):
    """父文档 + 系数/适配选择器 + 新增输入 -> 新文档。被新公式锁定的旧条目移除（列入 note）。不修改父文档。
    selectors：{键: (值, 来源)}；inputs：[(名, 行)]；evidence：[(名, 行含 certificate)]。"""
    new = copy.deepcopy(parent)
    for k, (v, s) in selectors.items():
        new["selectors"][k] = {"value": v, "source": s}
    for part, (ed, s) in (editions or {}).items():
        new["editions"][part] = {"edition": ed, "source": s}
    m = assemble(new, family, case)
    removed = []
    for sec in ("inputs", "evidence"):
        for n in sorted(list(new[sec])):
            if n in m.formulas:
                r = new[sec].pop(n)
                removed.append(f"{n}={r['value']} {r['unit']}（{sec}）")
    for n, row in inputs:
        new["inputs"][n] = dict(row)
    for n, row in evidence:
        new["evidence"][n] = dict(row)
    new["id"], new["title"] = doc_id, title
    psha = MS.source_sha256(parent)
    new["note"] = (f"由 {parent['id']}（sha256={psha}）派生：显式选择系数方法组与适配层，使随几何变化的系数在优化中由公式重算"
                   f"（gear/factor_recompute.py）。下列条目改由公式给出，已从文档移除：{'；'.join(removed)}。{extra_note}"
                   f"派生量不存。")
    errs = MS.validate(new)
    if errs:
        raise SD.SourceError(errs)
    return new


def _sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _cert(rel, locator):
    return {"kind": "file", "ref": rel, "sha256": _sha(rel), "locator": locator}


def k01_factor_document():
    """K01-spur -> K01-spur.factors：K01 显式系数契约（factor_methods.K01_FULL_FACTOR_SELECTORS，K 链既有映射）+ 两个适配层。"""
    from . import kisssoft_case as KC
    from . import math_source_kisssoft as MK
    from .factor_methods import K01_FULL_FACTOR_SELECTORS
    parent = MK.load_doc("K01-spur")
    ref, d = KC.build_model("K01-spur", factor_selectors=K01_FULL_FACTOR_SELECTORS)
    rel = "data/kisssoft/K01-spur.json"
    sel = {k: (ref.selectors[k], ref.selector_sources[k]) for k in K01_FULL_FACTOR_SELECTORS}
    sel["adapter.tolerances"] = ("iso1328_grade",
                                 "K01 报告 [Q-ISO 1328:2013] A6（第 110 行）；KISSsoft 由等级与几何计算 fpT/ffαT/fHβT（P2 第 13 节与本式逐项相同）；"
                                 "原作者输入 f_pt=11、f_falpha=12、f_Hbeta=10/10、f_Hbeta5=7.5 即本式在原几何下的值")
    sel["adapter.blank_bore"] = ("rim_from_root_min",
                                 "K01 报告 sR/mn=5（C_R 输入）与 di=77.58/377.5：di = df.i − 2·sR 在原几何下差 0.004 mm（< 末位半格）；"
                                 "KISSsoft P2 几何改动后 di=67.726/329.496 与本式逐位一致")
    eds = {"ISO 1328-1": ("2013", "K01 报告精度等级 [Q-ISO 1328:2013] A6（第 110 行）；iso1328.py 实现 ISO 1328-1:2013")}
    probe = copy.deepcopy(parent)
    for k, (v, s) in sel.items():
        probe["selectors"][k] = {"value": v, "source": s}
    for part, (ed, s) in eds.items():
        probe["editions"][part] = {"edition": ed, "source": s}
    m = assemble(probe, "kisssoft_chain", "K01-spur")
    have = set(parent["inputs"]) | set(parent["evidence"]) | set(parent["constraints"])
    certs = {"nu_40": _cert(rel, MK._loc("report", "nu_40", "value")),
             "Rz_H_1": _cert(rel, MK._loc("report", "Rz_H", "value")), "Rz_H_2": _cert(rel, MK._loc("report", "Rz_H", "value")),
             "sigma_Hlim_surface": _cert(rel, MK._loc("com", "ZR[0].mat.limh")),
             "surface_oil_mineral": _cert(rel, MK._loc("report_text", "lubrication", "text"))}
    sections = SD.model_to_sections(MK._authored_view(ref), certs)
    inputs, evidence = [], []
    for sec, out in (("inputs", inputs), ("evidence", evidence)):
        for n, row in sorted(sections[sec].items()):
            if n not in have and n not in m.formulas and n in m.specs:
                out.append((n, row))
    for i in ("1", "2"):
        qi = d["report"][f"Q_grade_{i}"]
        inputs.append((f"A1328_{i}", {"value": float(qi["value"]), "unit": "1", "provenance": "user",
                                      "source": f"KISSsoft K01-spur 报告 {qi['label']} A{qi['value']}（extracted.txt 第 {qi['line']} 行）"}))
    for n in ("root_mm", "root_um"):
        if n not in dict(inputs):
            inputs.append((n, {"value": 1.0, "unit": "mm" if n == "root_mm" else "um", "provenance": "standard_constant",
                               "source": "Definition of metric length unit"}))
    return derive_document(parent, "kisssoft_chain", "K01-spur", selectors=sel, inputs=inputs, evidence=evidence,
                           editions=eds, doc_id="K01-spur.factors",
                           title="KISSsoft 商业工具案例 K01-spur —— 系数重算修订（Z/Y 系数与公差、轮坯内径随几何由公式给出）",
                           extra_note="T_1 仍为工具计算证据（P/(2π n_1)）。")


C001_REL = "data/m31/golden/C001/derived-candidate.json"


def c001_factor_document():
    """C001 -> C001.factors：Z_L/Z_V/Z_R（ISO 6336-2 reference 子集，原图已核）、f_pt/f_falpha（ISO 1328-1:2013）、
    K_Hα/K_Fα（ISO 6336-1 方法B）改由公式；Z_NT/Y_NT/Y_δ/Y_R（渗氮碳共渗分支未实现）、K_Hβ（方法C 输入契约缺）保持。"""
    parent = MS.load_file()
    rel = C001_REL
    sel = {
        "method.Z_LVR": ("B_reference", "ISO 6336-2:2019 12.3.2 式(42)(47)(53) reference 子集（原图已核）；M31 收据 Z_L/Z_V/Z_R "
                                        "由同式、ν40=160、Rz=3.67 复现（见 tests/test_m34_factor_recompute.py）"),
        "method.Z_V_velocity": ("v_ref", "M31 收据 Z_V=0.963205 与分度圆 v 复算一致（python-gearbox 口径，同 K01 契约 v_ref）"),
        "method.life": ("external", "C001 材料 NITROCARBURIZED_STEEL：本库只有渗碳钢 0.85 曲线，渗氮碳共渗分支未实现 → 收据值保持"),
        "method.root_factors": ("external", "渗氮碳共渗 Y_δrelT/Y_RrelT 分支未实现 → 收据值保持（Y_X：m_n≤5 时表5 恒为 1）"),
        "method.K_Halpha": ("B", "ISO 6336-1:2019 8.3 方法B（本库 load_distribution.py，原图已核）；替代 M31 收据值"),
        "adapter.tolerances": ("iso1328_grade", "M31 C001 quality_grade=6；原证据 f_pt/f_falpha 即 ISO 1328-1:2013 式(5)/(8)+5.2.3 在原几何下的值"),
    }
    eds = {"ISO 1328-1": ("2013", "M31 C001 f_pt/f_falpha 证书：ISO 1328-1:2013 式(5)/(8)+5.2.3；iso1328.py 实现 ISO 1328-1:2013")}
    case = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    mat, op = case["engineering"]["material"], case["engineering"]["operating"]
    pin = case["engineering"]["stages"]["G1"]["pinion"]
    wh = case["engineering"]["stages"]["G1"]["wheel"]
    if pin["surface_roughness_um"] != wh["surface_roughness_um"]:
        raise NotImplementedError("两轮齿面粗糙度不同")
    loc = "engineering.stages.G1.{}.surface_roughness_um"
    ev = [("sigma_Hlim_surface", mat["contact_stress_limit_MPa"], "MPa", "engineering.material.contact_stress_limit_MPa",
           "M31 C001 材料假设 contact_stress_limit（两轮相同）作为 Z_L/Z_V/Z_R 的参考材料 σHlim"),
          ("nu_40", op["lubricant_viscosity_40c_cSt"], "mm^2/s", "engineering.operating.lubricant_viscosity_40c_cSt",
           "M31 C001 lubricant_viscosity_40c_cSt"),
          ("Rz_H_1", pin["surface_roughness_um"], "um", loc.format("pinion"),
           "M31 C001 surface_roughness_um 按 Rz 解释（案例未写 Ra/Rz；收据 Z_R=0.962679 以 Rz 解释复现，见测试；待用户确认）"),
          ("Rz_H_2", wh["surface_roughness_um"], "um", loc.format("wheel"), "同上（大轮）")]
    evidence = [(n, {"value": float(v), "unit": u, "provenance": "evidence", "source": s, "certificate": _cert(rel, l)})
                for n, v, u, l, s in ev]
    a = "assumption"
    inputs = [
        ("surface_oil_mineral", {"value": 1.0, "unit": "1", "provenance": a,
                                 "source": "M31 C001 未写油基；收据 Z_L=0.996718 与矿物油式(42) 复现（见测试）；待用户确认"}),
        ("surface_nu40_vi95", {"value": 1.0, "unit": "1", "provenance": a,
                               "source": "C001 未给 VI；按 ISO 6336-2:2019 12.3.2.1.1 ν40/VI95 基准显式接受近似"}),
        *[(f"N_Href_{i}", {"value": 5e7, "unit": "1", "provenance": a,
                           "source": "Z_L/Z_V/Z_R 适用域检查用参考循环数：取 5e7（≥ 渗氮碳共渗候选 2e6，取较严者）；"
                                     "C001 N_L ≥ 3e8，数值不受影响"}) for i in ("1", "2")],
        ("life_duration", {"value": float(op["design_life_h"]) * 3600.0, "unit": "s", "provenance": "user",
                           "source": f"M31 C001 engineering.operating.design_life_h={op['design_life_h']} h，换算为秒"}),
        *[(f"cycles_per_rev_{i}", {"value": 1.0, "unit": "1", "provenance": a,
                                   "source": "单向单啮合，每转受载一次（显式工况假设）"}) for i in ("1", "2")],
        *[(f"A1328_{i}", {"value": float(g), "unit": "1", "provenance": "user",
                          "source": f"M31 C001 engineering.stages.G1.{w}.quality_grade"})
          for i, g, w in (("1", pin["quality_grade"], "pinion"), ("2", wh["quality_grade"], "wheel"))],
        ("root_mm", {"value": 1.0, "unit": "mm", "provenance": "standard_constant", "source": "Definition of metric length unit"}),
        ("root_um", {"value": 1.0, "unit": "um", "provenance": "standard_constant", "source": "Definition of metric length unit"}),
        *[(f"mat_group_{i}", {"value": 3.0, "unit": "1", "provenance": a,
                              "source": "跑合材料组 3（表面硬化/渗氮类钢，ISO 6336-1:2019 8.3.6.2 式(79)，与文档 y_alpha_max=3 µm 同组）；"
                                        "NV 归组需对原图复核（O/D 登记）"}) for i in ("1", "2")],
        ("k_pb", {"value": 1.0, "unit": "1", "provenance": "user",
                  "source": "M31 C001 engineering.operating.flank_modification=NONE → 无补偿性齿廓修形，f_pb 不折减（8.3.2）"}),
    ]
    from .load_distribution import LD_CONSTANTS
    from .surface_factors import SURFACE_CONSTANTS
    for name, v, unit, ref in list(LD_CONSTANTS) + list(SURFACE_CONSTANTS):
        inputs.append((name, {"value": float(v), "unit": unit, "provenance": "standard_constant", "source": ref}))
    return derive_document(parent, "pair_model", None, selectors=sel, inputs=inputs, evidence=evidence, editions=eds,
                           doc_id="C001.factors",
                           title="M31 C001 第一级 —— 系数重算修订（Z_L/Z_V/Z_R、f_pt/f_falpha、K_Hα/K_Fα 随几何由公式给出）",
                           extra_note="K_Hβ、Z_NT/Y_NT、Y_δrelT/Y_RrelT、Y_X、Y_B、Y_DT、Z_W、Z_X 仍为 M31 收据证据（理由见优化声明 hold_rationale）。")


FACTOR_DOCS = {"K01-spur.factors": k01_factor_document, "C001.factors": c001_factor_document}


def source_path(doc_id):
    return ROOT / "data" / "source" / f"{doc_id}.math-source.json"


def load_doc(doc_id):
    return json.loads(source_path(doc_id).read_text(encoding="utf-8"))


def write_all():
    out = {}
    for doc_id, fn in FACTOR_DOCS.items():
        doc = fn()
        source_path(doc_id).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        out[doc_id] = doc
    return out


if __name__ == "__main__":
    for k, doc in write_all().items():
        print(k, MS.source_sha256(doc))
