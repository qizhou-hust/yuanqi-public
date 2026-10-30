"""Isolated interpreter bridge to the existing, hash-pinned M37 asset."""
import json
import math
import sys
from pathlib import Path

def main():
    root=Path(sys.argv[1]);inp=Path(sys.argv[2]);out=Path(sys.argv[3])
    sys.path.insert(0,str(root/'preprocessing-work'))
    import check_before_solve as old
    from extended_preflight import overlap_screen
    result=old.check(inp)
    deck=old.sp.read_deck(inp)
    # A complete geometric proof is deferred. This additional screen is explicit.
    result['sampled_initial_overlap']=overlap_screen(deck,8)
    result['static_procedures']=[b['data'] for b in deck['blocks'] if b['key']=='STATIC']
    meta=json.loads(inp.with_suffix('.meta.json').read_text(encoding='utf8'))
    source=json.loads((root/'m37/M37-FEA题目包/cases/L3_C001_G1.json').read_text(encoding='utf8'))
    reference=json.loads((root/'m37/M37-FEA题目包/expected/L3_C001_G1.json').read_text(encoding='utf8'))
    result['prescribed_state']=prescribed_state(deck,meta,source,reference,old.sp)
    out.write_text(json.dumps(result,allow_nan=False),encoding='utf8')

def prescribed_state(deck,meta,source,reference,sp):
    """Known-profile bore membership and exact step state, with serialized precision."""
    p=source['pair'];r1=p['m_mm']*p['z1']/2;r2=p['m_mm']*p['z2']/2
    o2=[0.,r1+r2];b1=r1*p['bore_diameter_ratio'];b2=r2*p['bore_diameter_ratio']
    exterior=sp.boundary_edges(deck);bores={'PINION':set(),'WHEEL':set()}
    for e,s in exterior:
        body=deck['body'][e];center=[0.,0.] if body=='PINION' else o2;radius=b1 if body=='PINION' else b2
        nodes=sp.edge_nodes(deck,e,s)
        if all(math.isclose(math.dist(deck['nodes'][n],center),radius,rel_tol=0,abs_tol=1e-8) for n in nodes):
            bores[body].update(nodes)
    masters=deck['sets'].get('PMASTER',[])
    good=bool(bores['PINION']) and bool(bores['WHEEL']) and len(masters)==1
    master=masters[0] if len(masters)==1 else None
    good=good and master in bores['PINION'] and math.dist(deck['nodes'][master],[b1,0.])<1e-8
    good=good and set(deck['sets'].get('WBORE',[]))==bores['WHEEL']
    expected={(n,d):0. for n in bores['WHEEL'] for d in [1,2]}
    if master is not None:expected[master,1]=0.
    for n in bores['PINION']:
        if n==master:continue
        x,y=deck['nodes'][n]
        for dof,coef in [(1,y/b1),(2,-x/b1)]:
            if abs(coef)<1e-12:expected[n,dof]=0.
    c=reference['values']['c_prime_th_CB']['value']
    rot=-.3*meta['Fn_per_b']/c*1e-3*b1/meta['rb1']
    wanted=[expected,{**expected,(master,2):rot},expected]
    steps=[]
    for step,values in enumerate(wanted):
        active=sp.active_bounds(deck,step)
        match=set(active)==set(values) and all(math.isclose(v,values[k],rel_tol=1e-10,abs_tol=1e-14) for k,v in active.items())
        good=good and match
        steps.append({'step':step,'keys_match':set(active)==set(values),'values_match':match,
                      'actual_count':len(active),'expected_count':len(values)})
    return {'pass':bool(good),'steps':steps,'bore_nodes':{k:len(v) for k,v in bores.items()},
            'expected_rotation_value':rot,'scope':'Known nominal bore circles and exact source-defined step supports; not arbitrary mesh BC inference'}

if __name__=='__main__':main()
