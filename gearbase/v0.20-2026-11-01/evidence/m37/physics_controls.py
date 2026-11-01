import sys, json, math, hashlib, subprocess, time
from pathlib import Path
import numpy as np
ROOT=Path('D:/my_Works/Gears/gearbase-v020-work')
BASE=Path(__file__).parent
OUT=BASE/'physics_controls'; OUT.mkdir(exist_ok=True)
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'data/m37_fea_pack/scripts')]
from gearmath.tools import solver_allowance, fea_prepare
import cases,ccx_io,run_m37
SOLVER=Path('D:/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def parse(text):
    nodes={}; loads={}; mode=''
    for line in text.splitlines():
        if line.startswith('**'): continue
        if line.startswith('*'): mode=line.split(',')[0].upper(); continue
        v=line.split(',')
        if mode=='*NODE': nodes[int(v[0])]=list(map(float,v[1:3]))
        if mode=='*CLOAD': loads.setdefault(int(v[0]),[0.,0.])[int(v[1])-1]+=float(v[2])
    return nodes,loads
def replace(text,loads):
    result=[]; skip=False
    for line in text.splitlines():
        if line.startswith('*CLOAD'):
            result.append(line)
            result.extend(f'{n},{i+1},{f:.16g}' for n,fs in loads.items() for i,f in enumerate(fs))
            skip=True; continue
        if line.startswith('*'): skip=False
        if not skip: result.append(line)
    return '\n'.join(result)+'\n'
def metrics(nodes,loads,meta):
    f=np.sum(list(loads.values()),axis=0); moment=sum(nodes[n][0]*v[1]-nodes[n][1]*v[0] for n,v in loads.items())
    fn=np.array(meta['load_dir'])*meta['Fn_per_b']; target=np.cross(meta['load_point'],fn).item()
    return {'force_N':f.tolist(),'moment_Nmm':moment,'target_moment_Nmm':target,'moment_residual_Nmm':moment-target,'force_residual_N':(f-fn).tolist()}
def prepare():
    plan={'predeclared':'Two same-mesh P08/P03 d18 controls; only patch nodal magnitudes change. Maximum-entropy reweight of original strictly positive normal weights imposes sum=Fn and moment=HPSTC. No tuning against stress/reference. Stop if residual mismatch persists.','cases':[]}
    sources={}
    for point in ('P08','P03'):
        src=BASE/'matrix'/f'L2_{point}_d18.inp'; mp=src.with_suffix('.meta.json')
        for p in (src,mp,src.with_suffix('.dat'),src.with_suffix('.record.json')): sources[str(p)]=sha(p)
        meta=json.loads(mp.read_text()); text=src.read_text(); nodes,loads=parse(text)
        ids=list(loads); direction=np.array(meta['load_dir']); Fn=meta['Fn_per_b']
        w=np.array([np.dot(loads[n],direction)/Fn for n in ids]); w/=sum(w)
        a=np.array([nodes[n][0]*direction[1]-nodes[n][1]*direction[0] for n in ids])
        target=np.cross(meta['load_point'],direction).item()
        item={'point':point,'original':metrics(nodes,loads,meta),'moment_per_unit_force_range':[min(a),max(a)],'target_moment_per_unit_force':target,'feasible':bool(min(a)<=target<=max(a))}
        if item['feasible']:
            scale=max(a)-min(a); q=(a-target)/scale
            def weights(lam):
                z=np.log(w)+lam*q; z-=max(z); r=np.exp(z); return r/sum(r)
            lo,hi=-1024.,1024.
            for _ in range(150):
                mid=(lo+hi)/2
                if np.dot(weights(mid),q)>0: hi=mid
                else: lo=mid
            wp=weights((lo+hi)/2)
            new={n:(Fn*wp[i]*direction).tolist() for i,n in enumerate(ids)}
            inp=OUT/f'{point}_d18_moment.inp'; inp.write_text(replace(text,new))
            inp.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2))
            item.update({'derived':metrics(nodes,new,meta),'weights_before':w.tolist(),'weights_after':wp.tolist(),'nodes':ids,'minimum_weight':min(wp),'path':str(inp),'unchanged_outside_CLOAD':replace(text,{})==replace(inp.read_text(),{})})
        plan['cases'].append(item)
    plan['source_sha256']=sources
    (OUT/'predeclared.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(plan,indent=2))
def run():
    plan=json.loads((OUT/'predeclared.json').read_text()); results=[]
    for item in plan['cases']:
        if not item['feasible']: continue
        inp=Path(item['path']); meta=json.loads(inp.with_suffix('.meta.json').read_text())
        permission=solver_allowance.verify(SOLVER)
        reader=fea_prepare.verified_profile(Path('D:/my_Works/Gears/v017-system-run/fea-prepare'),SOLVER)
        state,check,prepared=run_m37.preflight(inp,inp.with_suffix('.meta.json'),SOLVER)
        assert check['pass'] and not state.frd_requested()
        before={str(p):sha(p) for p in (inp,inp.with_suffix('.meta.json'),SOLVER)}
        command=f'cd /mnt/d/my_Works/Gears/v020-closure-run/m37/physics_controls && export LD_LIBRARY_PATH=/mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/runtime/usr/lib/x86_64-linux-gnu:/mnt/d/my_Works/Gears/parallel-v09-2026-10-29/m37/runtime-ccx/root/usr/lib/x86_64-linux-gnu && sha256sum /mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 | grep -q ^{solver_allowance.BINARY_SHA256} && OMP_NUM_THREADS=1 timeout 120s /mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 {inp.stem}'
        t=time.time(); r=subprocess.run(['wsl','-d','Ubuntu','--','bash','-lc',command],capture_output=True,timeout=135)
        inp.with_suffix('.log').write_bytes(r.stdout+r.stderr)
        assert not r.returncode, r.stderr
        assert before=={p:sha(p) for p in before}
        rec,_=reader.strict_record(inp.with_suffix('.dat').read_text(),inp.with_suffix('.sta').read_text(),state.strict_requests(),identity={'run_id':inp.stem,'input_sha256':sha(inp)},solver_version='2.23',**state.expectation())
        assert rec['status']=='accepted',rec
        ex,warn=cases.post_L2(meta,ccx_io.parse_dat(inp.with_suffix('.dat')))
        orig=json.loads((BASE/'matrix'/f'L2_{item["point"]}_d18.record.json').read_text())['extracted']
        nodes,loads=parse(inp.read_text()); blocks=ccx_io.parse_dat(inp.with_suffix('.dat')); RF=ccx_io.nodal(blocks,'forces','FIXED')
        reactions={n:v[:2] for n,v in RF.items()}
        reaction_moment=sum(nodes[n][0]*v[1]-nodes[n][1]*v[0] for n,v in reactions.items())
        record={'point':item['point'],'extracted':ex,'original_extracted':orig,'stress_change_percent':100*(ex['sigma_root_MPa']/orig['sigma_root_MPa']-1),'reaction_moment_Nmm':reaction_moment,'moment_equilibrium_residual_Nmm':reaction_moment+item['derived']['moment_Nmm'],'permission':permission,'strict_read':rec,'preflight':check,'command':command,'elapsed_seconds':time.time()-t,'warnings':warn,'identity_sha256':before,'raw_sha256':{str(p):sha(p) for p in (inp.with_suffix('.dat'),inp.with_suffix('.sta'),inp.with_suffix('.log'))}}
        inp.with_suffix('.record.json').write_text(json.dumps(record,indent=2)); results.append(record)
        print(item['point'],record['stress_change_percent'],ex['sigma_root_MPa'],flush=True)
    integrity={p:sha(p)==v for p,v in plan['source_sha256'].items()}
    (OUT/'results.json').write_text(json.dumps({'results':results,'canonical_integrity':integrity,'script_sha256':sha(__file__)},indent=2))
if __name__=='__main__':
    if '--run' in sys.argv: run()
    else: prepare()
