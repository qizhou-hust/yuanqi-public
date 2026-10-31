"""Static P4 preparation only; no COM imports, no calculations."""
from pathlib import Path
import re, json, hashlib
HERE=Path(__file__).resolve().parent
INSTALL=Path(r'D:/Program Files/KISSsoft AG/KISSsoft 2026')
seed=INSTALL/'example/01 Shafts.W10'
t=seed.read_text(encoding='utf16')
def setv(k,v):
 global t
 pattern=r'(?m)^'+re.escape(k)+r'=[^¶]*¶'
 if not re.search(pattern,t):raise ValueError('Unknown seed variable '+k)
 t=re.sub(pattern,lambda m:k+'='+str(v)+'¶',t)
def block(k,v):setv(k,v)
# Preserve official UTF16 native format and UIDs; remove all old geometry not used.
outer=re.search(r'shafts\[0\].outer.string=([^¶]*)¶',t).group(1)
cyls=re.findall(r'10@Cylinder [1-4]@\{[^\n]*?\}',outer)
assert len(cyls)==4
new=[]
for row,L,D in zip(cyls,[20,80,20,50],[30,34,30,25]):
 prefix,rest=row.split('@{'); vals=rest[:-1].split(','); vals[:2]=[str(L),str(D)];new.append(prefix+'@{'+','.join(vals)+'}')
block('shafts[0].outer.string','\n'.join(new));block('shafts[0].inner.string','')
# No retained official-example strength result is enabled.
for n in sorted(set(re.findall(r'Qu\[(\d+)\].Aktiviert=',t)),key=int):setv('Qu['+n+'].Aktiviert',0)
# Plain rigid-support native block copied verbatim from official example 03.
other=(INSTALL/'example/03 Shafts.W10').read_text(encoding='utf16')
support=next(row for block in re.findall(r'shafts\[\d+\].supports.string=([^¶]*)¶',other) for row in block.splitlines() if row.startswith('5540@Support@{'))
assert support.startswith('5540@Support@{')
rows=[]
for label,pos,uid in [('P4 Support A',10,573749132),('P4 Support B',110,573749133)]:
 row=support.replace('5540@Support@{','5540@'+label+'@{',1)
 row=re.sub(r'(@\{)[^,]*,',lambda m:m.group(1)+str(pos)+',',row,count=1)
 row=row.replace(',573749132,',','+str(uid)+',');rows.append(row)
block('shafts[0].supports.string','\n'.join(rows))
# All verified scalar names originate in the installed official seed.
scalars={'shafts[0].startPosition':-10,'shafts[0].speed':900,'shafts[0].material.DBID':19999,
 'shafts[0].material.bez':'P4 custom DIN743 1000/800/500/400/300',
 'shafts[0].material.dindb':16,'shafts[0].material.dinsigb':1000,'shafts[0].material.dinsigs':800,
 'shafts[0].material.dinsigbw':500,'shafts[0].material.dinsigzdw':400,'shafts[0].material.dintautw':300,
 'shafts[0].material.Rm':1000,'shafts[0].material.Rp':800,
 'shafts[0].w060.matGroupCase1':'true','W060Allg.Din.BeanspFall':1,
 'W060Allg.Din.sSollErmuedung':1.2,'W060Allg.Din.sSollStreck':1.2,
 'shafts[0].StressR.Maxzug':2,'shafts[0].StressR.Maxbieg':2,'shafts[0].StressR.Maxdrm':2,'shafts[0].StressR.Maxquer':2,
 'calculation.description':'P4 candidate - STATIC PREP ONLY - loads/supports must be verified before calculation',
 'calculation.name':'P4-shaft-static-candidate.W10'}
for k,v in scalars.items():setv(k,v)
# Clear load/save scripts, as in official seed, explicitly retained empty.
for k in ['script.preCalc','script.postCalc','script.postLoad','script.preSave','script.preLoad']:setv(k,'')
(HERE/'P4-shaft-static-candidate.W10').write_text(t,encoding='utf16',newline='')
meta=[['Cylindrical gear','position',60],['Cylindrical gear','pitchDiameter',40],['Cylindrical gear','pressureAngle',20],
 ['Cylindrical gear','numberOfTeeth',20],['Cylindrical gear','helixAngle',0],['Cylindrical gear','powerOrTorque',25],
 ['Cylindrical gear','isDriven',1],['Coupling / Motor','position',150],['Coupling / Motor','powerOrTorque',25],
 ['Coupling / Motor','isDriven',0],['Coupling / Motor','axialForceFactor',0],['Coupling / Motor','radialForceFactor',0]]
(HERE/'meta-input-plan.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
manifest={'seed':str(seed),'seed_sha256':hashlib.sha256(seed.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((HERE/'P4-shaft-static-candidate.W10').read_bytes()).hexdigest(),'outer_cylinders':4,'shaft_start_global_mm':-10,'boundaries_global_mm':[-10,10,90,110,160],'diameters_mm':[30,34,30,25],'Qu_activated_count':len(re.findall(r'Qu\[\d+\].Aktiviert=1¶',t)),'plain_support_count':2,'load_plan_must_apply':True,'COM_executed':False,'calculated':False}
(HERE/'candidate-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print(json.dumps(manifest,indent=2))
