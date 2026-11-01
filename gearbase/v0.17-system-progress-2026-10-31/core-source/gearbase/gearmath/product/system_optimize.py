"""Finite exact joint search, with scoped checks, conservative rejection and local cache.

No physics in this adapter. Every evaluated subproblem invokes design_check with
fresh contexts; only exact immutable input identities permit same-run reuse.
"""
import copy
import hashlib
import inspect
import json
import pathlib
from ..gear import source_optimize as SO
from ..gear import factor_recompute as FR
from ..gear import math_source as MS
from ..kernel import units as U
from ..system.system_optimize import total_volume_mm3
from ..system import iso281 as BRG, din6892 as KEY, shaft_line as SL
from . import design_check as DC
from . import system_input as SIN

HARD_MAX = 10000
SCOPES = ('gear_rating', 'shaft', 'bearing', 'key')


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()



def _certificates(doc):
    errors=MS.verify_certificates(doc)
    if errors:
        raise ValueError('Certificate verification failed: '+json.dumps(errors,ensure_ascii=False))
    rows=[]
    for name,leaf in sorted(doc['evidence'].items()):
        cert=leaf['certificate']
        if cert['kind']=='file':
            actual=hashlib.sha256((pathlib.Path(MS.ROOT)/cert['ref']).read_bytes()).hexdigest()
            if actual!=cert['sha256']:
                raise ValueError('Certificate bytes changed while taking identity: '+cert['ref'])
            rows.append({'evidence':name,'ref':cert['ref'],'actual_sha256':actual})
    return rows


def _nonnull(obj):
    if isinstance(obj, dict):
        if 'value' in obj and (obj['value'] is None or not obj.get('source')):
            raise ValueError('Explicit component leaf missing value/source')
        for val in obj.values():
            _nonnull(val)
    elif isinstance(obj, list):
        for val in obj:
            _nonnull(val)




def _design_refs(obj, available):
    if isinstance(obj, dict):
        if 'from_design' in obj and obj['from_design'] not in available:
            raise ValueError('Unknown/unavailable design quantity '+str(obj['from_design']))
        for value in obj.values(): _design_refs(value,available)
    elif isinstance(obj,list):
        for value in obj: _design_refs(value,available)


def _required(record, names, path):
    missing = set(names)-set(record)
    if missing:
        raise ValueError(path+': missing '+', '.join(sorted(missing)))


def _component_requirements(si):
    # Input shape only: use canonical L2 signatures for mandatory arguments.
    # This bounded route supports the existing explicit two-support shaft model.
    for i, sh in enumerate(si['shafts']):
        path='shafts['+str(i)+']'
        _required(sh, set(inspect.signature(SL.solve).parameters)|{'sections','bearings'}, path)
        if not sh['segments'] or not sh['loads'] or not sh['sections']:
            raise ValueError(path+': nonempty geometry, loads and safety sections required')
        _required(sh['bearings'], ('A','B'), path+'.bearings')
        for segment in sh['segments']:
            _required(segment, ('x0','x1','d','d_i'), path+'.segments')
        for load in sh['loads']:
            kind=load.get('kind')
            constructors={'torque':SL.torque_load,'line':SL.line_load,'point':SL.point_load}
            if kind=='mesh':
                # design_check._mesh_load names the diameter d_w and derives
                # F_t/F_r/F_a via mesh_forces; keep this explicit adapter map.
                names=(set(inspect.signature(SL.mesh_point_load).parameters)-{'F_t','F_r','F_a','r_w'})|set(inspect.signature(SL.mesh_forces).parameters)|{'d_w'}
            elif kind in constructors:
                names=set(inspect.signature(constructors[kind]).parameters)
            else:
                raise ValueError(path+': unknown/missing load kind')
            _required(load, names|{'kind'}, path+'.loads.'+kind)
        for section in sh['sections']:
            _required(section, ('x','stress_state','checks'), path+'.sections')
            choice=section['checks'].get('value')
            if not choice or any(c not in ('static','fatigue') for c in choice):
                raise ValueError(path+': unknown/missing section checks')
            if 'static' in choice:
                _required(section.get('static') or {}, ('load_factor','S_min','sigma_zdFK','sigma_bFK','tau_tFK'),path+'.static')
            if 'fatigue' in choice:
                _required(section.get('fatigue') or {}, SL._DIN743_KEYS,path+'.fatigue')
    for bid, bearing in si['bearings'].items():
        names=set(inspect.signature(BRG.bearing_life).parameters)-{'F_r','F_a'}
        _required(bearing, names|{'required_life_h'},'bearings.'+bid)
        if 'loads' in bearing:
            raise ValueError('Finite coupling requires shaft-derived bearing loads')
        if bearing['bearing_kind'].get('value') not in BRG.KINDS:
            raise ValueError('Unknown bearing kind')
        if bearing['bearing_kind'].get('value')=='radial_roller':
            _required(bearing['xy'].get('value') or {}, ('rows','alpha_deg'),'bearings.'+bid+'.xy')
        modified=bearing['a_ISO_inputs'].get('value')
        if isinstance(modified,dict):
            _required(modified,('kappa','ec','C_u'),'bearings.'+bid+'.a_ISO_inputs')
        refs={v for sh in si['shafts'] for v in sh['bearings'].values()}
        if bid not in refs:
            raise ValueError('Unreferenced bearing '+bid)
    refs={v for sh in si['shafts'] for v in sh['bearings'].values()}
    if refs!=set(si['bearings']):
        raise ValueError('Shaft/bearing reference mismatch')
    for key in si['keys']:
        _required(key,set(inspect.signature(KEY.method_c).parameters)|{'method'},'keys')
        if key['method'].get('value')!='C':
            raise ValueError('Unknown finite key method')


