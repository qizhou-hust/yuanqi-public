"""Input-only full-rating diagnostic graph for TR30 external examples 1--4.

No raw_outputs value is read while constructing this graph. Unsupported
branches and extra applicability assumptions are exposed, not replaced with
reference coefficients. This diagnostic does not grant standard acceptance.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re

from ..kernel.graph import Formula, InputSpec, Model
from ..kernel import units as U
from .rating import pair_model, LIBRARY_EDITIONS
from .inputs import full_input_table, input_specs
from .dynamic import CONSTANTS
from .load_distribution import LD_CONSTANTS, _y_group
from .life_factors import LIFE_CYCLES, CYCLE_INPUTS
from .root_factors import ROOT_AUX_FACTORS, ROOT_AUX_INPUTS
from .tr30_geometry import patch_tr30_geometry, TR30_GEOMETRY_INPUTS
from .formulas import f_eps_kink_warnings
from .tr30_examples58 import build_probe
from .material_limits import select_material_limits
from .tr30_material_factors import material_formulas, TR30_MATERIAL_INPUTS, set_tr30_material_inputs
from .surface_factors import (SURFACE_REFERENCE_ENDPOINTS, SURFACE_PER_GEAR_FACTORS,
    SURFACE_INPUTS, PER_GEAR_SURFACE_INPUTS, CONTACT_STRESS_NO_PITTING, CONTACT_STRESS_INPUTS,
    ZV_VELOCITY_VARIANTS, set_surface_constants)
from .contact_factors import ZBD_VARIANTS, ZBD_INPUTS, set_contact_method_evidence
from .iso1328 import fhbeta5_formulas
from .tr30_shared import a6_root_form, a6_sap, FSH0, contact_path_formula

F, S = Formula, InputSpec
DATA=Path(__file__).resolve().parents[2]/'data/tr30/examples-1-4.json'


def load_cases():
    return json.loads(DATA.read_text(encoding='utf-8'))['cases']


def _raw(case):
    return {r['key']:r for r in case['raw_inputs']}


def _word(expr, old, new):
    return re.sub(r'\b'+re.escape(old)+r'\b',new,expr)


def _number(raw,key,index=0):
    value=raw[key]['values'][index]
    if type(value) not in (int,float):
        raise ValueError(f'Missing independent numeric input {key}[{index}]')
    return value


def _materials(raw):
    choices={}
    for i,(material,quality,hardness) in enumerate(zip(raw['material']['values'],raw['material_quality']['values'],raw['case_hardness']['values']),1):
        if material=='Eh':
            choices[str(i)]={'family':'case_hardened_wrought','quality':quality,'hardness_scale':'HRC60','core_branch':'ge30_HRC'}
        elif material=='V (alloy steel)':
            choices[str(i)]={'family':'through_hardened_wrought_alloy','quality':quality,'hardness_scale':'HV','core_branch':'not_applicable'}
        else:
            raise NotImplementedError(f'Unsupported material {material!r}')
    return select_material_limits(choices)


# 例1–4（及例5–8）显式适用性前提：逐项原文依据与消除所需证据（原图已核页码）。
PREMISE_BASIS = {
    "contact_path_not_shortened": {
        "premise": "式(17)(18) 计算 M1/M2 时，根切不缩短有效啮合线",
        "source": "ISO 6336-2:2019 6.3（PDF24/印16）原文：Formula (17) and (18) are not valid, if undercut shortens the path of contact",
        "eliminable_by": "TR30 A.6（阅读副本 PDF51–52/印45–46）dFf（无根切前提即其方括号 ≥ 0）与 dNf：|dNf| ≥ |dFf|（内齿反向）",
        "needed_if_not_eliminated": "根切或凸台齿形的 dFf 已核公式（ISO 21771 原文或 TR30/ISO 6336 明文），或商业工具复算的 dFf/dNf",
    },
    "surface_oil_mineral": {
        "premise": "润滑油为矿物油（式(42) 的适用对象）",
        "source": "ISO 6336-2:2019 12.3.1/12.3.2.1.1（PDF33/印25）：Z_L 由矿物油试验得出，式(42) 用于矿物油；"
                  "TR30 A.9.2（PDF59/印53）对例1 实际套用式(42)，TR30 4.1（PDF12/印6）称后续例只给表格",
        "eliminable_by": "原文无：TR30 任一例都未声明油品类别（表中只给 ν40）",
        "needed_if_not_eliminated": "TR30 原文对油品的明文声明，或用户批准'TR30 用式(42) 即视为矿物油口径'作为条件证据",
    },
    "surface_nu40_vi95": {
        "premise": "ν40 按 VI = 95 基准使用式(42)",
        "source": "ISO 6336-2:2019 12.3.2.1.1（PDF33/印25）：The values for ν40 apply for the kinematic viscosity index VI = 95；"
                  "TR30 A.9.2（PDF59/印53）直接以 ν40 代入式(42)",
        "eliminable_by": "原文无：TR30 表只给 ν40，未给 VI",
        "needed_if_not_eliminated": "TR30 原文给出 VI，或用户批准'TR30 用式(42) 即视为 VI95 口径'作为条件证据",
    },
    "root_surface_intact_1": {
        "premise": "小轮齿根无深于 2Rz 的划痕/缺陷，无晶界氧化、化学影响",
        "source": "ISO 6336-3:2019 14.1 NOTE（PDF46/印38）：The method applied here is only valid when scratches or similar "
                  "defects deeper than 2 × Rz are not present；TR30 A.10 14.3.2.1（PDF67/印61）对例1 实际套用式(87)",
        "eliminable_by": "原文无：TR30 未声明齿根表面完整性（属实物状态）",
        "needed_if_not_eliminated": "实物齿根检验记录（产品层面），或用户批准'TR30 例题复现按式(87) 口径'作为条件证据",
    },
    "root_surface_intact_2": {
        "premise": "大轮齿根无深于 2Rz 的划痕/缺陷，无晶界氧化、化学影响",
        "source": "同 root_surface_intact_1（ISO 6336-3:2019 14.1 NOTE，PDF46/印38；TR30 PDF67/印61）",
        "eliminable_by": "原文无",
        "needed_if_not_eliminated": "同 root_surface_intact_1",
    },
}


def premise_audit(model):
    out = {}
    for name, basis in PREMISE_BASIS.items():
        if name in model.formulas:
            out[name] = {"status": "eliminated_by_formula", "formula": model.formulas[name].id, **basis}
        elif name in model.inputs:
            out[name] = {"status": model.inputs[name].provenance, **basis}
    return out


def build_model(case, _contact_path=None):
    """由原表输入建图。啮合线不缩短前提（ISO 6336-2 6.3）先尝试用 A.6 dFf/dNf 在图内判定；
    不可判定（例4 小轮根切，A.6 前提不成立）时退回显式 assumption，并在 model.tr30_premise_audit 记原因。"""
    if _contact_path is None:
        first = build_model(case, "A6_formula")
        check = first.evaluate(["contact_path_not_shortened"])
        if check.status == "ok":
            return first
        second = build_model(case, "assumption")
        second.tr30_premise_audit["contact_path_not_shortened"]["fallback_reason"] = \
            f"A.6 判定不可用：{check.status} {check.domain_violations or check.errors}"
        return second
    if type(case) is int:
        case=next(c for c in load_cases() if c['example_number']==case)
    if case.get('example_number') not in (1,2,3,4):
        raise NotImplementedError('Full-rating diagnostic presently covers external examples 1--4 only')
    raw=_raw(case)
    if min(raw['z']['values']) <= 0:
        raise NotImplementedError('Internal rating is not implemented by this adapter')
    if any(v!=0 for key in ('pr','q','s_pr') for v in raw[key]['values']):
        raise NotImplementedError('Protuberance/pre-finishing allowance needs a separate root adapter')
    if raw['method_K_V']['values']!=['Method B'] or raw['method_K_Hbeta']['values']!=['Method C']:
        raise NotImplementedError('Explicit Method B / Method C source selections required')
    if raw['favorable_contact']['values']!=['No','No'] or raw['helix_modification']['values']!=['None (No. 1)']:
        raise NotImplementedError('This first full-rating subset selects the source no-compensation/no-helix-modification branch')
    if raw['blank']['values']!=['Solid','Solid']:
        raise NotImplementedError('Only explicitly solid blanks currently supported')
    for key in ('Z_NT_1e10','Y_NT_1e10'):
        if raw[key]['values']!=[.85,.85]:
            raise NotImplementedError('Long-life endpoint must explicitly select .85 in both gears')
    if raw['reverse_bending']['values']!=['No','No']:
        raise NotImplementedError('Reverse root loading correction not supplied')
    if _number(raw,'beta')==0:
        contact='spur'
    else:
        label=raw['f_ZCa']['values'][0]
        if label=='based on 3D load distribution program':contact='helical_3d'
        elif label=='No modification':contact='helical_unmodified'
        else:raise NotImplementedError(f'Unmapped fZCa input declaration {label!r}')
    limits=_materials(raw)
    # ZV速度口径须由契约显式给出并带页码出处；缺失即阻断（KeyError→blocked）
    zv_velocity=case['surface_selectors']['method.Z_V_velocity']
    zv_cite=case['surface_selector_citations']['method.Z_V_velocity']
    if zv_velocity not in ZV_VELOCITY_VARIANTS:
        raise NotImplementedError(f'Unknown Z_V velocity basis {zv_velocity!r}')
    probe=build_probe(case)
    selectors={'method.K_V':'B','method.m_red':'exact','method.f_pb':'fpbT',
               'method.K_Hbeta':'C','method.K_Halpha':'B','method.root_shift':'generating'}
    fs=patch_tr30_geometry(pair_model(selectors=selectors).formulas.values(),
                          shift_source='span',mass_root='nominal_annex_a',kfbeta_root='nominal_annex_a')
    formulas={f.output:f for f in fs}
    for f in probe.formulas.values():formulas[f.output]=f
    # Independent TR table inputs, notably da and aw, cannot be formula targets.
    for name in probe.inputs:formulas.pop(name,None)
    # Pair-specific rack and effective widths, without changing shared formulas.
    rack=formulas.pop('rack_E')
    for i in (1,2):
        expr=_word(_word(rack.expr,'hfP',f'hfP_{i}'),'rhofP',f'rhofP_{i}')
        formulas[f'rack_E_{i}']=replace(rack,id=f'trr.rack_E.{i}',output=f'rack_E_{i}',expr=expr)
    for name,f in list(formulas.items()):
        expr=f.expr
        for i in (1,2):
            if name.endswith(f'_{i}') and f.id.startswith('root.'):
                for old,new in (('hfP',f'hfP_{i}'),('rhofP',f'rhofP_{i}'),('rack_E',f'rack_E_{i}')):
                    expr=_word(expr,old,new)
            if name in (f'bh_{i}',f'sigma_F_{i}'):
                expr=_word(expr,'b',f'b_{i}')
            if name==f'sigma_F_{i}':expr=_word(expr,'Y_B',f'Y_B_{i}')
            if name==f'sigma_FG_{i}':expr=_word(expr,'Y_X',f'Y_X_{i}')
            if name==f'sigma_HG_{i}':
                for q in ('Z_L','Z_V','Z_R','Z_W','Z_X'):
                    expr=_word(expr,q,f'{q}_{i}')
        if name=='C_B':expr=_word(expr,'hfP','((hfP_1+hfP_2)/2)')
        formulas[name]=replace(f,expr=expr)
    # Numeric fsh/fma in the input table are genuine inputs, not output replay.
    for key in ('f_sh','f_ma'):
        if type(raw[key]['values'][0]) in (int,float):formulas.pop(key,None)
    formulas.pop('F_bx_comp',None)
    formulas['F_bx']=F('trr.F_bx.no_favourable','F_bx','um','max(F_bx_add,F_bx_min)',
                         'ISO 6336-1:2019 equation (54)/(58); TR input explicitly says favorable contact No')
    formulas['b']=F('trr.b','b','mm','b_eff','ISO/TR 6336-30:2022 input table effective contact width')
    formulas['C_R']=F('trr.CR.solid','C_R','1','1','ISO 6336-1:2019 9.3.2 solid-blank branch')
    for i in (1,2):
        formulas[f'q_{i}']=F(f'trr.q.solid.{i}',f'q_{i}','1','0','ISO 6336-1:2019 equation (32), explicitly solid blank')
    # Real Ca_i and Cf_i replace the dynamic module's absent-relief Cay model.
    formulas['B_k']=F('trr.B_k.relief','B_k','1',
        'where(Q_grade >= 6, 1, abs(1-c_s*min(C_a_1+C_f_2,C_a_2+C_f_1)/line_load))',
        'ISO 6336-1:2019 equation (17), actual input tip/root relief and tolerance-class rule')
    formulas.pop('C_a',None)
    for stem,base in (('p','f_pb'),('f','f_falpha')):
        for i in ('1','2'):
            q=f'y_{stem}_{i}'
            formulas[q]=F(f'trr.{q}',q,'um',_y_group(i,160,12800,6400,.275,22,11,.075,3,base),
                           'ISO 6336-1:2019 6.5.4 and 8.3.6.2 equations (77)-(80), explicit material groups')
        formulas[f'y_{stem}']=F(f'trr.y_{stem}',f'y_{stem}','um',f'(y_{stem}_1+y_{stem}_2)/2',
                               'ISO 6336-1:2019 equation (80), two-material running-in mean')
    added=list(limits.formulas)+material_formulas(case)+LIFE_CYCLES+ROOT_AUX_FACTORS
    added+=SURFACE_REFERENCE_ENDPOINTS+SURFACE_PER_GEAR_FACTORS+CONTACT_STRESS_NO_PITTING+ZBD_VARIANTS[contact]
    added.append(ZV_VELOCITY_VARIANTS[zv_velocity])
    # 附录A A.6（PDF50–51/印45–46）：无根切、无凸台时的齿根形状圆与有效啮合起始圆（与例5–8 共用 tr30_shared）
    added+=[a6_root_form(i) for i in (1,2)]
    added+=[a6_sap(i,note='Tip form diameter taken as da (no tip chamfer declared in Tables 3/5/7/9); |dNf|<|dFf| is interference, out_of_domain') for i in (1,2)]
    # ISO 6336-2 6.3 式(17)(18) 前提"根切不缩短啮合线"由 A.6 dFf/dNf 判定（tr30_shared.contact_path_formula）
    if _contact_path=='A6_formula':added.append(contact_path_formula())
    # fHβ5：ISO 1328-1:2013 式(10)+5.2.3 图内取整（TR30 4.2.10，PDF13/印8）；fsh0：ISO 6336-1 表F.1（PDF137）
    added+=fhbeta5_formulas(lambda i:f'b_{i}')+[FSH0]
    added += [F('trr.surface_ref_material','sigma_Hlim_surface','MPa','sigma_Hlim_2',
                'Explicit TR1--4 reference-surface material selection: gear 2; same endpoint branch within supported pair'),
              F('trr.YST','Y_ST','1','2','ISO 6336-3:2019 standard test gear stress correction factor'),
              F('trr.sigma_F0.1','sigma_F0_1','MPa','F_t/(b_1*m_n)*Y_F_1*Y_S_1*Y_beta*Y_B_1*Y_DT', 'ISO 6336-3:2019 nominal root stress'),
              F('trr.sigma_F0.2','sigma_F0_2','MPa','F_t/(b_2*m_n)*Y_F_2*Y_S_2*Y_beta*Y_B_2*Y_DT', 'ISO 6336-3:2019 nominal root stress')]
    for i in (1,2):
        # No work-hardening credit is a declared conservative modelling choice;
        # no Brinell conversion or positive benefit is inferred from HV inputs.
        for end in ('static','ref'):
            added.append(F(f'trr.ZW.{end}.{i}',f'Z_W_{end}_{i}','1','1',
                           'ISO/TR 6336-30:2022 4.2.6 PDF14/printed8: both through/surface-hardened gears use ZW=1',
                           note='Original image checked; source material selection Eh/Eh or V/V, no HV-to-HB conversion'))
        added += [F(f'trr.Href.{i}',f'sigma_HG_ref_{i}','MPa',f'sigma_Hlim_{i}*Z_L_ref*Z_V_ref*Z_R_ref*Z_W_ref_{i}*Z_X_{i}',
                    'ISO 6336-2:2019 5.4.4.3 reference endpoint'),
                  F(f'trr.Hstatic.{i}',f'sigma_HG_static_{i}','MPa',f'1.6*sigma_Hlim_{i}*Z_W_static_{i}',
                    'ISO 6336-2:2019 Table 5 no-pitting static endpoint and equation (57)'),
                  F(f'trr.ZNTlong.{i}',f'Z_NT_long_{i}','1',f'where(N_L_{i} >= 5e7, Z_NT_{i}, 1)',
                    'ISO 6336-2:2019 independently selected long-life branch, no finite-life double counting'),
                  F(f'trr.HP.{i}',f'sigma_HP_{i}','MPa',f'sigma_HG_life_{i}/S_Hmin',
                    'ISO 6336-2:2019 permissible contact stress, whole-stress life path'),
                  F(f'trr.FP.{i}',f'sigma_FP_{i}','MPa',f'sigma_FG_{i}/S_Fmin',
                    'ISO 6336-3:2019 permissible root stress'),
                  F(f'trr.Z_N.{i}',f'Z_N_{i}','1',f'sigma_HG_life_{i}/sigma_HG_ref_{i}',
                    'ISO/TR 6336-30:2022 4.2.5: combined-stress life coefficient, distinct from ZNT'),
                  F(f'trr.Y_N.{i}',f'Y_N_{i}','1',f'Y_NT_{i}',
                    'ISO 6336-3:2019 reference/long-life root branch: combined and explicit life factor coincide',
                    (f'N_L_{i} >= 3e6',))]
    for f in added:formulas[f.output]=f
    for i in (1,2):
        factor_path=formulas[f'sigma_HG_{i}']
        formulas[f'sigma_HG_factor_{i}']=replace(factor_path,id=factor_path.id+'.factor_path',output=f'sigma_HG_factor_{i}')
        formulas[f'sigma_HG_{i}']=F(f'trr.HG.whole.{i}',f'sigma_HG_{i}','MPa',f'sigma_HG_life_{i}',
                                      'ISO/TR 6336-30:2022 4.2.5 PDF13/printed7: safety uses whole-stress limited-life interpolation')
    # Probe inputs win only as independent raw values; derived limits/factors
    # have no input declarations and cannot accidentally be reference-locked.
    specs=list(probe.specs.values())+full_input_table()+TR30_GEOMETRY_INPUTS+list(limits.inputs)+CYCLE_INPUTS
    specs+=ROOT_AUX_INPUTS+TR30_MATERIAL_INPUTS+SURFACE_INPUTS+PER_GEAR_SURFACE_INPUTS+CONTACT_STRESS_INPUTS+ZBD_INPUTS
    for i in (1,2):
        specs += [S(f'b_{i}','mm','Individual source facewidth',(f'b_{i} > 0',)),
                  S(f'rhofP_{i}','1','Individual source rack radius',(f'rhofP_{i} >= 0',)),
                  S(f'C_a_{i}','um','Actual tip relief from input table',(f'C_a_{i} >= 0',))]
    specs += [S('f_sh','um','Explicit numeric input shaft deformation'),S('f_ma','um','Explicit numeric input manufacturing misalignment')]
    editions={**LIBRARY_EDITIONS,'ISO/TR 6336-30':'2022','ISO 6336-5':'2016','ISO 1328-1':'2013'}
    model=Model(list(formulas.values()),inputs=input_specs(list(formulas.values()),specs),editions=editions)
    for name,value in probe.inputs.items():
        if name in model.specs:model.set(name,U.from_canonical(value.value,value.unit),value.unit,value.provenance,value.source)
    def put(name,value,unit,provenance='user',source=''):
        if name in model.specs:model.set(name,value,unit,provenance,source)
    def inp(name,key,index=0,unit=None):
        row=raw[key];cite=row['citation'];value=_number(raw,key,index)
        chosen=unit or row['unit']
        if row['unit']=='kN*m':value*=1000;chosen='N*m'
        if row['unit']=='h':value*=3600;chosen='s'
        put(name,value,chosen,'user',f"{cite['source']} PDF {cite['pdf_page']}: {cite['location']}")
    for name,key in (('E','E'),('nu','nu'),('K_A','K_A'),('K_gamma','K_gamma'),('nu_40','nu40'),('life_duration','life_h'),('l_sh','bearing_span'),('s_sh','bearing_offset'),('d_sh','shaft_diameter'),('S_Hmin','S_Hmin'),('S_Fmin','S_Fmin')):
        inp(name,key)
    for i in (1,2):
        for name,key in ((f'b_{i}','b'),(f'hfP_{i}','hfP'),(f'rhofP_{i}','rhofP'),(f'C_a_{i}','C_a'),(f'C_f_{i}','C_f'),(f'f_falpha_{i}','f_falpha'),(f'f_Hbeta_{i}','f_Hbeta'),(f'rho_{i}','rho'),(f'DT_grade_{i}','quality'),(f'cycles_per_rev_{i}','N_mesh')):
            inp(name,key,i-1)
        material=raw['material']['values'][i-1]
        put(f'mat_group_{i}',3 if material=='Eh' else 1,'1','user',f'Explicit source material {material}; ISO running-in material group')
        hard=raw['case_hardness']['values'][i-1]
        put(f'material_surface_hardness_{i}',float(re.search(r'\d+(?:\.\d+)?',hard).group()),'1','user',str(raw['case_hardness']['citation']))
        if material=='Eh':
            core=raw['core_hardness']['values'][i-1]
            put(f'material_core_hardness_{i}',float(re.search(r'\d+(?:\.\d+)?',core).group()),'1','user',str(raw['core_hardness']['citation']))
        put(f'd_inner_{i}',0,'mm','derived','TR input explicitly declares Solid blank; no annular bore')
        rough=str(raw['roughness_flank']['values'][i-1])
        ra_match=re.match(r'^\s*([+-]?\d+(?:[,.]\d+)?)',rough)
        if not ra_match:raise ValueError('Independent outer Ra value required')
        ra=float(ra_match.group(1).replace(',','.'))
        bracket=re.search(r'\(([^)]+)\)',rough)
        if not bracket:raise ValueError('TR4.2.7 explicit Rz parenthesis required in first subset')
        if abs(float(bracket.group(1).replace(',','.'))-6*ra)>1e-10:
            raise ValueError('Parenthesized Rz disagrees with independent Ra and TR4.2.7')
        put(f'Rz_H_{i}',6*ra,'um','derived','TR30 4.2.7 Rz=6Ra, independently checked against parentheses; '+str(raw['roughness_flank']['citation']))
    for key in ('f_sh','f_ma'):
        if type(raw[key]['values'][0]) in (int,float):inp(key,key)
    grade=min(raw['quality']['values'])
    if not(all(q<=5 for q in raw['quality']['values']) or all(q>=6 for q in raw['quality']['values'])):
        raise NotImplementedError('Mixed Bk tolerance-class branches need per-gear implementation')
    put('Q_grade',grade,'1','derived','Both source grades lie on the same Bk tolerance branch')
    put('k_pb',.5 if raw['profile_compensated']['values']==['Yes'] else 1,'1','user',str(raw['profile_compensated']['citation']))
    if raw['arrangement']['values']!=['a']:raise NotImplementedError('Only declared arrangement a in subset')
    for name,value,source in [('pinion_arrangement',1,'Source arrangement a'),('pinion_stiffening',1,'Explicit solid pinion stiffness interpretation; bearing offset is zero'),('B_star',1,'Source one-mesh power path'),('helix_mod',1,'Source None (No.1)'),('contact_favourable',0,'Source favorable contact No'),('DT_profile_modified',1 if raw['profile_compensated']['values']==['Yes'] else 0,'Source profile compensation flag')]:
        put(name,value,'1','user',source)
    for name,value,source in [('surface_oil_mineral',1,'Mineral-oil viscosity relation chosen for TR diagnostics; base-stock not explicitly qualified'),('surface_nu40_vi95',1,'Explicit VI95 approximation; raw table gives nu40, not VI'),('contact_path_not_shortened',1,'No active-path shortening in first external-rack diagnostic subset; full undercut audit pending')]:
        put(name,value,'1','assumption',source)
    put('contact_no_pitting_steel',1,'1','user','Raw source limited pitting No, material Eh/V')
    for name,value,unit,source in CONSTANTS+LD_CONSTANTS:put(name,value,unit,'standard_constant',source)
    limits.set_constants(model);set_surface_constants(model);set_tr30_material_inputs(model,case)
    set_contact_method_evidence(model,contact,str(raw['f_ZCa']['citation']))
    model.selectors={**selectors,'method.Z_BD':contact,'method.root_geometry':'TR30_span_generated_nominal_mass_height',
                     'method.Z_W':'TR30_4.2.6_same_hardened_pair','method.material_limits':'ISO6336-5_2016_explicit_MQ',
                     'method.contact_life_stress':'TR30_4.2.5_whole_stress_0.3705','method.Z_V_velocity':zv_velocity}
    model.selector_sources['method.Z_V_velocity']=f"{zv_cite['source']} PDF {zv_cite['pdf_page']}: {zv_cite['location']}"
    model.selector_sources.update({k:'TR30 raw input contract and explicit diagnostic scope' for k in model.selectors if k not in model.selector_sources})
    model.tr30_premise_audit=premise_audit(model)
    model.tr30_case=case['id'];model.tr30_diagnostic_limitations=[
        'Original geometry/reference-factor audit is separate from whole-model standard acceptance',
        'Mineral-oil VI95 and no-active-path-shortening applicability are explicit assumptions',
        'TR30 4.2.6 explicitly sets ZW=1 for both declared material pairs; no silent HV-to-HB conversion',
        'Per-factor finite-life decomposition and whole-stress 0.3705 interpolation remain separate outputs']
    return model


# Only these aliases have a documented meaning in the current full graph.
_OUTPUT_ALIASES={
    'da':'da','d_a':'da','db':'db','d_b':'db','df':'df','d_f':'df','xE':'xE','x_E':'xE',
    'd_w':'dw','v':'v_w','v_w':'v_w','c_gammaalpha':'c_gamma_alpha','c_gammabeta':'c_gamma_beta',
    'c_prime':'c_s','F_betax':'F_bx','F_betay':'F_by',
}
_STAGES=('geometry','load','K','Z/Y','stress','safety')


def _stage(key):
    if key.startswith('S_'):return 'safety'
    if key.startswith('sigma_'):return 'stress'
    if key.startswith(('Y_','Z_','f_eps')):return 'Z/Y'
    if key in ('F_t','v','v_w'):return 'load'
    if key.startswith(('K_','c_','f_','F_beta','y_','N_res','m_red')):return 'K'
    return 'geometry'


def compare_rating(case):
    """Evaluate every supported reference separately and preserve every blocker.

    The published .01 absolute and .5% relative criteria are required together.
    Compatibility with the printed rounding interval is reported separately;
    it never changes strict_match or grants acceptance.
    """
    if type(case) is int:case=next(c for c in load_cases() if c['example_number']==case)
    head={'id':case.get('id'),'example_number':case.get('example_number'),'accepted':False,
          'evidence_level':'not_assessed','product_strength':'not_assessed','numerical_complete':False,
          'scope':'input-only full-strength diagnostic, source/applicability acceptance remains independent'}
    try:model=build_model(case)
    except (KeyError,ValueError,NotImplementedError) as error:
        return {**head,'status':'blocked_unsupported_or_missing_inputs','errors':[str(error)],'rows':[],
                'first_divergence':None,'missing':[],'unsupported':[]}
    rows=[];unsupported=[];missing=set();blocked=[]
    for ref in case['raw_outputs']:
        key=ref['key'];prefix=_OUTPUT_ALIASES.get(key,key)
        for i,expected in enumerate(ref['values']):
            name=f'{prefix}_{i+1}' if len(ref['values'])==2 else prefix
            stage=_stage(key)
            row={'quantity':name,'source_quantity':key,'stage':stage,'reference':expected,'unit':ref['unit'],
                 'citation':ref['citation'],'display':ref['display'][i],'formula_derived':name in model.formulas}
            if type(expected) not in (int,float):
                rows.append({**row,'status':'reference_not_applicable','strict_match':False});continue
            if name in model.inputs:
                actual=U.from_canonical(model.inputs[name].value,model.inputs[name].unit)
                rows.append({**row,'actual':actual,'status':'input_not_formula','strict_match':False});continue
            if name not in model.formulas:
                unsupported.append(name)
                rows.append({**row,'status':'unsupported_no_formula','strict_match':False});continue
            result=model.evaluate([name])
            if result.status!='ok':
                missing.update(result.missing);blocked.append(name)
                rows.append({**row,'status':result.status,'missing':result.missing,'errors':result.errors,
                             'domain_violations':result.domain_violations,'strict_match':False});continue
            # TR30 表 fsh0 单位栏印 µm；ISO 6336-1 表F.1（PDF137）为 µm·mm/N，数值相同，按后者换算
            unit='um*mm/N' if name=='f_sh0' else ref['unit']
            try:actual=U.from_canonical(result.values[name],unit)
            except (ValueError,KeyError):
                # The source's stiffness notation is typographical only.
                if ref['unit']=='N/mm/um':actual=U.from_canonical(result.values[name],'N/(mm*um)')
                else:raise
            difference=actual-expected
            absolute=abs(difference)<=.01+1e-12
            relative=abs(difference)<=.005*abs(expected)+1e-12
            display=str(ref['display'][i]).replace(' ','').replace(',','.')
            dp=len(display.rsplit('.',1)[1]) if '.' in display else 0
            rounding=abs(difference)<=.5*10**(-dp)+1e-12
            rows.append({**row,'actual':actual,'difference':difference,'absolute_tolerance':.01,'relative_tolerance':.005,
                         'absolute_match':absolute,'relative_match':relative,'strict_match':absolute and relative,
                         'rounding_compatible':rounding,'status':'match' if absolute and relative else 'divergence'})
    rows.sort(key=lambda row:_STAGES.index(row['stage']))
    first=next((row for row in rows if row['status']=='divergence'),None)
    both=[]
    for i in (1,2):
        result=model.evaluate([f'sigma_HG_factor_{i}',f'sigma_HG_life_{i}',f'S_H_{i}'])
        if result.status=='ok':both.append({'gear':i,'sigma_HG_factor':result.values[f'sigma_HG_factor_{i}'],
                                           'sigma_HG_whole':result.values[f'sigma_HG_life_{i}'],
                                           'S_H_whole':result.values[f'S_H_{i}']})
    assumptions={name:{'value':U.from_canonical(value.value,value.unit),'unit':value.unit,'source':value.source}
                 for name,value in model.inputs.items() if value.provenance=='assumption'}
    feps=model.evaluate(['f_eps'])
    warnings=f_eps_kink_warnings(model,feps) if feps.status=='ok' else []
    targets=('K_V','K_Hbeta','K_Halpha','K_Falpha','K_Fbeta','sigma_H_1','sigma_H_2','sigma_F_1','sigma_F_2','S_H_1','S_H_2','S_F_1','S_F_2')
    actuals={}
    for q in targets:
        result=model.evaluate([q])
        if result.status=='ok':actuals[q]=result.values[q]
    return {**head,'status':'full_rating_diagnostic','model_sha256':model.sha256(),'selectors':model.selectors,
            'selector_sources':model.selector_sources,'rows':rows,'first_divergence':first,
            'missing':sorted(missing),'unsupported':sorted(set(unsupported)),'blocked_outputs':blocked,
            'formula_rows':sum(r['formula_derived'] for r in rows),'strict_matched_rows':sum(r.get('strict_match',False) for r in rows),
            'rounding_compatible_rows':sum(r.get('rounding_compatible',False) for r in rows),
            'end_to_end_outputs':actuals,'assumptions':assumptions,'contact_life_paths':both,'warnings':warnings,
            'limitations':model.tr30_diagnostic_limitations,'premise_audit':model.tr30_premise_audit}


compare_case=compare_rating


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    report={'schema':'gearmath.tr30_full_rating_diagnostic/v1','cases':[compare_rating(case) for case in load_cases()]}
    content=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(content,encoding='utf-8')
    print(json.dumps([{'example':r['example_number'],'strict_matches':r.get('strict_matched_rows'),
                      'formula_rows':r.get('formula_rows'),'unsupported':r.get('unsupported'),
                      'first_divergence':r['first_divergence']} for r in report['cases']],ensure_ascii=False,indent=2))
    raise SystemExit(2)
