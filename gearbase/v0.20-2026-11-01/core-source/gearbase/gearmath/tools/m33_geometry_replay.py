import copy, csv, hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from gearmath.gear.tr30_full58 import build_model
from gearmath.kernel import units as U
SPECS=[(7,'EXTRA:s_Fn',i,'sFn_'+str(i)) for i in (1,2)]+[(8,k,i,n+'_'+str(i)) for k,n in [('EXTRA:h_Fe','hFe'),('EXTRA:s_Fn','sFn'),('EXTRA:rho_F','rhoF')] for i in (1,2)]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
PINS={7:'580f8720c6038b59f19d34e1fa3ae085b602f5659363aaa0f828fafbf374b7c3',8:'fa0042f9c9c459c5ae3c63ee55dbe1ee84c194113b39f9b43d0af491640e6e58'}
def run():
    if len(SPECS)!=8 or len(set((c,k,i) for c,k,i,n in SPECS))!=8: raise ValueError('coverage')
    models={c:build_model(c,zv_velocity='v_ref',hardness_conversion='ISO18265_A1_linear',rz_source='printed_rz' if c==8 else None) for c in (7,8)}
    rows=[]
    for c,k,i,n in SPECS:
        p=ROOT/'data/m33_evidence'/('ex%d.csv'%c)
        if sha(p)!=PINS[c]: raise ValueError('reference hash mismatch')
        with p.open(encoding='utf-8-sig',newline='') as f: records=list(csv.DictReader(f))
        m=[r for r in records if r['量键']==k and r['轮(1/2/空=单值)']==str(i)]
        if len(m)!=1 or m[0]['单位']!='mm': raise ValueError('missing or duplicate reference '+n)
        ref=float(m[0]['KISSsoft值(≥4位有效数字,尽量全精度)']); model=models[c]; out=model.evaluate([n])
        if not ref or out.status!='ok' or n not in model.formulas: raise ValueError('missing model or reference '+n)
        v=U.from_canonical(out.values[n],'mm'); e=abs(v-ref)/abs(ref)
        rows.append(dict(case=c,quantity=n,unit='mm',model=v,reference=ref,relative_error=e,strict_pass=e<=1e-6,source=p.relative_to(ROOT).as_posix(),source_sha256=sha(p),reference_key=k,source_note=m[0]['备注(取值方式/与默认不同的设置)'],formula_source=model.formulas[n].ref))
    return dict(producer_sha256=sha(Path(__file__)),scope='user identified eight historical geometry differences',user_wording='本地已找到例7/8的8条历史差异且均小于1% ，应该是这几个',original_2_of_6_identified=False,status='numeric_candidate' if all(r['relative_error']<=.01 for r in rows) else 'fail',limit=.01,strict_geometry_limit=1e-6,input_identity='blocked: example 8 final hfP differs from original table',input_sha256=sha(ROOT/'data/tr30/examples-5-8.json'),rows=rows,model_source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'gearmath').rglob('*.py'))})
def receipt_is_current(receipt):
    current={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'gearmath').rglob('*.py'))}
    return receipt.get('producer_sha256')==sha(Path(__file__)) and receipt.get('model_source_hashes')==current and receipt.get('input_sha256')==sha(ROOT/'data/tr30/examples-5-8.json') and all(sha(ROOT/r['source'])==r['source_sha256']==PINS[r['case']] for r in receipt['rows'])
def verify_receipt(receipt):
    try:
        if not receipt_is_current(receipt) or receipt.get('limit') != .01: return False
        fresh=run()
        # libm can differ by a few ulps across Windows/Linux. This replay
        # tolerance only checks recorded computed numbers; it does not relax
        # the original 1% comparison, which always uses the fresh model.
        checked=copy.deepcopy(receipt)
        if len(checked['rows']) != len(fresh['rows']): return False
        for row, target in zip(checked['rows'],fresh['rows']):
            for field in ('model','relative_error'):
                value=row[field]
                if type(value) not in (int,float) or not math.isfinite(value) or not math.isclose(value,target[field],rel_tol=1e-12,abs_tol=1e-15): return False
                row[field]=target[field]
        return checked == fresh and fresh['status']=='numeric_candidate' and len(fresh['rows'])==8 and all(x['relative_error']<=.01 for x in fresh['rows'])
    except (KeyError, ValueError, OSError, TypeError): return False
if __name__=='__main__':
    r=run(); p=ROOT/'output/m33/geometry-closure.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(r['status'],len(r['rows']),max(x['relative_error'] for x in r['rows'])); sys.exit(0 if r['status']=='numeric_candidate' else 1)
