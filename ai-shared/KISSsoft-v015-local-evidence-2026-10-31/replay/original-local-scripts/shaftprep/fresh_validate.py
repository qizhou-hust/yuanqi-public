from pathlib import Path
import json,sys,hashlib,math,re,tempfile,shutil
import win32com.client
sys.stdout.reconfigure(encoding='utf8')
HERE=Path(__file__).resolve().parent
for p in sorted(HERE.glob('R1-*-run.json')):
 r=json.loads(p.read_text(encoding='utf8'));k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('W010',False);k.SetSilentMode(True);k.SetLanguage(1)
 try:
  native=p.with_suffix('.W10');k.LoadFile(str(native));ok=bool(k.CalculateRetVal())
  names=list(r['values'])+['Qu[0].sErmuedung','Qu[0].sStatisch']
  values={f:k.GetVar(f) for f in names}
  assert ok and math.isclose(float(values['Qu[0].Rz']),6.3,abs_tol=1e-12)
  assert values['Qu[0].OberflPos']=='20000'
  msg=k.Message();assert not any('19999' in str(t) for t in msg)
  r['fresh_module_ok']=ok;r['fresh_module_messages']=msg;r['fresh_values']=values
  r['values']['Qu[0].sErmuedung']=values['Qu[0].sErmuedung'];r['values']['Qu[0].sStatisch']=values['Qu[0].sStatisch']
  k.Report(0)
  source=max(Path(tempfile.gettempdir()).glob('KISS_*/*.pprpt'),key=lambda x:x.stat().st_mtime)
  shutil.copy2(source,p.with_suffix('.pprpt'))
  p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
  print(p.stem,'Rz',values['Qu[0].Rz'],'SD',values['Qu[0].sErmuedung'],'SS',values['Qu[0].sStatisch'],flush=True)
 finally:k.ReleaseModule()
