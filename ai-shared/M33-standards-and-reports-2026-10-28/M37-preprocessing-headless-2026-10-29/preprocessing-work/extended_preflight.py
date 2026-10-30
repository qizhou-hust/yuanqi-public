"""Read-only high-order mesh, sampled interference and ph10 equilibrium audit.

No solver inputs, contact parameters or acceptance thresholds are changed.
"""
from pathlib import Path
import sys, json, hashlib, math
import numpy as np
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

ROOT=Path(__file__).resolve().parent; BASE=ROOT.parent
sys.path.insert(0,str(ROOT/'m37-preflight'))
sys.path.insert(0,str(BASE/'m37/M37-FEA题目包/scripts'))
import semantic_preflight as sp
import ccx_io, cases

def jacobian_check(deck):
    """Exact candidate locations for the quadratic determinant, floating arithmetic.
    A TRI6 coordinate map has affine derivatives and quadratic determinant.
    The minimum over the reference triangle occurs at a vertex, an edge stationary
    point, or an interior stationary point. No finite sampling is used for this gate.
    """
    ids=list(deck['elements']); xy=np.array([[deck['nodes'][n] for n in deck['elements'][e]] for e in ids])
    def det(r,s):
        l=1-r-s
        dr=np.array([1-4*l,4*r-1,0,4*(l-r),4*s,-4*s])
        ds=np.array([1-4*l,0,4*s-1,-4*r,4*r,4*(l-s)])
        u=np.einsum('n,eni->ei',dr,xy);v=np.einsum('n,eni->ei',ds,xy)
        return u[:,0]*v[:,1]-u[:,1]*v[:,0]
    f=det(0,0); x=det(1,0);y=det(0,1)
    a=2*(x-2*det(.5,0)+f);d=x-f-a
    c=2*(y-2*det(0,.5)+f);e=y-f-c
    b=4*(det(.5,.5)-f-.25*a-.25*c-.5*d-.5*e)
    def val(r,s):return a*r*r+b*r*s+c*s*s+d*r+e*s+f
    candidates=[f,x,y]
    for A,B,C,loc in [(a,d,f,0),(c,e,f,1),(a-b+c,b-2*c+d-e,c+e+f,2)]:
        t=np.divide(-B,2*A,out=np.full(len(ids),np.nan),where=np.abs(A)>1e-30)
        q=A*t*t+B*t+C;candidates.append(np.where((t>0)&(t<1),q,np.inf))
    den=4*a*c-b*b
    r=np.divide(b*e-2*c*d,den,out=np.full(len(ids),np.nan),where=np.abs(den)>1e-30)
    s=np.divide(b*d-2*a*e,den,out=np.full(len(ids),np.nan),where=np.abs(den)>1e-30)
    candidates.append(np.where((r>0)&(s>0)&(r+s<1),val(r,s),np.inf))
    mins=np.min(candidates,axis=0)
    edges={};bad_nonconforming=0
    for eid,ns in deck['elements'].items():
        for i,j,k in sp.TRI:edges.setdefault(tuple(sorted([ns[i],ns[j]])),[]).append(ns[k])
    for mids in edges.values():
        if len(set(mids))>1:bad_nonconforming+=1
    manifold=sum(len(v)>2 for v in edges.values())
    return {'elements':len(ids),'minimum_jacobian_mm2':float(min(mins)),
            'minimum_element':ids[int(np.argmin(mins))], 'nonpositive_elements':int(sum(mins<=0)),
            'nonmanifold_edges':manifold,'mismatched_shared_midside_nodes':bad_nonconforming,
            'method':'All stationary candidates of the quadratic TRI6 Jacobian on the reference triangle; floating arithmetic, not interval certification',
            'pass':bool(np.isfinite(mins).all() and min(mins)>0 and not manifold and not bad_nonconforming)}

def overlap_screen(deck,nsub):
    exterior=sp.boundary_edges(deck); polys={}; deviation=0.
    for body in ['PINION','WHEEL']:
        lines=[]
        for eid,side in exterior:
            if deck['body'][eid]!=body:continue
            points=np.array([deck['nodes'][n] for n in sp.edge_nodes(deck,eid,side)])
            ts=np.linspace(-1,1,nsub+1);pts=np.array([sp.curve(points,t) for t in ts])
            pts[0]=points[0];pts[-1]=points[1]  # preserve exact shared-node identity
            # The quadratic arc-to-chord error is maximal at each subsegment midpoint.
            err=max(np.linalg.norm(sp.curve(points,(ts[i]+ts[i+1])/2)-(pts[i]+pts[i+1])/2) for i in range(nsub))
            deviation=max(deviation,float(err)); lines.append(LineString(pts))
        regions=list(polygonize(unary_union(lines)))
        # Largest polygon is the gear material ring; bore polygon must not be filled.
        polys[body]=max(regions,key=lambda p:p.area)
    inter=polys['PINION'].intersection(polys['WHEEL'])
    return {'subsegments_per_quadratic_edge':nsub,'max_arc_chord_deviation_mm':deviation,
            'intersection_area_mm2':inter.area,'polygon_valid':all(p.is_valid for p in polys.values()),
            'screen_clear':inter.area<1e-8,'scope':'Sampled whole-body polygon interference screen, not certified curved-boundary nonpenetration'}

