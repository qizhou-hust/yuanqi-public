"""K02--K05 explicit, conditional end-to-end diagnostic contracts.

The original pair formulas remain the numerical authority. This adapter adds
per-gear widths/rack inputs and additive tip alteration. It does not certify
unimplemented shaper/protuberance roots or commercial material-factor inputs.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import re

from ..kernel import units as U
from ..kernel.graph import Formula, InputSpec, Model
from . import kisssoft_case as KC
from .dynamic import CONSTANTS
from .inputs import full_input_table, input_specs
from .load_distribution import set_ld_constants
from .rating import LIBRARY_EDITIONS, pair_model

DATA = Path(__file__).resolve().parents[2] / "data" / "kisssoft"
CASES = ("K02-helical", "K03-premachining", "K04-EV-stage1", "K05-EV-stage2")
F, S = Formula, InputSpec
# 报告显示值之外的原生全精度证据（KISSsoft .Z12 字段）与 P4 轮新增的显式口径，逐例登记来源
EXTRAS_FILE = DATA / "K02-K05-extras.json"
THETA_STEP = "kisssoft_step_1e-5"     # KISSsoft θ 迭代终止准则：相邻迭代差<1e-5 即取最新迭代值
THETA_TOL = 1e-5
RIM_MIN = "minimum_root_diameter_df_i"   # YB 的轮缘厚 sR 从最小根圆直径 df.i 量起（KISSsoft：K04 报告 [sr]）


# 本模块新增的比较量：报告 13.1 轮坯质量（核对原生 ρ 与 di，是 m_red 的输入一致性证据）
MULTI_OUTPUTS = [(2, "mass_1", "report:mass_1", "kg"), (2, "mass_2", "report:mass_2", "kg"),
                 (6, "Y_B_1", "com:ZR[0].Fuss.YB", "1"), (6, "Y_B_2", "com:ZR[1].Fuss.YB", "1")]


def load(case):
    return case if isinstance(case, dict) else json.loads((DATA / f"{case}.json").read_text(encoding="utf-8"))


def extras(case_id):
    """P4 补充契约：原生全精度字段 + 附加适配口径；缺失即拒绝（不静默回退到报告 2 位小数/假设密度）。"""
    rows = json.loads(EXTRAS_FILE.read_text(encoding="utf-8"))["cases"]
    if case_id not in rows:
        raise ValueError("No native-evidence/extras contract for " + str(case_id))
    return rows[case_id]


ZV_SELECTOR = "method.Z_V_velocity"


def _zv_selector_declared():
    """P1 轮在 factor_methods.FACTOR_OPTIONS 增设 method.Z_V_velocity ∈ {v_w, v_ref} 后才为真；未合入时返回 False。"""
    from .factor_methods import FACTOR_OPTIONS
    return ZV_SELECTOR in FACTOR_OPTIONS


def _factor_selectors(x):
    """案例契约声明的系数方法选择器；ZV 速度口径选择器只在模型已声明时才传入（否则由适配层局部公式承担）。"""
    fx = x.get("factors")
    if not fx:
        return None
    sel = dict(fx["selectors"])
    src = dict(fx["selector_sources"])
    if _zv_selector_declared():
        sel[ZV_SELECTOR] = fx["Z_V_velocity"]["select"]
        src[ZV_SELECTOR] = fx["Z_V_velocity"]["evidence"]
    return sel, src


def _word(expr, name, replacement):
    return re.sub(r"\b" + re.escape(name) + r"\b", replacement, expr)


def _formulas(data):
    """Specialize existing formulas, then explicitly replace declared geometry."""
    x = extras(data["id"])
    fsel = _factor_selectors(x)
    base = pair_model(selectors=data["selectors"]) if fsel is None else \
        pair_model(selectors=data["selectors"], factor_selectors=fsel[0], factor_selector_sources=fsel[1])
    local_zv = fsel is not None and not _zv_selector_declared()
    rim_min = fsel is not None and fsel[0].get("method.root_aux") == "external_annular" \
        and x["adapter_selectors"].get("rim_thickness_root_circle") == RIM_MIN
    fs = []
    theta_tol = THETA_TOL if extras(data["id"])["adapter_selectors"].get("root_theta_iteration") == THETA_STEP else None
    shaper = data["id"] == "K03-premachining"
    for f in base.formulas.values():
        expr, output = f.expr, f.output
        if shaper and f.id.startswith("root."):
            continue
        if output == "rack_E":
            for i in (1, 2):
                local = _word(_word(expr, "hfP", f"hfP_{i}"), "rhofP", f"rhofP_{i}")
                fs.append(replace(f, id=f"km.rack_E.{i}", output=f"rack_E_{i}", expr=local))
            continue
        if shaper and output in ("df_1", "df_2"):
            continue
        for i in (1, 2):
            if output == f"da_{i}":
                expr = f"d_{i} + 2*m_n*(haP_{i} + x_{i}) + 2*k_X_{i}"
            if output == f"df_{i}":
                expr = f"d_{i} - 2*m_n*(hfP_{i} - x_{i})"
            if output in (f"bh_{i}", f"sigma_F_{i}"):
                expr = _word(expr, "b", f"b_{i}")
            if output == f"sigma_F_{i}":
                expr = _word(expr, "Y_B", f"Y_B_{i}")
            if output == f"zn_c_{i}":
                expr = f"zn_{i}"
            if output.endswith(f"_{i}") and f.id.startswith("root."):
                for old, new in (("rack_E", f"rack_E_{i}"), ("hfP", f"hfP_{i}"), ("rhofP", f"rhofP_{i}")):
                    expr = _word(expr, old, new)
        if output == "C_B":
            expr = _word(expr, "hfP", "((hfP_stiff_1 + hfP_stiff_2)/2)")
        if output in ("Z_B", "Z_D") and data['adapter_selectors']['contact_stress_adjustment']=='report_fZCa':
            fs.append(replace(f, output=output+'_iso', id=f.id+'.iso', expr=expr))
            fs.append(F(f'km.{output}.fZCa', output, '1', f'{output}_iso*sqrt(f_ZCa)',
                        'ISO 6336-2:2019 6.3b equation (19), PDF24; report fZCa is explicit evidence input',
                        ('eps_beta >= 1', 'eps_alpha > 1'),
                        note='This adapter is restricted to the supplied overlap>=1 cases; K04 high-contact 6.4 applicability remains conditional'))
            continue
        if rim_min and f.id.startswith("rf.rim_thickness."):
            # 报告 [sr]（K04 第1037行 16.26/7.53）= (df.i − di)/2，df.i 为含齿厚/根径偏差的最小根圆直径；
            # 库公式用名义 df，对 K04 大轮 YB 差 −4.2%。df.i 本身见下方 km.df_min（与原生 ZR[i].df.i 逐位一致）
            fs.append(replace(f, expr=expr.replace("df_", "df_min_"),
                              domain=tuple(t.replace("df_", "df_min_") for t in f.domain),
                              note=f.note + "; 适配层：sR 从最小根圆 df.i 量起"))
            continue
        if local_zv and output == "Z_V":
            # ISO 6336-2:2019 12.3.2.2.1 文字写"circumferential velocity at the pitch line"，式(47)写 v_w；
            # KISSsoft（K01–K05）与 TR30 附录 A.9.2 一致取参考圆线速度 v。method.Z_V_velocity 合入后本分支自动失效
            fs.append(replace(f, expr=_word(expr, "surface_v_w", "v"),
                              note=f.note + "; 适配层局部：速度取参考圆 v（见 data/kisssoft/K02-K05-extras.json factors.Z_V_velocity）"))
            continue
        if output in ("f_pbT_1", "f_pbT_2") and data["id"] in ("K02-helical", "K05-EV-stage2"):
            # DIN3961 and ISO1328:1995 reported base-pitch tolerances are
            # independent manufacturing inputs, not inferred from target KV.
            expr = "f_base_" + output[-1]
        if theta_tol is not None and f.kind == "fixed_point" and output in ("theta_1", "theta_2"):
            # KISSsoft 的 θ 迭代以相邻差<1e-5 终止；收敛到 1e-14 的值与 COM sFn/hF/roF 差 ≤1.8e-5（K05 qs1 末位分歧来源）
            fs.append(replace(f, expr=expr, tol=theta_tol, fixed_point_derivative="finite_iteration",
                              note=f.note + f"; KISSsoft 终止准则 |Δθ|<{theta_tol:g}（显式适配口径，非标准条款）；导数对应相同截断迭代"))
            continue
        fs.append(replace(f, expr=expr, note=f.note + "; explicit K02-K05 adapter" if expr != f.expr else f.note))
    if rim_min:
        for i in (1, 2):
            fs.append(F(f"km.df_min.{i}", f"df_min_{i}", "mm", f"d_{i} - 2*m_n*(hfP_{i} - xE_{i})",
                        "最小根圆直径 df.i（xE,i 为最小齿厚偏差下的生成变位）；原生 ZR[i].df.i 对 K02/K04/K05 逐位一致，报告 [df.e/i]"))
    # 轮坯质量（报告 13.1 [m]）：ρ·π/4·(dm²−di²)·b，dm=(da+df)/2；只作输入一致性比较，不进入强度链
    for i in (1, 2):
        fs.append(F(f"km.mass.{i}", f"mass_{i}", "kg", f"rho_{i}*pi/4*(dm_{i}**2 - d_inner_{i}**2)*b_{i}",
                    "KISSsoft 报告 13.1 质量（(da+df)/2…di 圆环）；本库 ISO 6336-1 6.5.9 式(31)(32) 同一齿坯假设"))
    fs.append(F("km.b", "b", "mm", "min(b_1,b_2)",
                "ISO 6336-1:2019 effective contact facewidth; KISSsoft reports b_eff=min(b1,b2)"))
    if data["selectors"]["method.K_Hbeta"] == "C":
        fs.append(F("km.f_ma_B2", "f_ma_B2", "um", "B_2*f_ma",
                    "ISO 6336-1:2019 equation (54); report labels the product fm_alpha*B2"))
    if "bs_b" in data["report"]:
        fs += KC.BLANK
    else:
        # q is still calculated; C_R itself remains evidence, visibly excluded
        # from formula validation when blank dimensions were not supplied.
        fs += [f for f in KC.BLANK if f.output.startswith("q_")]
    return base, fs


def _set_factor_inputs(m, d, x, sel, put, report):
    """把案例契约声明的系数方法所需输入映射进模型；每个值都有报告行/COM 字段/原生文件行/标准条款出处。
    不读取 KISSsoft 的系数结果来算系数本身（ZL/ZV/ZR/ZNT/YNT/Yδ/YR/YX/ZW/ZX/YB/YDT 的 COM 值只作比较目标）。"""
    from .root_factors import set_root_constants
    from .surface_factors import set_surface_constants
    c, rep, fx = d["com"], d["report"], x["factors"]
    if sel.get("method.Z_LVR") == "B_reference":
        s1, s2 = c["ZR[0].mat.limh"], c["ZR[1].mat.limh"]
        put("sigma_Hlim_surface", min(s1, s2), "MPa", "evidence",
            "COM ZR[0/1].mat.limh 取较小者；ISO 6336-2:2019 12.3.2.2.1 PDF35/印刷27 'σH lim of the softer of the materials'")
        put("surface_oil_mineral", 1, "1", "evidence", f"report line {fx['mineral_oil_line']} 'Mineral-oil base'")
        report("nu_40", "nu_40")
        rz = fx["roughness"]
        for i in (1, 2):
            put(f"Rz_H_{i}", rz["Rz_H"][i - 1], rz["unit"], "evidence", f"report [RZH] line {rz['Rz_H_line']} 第{i}列")
        put("surface_nu40_vi95", 1, "1", "assumption",
            "报告给出 ν40/ν100 但库公式只接受 ν40/VI95 基准：按 ISO 6336-2:2019 12.3.2.1.1 显式接受该近似")
        for i in (1, 2):
            h = fx["N_Href"][i - 1]
            put(f"N_Href_{i}", h["value"], "1", "assumption", h["source"])
        set_surface_constants(m)
    if "life_duration" in m.specs:      # 任一寿命相关方法非 external 时 N_L 由工况恒等式给出
        put("life_duration", c["ZS.H"] * 3600, "s", "user", "COM ZS.H，小时换算为秒")
        for i in (1, 2):
            put(f"cycles_per_rev_{i}", 1, "1", "assumption", "单向单啮合，每转受载一次；显式工况假设，报告 NL 只作对照")
    else:
        for i in (1, 2):
            row = rep[f"N_L_{i}"]
            put(f"N_L_{i}", row["value"], row["unit"], "evidence", f"report {row['label']} line {row['line']}（原报告单位为百万次，已换算）")
    if sel.get("method.root_factors") == "case_hardened_reference":
        rz = fx["roughness"]
        for i in (1, 2):
            put(f"Rz_F_{i}", rz["Rz_F"][i - 1], rz["unit"], "evidence", f"report [RZF] line {rz['Rz_F_line']} 第{i}列")
            put(f"root_surface_intact_{i}", 1, "1", "assumption", "按粗糙度模型假设齿根无深划痕；原始报告未提供实测表面完整性证据")
        set_root_constants(m)
    if sel.get("method.contact_aux") == "both_case_hardened":
        put("aux_both_case_hardened", 1, "1", "evidence", f"report line {fx['both_case_hardened_line']} 两轮均 'Case hardening steel, case-hardened'")
    if sel.get("method.root_aux") == "external_annular":
        for i in (1, 2):
            g = rep[f"Q_grade_{i}"]
            put(f"DT_grade_{i}", g["value"], "1", "user", f"report {g['label']} line {g['line']}")
        pm = d["report_text"]["profile_modification"]
        put("DT_profile_modified", fx["profile_modified"], "1", "user", f"report line {pm['line']} {pm['text']}")
        set_root_constants(m)
    return m


def build_model(case):
    d = load(case)
    if d.get("id") not in CASES:
        raise ValueError("No multi-case contract for " + str(d.get("id")))
    c, rep = d["com"], d["report"]
    if d.get('editions') != LIBRARY_EDITIONS or set(d.get('edition_sources', {})) != set(LIBRARY_EDITIONS):
        raise ValueError('Explicit editions and per-part report sources are required')
    adapter=d.get('adapter_selectors', {})
    required_adapter={'geometry.widths':'individual_root_min_contact','geometry.tip':'additive_kXmn_mm',
                      'geometry.root':'evidence_shaper_unsupported' if d['id'].startswith('K03') else 'individual_rack',
                      'stiffness_teeth':'exact_geometry',
                      'contact_stress_adjustment':'none_spur' if d['id'].startswith('K03') else 'report_fZCa'}
    if adapter != required_adapter:
        raise ValueError('Explicit geometry/stiffness/adjustment selectors missing or unsupported')
    x = extras(d["id"])
    fsel = _factor_selectors(x)
    root_aux_wired = fsel is not None and fsel[0].get("method.root_aux") == "external_annular"
    if c["RechSt.RechenMethID"] != 10029 or c["RechSt.GeometrieMeth"] != 1:
        raise NotImplementedError("Case editions/methods differ from the explicit contract")
    if c["Zst.KVFlag"] != "false" or c["Zst.KHaFlag"] != "false":
        raise NotImplementedError("KV/KHa are not automatic in the supplied source")
    if c["Zst.KHbVariant"] not in (0, 1):
        raise NotImplementedError("Unmapped KHbeta automatic/input flag")
    wanted = "C" if c["Zst.KHbVariant"] == 0 else "external"
    if d["selectors"]["method.K_Hbeta"] != wanted:
        raise ValueError("KHbeta method contradicts original automatic/input flag")
    base, fs = _formulas(d)
    extra = []
    extra.append(S('f_ZCa','1','Explicit commercial report additional contact-stress correction',('f_ZCa >= 1',)))
    for i in (1, 2):
        extra += [S(f"b_{i}", "mm", "Individual root effective width", (f"b_{i} > 0",)),
                  S(f"haP_{i}", "1", "Individual final rack addendum", (f"haP_{i} > 0",)),
                  S(f"hfP_{i}", "1", "Individual final rack dedendum", (f"hfP_{i} > 0",)),
                  S(f"rhofP_{i}", "1", "Individual final rack radius", (f"rhofP_{i} >= 0",)),
                  S(f"hfP_stiff_{i}", "1", "Final rack dedendum for mean stiffness factor", (f"hfP_stiff_{i} > 0",)),
                  S(f"k_X_{i}", "mm", "Signed additive tip alteration kXmn, millimetres"),
                  S(f"f_base_{i}", "um", "Explicit base pitch tolerance from source", (f"f_base_{i} > 0",)),
                  S(f"df_{i}", "mm", "Evidence shaper root diameter; not a formula validation", (f"df_{i} > 0",))]
        if not root_aux_wired:   # 选 method.root_aux=external_annular 后 Y_B_i 为公式输出，不再是证据输入
            extra.append(S(f"Y_B_{i}", "1", "Individual rim factor, explicit commercial evidence", (f"Y_B_{i} > 0",)))
    table = full_input_table() + KC.BLANK_INPUTS + extra
    if fsel is not None:
        from .factor_methods import compile_factors, validation_status
        table += compile_factors(fsel[0])[1]
    m = Model(fs, inputs=input_specs(fs, table), editions=d['editions'])
    for part,edition in d['editions'].items():
        m.set_edition(part,edition,d['edition_sources'][part])
    m.selectors = dict(d["selectors"])
    m.selectors.update(adapter)
    m.selectors.update(x["adapter_selectors"])
    m.selector_sources = {k: f"{d['id']} explicit contract, source hashes in data/kisssoft/{d['id']}.json" for k in m.selectors}
    m.selector_sources.update(d['adapter_selector_sources'])
    m.selector_sources.update(x["adapter_selector_sources"])
    if fsel is not None:
        m.selectors.update(fsel[0])
        m.selector_sources.update(fsel[1])
        m.factor_validation = validation_status(fsel[0])
    m.required_evidence = base.required_evidence.copy()

    def put(name, value, unit, provenance="user", source=""):
        if name in m.specs:
            m.set(name, value, unit, provenance, f"{d['id']}: " + source)

    def report(name, key, unit=None):
        if name in m.specs:
            r = rep[key]
            put(name, r['value'], unit or r['unit'], "user", f"report {r['label']}, extracted.txt line {r['line']}")

    for name, unit, key, note in KC.INPUT_MAP:
        if name in ("b", "haP", "hfP", "rhofP"):
            continue
        if isinstance(key, tuple):
            if c[key[0]] != c[key[1]]:
                raise NotImplementedError(f"Single input {name} differs across gears")
            value = c[key[0]]
        else:
            value = c[key]
        put(name, value, unit, source=f"COM {key}; {note}")
    # Nominal power/speed, never the commercial target torque/stress.
    power = U.to_canonical(c['ZS.Pnominal'], 'kW')
    speed = U.to_canonical(c['ZR[0].nnominal'], 'rpm')
    put('T_1', power/(2*math.pi*speed), 'N*mm', 'derived', 'P/(2*pi*n), COM ZS.Pnominal and ZR[0].nnominal')
    for i in (1, 2):
        prefix = f'ZR[{i-1}]'
        put(f'b_{i}', c[prefix+'.b'], 'mm', source='COM '+prefix+'.b; report root beff')
        for stem in ('haP','hfP','rhofP'):
            put(f'{stem}_{i}', c[prefix+'.Tool.RefProfile.'+stem], '1', source='COM '+prefix+'.Tool.RefProfile.'+stem)
        # The shaper's finished reference rack differs from the cutting tool.
        if d['id'].startswith('K03'):
            report(f'hfP_stiff_{i}', f'hfP_final_{i}')
        else:
            put(f'hfP_stiff_{i}', c[prefix+'.Tool.RefProfile.hfP'], '1', source='COM final rack dedendum')
        put(f'k_X_{i}', c[prefix+'.kXmn'], 'mm', source='COM '+prefix+'.kXmn (dimensional k*mn)')
        put(f'C_f_{i}', c[prefix+'.Cf'], 'um', source='COM '+prefix+'.Cf')
        report(f'A_sn_i_{i}', f'A_sn_i_{i}')
        # 轮坯内径：报告 [di] 只有 2 位小数（K04 大轮 128.54，原生 128.537 → nE1/mRed 末位分歧的来源）；
        # 取原生全精度值，且必须落在报告显示值的半个末位内，否则拒绝（不能用原生字段悄悄改写报告）
        r = rep[f'd_inner_{i}']; di = x["native"]["fields"][f"ZR[{i-1}].di"]
        if abs(di["value"] - r["value"]) > 0.5 * 10 ** (-r["decimals"]) * (1 + 1e-9):
            raise ValueError(f"native di {di['value']} 与报告 {r['value']} 不一致")
        put(f'd_inner_{i}', di["value"], di["unit"], 'evidence',
            f"native {x['native']['file']} line {di['line']} ZR[{i-1}].di (report [di] line {r['line']} 仅 {r['decimals']} 位小数); sha256 {x['native']['sha256'][:12]}")
        report(f'f_pt_{i}', f'f_pt_{i}')
        report(f'f_base_{i}', f'f_pbT_{i}')
        report(f'f_falpha_{i}', f'f_falpha_{i}')
        report(f'f_Hbeta_{i}', f'f_Hbeta_{i}')
        put(f'mat_group_{i}', 3, '1', source='Report material: nitrided/case-hardened steel; group 3')
        # 密度：原生文件 ZR[i].mat.rho（kg/m³）；报告无齿轮密度，旧版以 7.83e-6 假设，现由原生字段取代
        nat = x["native"]; rho = nat["fields"][f"ZR[{i-1}].mat.rho"]
        put(f'rho_{i}', rho["value"], rho["unit"], 'evidence', f"native {nat['file']} line {rho['line']} ZR[{i-1}].mat.rho; sha256 {nat['sha256'][:12]}")
        if d['id'].startswith('K03'):
            put(f'df_{i}', c[prefix+'.df.nul'], 'mm', 'evidence', 'COM '+prefix+'.df.nul; unsupported shaper geometry')
        put(f'Y_B_{i}', c[f'ZR[{i-1}].Fuss.YB'], '1', 'evidence', f'COM ZR[{i-1}].Fuss.YB; per-gear rim factor')   # 已公式化时 put 自动跳过
    if min(rep['Q_grade_1']['value'], rep['Q_grade_2']['value']) < 6:
        raise NotImplementedError('Different per-gear Bk branches require explicit implementation')
    put('Q_grade', min(rep['Q_grade_1']['value'], rep['Q_grade_2']['value']), '1', source='Both reported grades >=6; Bk=1 for both gears')
    if 'bs_b' in rep:
        report('bs_b','bs_b');report('sR_mn','sR_mn')
    else:
        r=rep['C_R'];put('C_R',r['value'],'1','evidence',f"report {r['label']} line {r['line']}; blank dimensions unavailable")
    if 'f_ZCa' in m.specs:
        row=rep['f_ZCa'];put('f_ZCa',row['value'],'1','evidence',f"report {row['label']} line {row['line']}; {row['note']}")
    if fsel is not None:
        _set_factor_inputs(m, d, x, fsel[0], put, report)
    for name, key, note in KC.EVIDENCE_MAP + [r for key, rows in KC.EXTERNAL_EVIDENCE.items() if d['selectors'].get(key)=='external' for r in rows]:
        if name not in m.specs:
            continue
        if isinstance(key, tuple):
            if c[key[0]] != c[key[1]]:
                raise NotImplementedError(f'Common factor {name} differs between gears')
            value=c[key[0]]
        else:value=c[key]
        put(name,value,'1','evidence',f'COM {key}; coefficient not independently verified by this adapter')
    for name in ('K_gamma','l_sh','s_sh','d_sh','pinion_arrangement','f_Hbeta5','S_Hmin','S_Fmin'):
        if name in m.specs:report(name,name)
    if d['selectors']['method.K_Hbeta']=='C':
        put('pinion_stiffening',0,'1',source='Report Without stiffening')
        put('helix_mod',3 if d['id'].startswith('K02') else 1,'1',source='Report crowned Cbeta=.5(fma+fsh)' if d['id'].startswith('K02') else 'Report tooth without flank line modification')
        put('contact_favourable',1,'1',source='Report Position of contact pattern: favorable')
        put('B_star',1,'1',source='Single mesh power path, ISO 6336-1 equation (59)')
    put('k_pb',1 if d['id'].startswith('K03') else .5,'1',source='Report profile modification setting; ISO 6336-1 8.3.2')
    for name,value,unit,source in CONSTANTS:
        put(name,value,unit,'standard_constant',source)
    set_ld_constants(m)
    return m,d


def compare(case):
    m,d = build_model(case)
    x = extras(d['id'])
    unsupported=[]
    if d['id'].startswith('K03'):
        unsupported=['root_geometry_shaper_protuberance','sigma_F_1','sigma_F_2','S_F_1','S_F_2']
    outputs=[]
    for stage,name,source,unit in KC.OUTPUTS + MULTI_OUTPUTS:
        if d['id'].startswith('K03') and (name.startswith(('xE_','den_','alpha_Fen_','sFn_','hFe_','rhoF_','qs_','Y_F_','Y_S_','sigma_F','S_F')) or name=='Y_beta'):
            continue
        kind,key=source.split(':',1)
        if key not in d['com' if kind=='com' else 'report']:
            continue
        if name == 'Y_B':
            continue   # 两轮 YB 可不同（K04），改比 Y_B_1/Y_B_2
        if name == 'f_ma':
            name = 'f_ma_B2'
        if name in m.formulas or (name in m.inputs and m.inputs[name].provenance=='derived'):
            outputs.append((stage,name,source,unit))
    result=m.evaluate([name for _,name,_,_ in outputs])
    head={'case':d['id'],'selectors':m.selectors,'model_sha256':result.model_sha256,
          'source_status':'original_case_and_report_hashes_recorded','product_strength':'not_assessed',
          'full_formula_validation':False,
          'standard_applicability_pending':['ISO 6336-2:2019 6.4 high-contact case conditions'] if d['id'].startswith('K04') else [],
          'unsupported':unsupported,'limitations':d['limitations'],
          'native_evidence':{'file':x['native']['file'],'sha256':x['native']['sha256'],'fields':x['native']['fields']},
          'z_v_velocity':{'selector_declared_in_library':_zv_selector_declared(),'select':x['factors']['Z_V_velocity']['select'],
                          'evidence':x['factors']['Z_V_velocity']['evidence']},
          'factor_validation':getattr(m,'factor_validation',{}),
          'wired_factor_formulas':sorted(q for q in ('Z_L','Z_V','Z_R','Z_NT_1','Z_NT_2','Y_NT_1','Y_NT_2','Y_drelT_1','Y_drelT_2','Y_RrelT_1','Y_RrelT_2','Y_X','Z_W','Z_X','Y_B_1','Y_B_2','Y_DT') if q in m.formulas),
          'factor_evidence_remaining':sorted(q for q in ('Z_L','Z_V','Z_R','Z_NT_1','Z_NT_2','Y_NT_1','Y_NT_2','Y_drelT_1','Y_drelT_2','Y_RrelT_1','Y_RrelT_2','Y_X','Z_W','Z_X','Y_B_1','Y_B_2','Y_DT') if q in m.inputs and m.inputs[q].provenance=='evidence'),
          'evidence_inputs':{name:{'value':U.from_canonical(v.value,v.unit),'unit':v.unit,'source':v.source} for name,v in m.inputs.items() if v.provenance=='evidence'},
          'assumptions':{name:{'value':U.from_canonical(v.value,v.unit),'unit':v.unit,'source':v.source} for name,v in m.inputs.items() if v.provenance=='assumption'}}
    if result.status!='ok':
        return {**head,'status':result.status,'rows':[],'first_divergence':None,'missing':result.missing,'errors':result.errors,'domain_violations':result.domain_violations}
    rows=KC._rows(d,result,outputs)
    first=next((r for r in rows if r['verdict']=='分歧'),None)
    return {**head,'status':'numerically_matched_conditional' if first is None and not unsupported else 'partial_or_divergent',
            'declared_formula_rows_matched':first is None,
            'rows':rows,'first_divergence':first,'matched_rows':sum(r['verdict']=='一致' for r in rows),'compared_rows':len(rows),
            'end_to_end_outputs':{q:result.values[q] for q in ('sigma_H_1','sigma_H_2','S_H_1','S_H_2','sigma_F_1','sigma_F_2','S_F_1','S_F_2') if q in result.values}}


def run_suite():
    return {'schema':'gearbase.kisssoft_multi_results/1','cases':[compare(case) for case in CASES],
            'scope':'conditional formula diagnostics; not TR30 and not product release'}


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    report=run_suite();text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text,encoding='utf-8')
    print(json.dumps([{'case':r['case'],'status':r['status'],'rows':r.get('compared_rows',0),'first_divergence':r['first_divergence']} for r in report['cases']],ensure_ascii=False,indent=2))
    raise SystemExit(0 if all(r['status']=='numerically_matched_conditional' for r in report['cases']) else 2)
