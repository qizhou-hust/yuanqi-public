"""Fail-closed, read-only pre-solve check for the known M37 L3 penalty profile.

Exit 0 means the enumerated input checks pass. It is never model acceptance.
Unknown deck features or a failed check exit 2. Does not launch a solver.
"""
from pathlib import Path
import argparse, sys, json, math
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'m37-preflight'))
import semantic_preflight as sp
from extended_preflight import jacobian_check

ALLOWED={'HEADING','NODE','ELEMENT','ELSET','MATERIAL','ELASTIC','SOLID SECTION','SURFACE',
         'SURFACE INTERACTION','SURFACE BEHAVIOR','CONTACT PAIR','EQUATION','NSET',
         'BOUNDARY','STEP','STATIC','END STEP','CLOAD','NODE PRINT','CONTACT PRINT'}
ATTRS={'ELEMENT':{'TYPE','ELSET'},'ELSET':{'ELSET'},'MATERIAL':{'NAME'},
       'SOLID SECTION':{'ELSET','MATERIAL'},'SURFACE':{'NAME','TYPE'},
       'SURFACE INTERACTION':{'NAME'},'SURFACE BEHAVIOR':{'PRESSURE-OVERCLOSURE'},
       'CONTACT PAIR':{'INTERACTION','TYPE'},'NSET':{'NSET','GENERATE'},
       'BOUNDARY':{'OP'},'STEP':{'INC'},'NODE PRINT':{'NSET'},'CONTACT PRINT':{'SLAVE','MASTER'}}

def check(path):
    path=Path(path).resolve(); deck=sp.read_deck(path)
    meta=json.loads(path.with_suffix('.meta.json').read_text(encoding='utf8'))
    errors=[];blocks=deck['blocks']
    unknown=sorted({b['key'] for b in blocks}-ALLOWED)
    if unknown:errors.append('Unsupported keyword(s): '+str(unknown))
    for b in blocks:
        extra=set(b['attrs'])-ATTRS.get(b['key'],set())
        if extra:errors.append('Unsupported '+b['key']+' attribute(s): '+str(sorted(extra)))
        if b['key']=='BOUNDARY' and b['attrs'].get('OP','NEW')!='NEW':errors.append('Unsupported BOUNDARY OP')
        if b['key']=='SURFACE' and b['attrs'].get('TYPE','ELEMENT')!='ELEMENT':errors.append('Expected element-based surface')
    def of(key):return [b for b in blocks if b['key']==key]
    if {b['attrs'].get('ELSET'):b['data'] for b in of('ELSET')}!={'PINION':['PINION_T6'],'WHEEL':['WHEEL_T6']}:errors.append('Unsupported section ELSET expansion')
    if {b['attrs'].get('ELSET') for b in of('ELEMENT')}!={'PINION_T6','WHEEL_T6'}:errors.append('Unexpected element body grouping')
    if meta.get('case')!='L3' or meta.get('variant')!='penalty':errors.append('Not M37 L3 penalty profile')
    if len(of('STEP'))!=2 or any('NLGEOM' in b['attrs'] for b in of('STEP')):errors.append('Expected two small-displacement steps')
    if len(of('STATIC'))!=2:errors.append('Expected two STATIC procedures')
    if len(of('ELASTIC'))!=1:errors.append('Expected one linear isotropic material')
    if len(of('MATERIAL'))!=1 or of('MATERIAL')[0]['attrs']!={'NAME':'STEEL'}:errors.append('Material identity mismatch')
    if {(s['set'],s['material'],s['thickness_mm']) for s in deck['sections']}!={('PINION','STEEL',1.),('WHEEL','STEEL',1.)}:errors.append('Wrong section/material assignment')
    cp=of('CONTACT PAIR')
    if len(cp)!=1 or cp[0]['attrs']!={'INTERACTION':'CI1','TYPE':'SURFACE TO SURFACE'} or cp[0]['data']!=['PFL,WFL']:errors.append('Contact pair identity/formulation mismatch')
    si=of('SURFACE INTERACTION')
    if len(si)!=1 or si[0]['attrs']!={'NAME':'CI1'}:errors.append('Contact interaction identity mismatch')
    sb=of('SURFACE BEHAVIOR')
    if len(sb)!=1 or sb[0]['attrs']!={'PRESSURE-OVERCLOSURE':'LINEAR'}:errors.append('Unsupported contact behavior')
    else:
        k=float(sb[0]['data'][0]);expected=meta['alpha']*deck['elastic'][0][0]/meta['h']
        # Deck writer prints six significant digits; this is serialization allowance only.
        if not math.isclose(k,expected,rel_tol=5e-6):errors.append('Penalty differs from alpha * E / h')
    if len(deck['loads'])!=1 or deck['loads'][0]['step']!=2:errors.append('Expected one final-step generalized torque load')
    if len(of('CLOAD'))!=1 or of('CLOAD')[0]['attrs']:errors.append('Unsupported CLOAD attributes')
    for b in deck['bounds']:
        if b['step']==2 and not b['op_new']:errors.append('Final boundary reset missing')
    basic=sp.audit(path,'checked',-1,export=False)
    actual=basic['load']['input_moment_about_pinion_center_Nmm'];target=basic['load']['target_torque_per_1mm_Nmm']
    if not math.isclose(actual,-target,rel_tol=1e-8):errors.append('Signed input torque mismatch: profile requires clockwise drive')
    load=deck['loads'][0] if len(deck['loads'])==1 else None
    if load and (load['node'] not in deck['sets']['PMASTER'] or load['dof']!=2):errors.append('Generalized load must act on PMASTER DOF 2')
    mesh=jacobian_check(deck)
    return {'schema':'m37.pre-solve-check/v1','input_sha256':sp.SHA(path),'input':str(path),
        'profile':'M37_L3_CPE6_small_displacement_frictionless_penalty_two_step',
        'supported_profile_errors':errors,'input_checks':basic,'mesh':mesh,
        'ready_for_diagnostic_solve':not errors and basic['pass'] and mesh['pass'],
        'accepted':False,'not_checked':['Certified whole-boundary penetration','Contact-patch pressure convergence',
            'All elastic stiffness matrix eigenmodes','Nonlinear geometry applicability','Model-to-reference definition agreement'],
        'execution_contract':'Recheck immediately before launch. The solver input must retain this SHA256. Existing solver wrappers are not silently modified.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args()
    try:result=check(args.input)
    except Exception as e:result={'schema':'m37.pre-solve-check/v1','ready_for_diagnostic_solve':False,'accepted':False,'parse_or_profile_error':f'{type(e).__name__}: {e}'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:result.get(k) for k in ['ready_for_diagnostic_solve','supported_profile_errors','parse_or_profile_error']},ensure_ascii=False))
    return 0 if result['ready_for_diagnostic_solve'] else 2

if __name__=='__main__':sys.exit(main())