def optimize(design_doc, system_input, problem):
    """Return exact feasible ranking by (volume, lexicographic candidate IDs).

    Required keys: objective, max_combinations, hold_evidence (name: reason),
    gear [{id,source,inputs}], shaft [{id,source,shafts,keys}],
    bearing [{id,source,bearings}]. Geometry edits are restricted to existing
    cylindrical inputs m_n,b,z_1,z_2,x_1,x_2,beta. All component records replace
    the corresponding lists; no patching defaults. Search never edits callers.
    """
    out = {'status': 'blocked', 'best': None, 'feasible': [], 'errors': [],
           'rejections': [], 'problem_sha256': None,
           'stats': {'cartesian_combinations': 0, 'visited_combinations': 0,
                     'pruned_combinations': 0, 'design_check_calls': 0,
                     'gear_evaluations': 0, 'shaft_key_evaluations': 0,
                     'bearing_evaluations': 0, 'objective_evaluations': 0, 'cache_hits': 0},
           'limitations': ['Authored finite cylindrical capability probe only; not real C001 A6 completion.',
                           'Held evidence is unchanged across geometry; no external evidence promotion.',
                           'Objective is gear blank + shaft volume; bearing envelope/cost excluded.',
                           'No worm/planetary full-system rating; M40 remains frozen.']}
    stats=out['stats']
    try:
        doc, si, p = copy.deepcopy((design_doc, system_input, problem))
        out['problem_sha256']=_hash([doc,si,p])
        required={'objective','max_combinations','hold_evidence','gear','shaft','bearing'}
        if set(p)!=required or p['objective']!='gear_blank_plus_shaft_volume_mm3':
            raise ValueError('Unknown/missing problem fields or objective')
        if MS.validate(doc) or SIN.validate(si):
            raise ValueError('Invalid source document or system input')
        certificates=_certificates(doc)
        out['certificate_files']=certificates
        out['problem_sha256']=_hash([doc,si,p,certificates])
        if si['design_ref']['source_id']!=doc['id'] or si['design_ref']['model_family']!='pair_model':
            raise ValueError('This finite probe requires matching cylindrical pair_model source')
        if not FR.uses_recompute(doc):
            raise ValueError('Source-owned factor recomputation selectors required')
        hold=p['hold_evidence']
        if not isinstance(hold,dict) or set(hold)!=set(doc['evidence']) or any(not isinstance(v,str) or not v.strip() for v in hold.values()):
            raise ValueError('All held evidence requires explicit nonempty rationale')
        axes=[]
        for axis, fields in [('gear',{'inputs'}),('shaft',{'shafts','keys'}),('bearing',{'bearings'})]:
            rows=p[axis]
            if not isinstance(rows,list) or not rows:
                raise ValueError('Empty/missing finite axis '+axis)
            ids=[]
            for row in rows:
                if set(row)!=fields|{'id','source'} or not isinstance(row['id'],str) or not row['id'].strip() or not isinstance(row['source'],str) or not row['source'].strip():
                    raise ValueError('Invalid finite record '+axis)
                ids.append(row['id'])
                _nonnull(row)
                if axis=='gear':
                    if not row['inputs'] or not set(row['inputs']) <= {'m_n','b','z_1','z_2','x_1','x_2','beta'} or not set(row['inputs'])<=set(doc['inputs']):
                        raise ValueError('Unknown or non-variable gear input')
                else:
                    for f in fields:
                        if not isinstance(row[f],dict if f=='bearings' else list) or not row[f]:
                            raise ValueError('Explicit nonempty component list required')
            if len(set(ids))!=len(ids):
                raise ValueError('Duplicate IDs in '+axis)
            axes.append(rows)
        n=len(axes[0])*len(axes[1])*len(axes[2])
        stats['cartesian_combinations']=n
        limit=p['max_combinations']
        if type(limit) is not int or not 1<=limit<=HARD_MAX or n>limit:
            raise ValueError('Cartesian domain exceeds explicit/hard search limit')
        # Preflight every independent record before pruning, including branches
        # whose physical checks may fail. Missing leaves never hide behind pruning.
        for g in p['gear']:
            d=copy.deepcopy(doc); d['inputs'].update(g['inputs'])
            if MS.validate(d): raise ValueError('Invalid candidate gear document')
            if _certificates(d)!=certificates:
                raise ValueError('Candidate certificate identity changed')
            model=SO.build_family_model(d,'pair_model')
            available=set(DC.DESIGN_QUANTITIES)&(set(model.formulas)|set(model.inputs))
            for axis in ('shaft','bearing'):
                _design_refs(p[axis],available)
        for axis, fields in [('shaft',('shafts','keys')),('bearing',('bearings',))]:
            for row in p[axis]:
                s=copy.deepcopy(si)
                s.update(shafts=p['shaft'][0]['shafts'],keys=p['shaft'][0]['keys'],bearings=p['bearing'][0]['bearings'])
                for f in fields: s[f]=row[f]
                if SIN.validate(s): raise ValueError('Invalid '+axis+' record')
                _component_requirements(s)
        cache={}
        def checked(d,s,scopes):
            key=_hash([d,s,list(scopes)])
            if key in cache:
                stats['cache_hits']+=1
                return cache[key]
            result=DC.check(d,s,list(scopes))
            stats['design_check_calls']+=1
            stats[{'gear_rating':'gear_evaluations','shaft':'shaft_key_evaluations','bearing':'bearing_evaluations'}[scopes[0]]]+=1
            checks={k:result['checks'][k] for k in scopes}
            if any(c['status'] not in ('pass','fail') or c['errors'] or c['missing'] or c['unconfirmed'] for c in checks.values()):
                raise ValueError('Candidate check blocked: '+json.dumps(checks,ensure_ascii=False))
            cache[key]=checks
            return checks
        for g in p['gear']:
            d=copy.deepcopy(doc); d['inputs'].update(g['inputs'])
            gc=checked(d,si,('gear_rating',))
            if gc['gear_rating']['status']=='fail':
                count=len(p['shaft'])*len(p['bearing']); stats['pruned_combinations']+=count
                out['rejections'].append({'ids':[g['id']], 'scope':'gear_rating','combinations':count,'checks':gc})
                continue
            for sh in p['shaft']:
                s=copy.deepcopy(si); s.update(shafts=sh['shafts'],keys=sh['keys'])
                sc=checked(d,s,('shaft','key'))
                if any(c['status']=='fail' for c in sc.values()):
                    count=len(p['bearing']); stats['pruned_combinations']+=count
                    out['rejections'].append({'ids':[g['id'],sh['id']], 'scope':'shaft/key','combinations':count,'checks':sc})
                    continue
                for b in p['bearing']:
                    candidate=copy.deepcopy(s); candidate['bearings']=b['bearings']
                    stats['visited_combinations']+=1
                    bc=checked(d,candidate,('bearing',))
                    ids=[g['id'],sh['id'],b['id']]
                    if bc['bearing']['status']=='fail':
                        out['rejections'].append({'ids':ids,'scope':'bearing','combinations':1,'checks':bc})
                        continue
                    m=SO.build_family_model(d,'pair_model')
                    volume=U.from_canonical(m.evaluate(['V_blank']).values['V_blank'],'mm^3')
                    objective=total_volume_mm3(gear_blank_mm3=volume,shafts=sh['shafts'])
                    stats['objective_evaluations']+=1
                    out['feasible'].append({'ids':ids,'objective':objective,'objective_unit':'mm^3',
                                            'candidate_sha256':_hash([d,candidate,g,sh,b,certificates]),
                                            'design_sha256':_hash(d),'system_input_sha256':_hash(candidate),
                                            'checks':dict(gc,**sc,**bc)})
        if _certificates(doc)!=certificates:
            raise ValueError('Certificate identity changed during search')
        out['feasible'].sort(key=lambda r:(r['objective'],r['ids']))
        out['best']=out['feasible'][0] if out['feasible'] else None
        out['status']='completed'
        out['hold_evidence']=hold
    except Exception as exc:
        out['errors'].append({'code':type(exc).__name__,'message':str(exc)})
        out['best']=None
        out['feasible']=[]
    return out
