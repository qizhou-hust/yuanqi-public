"""Prepared only. Parent owns the single COM instance. This file never dispatches COM."""
from pathlib import Path
import json,re,math,hashlib,tempfile,shutil
HERE=Path(__file__).resolve().parent
INSTALL=Path(r'D:/Program Files/KISSsoft AG/KISSsoft 2026')
BASE=Path(r'D:/my_Works/Gears/kisssoft-v014-run/p4shaft/P4-shaft-corrected-static.W10')
def dump(k,fields):
 out={}
 for f in fields:
  try:out[f]=k.GetVar(f)
  except Exception as e:out[f]={'error':str(e)}
 return out
def report(k,stem,module):
 # The module Report pipeline builds complete dynamic shaft/strength reports.
 # ReportWithParameters on the static wrapper misses that initialization.
 k.Report(0)
 candidates=list(Path(tempfile.gettempdir()).glob('KISS_*/*.pprpt'))
 if not candidates:raise RuntimeError('No native report produced')
 source=max(candidates,key=lambda p:p.stat().st_mtime)
 shutil.copy2(source,HERE/(stem+'.pprpt'))
def run_r1(k,roughness_record_id):
 if int(roughness_record_id)<20000:raise ValueError("Require a real saved W000/W010OBER user-record ID >=20000; 19999 is invalid here")
 cases=json.loads((HERE/'R1-cases.json').read_text(encoding='utf8'))
 result_fields=json.loads((HERE/'result-fields.json').read_text(encoding='utf8'))
 for case in cases:
  k.LoadFile(str(HERE/case['file']))
  for label in ['Cylindrical gear','Coupling / Motor']:
   k.CallFuncNParam(['SetElementData',label,'lengthOfLoad',str(case['lengthOfLoad_mm'])])
  # Validated GUI/database record only; never write the derived Rz cache.
  k.SetVar('Qu[0].OberflPos',str(int(roughness_record_id)))
  ok=bool(k.CalculateRetVal())
  values=dump(k,result_fields+['Qu[0].Rz','Qu[0].OberflPos','shafts[0].loads.string','shafts[0].supports.string','shafts.size()'])
  stem=Path(case['file']).stem+'-run';k.SaveFile(str(HERE/(stem+'.W10')))
  report(k,stem,'W010')
  checks={'roughness_exact':False,'section_name':values.get('Qu[0].Name')==case['section']}
  try:checks['roughness_exact']=abs(float(values['Qu[0].Rz'])-6.3)<1e-12
  except (ValueError,TypeError,KeyError):pass
  messages=k.Message();k.LoadFile(str(HERE/(stem+'.W10')));reload_ok=bool(k.CalculateRetVal())
  after=dump(k,list(values));diff={f:[v,after[f]] for f,v in values.items() if v!=after[f]}
  (HERE/(stem+'.json')).write_text(json.dumps({'case':case,'version':k.GetKsoftVersion(),'calculated':ok,'reload_ok':reload_ok,'reload_differences':diff,'native_sha256':hashlib.sha256((HERE/(stem+'.W10')).read_bytes()).hexdigest(),'checks':checks,'messages':messages,'values':values},ensure_ascii=False,indent=2),encoding='utf8')
  print(stem,ok,reload_ok,checks,'drift',len(diff),flush=True)
def run_r2(k,fr_N):
 # Call only on module W050; use measured R1b reaction magnitude as argument.
 k.LoadFile(str(HERE/'R2-6206-RZ.W50'))
 forces=list(fr_N) if isinstance(fr_N,(list,tuple)) else [fr_N,fr_N]
 for i in range(2):k.SetVar(f'Lag[{i}].Fr',format(forces[i],'.17g'))
 ok=bool(k.CalculateRetVal());fields=['Allg.Drehzahl','Allg.AusfallW','Allg.ErwLebensd']
 # Additional output fields are taken directly from official W050 report expressions.
 text=(INSTALL/'rpt/W050Le0.RPT').read_bytes()
 text=text.decode('utf16') if text[:2] in [b'\xff\xfe',b'\xfe\xff'] else text.decode('utf8',errors='replace')
 for expr in re.findall(r'\{([^{}]+)\}',text):
  if expr.startswith('Lag[#lagNr].') and re.fullmatch(r'[\w.\[\]#]+',expr):
   for i in range(2):fields.append(expr.replace('#lagNr',str(i)))
 values=dump(k,sorted(set(fields)));k.SaveFile(str(HERE/'R2-6206-RZ-run.W50'));report(k,'R2-6206-RZ-run','W050')
 messages=k.Message();k.LoadFile(str(HERE/'R2-6206-RZ-run.W50'));reload_ok=bool(k.CalculateRetVal());after=dump(k,list(values))
 (HERE/'R2-6206-RZ-run.json').write_text(json.dumps({'version':k.GetKsoftVersion(),'calculated':ok,'reload_ok':reload_ok,'reload_differences':{f:[v,after[f]] for f,v in values.items() if after[f]!=v},'messages':messages,'reaction_N':forces,'values':values,'formula_check_h':[(20300/f)**3*1e6/(60*900) for f in forces]},ensure_ascii=False,indent=2),encoding='utf8')
def run_r3(k,densities=(2,4,8,16)):
 # Knotendichte is an exact native setting; larger value means denser subdivision, verify resultant node count.
 results=[]
 for density in densities:
  k.LoadFile(str(BASE));k.SetVar('WelG.Knotendichte',str(density))
  for label in ['Cylindrical gear','Coupling / Motor']:k.CallFuncNParam(['SetElementData',label,'lengthOfLoad','1'])
  ok=bool(k.CalculateRetVal());values=dump(k,['WelG.Knotendichte','WelG.AnzahlKn','WelG.AnzahlDr','shaftAdditionalData.maxBend','shaftAdditionalData.maxBendPos','shafts[0].supportsDoc.paragraph1[0][0]','shafts[0].supportsDoc.paragraph1[0][1]','shafts[0].supportsDoc.paragraph1[1][0]','shafts[0].supportsDoc.paragraph1[1][1]','shafts.size()'])
  stem=f'R3-density-{density}';k.SaveFile(str(HERE/(stem+'.W10')));report(k,stem,'W010')
  results.append({'density':density,'calculated':ok,'messages':k.Message(),'values':values})
 (HERE/'R3-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':
 raise SystemExit('No COM dispatch here. Parent calls run_r1(k,actual_saved_roughness_ID), run_r2(k,measured_Fr_N), run_r3(k) with its exclusive COM instance.')
