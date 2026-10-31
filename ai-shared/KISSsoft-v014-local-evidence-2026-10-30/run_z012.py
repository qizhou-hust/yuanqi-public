"""Local external calculation evidence. Never overwrites source inputs."""
from pathlib import Path
import sys, json, re, hashlib, math
from datetime import datetime, timezone
import win32com.client, win32api
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent
INSTALL=Path(r'D:\Program Files\KISSsoft AG\KISSsoft 2026')
def decode(p):
    b=p.read_bytes()
    return b.decode('utf-16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8',errors='replace')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def read(k,f):
    v=k.GetVar(f)
    try:return float(v)
    except (TypeError,ValueError):return v
def fields():
    names=['Z010ISOGeneralFactorse.rpt','Z010ISOBendinge.rpt','Z010ISOBendingResulte.rpt','Z010ISOPittinge.rpt','Z010Geometrye.rpt','Z010ToothThicknesse.rpt','Z010Scoringe.rpt','Z010Micropittinge.rpt','Z010Materiale.rpt']
    out=set()
    for n in names:
        p=INSTALL/'rpt'/n
        if p.exists():out.update(re.findall(r'(?:ZR\[[01]\]|ZPP\[[01]\]|ZP\[0\]|ZS|Zst|RechSt)\.[A-Za-z0-9_.]+',decode(p)))
    out.update(['RechSt.RechenMethID','Zst.KHbVariant','Zst.KVFlag','ZS.Geo.mn','ZS.Geo.alfn','ZS.Geo.beta','ZS.Pnominal','ZS.KA','ZP[0].a','ZP[0].Ft','ZP[0].KHdat.fsh00','ZP[0].KHdat.fsh0','ZP[0].KHdat.fsh','ZP[0].KHdat.Fm','ZP[0].b','ZP[0].bB','ZP[0].KHb','ZP[0].KV.KV','ZP[0].Eps.a'])
    for i in (0,1):
        out.update(f'ZR[{i}].{s}' for s in ['z','b','x.nul','san','nnominal','Tnominal','Qpre','mat.bez','mat.limh','mat.limf','Tool.RefProfile.haP','Tool.RefProfile.hfP','Tool.RefProfile.rhofP','Flanke.ZNT','Fuss.YNT','Fuss.YX','Fuss.YR'])
        out.update(f'ZPP[{i}].{s}' for s in ['Flanke.SH','Fuss.SFnorm','Fuss.Ydrel','Flanke.ZV','Flanke.ZL','Flanke.ZR'])
    return sorted(out)
def run(case,source,edits):
    folder=ROOT/case;folder.mkdir(exist_ok=True)
    source=Path(source).resolve();initial=sha(source)
    k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False);k.SetSilentMode(True);k.SetLanguage(1)
    r={'id':case,'source':str(source),'source_sha256':initial,'generated_utc':datetime.now(timezone.utc).isoformat(),'module':'Z012','edits':[],'accepted':False}
    try:
        r['version']=k.GetKsoftVersion();r['license']=bool(k.CheckLicense('Z012'))
        vi=win32api.GetFileVersionInfo(str(INSTALL/'bin'/'KISSsoft.exe'),'\\')
        r['file_version']='.'.join(str(x) for x in (vi['FileVersionMS']>>16,vi['FileVersionMS']&65535,vi['FileVersionLS']>>16,vi['FileVersionLS']&65535))
        k.LoadFile(str(source))
        for f,v in edits.items():
            before=read(k,f);k.SetVar(f,str(v));r['edits'].append({'field':f,'before':before,'requested':v,'readback':read(k,f)})
        r['calculate_return']=bool(k.CalculateRetVal());r['messages']=k.Message()
        vals={};errors={}
        for f in fields():
            try:
                v=read(k,f)
                if v=='':errors[f]='not exposed/empty'
                else:vals[f]=v
            except Exception as e:errors[f]=str(e)
        r['values']=vals;r['errors']=errors
        native=folder/(case+'.Z12');k.SaveFile(str(native));r['native_sha256']=sha(native)
        k.ReportWithParameters('Z012Le0.RPT',str(folder/(case+'.rtf')),0,0)
        k.ReportWithParameters('Z012Le0.RPT',str(folder/(case+'.html')),0,2)
        k.LoadFile(str(native));r['reload_calculate_return']=bool(k.CalculateRetVal());r['reload_messages']=k.Message()
        r['reload_differences']={}
        for f,v in vals.items():
            a=read(k,f)
            same=math.isclose(v,a,rel_tol=1e-9,abs_tol=1e-9) if isinstance(v,float) and isinstance(a,float) else a==v
            if not same:r['reload_differences'][f]={'before':v,'after':a}
        r['source_unchanged']=sha(source)==initial
        dump(folder/'run.json',r)
        print(json.dumps({x:r[x] for x in ['id','calculate_return','reload_calculate_return','reload_differences','messages']},ensure_ascii=False),flush=True)
        return r
    finally:k.ReleaseModule()
if __name__=='__main__':
    cfg=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
    for c in cfg:run(c['id'],c['source'],c.get('edits',{}))
