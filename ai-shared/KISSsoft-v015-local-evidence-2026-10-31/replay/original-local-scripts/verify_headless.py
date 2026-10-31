from pathlib import Path
import json,hashlib,math
import win32com.client,fitz
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for case in ['P5-A-tip-coefficient-input','P5-B-auto']:
 p=ROOT/case;r=json.loads((p/'run.json').read_text(encoding='utf8'))
 k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False);k.SetSilentMode(True)
 try:
  k.LoadFile(str(p/(case+'.Z12')));ok=bool(k.CalculateRetVal())
  fields=['ZPP[0].Flanke.SH','ZPP[1].Flanke.SH','ZPP[0].Fuss.SFnorm','ZPP[1].Fuss.SFnorm','ZP[0].a','ZP[0].Eps.a','ZR[0].kXmn','ZR[1].kXmn','ZP[0].KHdat.l','ZP[0].KHdat.S','ZP[0].KHdat.dsh']
  actual={f:k.GetVar(f) for f in fields}
  assert ok and all(math.isclose(float(actual[f]),r['values'][f],rel_tol=1e-12,abs_tol=1e-12) for f in fields)
  assert all(float(actual[f])>=limit for f,limit in [(fields[0],1),(fields[1],1),(fields[2],1.4),(fields[3],1.4)])
  if case.startswith('P5-A'):
   assert float(actual['ZR[0].kXmn'])==0 and float(actual['ZR[1].kXmn'])==0
   assert [float(actual[f]) for f in fields[-3:]]==[88,8.8,44]
  r['fresh_headless_module_values']=actual;r['fresh_headless_module_ok']=ok;r['external_user_numeric_gate_pass']=True
  (p/'run.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
 finally:k.ReleaseModule()
for p in ROOT.glob('*/run.json'):
 r=json.loads(p.read_text(encoding='utf8'))
 assert r['calculate_return'] and r['reload_calculate_return'] and not r['reload_differences'],p
 assert sha(Path(r['source']))==r['source_sha256'] and r['source_unchanged'],p
 assert sha(p.parent/(r['id']+'.Z12'))==r['native_sha256'],p
 rows.append({'case':r['id'],'calculated_and_reloaded':True,'source_and_native_hashes':True})
for p in ROOT.glob('R[45]-*/result.json'):
 r=json.loads(p.read_text(encoding='utf8'));assert r['calculate_ok'] and r['reload_ok'] and not r['reload_differences'],p
 rows.append({'case':p.parent.name,'calculated_and_reloaded':True})
for p in (ROOT/'shaftprep').glob('R1-*-run.json'):
 r=json.loads(p.read_text(encoding='utf8'));v=r['fresh_values']
 assert r['calculated'] and r['reload_ok'] and r['fresh_module_ok'] and not r['reload_differences']
 assert math.isclose(float(v['Qu[0].Rz']),6.3,abs_tol=1e-12) and v['Qu[0].OberflPos']=='20000'
 assert float(v['Qu[0].Ampl.Mtres'])==0
 assert float(v['Qu[0].sStatisch'])>1.2
 if not r['case']['static_only']:assert 1.2<float(v['Qu[0].sErmuedung'])<1000
 t=p.with_suffix('.txt').read_text(encoding='utf8');assert 'Strength calculation according to DIN 743:2012' in t and '6.300' in t
 assert sha(p.with_suffix('.W10'))==r['native_sha256']
 rows.append({'case':p.stem,'fresh_module_and_real_roughness_record':True})
pdfs=[]
for p in ROOT.glob('*/*.pdf'):
 if p.parent.name=='shaftprep' and not p.with_suffix('.pprpt').exists():continue
 d=fitz.open(p);t='\n'.join(x.get_text() for x in d)
 assert len(d)>0 and len(t)>100 and '1IF (' not in t and '<EXECUTE=' not in t,p
 pdfs.append({'file':str(p.relative_to(ROOT)),'pages':len(d),'chars':len(t)})
out={'status':'PASS_LISTED_CHECKS_ONLY','scope':'P5 complete; other requested items have explicit open evidence gaps','all_future_calls_headless':True,'calculation_checks':rows,'pdf_checks':pdfs}
(ROOT/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print('Verified',len(rows),'calculation records,',len(pdfs),'readable PDFs; P5 A/B pass in fresh headless modules.')
