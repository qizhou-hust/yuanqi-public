"""Recalculate isolated KISSsoft evidence; never replace the prior evidence.

Material baseline is saved by the native UI's hardness/limit calculators.
Diagnostic edits are explicit and do not authorize M33 acceptance.
"""
from pathlib import Path
import json, math, csv, re, hashlib
from datetime import datetime, timezone
import win32com.client

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parents[1]/'M33-TR30-7-8-2026-10-29'
INSTALL=Path(r'D:\Program Files\KISSsoft AG\KISSsoft 2026')

def read(k,name):
    value=k.GetVar(name)
    try:return float(value)
    except (ValueError,TypeError):return value

def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')

def run(name,number,source,edits=None,description=''):
    edits=edits or {}
    folder=ROOT/name;folder.mkdir(exist_ok=True)
    fields=set(json.loads((OLD/f'TR30-example-{number}'/'run.json').read_text(encoding='utf8'))['values'])
    for p in (INSTALL/'rpt').iterdir():
        if p.suffix.lower()=='.rpt' and p.name.lower().startswith('z010') and 'e.' in p.name.lower():
            b=p.read_bytes();t=b.decode('utf16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf8',errors='replace')
            fields.update(re.findall(r'(?:ZR\[[01]\]|ZPP\[[01]\]|ZP\[0\]|ZS|Zst)\.[A-Za-z0-9_.]+',t))
    fields.update(['ZR[0].NL','ZR[1].NL','ZS.v','ZR[0].sr','ZR[1].sr',*edits])
    k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False)
    k.SetSilentMode(True);k.SetLanguage(1)
    try:
        k.LoadFile(str(source));change=[]
        for key,value in edits.items():
            before=read(k,key);k.SetVar(key,str(value).lower() if isinstance(value,bool) else str(value))
            change.append({'field':key,'before':before,'requested':value,'readback':read(k,key)})
        k.SetVar('calculation.description',f'TR30 example {number} {name} - UNACCEPTED')
        k.SetVar('calculation.comment',description)
        attempts=[]
        for _ in range(2):
            ok=bool(k.CalculateRetVal());attempts.append({'ok':ok,'messages':k.Message()})
            if ok:break
        if not ok:raise RuntimeError(attempts)
        values={};errors={}
        for f in sorted(fields):
            try:
                x=read(k,f)
                if x=='':errors[f]='No exposed value'
                else:values[f]=x
            except Exception as e:errors[f]=str(e)
        native=folder/(name+'.Z12');k.SaveFile(str(native))
        k.ReportWithParameters('Z012Le0.RPT',str(folder/(name+'.rtf')),0,0)
        version=k.GetKsoftVersion()
        k.LoadFile(str(native));reload_ok=bool(k.CalculateRetVal());reload_messages=k.Message()
        after={f:read(k,f) for f in values}
        delta={f:{'before':v,'after':after[f]} for f,v in values.items() if not
               (math.isclose(v,after[f],rel_tol=1e-10,abs_tol=1e-10) if isinstance(v,float) and isinstance(after[f],float) else v==after[f])}
        result={'case':number,'variant':name,'description':description,'acceptance':'NOT_ACCEPTED',
                'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'generated_utc':datetime.now(timezone.utc).isoformat(),'runtime_version':version,
                'module':'Z012','report_language':'English','edits':change,'attempts':attempts,
                'calculate_return':ok,'values':values,'errors':errors,'reload_values':after,
                'reload_calculate_return':reload_ok,'reload_messages':reload_messages,'reload_differences':delta}
        dump(folder/'run.json',result)
        with (folder/'high-precision-values.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['variable','value'])
            for key,v in sorted(after.items()):w.writerow([key,format(v,'.17g') if isinstance(v,float) else v])
        print(name,'ok',ok,'reload',reload_ok,'drift',len(delta),'fields',len(values),flush=True)
        if not reload_ok or delta:raise RuntimeError('Native reload gate failed')
        return result
    finally:k.ReleaseModule()

if __name__=='__main__':
    run('ex7-base-native',7,ROOT/'ex7-native-material.Z12',description='TR30 original inputs; limits from native ISO hardness and endurance-limit dialogs. Ancillary defaults and unresolved input issues are documented.')
    limits={f'ZR[{i}].mat.{q}':x for i,pair in enumerate(((661,256),(603,238))) for q,x in zip(('limh','limf'),pair)}
    run('ex7-diag-lim',7,ROOT/'ex7-base-native'/'ex7-base-native.Z12',limits,'DIAGNOSTIC ONLY: printed TR30 strength limits used explicitly to isolate material-limit differences.')
    run('ex8-Rz2.3',8,OLD/'TR30-example-8'/'TR30-example-8.Z12',description='Original printed Rz=2.3; inherited candidate baseline. Native material validation and input identity are recorded separately.')
    # No valid headless Ra -> Rz function has been established. RZFlag=0
    # overwrites Ra and Rz using defaults and is NOT the requested variant.
    # Failed exploratory evidence is retained under research/FAILED-*.
