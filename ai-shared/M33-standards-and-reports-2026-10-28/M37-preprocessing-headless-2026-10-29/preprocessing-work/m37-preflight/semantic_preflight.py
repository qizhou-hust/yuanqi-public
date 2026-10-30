"""Audit existing M37 input semantics; never alter decks or mechanical acceptance gates.

The geometry exports describe a 1 mm extrusion for review only, not a 3D solve.
"""
from pathlib import Path
from collections import Counter
import json,hashlib,math
import numpy as np

OUT=Path(__file__).resolve().parent;BASE=OUT.parent.parent
GEOM=OUT/'geometry';GEOM.mkdir(exist_ok=True)
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
TRI=((0,1,3),(1,2,4),(2,0,5))

def read_deck(path):
    blocks=[];current=None;step=0
    for raw in path.read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('**'):continue
        if line.startswith('*'):
            parts=[p.strip() for p in line.upper().split(',')]
            key=parts[0][1:];attrs={}
            for p in parts[1:]:
                a,_,v=p.partition('=');attrs[a]=v
            if key=='STEP':step+=1
            current={'key':key,'attrs':attrs,'data':[],'step':step};blocks.append(current)
        else:current['data'].append(line)
    nodes={};elements={};body={};sets={};surfaces={};equations=[];bounds=[];loads=[];sections=[];elastic=[];materials={};current_material=None
    for b in blocks:
        k,a,lines=b['key'],b['attrs'],b['data']
        rows=[[v.strip() for v in line.split(',') if v.strip()] for line in lines]
        if k=='NODE':
            for r in rows:nodes[int(r[0])]=list(map(float,r[1:3]))
        elif k=='ELEMENT':
            assert a['TYPE']=='CPE6',a
            for r in rows:
                e=int(r[0]);elements[e]=list(map(int,r[1:]));body[e]='PINION' if a['ELSET'].startswith('PINION') else 'WHEEL'
        elif k=='NSET':
            vals=[int(v) for r in rows for v in r]
            if 'GENERATE' in a:vals=list(range(vals[0],vals[1]+1,vals[2] if len(vals)>2 else 1))
            sets.setdefault(a['NSET'],[]).extend(vals)
        elif k=='SURFACE':surfaces[a['NAME']]=[(int(r[0]),int(r[1][1:])) for r in rows]
        elif k=='EQUATION':
            vals=[v for r in rows for v in r];n=int(vals[0]);assert len(vals)==1+3*n
            equations.append([(int(vals[i]),int(vals[i+1]),float(vals[i+2])) for i in range(1,len(vals),3)])
        elif k=='BOUNDARY':bounds.append({'step':b['step'],'op_new':a.get('OP')=='NEW','rows':rows})
        elif k=='CLOAD':
            for r in rows:loads.append({'step':b['step'],'node':int(r[0]),'dof':int(r[1]),'value':float(r[2])})
        elif k=='SOLID SECTION':sections.append({'set':a['ELSET'],'material':a['MATERIAL'],'thickness_mm':float(rows[0][0])})
        elif k=='MATERIAL':
            current_material=a['NAME'];assert current_material not in materials,'Duplicate material'
            materials[current_material]={}
        elif k=='ELASTIC':
            values=list(map(float,rows[0]));elastic.append(values)
            assert current_material is not None,'Elastic card has no material owner'
            materials[current_material]['elastic']=values
    return {'nodes':nodes,'elements':elements,'body':body,'sets':sets,'surfaces':surfaces,'equations':equations,'bounds':bounds,'loads':loads,'sections':sections,'elastic':elastic,'materials':materials,'blocks':blocks}

def edge_nodes(deck,e,side):return [deck['elements'][e][i] for i in TRI[side-1]]
def curve(xy,t):
    xy=np.asarray(xy);return ((xy[0]+xy[1])/2-xy[2])*t*t+(xy[1]-xy[0])*t/2+xy[2]
def edge_normal(deck,e,side,t):
    xyz=np.array([deck['nodes'][n] for n in deck['elements'][e]])
    xy=xyz[list(TRI[side-1])];v=(xy[0]+xy[1]-2*xy[2])*t+(xy[1]-xy[0])/2
    cross=np.linalg.det(np.array([xyz[1]-xyz[0],xyz[2]-xyz[0]]))
    normal=np.array([v[1],-v[0]])*(1 if cross>0 else -1)
    return normal/np.linalg.norm(normal)

