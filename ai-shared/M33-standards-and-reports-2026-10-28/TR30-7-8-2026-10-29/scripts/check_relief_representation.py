"""Bound the explicitly disclosed auxiliary relief-length representation.

This is not an acceptance waiver. The source tables do not supply relief length.
The delivered Z12 files are never overwritten by this sensitivity run.
"""
from pathlib import Path
import json,math
import win32com.client
from build_cases import read,write_json
from finalize_reports import output_value
ROOT=Path(__file__).resolve().parents[1]
k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False);k.SetSilentMode(True)
try:
 for n in (7,8):
  folder=ROOT/f'TR30-example-{n}'
  run=json.loads((folder/'run.json').read_text(encoding='utf8'));v=run['reload_values']
  rows=json.loads((folder/'comparison.json').read_text(encoding='utf8'))
  k.LoadFile(str(folder/f'TR30-example-{n}.Z12'))
  for i in (0,1):k.SetVar(f'ZR[{i}].Corr.rechts[0].factor1','1')
  ok=bool(k.CalculateRetVal());assert ok
  alt={key:read(k,key) for key in v};comparisons=[];counts={}
  for row in rows:
   gear=int(row['quantity'][-1])-1 if row['quantity'].endswith(('_1','_2')) else 0
   a,_=output_value(row['source_quantity'],gear,n,v);b,_=output_value(row['source_quantity'],gear,n,alt)
   same=(math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12) if isinstance(a,(float,int)) and isinstance(b,(float,int)) else None)
   comparisons.append(dict(quantity=row['quantity'],LCa_half_mn=a,LCa_one_mn=b,unchanged=same))
  for row in comparisons:counts[str(row['unchanged'])]=counts.get(str(row['unchanged']),0)+1
  report=dict(case=n,accepted=False,calculate_ok=ok,messages=k.Message(),counts=counts,
      input_missing_from_TR30='Relief length and shape',baseline=dict(shape='linear',LCa_over_mn=.5,Ca_um=13),
      sensitivity=dict(shape='linear',LCa_over_mn=1,Ca_um=13),rows=comparisons,
      conclusion='Numerical invariance for mapped rating outputs is only a sensitivity result, not proof of a source-defined relief geometry.')
  write_json(folder/'relief-length-sensitivity.json',report);print(n,counts,flush=True)
finally:k.ReleaseModule()
