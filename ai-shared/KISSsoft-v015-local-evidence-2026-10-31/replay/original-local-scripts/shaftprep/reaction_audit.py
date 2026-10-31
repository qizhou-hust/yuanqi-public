from pathlib import Path
import json,re,math
HERE=Path(__file__).resolve().parent
def forces(s):
 out={}
 for m in re.finditer(r'F=([-+0-9.eE,]+)',s):
  f=m.group(1).split(',')
  if len(f)!=3:continue
  before=s[max(0,m.start()-200):m.start()]
  labels=['P4 Support A','P4 Support B','Cylindrical gear','Coupling / Motor']
  match=sorted([(before.rfind(label),label) for label in labels],reverse=True)[0]
  if match[0]>=0:out[match[1]]={'raw_serialized_components':f,'F_N':[float(x) for x in f]}
 return out
rows=[]
for a in json.loads((HERE/'R3-results.json').read_text(encoding='utf8')):
 fs=forces(a['values']['shafts.size()'])
 residual=[sum(v['F_N'][i] for v in fs.values()) for i in range(3)]
 rows.append({'density_setting':a['density'],'maximum_deflection_mm_raw':a['values']['shaftAdditionalData.maxBend'],'forces':fs,
              'force_balance_residual_N':residual,'residual_norm_N':math.sqrt(sum(f*f for f in residual)),
              'precision':'External reaction vectors from native serialized results: approximately 10 significant digits; deflection is raw GetVar precision.',
              'interpretation':'Identical densities do not establish mesh convergence: linear cylindrical shaft uses analytical transfer matrices.'})
source=json.loads((HERE/'R1-L1-S1-run.json').read_text(encoding='utf8'))
fs=forces(source['fresh_values']['shafts.size()'])
for v in fs.values():v['magnitude_N']=math.sqrt(sum(f*f for f in v['F_N']))
out={'R1b_native_support_reactions':fs,'density_study':rows,
     'section_shear_warning':'Internal section shear is not identical to the displayed external reaction. It must not replace external reactions when auditing residuals.'}
(HERE/'reaction-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print({k:v['magnitude_N'] for k,v in fs.items()});print('density residuals',[(r['density_setting'],r['residual_norm_N']) for r in rows])
