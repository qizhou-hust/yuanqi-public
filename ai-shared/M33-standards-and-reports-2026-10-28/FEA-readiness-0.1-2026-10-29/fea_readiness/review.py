"""Diagnostic rules. PASS is local to a named check, never engineering acceptance."""
import math
from .contracts import finite, resultant, rule, sha256, vector

IDENTITY_FIELDS=('quantity','unit','support_region','extraction','load_state')

def nonempty(value):
    return isinstance(value,str) and bool(value.strip())

def balance_check(loads, origin_mm, force_scale_N, moment_scale_Nmm, force_tol, moment_tol):
    fs=finite(force_scale_N,'force_scale_N',True);ms=finite(moment_scale_Nmm,'moment_scale_Nmm',True)
    ft=finite(force_tol,'force_tol',True);mt=finite(moment_tol,'moment_tol',True)
    if not loads:return rule('balance','UNKNOWN','Missing free-body loads/reactions')
    r=resultant(loads,origin_mm)
    fr=math.sqrt(sum(x*x for x in r['force_N']))/fs
    mr=math.sqrt(sum(x*x for x in r['moment_Nmm']))/ms
    return rule('balance','PASS' if fr<=ft and mr<=mt else 'FAIL',
                'Same free-body force and moment residuals; check omitted reactions and moment origins on failure',
                {**r,'force_residual_rel':fr,'moment_residual_rel':mr},
                {'force_rel':ft,'moment_rel':mt})

def convergence_check(rows, tolerance):
    tol=finite(tolerance,'convergence_tolerance',True)
    if len(rows)<3:return rule('mesh_convergence','UNKNOWN','At least three identified mesh levels required')
    identity={tuple(r.get(k) for k in ('physics_id',)+IDENTITY_FIELDS) for r in rows}
    if len(identity)!=1 or not all(nonempty(x) for x in next(iter(identity))):
        return rule('mesh_convergence','UNKNOWN','Physical case, quantity, units, support, extraction and load state must agree')
    hs=[finite(r['h_mm'],'h_mm',True) for r in rows]
    vs=[finite(r['value'],'value') for r in rows]
    if not all(a>b for a,b in zip(hs,hs[1:])):
        return rule('mesh_convergence','UNKNOWN','Provide coarse-to-fine local mesh scales, not node counts')
    ratios=[a/b for a,b in zip(hs,hs[1:])]
    ds=[b-a for a,b in zip(vs,vs[1:])]
    if not all(d*ds[0]>0 for d in ds):
        return rule('mesh_convergence','UNKNOWN','Oscillation or identical printed values cannot establish an asymptotic order')
    if not all(math.isclose(r,ratios[0],rel_tol=1e-5) for r in ratios):
        return rule('mesh_convergence','UNKNOWN','v0.1 order estimator requires uniform refinement ratio')
    p=math.log(abs(ds[-2]/ds[-1]))/math.log(ratios[0])
    change=abs(ds[-1])/max(abs(vs[-1]),1e-30)
    est=abs(ds[-1])/(ratios[0]**p-1) if p>0 else None
    passed=p>0 and est/max(abs(vs[-1]),1e-30)<=tol
    return rule('mesh_convergence','PASS' if passed else 'FAIL',
        'Positive order and Richardson estimated relative error; no absolute-value repair of divergent order',
        {'observed_order':p,'last_change_rel':change,'estimated_error':est},tol,next(iter(identity))[2])

def theory_check(actual, predicted, applicable, tolerance, definition, comparison_identity=None):
    identity=comparison_identity or {}
    a_id=identity.get('actual',{});p_id=identity.get('predicted',{})
    same=all(nonempty(a_id.get(k)) and a_id[k]==p_id.get(k) for k in IDENTITY_FIELDS)
    if applicable is not True or not nonempty(definition) or not same:
        return rule('theory_comparison','UNKNOWN','Establish shared quantity definition, topology and analytical applicability first')
    a=finite(actual,'actual');p=finite(predicted,'predicted',True);tol=finite(tolerance,'theory_tolerance',True)
    rel=abs(a-p)/abs(p)
    return rule('theory_comparison','PASS' if rel<=tol else 'FAIL',
        'Same-definition comparison: '+definition+'; investigate units, topology, loading and convergence before changing parameters',rel,tol)

