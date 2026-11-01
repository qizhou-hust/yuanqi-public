import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from gearmath.tools import m33_geometry_replay as core
from gearmath.kernel import units as U

PINS={'ex7-map.csv':'c6a02e9b60bbfe8e9c9be396eb19cbe0a8b3f5b34e6c99cc7001d20c2876cf18','ex8-map.csv':'88f39653b77a50b2c4ad317d5ccf954844eeaa645e25a4fa42ccadca6ce5c0db','ex8-native-run.json':'99b1f1507eaefd484149e55b7e63760653f30b0a29f07b2df9ee68513f07d573'}
def run():
    native=ROOT/'data/m33_evidence/ex8-native-run.json'; source=json.loads(native.read_text(encoding='utf8'))
    if core.sha(native)!=PINS[native.name]: raise ValueError('native hash mismatch')
    if not source['calculate_return'] or not source['reload_calculate_return'] or source['reload_differences']: raise ValueError('native run not validated')
    models={c:core.build_model(c,zv_velocity='v_ref',hardness_conversion='ISO18265_A1_linear',rz_source='printed_rz' if c==8 else None,protuberance_dff='numerical_envelope' if c==8 else None) for c in (7,8)}
    for i in (0,1):
        key=f'ZR[{i}].BP_f.hfP'; val=source['values'][key]
        if source['reload_values'][key]!=val: raise ValueError('native input drift')
        models[8].set(f'hfP_{i+1}',val,'1','evidence','KISSsoft saved/reopened native final rack')
    rows=[]; hashes={}
    for c in (7,8):
        fp=ROOT/f'data/m33_evidence/ex{c}.csv'; mp=ROOT/f'data/m33_evidence/ex{c}-map.csv'
        if core.sha(mp)!=PINS[mp.name]: raise ValueError('mapping hash mismatch')
        if core.sha(fp)!=core.PINS[c]: raise ValueError('reference hash mismatch')
        hashes[mp.relative_to(ROOT).as_posix()]=core.sha(mp)
        with fp.open(encoding='utf-8-sig',newline='') as f: ref=list(csv.DictReader(f))
        with mp.open(encoding='utf-8-sig',newline='') as f: mapping=[r for r in csv.DictReader(f) if r['stage']=='geometry']
        for m in mapping:
            hits=[r for r in ref if r['量键']==m['key'] and r['轮(1/2/空=单值)']==m['gear']]
            if len(hits)!=1: raise ValueError('reference identity')
            r=hits[0]; name=m['model_quantity']; unit=r['单位']; raw=r['KISSsoft值(≥4位有效数字,尽量全精度)']; model=models[c]
            row=dict(case=c,key=m['key'],gear=m['gear'],quantity=name,unit=unit,reference=float(raw) if raw else None)
            if not raw: row['status']='missing_reference'
            elif name not in model.formulas and name not in model.inputs: row['status']='missing_model'
            else:
                out=model.evaluate([name]);
                if out.status!='ok': row['status']='evaluation_'+out.status
                else:
                    v=U.from_canonical(out.values[name],unit); refval=float(raw); row.update(model=v,relative_error=abs(v-refval)/abs(refval) if refval else (0 if not v else None),status='formula' if name in model.formulas else ('numerical_method' if name in getattr(model,'tr30_numerical_nodes',{}) else 'input'))
            rows.append(row)
    counts={status:len({(r['case'],r['quantity']) for r in rows if r['status']==status}) for status in ('formula','input','numerical_method')}
    if len(rows)!=64 or counts!={'formula':50,'input':4,'numerical_method':2}: raise ValueError('geometry mapping coverage changed')
    return dict(unique_counts=counts,scope='available mapped geometry rows; native final rack diagnostic',native_input_sha256=core.sha(native),native_hfP=[source['values'][f'ZR[{i}].BP_f.hfP'] for i in (0,1)],mapping_hashes=hashes,producer_sha256=core.sha(Path(__file__)),base_producer_sha256=core.sha(Path(core.__file__)),input_sha256=core.sha(ROOT/'data/tr30/examples-5-8.json'),model_source_hashes={p.relative_to(ROOT).as_posix():core.sha(p) for p in sorted((ROOT/'gearmath').rglob('*.py'))},rows=rows, full_e4='blocked; native rack differs from printed table; numerical dFf definition remains unconfirmed; diagnostic only')
def receipt_is_current(r):
    return r['producer_sha256']==core.sha(Path(__file__)) and r['base_producer_sha256']==core.sha(Path(core.__file__)) and r['native_input_sha256']==core.sha(ROOT/'data/m33_evidence/ex8-native-run.json') and r['input_sha256']==core.sha(ROOT/'data/tr30/examples-5-8.json') and r['mapping_hashes']=={(ROOT/'data/m33_evidence'/name).relative_to(ROOT).as_posix():core.sha(ROOT/'data/m33_evidence'/name) for name in ('ex7-map.csv','ex8-map.csv')} and r['model_source_hashes']=={p.relative_to(ROOT).as_posix():core.sha(p) for p in sorted((ROOT/'gearmath').rglob('*.py'))}
if __name__=='__main__':
    r=run();p=ROOT/'output/m33/native-geometry-diagnostic.json';p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('rows',len(r['rows']),'statuses', {s:sum(x['status']==s for x in r['rows']) for s in set(x['status'] for x in r['rows'])}); print('max',max(x['relative_error'] for x in r['rows'] if x.get('relative_error') is not None))