def nearest(deck,name,point):
    ids=deck['surfaces'][name];p=np.asarray(point);best=None
    ids=sorted(ids,key=lambda es:min(math.dist(deck['nodes'][n],point) for n in edge_nodes(deck,*es)))[:12]
    for e,side in ids:
        pp=np.array([deck['nodes'][n] for n in edge_nodes(deck,e,side)])
        A=(pp[0]+pp[1])/2-pp[2];B=(pp[1]-pp[0])/2;D=pp[2]-p
        roots=np.polynomial.polynomial.polyroots([D@B,B@B+2*D@A,3*A@B,2*A@A])
        for t in [-1.,1.]+[float(x.real) for x in roots if abs(x.imag)<1e-8 and -1<=x.real<=1]:
            q=curve(pp,t);distance=float(np.linalg.norm(q-p))
            if best is None or distance<best['distance_mm']:
                best={'element':e,'side':side,'parameter':t,'point_mm':q.tolist(),'distance_mm':distance,'outward_normal':edge_normal(deck,e,side,t).tolist()}
    return best

def active_bounds(deck,step):
    active={}
    for block in deck['bounds']:
        if block['step']>step:continue
        if block['op_new']:active={}
        for row in block['rows']:
            target=row[0];ns=[int(target)] if target.isdigit() else deck['sets'][target]
            for node in ns:
                for dof in range(int(row[1]),int(row[2] if len(row)>2 else row[1])+1):
                    active[node,dof]=float(row[3]) if len(row)>3 else 0.
    return active

def rigid_check(deck,meta):
    node_body={n:deck['body'][e] for e,ns in deck['elements'].items() for n in ns}
    def mode(node,dof):
        side=node_body[node];x,y=deck['nodes'][node];index=0 if side=='PINION' else 3
        if index:x-=meta['O2'][0];y-=meta['O2'][1]
        row=np.zeros(6);row[index+dof-1]=1;row[index+2]=-y if dof==1 else x
        return row
    rows=[sum((coef*mode(n,d) for n,d,coef in eq),np.zeros(6)) for eq in deck['equations']]
    checks=[];dep=[(eq[0][0],eq[0][1]) for eq in deck['equations']]
    for step in [0,1,2]:
        bc=active_bounds(deck,step);matrix=np.array(rows+[mode(n,d) for n,d in bc])
        matrix/=np.maximum(np.linalg.norm(matrix,axis=1)[:,None],1e-20)
        rank=int(np.linalg.matrix_rank(matrix,tol=1e-8));target=6 if step==1 else 5
        # With wheel fixed, the intended free rigid mode is pinion rotation only.
        rotational_residual=float(np.max(np.abs(matrix[:,2])))
        overlap=set(dep)&set(bc)
        checks.append({'step':step,'rigid_mode_constraint_rank':rank,'expected_rank':target,
                       'pinion_rotation_constraint_residual':rotational_residual,
                       'dependent_MPC_DOF_also_prescribed':len(overlap),
                       'pass':rank==target and not overlap and (step==1 or rotational_residual<1e-8)})
    return {'steps':checks,'equation_count':len(rows),'unique_dependent_DOF':len(dep)==len(set(dep)),
            'scope':'Rigid-mode algebra in the 2D plane; not a stiffness-matrix rank or 3D stability proof',
            'pass':all(c['pass'] for c in checks) and len(dep)==len(set(dep))}

def boundary_edges(deck):
    occurrences={}
    for e,ns in deck['elements'].items():
        for side,tri in enumerate(TRI,1):
            key=tuple(sorted((ns[tri[0]],ns[tri[1]])));occurrences.setdefault(key,[]).append((e,side))
    return [v[0] for v in occurrences.values() if len(v)==1]