def contact_check(active_elements, trigger_ratio, source_hashes=None):
    t=finite(trigger_ratio,'trigger_ratio',True)
    if not active_elements:return rule('actual_contact_mesh','UNKNOWN','No actual pressure support evidence')
    if any(e.get('element') is None or e.get('side') is None or not nonempty(e.get('source_sha256'))
           or (source_hashes is not None and e.get('source_sha256') not in source_hashes) for e in active_elements):
        return rule('actual_contact_mesh','UNKNOWN','Actual contact evidence needs element/side identity and a bound raw source hash')
    values=[finite(e['edge_chord_over_contact_target_h'],'edge_chord_over_contact_target_h',True) for e in active_elements]
    peak=max(values)
    return rule('actual_contact_mesh','FAIL' if peak>t else 'PASS',
        'Diagnostic local convergence trigger on actual loaded edges; extra contact may be elastic extended contact, not necessarily penetration',peak,t,
        evidence=[{'element':e.get('element'),'ratio':v} for e,v in zip(active_elements,values) if v>t])

def review(result):
    """Read a standardized result contract; adapters supply raw evidence and sign conventions.

    Scalar residuals remain auditable assertions from the adapter. Source hashes and
    run identity do not prove extraction correctness; raw-parser validation is separate.
    """
    checks=[];sources=result.get('sources',[])
    try:
        valid=bool(sources) and all(sha256(s['path'])==s['sha256'] for s in sources)
    except (OSError,KeyError):valid=False
    checks.append(rule('result_sources','PASS' if valid else 'UNKNOWN','Raw source SHA256 binding'))
    run=result.get('run',{})
    complete=(type(run.get('returncode')) is int and run.get('returncode')==0 and run.get('final_step_complete') is True
              and run.get('input_sha256')==result.get('input_sha256') and bool(result.get('input_sha256'))
              and run.get('error_free') is True and run.get('timed_out') is False
              and run.get('finished_marker') is True and run.get('dat_present') is True)
    checks.append(rule('run_completion','PASS' if complete else 'UNKNOWN','Exit, final step, errors and input identity'))
    balance=result.get('balance')
    if balance:
        checks.append(balance_check(**balance))
    elif result.get('balance_residuals'):
        residuals=result['balance_residuals'];coverage={};valid=True
        hashes={s.get('sha256') for s in sources}
        for item in residuals:
            valid=valid and all(nonempty(item.get(k)) for k in ['name','definition','free_body','extraction_id'])
            valid=valid and item.get('kind') in {'force','moment'} and item.get('source_sha256') in hashes
            try:
                origin=tuple(vector(item.get('moment_origin_mm'),'moment_origin_mm'))
                finite(item.get('scale'),'residual_scale',True)
            except (ValueError,TypeError):valid=False;origin=None
            coverage.setdefault((item.get('free_body'),origin),set()).add(item.get('kind'))
        # At least one actual free body must have both force and moment checks.
        valid=valid and any(kinds=={'force','moment'} for kinds in coverage.values())
        if not valid:checks.append(rule('balance','UNKNOWN','Residuals require force+moment coverage, body/origin/scale, nonempty extraction definitions and raw-source binding'))
        else:
            for item in residuals:
                value=finite(item['value'],item['name']);limit=finite(item['limit'],'limit',True)
                if value<0:raise ValueError('Residual cannot be negative')
                checks.append(rule('balance.'+item['name'],'PASS' if value<=limit else 'FAIL',item['definition'],value,limit))
    else:checks.append(rule('balance','UNKNOWN','Missing actual free-body equilibrium evidence'))
    checks.append(contact_check(result.get('active_contact_elements',[]),result.get('contact_mesh_trigger_ratio',2),
                                {s.get('sha256') for s in sources}))
    mesh=result.get('mesh_study')
    checks.append(convergence_check(**mesh) if mesh else rule('mesh_convergence','UNKNOWN','No identified three-level mesh study'))
    theory=result.get('theory_comparison')
    checks.append(theory_check(**theory) if theory else rule('theory_comparison','UNKNOWN','No comparable analytical reference'))
    failed=[r['check_id'] for r in checks if r['status']=='FAIL']
    unknown=[r['check_id'] for r in checks if r['status']=='UNKNOWN']
    next_checks=[]
    if any(x.startswith('balance') for x in failed):next_checks.append('Reconstruct one free body from raw nodal reactions and contact resultants at one moment origin')
    if 'actual_contact_mesh' in failed:next_checks.append('Refine the actual loaded edge and its counterpart at fixed physical inputs; retain all pressure and compare patch force/width/peak across meshes')
    if 'theory_comparison' in failed or 'theory_comparison' in unknown:next_checks.append('Establish load sharing, extended contact, root/rim compliance, secant versus tangent stiffness and the reference definition before comparison')
    return {'schema':'fea-readiness.review/0.1','checks':checks,'failed':failed,'unknown':unknown,
            'engineering_accepted':False,'next_discriminating_checks':next_checks,
            'decision':'diagnostic_action_required' if failed or unknown else 'enumerated_checks_passed_requires_engineering_acceptance'}
