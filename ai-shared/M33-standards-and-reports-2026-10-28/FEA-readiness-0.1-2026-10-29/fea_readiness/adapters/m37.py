import math
import subprocess
import sys
import tempfile
from pathlib import Path
from ..contracts import load_json, rule, sha256
from ..theory import precalculate

def check(spec):
    cfg=spec['native'];root=Path(cfg['asset_root']).resolve();inp=Path(cfg['input']).resolve()
    lock=load_json(Path(__file__).with_name('m37-assets.json'))
    assets=[root/p for p in lock['files']]
    bad=[p for p,h in lock['files'].items() if not (root/p).is_file() or sha256(root/p)!=h]
    if bad:return {'checks':[rule('m37_assets','FAIL','Missing or changed pinned M37 sources',bad)],'files':[]}
    checks=[rule('m37_assets','PASS','Existing source files match the reviewed SHA256 lock')]
    meta=load_json(inp.with_suffix('.meta.json'));source=load_json(root/'m37/M37-FEA题目包/cases/L3_C001_G1.json')
    pair=source['pair'];mat=source['material'];inputs=spec['theory']['inputs']
    expected={'z1':pair['z1'],'z2':pair['z2'],'module_mm':pair['m_mm'],'alpha_deg':pair['alpha_deg'],
              'face_width_mm':pair['b_mm'],'torque_Nm':pair['T1_Nm'],'s_mm':meta['s_ref'],'addendum_coeff':pair['haP']}
    defaults={'s_mm':0.,'addendum_coeff':1.}
    matches=spec['theory']['kind']=='nominal_spur' and all(
        math.isclose(float(inputs.get(k,defaults.get(k,math.nan))),v,rel_tol=1e-12,abs_tol=1e-12) for k,v in expected.items())
    material=spec['theory'].get('material',{})
    matches=matches and material=={'E1_MPa':mat['E_MPa'],'nu1':mat['nu'],'E2_MPa':mat['E_MPa'],'nu2':mat['nu']}
    t=precalculate(spec['theory'])
    g=t.get('geometry',{})
    matches=matches and all(math.isclose(g.get(k,math.nan),meta[m],rel_tol=1e-10,abs_tol=1e-10) for k,m in
        [('rb1_mm','rb1'),('rb2_mm','rb2'),('torque_per_1mm_Nmm','T_per_b'),('full_load_q_N_per_mm','Fn_per_b')])
    matches=matches and bool(meta.get('pairs')) and len(meta['pairs'])==g.get('nominal_pairs_at_phase')
    checks.append(rule('theory_native_binding','PASS' if matches else 'FAIL','Source gear, phase, material and per-mm loading agree; nominal geometry excludes thickness allowance and generated fillet'))
    with tempfile.TemporaryDirectory(prefix='fea-readiness-check-') as tmp:
        out=Path(tmp)/'native.json'
        proc=subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__).with_name('m37_bridge.py')),str(root),str(inp),str(out)],
                            capture_output=True,text=True,encoding='utf8',timeout=180,shell=False)
        if proc.returncode!=0 or not out.is_file():
            raise ValueError('Native adapter failed: '+proc.stderr[-1800:])
        r=load_json(out)
    checks.append(rule('prescribed_state','PASS' if r['prescribed_state']['pass'] else 'FAIL',
        'Complete bore membership and every prescribed DOF/value match each source-defined step',r['prescribed_state']))

    # Bind every phase contact point, not only s_ref and pair count. The nominal
    # line-of-action frame is (cos(alpha)*s, r1+sin(alpha)*s) for this profile.
    expected_pairs=[]
    g_pairs=g.get('pair_offsets',[])
    for k in g_pairs:
        ss=meta['s_ref']+k*g['base_pitch_mm']
        expected_pairs.append((k,ss,[math.cos(math.radians(pair['alpha_deg']))*ss,
                                      g['r1_mm']+math.sin(math.radians(pair['alpha_deg']))*ss]))
    pair_ok=len(meta['pairs'])==len(expected_pairs)
    if pair_ok:
        for actual,expected in zip(meta['pairs'],expected_pairs):
            pair_ok=pair_ok and actual.get('k')==expected[0] and math.isclose(actual.get('s',math.nan),expected[1],rel_tol=1e-10,abs_tol=1e-10)
            pair_ok=pair_ok and len(actual.get('point',[]))==2 and all(math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10) for a,b in zip(actual.get('point',[]),expected[2]))
    checks.append(rule('phase_contact_binding','PASS' if pair_ok else 'FAIL',
        'Every native active pair k/s/point agrees with the analytical phase and line-of-action definition',
        {'expected':expected_pairs,'actual':meta.get('pairs',[])}))
    checks.append(rule('native_profile','PASS' if r['ready_for_diagnostic_solve'] else 'FAIL',
                       'Pinned CPE6/two-step/penalty profile, material, contact, torque, rigid intent and Jacobian checks',
                       evidence=[{'input_sha256':r['input_sha256']}]))
    overlap=r['sampled_initial_overlap']
    checks.append(rule('initial_overlap_screen','PASS' if overlap['screen_clear'] and overlap['polygon_valid'] else 'FAIL',
        'Eight-chord quadratic-edge interference screen; not certified full curved-boundary nonpenetration',overlap))
    # Runner completion assumes unit duration in each of exactly two steps.
    static=r['static_procedures']
    durations=[float(s[0].split(',')[1]) if s and len(s[0].split(','))>1 else 1. for s in static]
    checks.append(rule('step_duration','PASS' if durations==[1.,1.] else 'FAIL','Supported two unit-duration STATIC steps',durations))
    return {'checks':checks,'files':[str(inp),str(inp.with_suffix('.meta.json'))]+[str(p) for p in assets],
            'report':r,'scope':'M37 L3 known source profile only; UNKNOWN features block; sampled overlap is diagnostic'}
