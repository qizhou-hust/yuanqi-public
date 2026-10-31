"""Fresh headless reloads only; never sends UI input or overwrites natives."""
from pathlib import Path
import json,math,hashlib
import win32com.client

ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def same(a,b):
    if a==b:return True
    try:return math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-11)
    except (ValueError,TypeError):return False
rows=[]
for p in sorted(ROOT.glob('R[45]-*/result.json')):
    r=json.loads(p.read_text(encoding='utf8'));c=r['case'];native=p.parent/(c['id']+c['ext'])
    assert sha(native)==r['sha256']
    assert sha(Path(c['source']))==r['source_sha256']
    k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft')
    k.GetModule(c['module'],False);k.SetSilentMode(True)
    try:
        k.LoadFile(str(native));ok=bool(k.CalculateRetVal())
        values={f:k.GetVar(f) for f in r['values']}
        diffs={f:[v,values[f]] for f,v in r['values'].items() if not same(v,values[f])}
        assert ok and not diffs,(c['id'],diffs)
        rows.append({'case':c['id'],'module':c['module'],'version':k.GetKsoftVersion(),'fresh_headless_ok':ok,'native_sha256':sha(native),'source_sha256':r['source_sha256'],'differences':diffs,'messages':k.Message(),'raw_values':values})
    finally:k.ReleaseModule()
p=ROOT/'shaftprep/R2-6206-RZ-run.json';r=json.loads(p.read_text(encoding='utf8'));native=p.with_suffix('.W50')
k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('W050',False);k.SetSilentMode(True)
try:
    k.LoadFile(str(native));ok=bool(k.CalculateRetVal())
    vals={f:k.GetVar(f) for f in r['values']}
    diffs={f:[v,vals[f]] for f,v in r['values'].items() if not same(v,vals[f])}
    assert ok and not diffs,diffs
    rows.append({'case':'R2-6206-RZ','module':'W050','version':k.GetKsoftVersion(),'fresh_headless_ok':ok,'native_sha256':sha(native),'differences':diffs,'messages':k.Message(),'raw_values':vals})
finally:k.ReleaseModule()
k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False);k.SetSilentMode(True)
try:
    native=ROOT/'M39-K02-helical-Ca-not-optimal/M39-K02-helical-Ca-not-optimal.Z12'
    k.LoadFile(str(native));assert k.CalculateRetVal()
    ww=k.GetVar('ZP[0].RefMP.WW');assert float(ww)==1
    rows.append({'case':'K02-WW-direct-read','module':'Z012','version':k.GetKsoftVersion(),'fresh_headless_ok':True,'native_sha256':sha(native),'raw_values':{'ZP[0].RefMP.WW':ww},'scope':'This saved material pair only'})
finally:k.ReleaseModule()
(ROOT/'fresh-supplement-verification.json').write_text(json.dumps({'all_calls_headless':True,'checks':rows},ensure_ascii=False,indent=2),encoding='utf8')
print('Fresh headless verification passed:',len(rows),'records; no GUI input.')
