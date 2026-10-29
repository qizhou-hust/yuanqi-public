"""Native life-curve diagnostics, using only the required service-life input."""
from run_variants import run,ROOT,dump
import json
source=ROOT/'ex7-base-native'/'ex7-base-native.Z12'
base=json.loads((source.parent/'run.json').read_text(encoding='utf8'))['values']
rows=[]
for gear in (1,2):
    # Only the driving member's nnominal is an active input. The other
    # nnominal retains the inactive seed entry; obtain speed by tooth ratio.
    speed=abs(base['ZR[0].nnominal'])*(1 if gear==1 else base['ZR[0].z']/base['ZR[1].z'])
    for cycles in (100000,600000,10000000,1000000000,10000000000):
        name=f'ex7-life-g{gear}-N{cycles}'
        saved=ROOT/name/'run.json'
        if saved.exists() and gear==1:
            result=json.loads(saved.read_text(encoding='utf8'))
        else:
            result=run(name,7,source,{'ZS.H':cycles/(60*speed)},
                       f'DIAGNOSTIC ONLY: vary service life to obtain gear {gear} NL={cycles}; speed from driving n1 and z1/z2. Retain base geometry/material/options.')
        v=result['reload_values'];r=f'ZR[{gear-1}].'
        row={'gear':gear,'target_cycles':cycles,'hours':v['ZS.H'],'actual_cycles':v[r+'NL'],
             'ZNT':v[r+'Flanke.ZNT'],'YNT':v[r+'Fuss.YNT'],'variant':result['variant']}
        assert abs(row['actual_cycles']/cycles-1)<1e-10,row
        rows.append(row)
dump(ROOT/'life-curve.json',rows)
