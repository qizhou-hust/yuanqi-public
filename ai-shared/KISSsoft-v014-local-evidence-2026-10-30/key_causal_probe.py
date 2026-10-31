from pathlib import Path
import json,sys
import win32com.client
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parent
c=json.loads((root/'P4-connections-config.json').read_text(encoding='utf8'))['cases'][0]
k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('M02A',False);k.SetSilentMode(True)
rows=[]
try:
    k.LoadFile(c['source']);print('baseline',k.CalculateRetVal(),flush=True)
    for f,v in c['set'].items():
        k.SetVar(f,str(v));ok=bool(k.CalculateRetVal());rows.append({'field':f,'requested':v,'ok':ok,'messages':k.Message()})
        print(f,ok,flush=True)
        if not ok:
            k.LoadFile(c['source']);k.SetVar(f,str(v));single=bool(k.CalculateRetVal());rows[-1]['single_edit_ok']=single
            print('single edit',single,flush=True);break
finally:k.ReleaseModule()
(root/'key-causal-probe.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
