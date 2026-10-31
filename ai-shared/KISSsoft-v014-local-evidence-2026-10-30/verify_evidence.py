from pathlib import Path
import json,hashlib,math
import fitz
ROOT=Path(__file__).resolve().parent
rows=[]
for p in sorted(ROOT.glob('P*/run.json')):
    r=json.loads(p.read_text(encoding='utf8')); source=Path(r['source'])
    rows.append({'id':r['id'],'calculated':r['calculate_return'],'reloaded':r['reload_calculate_return'],
                 'no_drift':not r['reload_differences'],'source_hash_matches':hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256'],
                 'native_hash_matches':hashlib.sha256((p.parent/(r['id']+'.Z12')).read_bytes()).hexdigest()==r['native_sha256']})
for p in sorted(ROOT.glob('P4*/result.json')):
    r=json.loads(p.read_text(encoding='utf8'))
    rows.append({'id':p.parent.name,'calculated':r.get('calculate_ok',False),'reloaded':r.get('reload_ok',False),
                 'no_drift':not r.get('reload_differences',{'missing':1})})
pdfs=[]
for p in sorted(ROOT.rglob('*.pdf')):
    d=fitz.open(p);t='\n'.join(x.get_text() for x in d)
    pdfs.append({'path':str(p.relative_to(ROOT)),'pages':len(d),'text_chars':len(t),'unexpanded':'<EXECUTE=' in t or '1IF(' in t,
                 'consistent_warning':'Calculation not consistent' in t})
assert all(r.get('source_hash_matches',True) and r.get('native_hash_matches',True) for r in rows)
assert all(p['pages']>0 and p['text_chars']>100 and not p['unexpanded'] for p in pdfs)
for case in ['P1-TR30-example7-unchanged','P2-K01-geometry-mapped','P3-K01-spur','P3-K02-helical','P3-K03-premachining','P3-K04-EV-stage1','P3-K05-EV-stage2']:
    r=next(r for r in rows if r['id']==case)
    assert r['calculated'] and r['reloaded'] and r['no_drift'],r
for case in ['P3-K01-spur','P3-K02-helical']:
    r=json.loads((ROOT/case/'p3-detail.json').read_text(encoding='utf8'))
    assert r['seven_points_valid']
for case,pref in [('A1',90),('A2',113.1975),('A3',50),('A4',43.533257064409106)]:
    r=json.loads((ROOT/f'P4-fit-{case}-mapped-v2'/'result.json').read_text(encoding='utf8'))
    assert r['calculate_ok'] and r['reload_ok'] and not r['reload_differences']
    assert math.isclose(float(r['values']['m01allg.s']),4.8,abs_tol=1e-10)
    assert math.isclose(float(r['values']['m01r.p[0]']),pref,abs_tol=1e-8)
out={'status':'PASS_FOR_LISTED_GATES_NOT_ALL_REQUESTS_COMPLETE','calculations':rows,'pdfs':pdfs}
(ROOT/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print('Verified source/native hashes, required round trips, MP seven points, four interference pressures and',len(pdfs),'PDFs. Failed diagnostic calculations remain labelled.')