def audit(path,scope,phase,export=True):
    deck=read_deck(path);meta=json.loads(path.with_suffix('.meta.json').read_text(encoding='utf8'))
    exterior=boundary_edges(deck);exset=set(exterior)
    pairs=[]
    for pair in meta['pairs']:
        p=nearest(deck,'PFL',pair['point']);w=nearest(deck,'WFL',pair['point'])
        delta=np.array(w['point_mm'])-p['point_mm'];dot=float(np.dot(p['outward_normal'],w['outward_normal']))
        pairs.append({'theoretical_point_mm':pair['point'],'pinion':p,'wheel':w,
                      'nearest_point_gap_mm':float(np.linalg.norm(delta)),
                      'signed_normal_gap_mm':float(delta@p['outward_normal']),
                      'opposing_normal_dot':dot,
                      'pass':max(p['distance_mm'],w['distance_mm'])<.01 and np.linalg.norm(delta)<.001 and dot<-.999})
    contact={'pairs':pairs,'surfaces_on_exterior':all(es in exset for s in deck['surfaces'].values() for es in s),
             'surface_body_identity':all(deck['body'][e]==expected for name,expected in [('PFL','PINION'),('WFL','WHEEL')] for e,_ in deck['surfaces'][name]),
             'scope':'Initial nearest surfaces and normals at theoretical contact points; not a full interference or pressure-distribution proof',
             'thresholds':{'distance_mm':.01,'gap_mm':.001,'normal_dot_max':-.999}}
    contact['pass']=all(p['pass'] for p in pairs) and contact['surfaces_on_exterior'] and contact['surface_body_identity']
    bc=rigid_check(deck,meta)
    F=np.zeros(2);M=0.
    for load in deck['loads']:
        v=load['value'];x,y=deck['nodes'][load['node']];d=load['dof'];F[d-1]+=v;M+=x*v if d==2 else -y*v
    source_case=json.loads((BASE/'m37/M37-FEA题目包/cases/L3_C001_G1.json').read_text(encoding='utf8'))
    target=source_case['pair']['T1_Nm']*1000/source_case['pair']['b_mm']
    torque_error=abs(M+target)/target
    load={'input_force_N':F.tolist(),'input_moment_about_pinion_center_Nmm':M,'target_torque_per_1mm_Nmm':target,
          'relative_moment_error':torque_error,'required_signed_moment_Nmm':-target,'pass':torque_error<1e-8,
          'interpretation':'A generalized load at the rigid bore master supplies the torque. Its raw resultant force need not be zero; bore constraints provide balancing reactions.'}
    units={'unit_system':'N, mm, MPa; declared from source case, not encoded by CalculiX','plane_model':'CPE6 plane strain','section_thickness_mm':[s['thickness_mm'] for s in deck['sections']],
           'full_gear_face_width_mm':source_case['pair']['b_mm'],'E_MPa':deck['elastic'][0][0],'nu':deck['elastic'][0][1],
           'section_material_assignments':[{**s,'elastic':deck['materials'].get(s['material'],{}).get('elastic')} for s in deck['sections']],
           'pass':{s['set'] for s in deck['sections']}=={'PINION','WHEEL'} and len(deck['sections'])==2
               and all(s['thickness_mm']==1 and deck['materials'].get(s['material'],{}).get('elastic')==[source_case['material']['E_MPa'],source_case['material']['nu']] for s in deck['sections'])}
    result={'scope':scope,'phase':phase,'input':str(path),'input_sha256':SHA(path),'contact':contact,'rigid_boundary':bc,'load':load,'units':units,
            'pass':all(c['pass'] for c in [contact,bc,load,units])}
    if export:
        tags={es:name for name,surf in deck['surfaces'].items() for es in surf}
        edges=[]
        for e,s in exterior:
            xy=[deck['nodes'][n] for n in edge_nodes(deck,e,s)]
            edges.append({'element':e,'side':s,'body':deck['body'][e],'tag':tags.get((e,s),'OTHER'),
                          'points_mm':[curve(xy,t).tolist() for t in [-1,-.5,0,.5,1]]})
        controls=[]
        for step in [0,1,2]:
            active=active_bounds(deck,step)
            controls.append({'step':step,'rows':[{'node':n,'point_mm':deck['nodes'][n],'dof':d,'value':v} for (n,d),v in active.items()]})
        geo={'schema':'m37.geometry-review/v1','purpose':'Geometry/BC/contact/load review only, not 3D stress analysis','input_sha256':SHA(path),
             'case':f'{scope}_ph{phase:02d}','extrusion_mm':1,'origin_mm':[0,0],'wheel_center_mm':meta['O2'],
             'boundary_edges':edges,'contact_pairs':pairs,'boundary_conditions':controls,
             'loads':[{**x,'point_mm':deck['nodes'][x['node']]} for x in deck['loads']],
             'rigid_coupling':{'pinion_master_nodes':deck['sets']['PMASTER'],'pinion_master_points_mm':[deck['nodes'][n] for n in deck['sets']['PMASTER']],
                               'equation_count':len(deck['equations']),'interpretation':'All pinion bore displacements follow one in-plane infinitesimal rotation; wheel bore translations fixed.'}}
        (GEOM/f'{scope}_ph{phase:02d}.json').write_text(json.dumps(geo,separators=(',',':')),encoding='utf8')
        if (scope,phase) in [('original',0),('periodic',0),('periodic',10)]:
            ids=sorted(deck['nodes']);lookup={n:i for i,n in enumerate(ids)}
            es=sorted(deck['elements'])
            np.savez_compressed(GEOM/f'{scope}_ph{phase:02d}-mesh.npz',node_ids=ids,xy_mm=[deck['nodes'][n] for n in ids],
                element_ids=es,tri6=[[lookup[n] for n in deck['elements'][e]] for e in es],body=[0 if deck['body'][e]=='PINION' else 1 for e in es])
    return result