def phase_audit(phase):
    stem=f'L3_C001_G1_ph{phase:02d}_d12'
    folder=BASE/'m37-l3-periodic-diagnostic/runs/L3'
    if phase in [10,11]:folder=ROOT/f'm37-ph10-ph11-evidence/ph{phase:02d}'
    inp=folder/(stem+'.inp');deck=sp.read_deck(inp)
    meta=json.loads(inp.with_suffix('.meta.json').read_text(encoding='utf8'))
    blocks=ccx_io.parse_dat(inp.with_suffix('.dat')); ct=ccx_io.contact_tables(blocks)
    RF=ccx_io.nodal(blocks,'forces','WBORE');F=np.sum(list(RF.values()),axis=0)[:2]
    cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    O=np.array(meta['O2']); M=sum(cross(np.array(meta['wbore_xy'][str(n)])-O,f[:2]) for n,f in RF.items())
    cf=np.array(ct['force_moment'][:2]);cm=ct['force_moment'][5]
    shifted=cm-cross(O,cf)
    values,_=cases.post_L3(meta,blocks)
    eq={'wheel_RF_N':F.tolist(),'contact_surface_force_N':cf.tolist(),
        'wheel_RF_moment_Nmm':M,'contact_moment_global_Nmm':cm,'contact_moment_wheel_center_Nmm':shifted,
        'input_torque_Nmm':meta['T_per_b'],
        'wheel_contact_force_residual_rel':float(np.linalg.norm(F-cf)/meta['Fn_per_b']),
        'wheel_contact_moment_residual_rel':abs(M-shifted)/abs(M),
        'pinion_contact_vs_input_torque_residual_rel':abs(cm-meta['T_per_b'])/meta['T_per_b'],
        'sign_convention':'CF reported on pinion; wheel support RF has same sign. Contact moment transferred from global origin to wheel center before comparison.',
        'scope':'Checks printed contact statistics against wheel-bore RF and input torque; not full-system nodal reaction/energy audit'}
    surf=dict(deck['surfaces']['PFL']);peaks={}
    for row in ct['stress_rows']:
        eid=int(row[0]);p=abs(row[2])
        if p>peaks.get(eid,0):peaks[eid]=p
    active=[]
    for eid,p in sorted(peaks.items(),key=lambda x:-x[1]):
        if p<=1e-5:continue
        side=surf[eid];pts=np.array([deck['nodes'][n] for n in sp.edge_nodes(deck,eid,side)])
        chord=float(np.linalg.norm(pts[1]-pts[0]))
        active.append({'element':eid,'side':side,'pmax_MPa':p,'edge_points_mm':pts.tolist(),'edge_length_chord_mm':chord,
                       'edge_chord_over_contact_target_h':chord/meta['h'],
                       'nearest_theoretical_contact_point_mm':min(float(np.linalg.norm(pts[2]-pr['point'])) for pr in meta['pairs'])})
    row={'phase':phase,'input_sha256':sp.SHA(inp),'dat_sha256':sp.SHA(inp.with_suffix('.dat')),'actual_balance':eq,
        'ideal_reference_comparison_unchanged':values,'active_pressure_elements':active,'mesh':jacobian_check(deck)}
    if phase==10:
        eid=active[0]['element'];side=surf[eid];pts=np.array([deck['nodes'][n] for n in sp.edge_nodes(deck,eid,side)])
        gap=[]
        for t in np.linspace(-1,1,41):
            p=sp.curve(pts,t);q=sp.nearest(deck,'WFL',p);v=p-np.array(q['point_mm'])
            gap.append({'t':float(t),'pinion_point_mm':p.tolist(),'nearest_wheel':q,
                        'signed_distance_along_wheel_outward_mm':float(v@q['outward_normal'])})
        row['tip_initial_gap_samples']=gap
        row['tip_gap_summary']={'minimum_signed_mm':min(g['signed_distance_along_wheel_outward_mm'] for g in gap),
            'minimum_unsigned_mm':min(g['nearest_wheel']['distance_mm'] for g in gap),
            'maximum_unsigned_mm':max(g['nearest_wheel']['distance_mm'] for g in gap),
            'interpretation':'Positive means locally outside the wheel along its nearest outward normal; sampled initial geometry, not deformed/contact-gap proof'}
        row['global_interference_screens']=[overlap_screen(deck,n) for n in [4,8,32]]
    row['actual_pressure_support_review']={'target_contact_h_mm':meta['h'],
        'maximum_active_edge_chord_over_target_h':max(e['edge_chord_over_contact_target_h'] for e in active),
        'original_h_check':meta['h_check'],
        'interpretation':'Original h_check covers only a disk around theoretical contact points. Audit actual loaded elements too; no pressure is deleted from the result.',
        'requires_additional_local_mesh_convergence':max(e['edge_chord_over_contact_target_h'] for e in active)>2,
        'trigger_ratio':2,'trigger_is':'Diagnostic refinement trigger, not a replacement for original acceptance threshold'}
    return row

def main():
    rows=[phase_audit(p) for p in [9,10,11]]
    for r in rows:print(r['phase'],r['mesh'],r['actual_balance'],r.get('tip_gap_summary'),flush=True)
    out={'schema':'m37.extended-preflight/v1','accepted':False,'physical_input_changed':False,
        'scope':'Additional read-only diagnostic; formal original acceptance gates unchanged','phases':rows,
        'limitations':['Full curved-boundary interference is not mathematically certified.',
            'Stiffness reference identity, neighboring tooth-tip pressure convergence, and contact discretization remain open.',
            'Positive Jacobian does not certify good aspect ratio, contact mesh resolution, or pressure convergence.']}
    (ROOT/'extended-preflight.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