if __name__=='__main__':
    results=[]
    for scope,folder in [('original','m37-results'),('periodic','m37-l3-periodic-diagnostic')]:
        for phase in range(16):
            r=audit(BASE/folder/'runs/L3'/f'L3_C001_G1_ph{phase:02d}_d12.inp',scope,phase)
            results.append(r);print(scope,phase,r['pass'],r['contact']['pass'],r['rigid_boundary']['pass'],flush=True)
    diagnostic=json.loads((BASE/'m37-diag-p02/diagnostic.json').read_text(encoding='utf8'))
    p02=[]
    for r in diagnostic['records']:
        inp=BASE/'m37-diag-p02'/(r['id']+'.inp');nodes={};loads=[];key=''
        for line in inp.read_text().splitlines():
            if line.startswith('*'):key=line.split(',')[0];continue
            row=line.split(',')
            if key=='*NODE':nodes[int(row[0])]=list(map(float,row[1:3]))
            elif key=='*CLOAD':loads.append((int(row[0]),int(row[1]),float(row[2])))
        meta=json.loads(inp.with_suffix('.meta.json').read_text(encoding='utf8'));y0=meta['geometry_check']['point_30deg'][1]
        force=[sum(v for _,d,v in loads if d==axis) for axis in [1,2]]
        moment=sum(nodes[n][0]*v if d==2 else -(nodes[n][1]-y0)*v for n,d,v in loads)
        point=meta['load_point'];nominal=point[0]*force[1]-(point[1]-y0)*force[0]
        ratio=moment/nominal;force_error=abs(math.hypot(*force)-meta['Fn_per_b'])/meta['Fn_per_b']
        p02.append({'id':r['id'],'inp_sha256':SHA(inp),'force_N':force,'force_relative_error':force_error,'moment_Nmm':moment,
                    'moment_ratio':ratio,'pass':force_error<1e-10 and abs(ratio-1)<1e-6})
    summary={'schema':'m37.semantic-preflight/v1','scope':'Input geometry and boundary semantics only; no stress/model/product acceptance claim',
             'cases':results,'P02_clipped_loads':p02,'P02_relative_moment_spread':max(r['moment_ratio'] for r in p02)-min(r['moment_ratio'] for r in p02),
             'regression':{'original_invalid_phases_fail':all(not r['pass'] for r in results if r['scope']=='original' and r['phase']<10),
                           'original_valid_phases_pass':all(r['pass'] for r in results if r['scope']=='original' and r['phase']>=10),
                           'periodic_16_pass':all(r['pass'] for r in results if r['scope']=='periodic'),
                           'P02_force_and_moment_stable':all(r['pass'] for r in p02)}}
    (OUT/'preflight.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary['regression']),flush=True)
    assert all(summary['regression'].values()),'Input semantic regression did not meet required outcome; inspect evidence'
