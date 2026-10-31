from pathlib import Path
import sys,json,re,math
import win32com.client
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_z012 import ROOT,INSTALL,decode,dump,read
sys.stdout.reconfigure(encoding='utf8')
ids=['K01-spur','K02-helical','K03-premachining','K04-EV-stage1','K05-EV-stage2']
for cid in ids:
    folder=ROOT/('P3-'+cid);k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False);k.SetSilentMode(True);k.SetLanguage(1)
    try:
        k.LoadFile(str(folder/('P3-'+cid+'.Z12')));ok=bool(k.CalculateRetVal());fs=set()
        native=decode(folder/('P3-'+cid+'.Z12'))
        for l in native.splitlines():
            f=l.split('=')[0]
            if any(q in f for q in ['ZS.Oil.','RechSt.Scoring','RechSt.Micro','RechSt.Fressen','RechSt.ThetaM','ZS.SSi_fix','ZR[0].Ra','ZR[1].Ra','ZR[0].Ca','ZR[1].Ca','ZR[0].BM','ZR[1].BM']):fs.add(f)
        for n in ['Z010Scoringe.rpt','Z010Micropittinge.rpt','Z010IntermediateMicropittinge.rpt']:
            t=decode(INSTALL/'rpt'/n).replace('ZP[#mesh]','ZP[0]').replace('ZPP[#ZPP1INDEX]','ZPP[0]').replace('ZPP[#ZPP2INDEX]','ZPP[1]')
            fs.update(re.findall(r'(?:ZR\[[01]\]|ZPP\[[01]\]|ZP\[0\]|ZS|RechSt)\.[A-Za-z0-9_.]+',t))
        pt_fields=['gY','GamY','ronY','XY','pHYB','phidynYB','vgY','Theta_flY','TheBY','UY','WY','alpha','SGFY','hY','lamGFY','Slam']
        for i in range(7):
            fs.update(f'ZP[0].MP_ISO.analysisPoints[{i}].{f}' for f in pt_fields)
            for j in (0,1):fs.update(f'ZPP[{j}].MP_ISO.analysisPoints[{i}].{f}' for f in ['vrY','rtY','dY'])
        vals={};errors={}
        for f in sorted(fs):
            try:
                v=read(k,f)
                if v=='':errors[f]='empty/unexposed'
                else:vals[f]=v
            except Exception as e:errors[f]=str(e)
        k.ReportWithParameters('Z010IntermediateMicropittinge.rpt',str(folder/'micropitting-seven-points.rtf'),0,0)
        k.ReportWithParameters('Z010IntermediateMicropittinge.rpt',str(folder/'micropitting-seven-points.html'),0,2)
        valid=vals.get('ZS.Oil.FZGtestMP',0)>0 and vals.get('ZS.Oil.MicroPittingTest',0)>0
        r={'calculate_ok':ok,'messages':k.Message(),'micropitting_inputs_present':valid,'values':vals,'errors':errors,'seven_points_valid':valid and all(vals.get(f'ZP[0].MP_ISO.analysisPoints[{i}].hY',0)>0 for i in range(7))}
        dump(folder/'p3-detail.json',r)
        print(cid,'MPinputs',valid,'sevenpoints',r['seven_points_valid'],{f:v for f,v in vals.items() if f in ['ZP[0].FIT.SSint','ZP[0].FBT.SB','ZP[0].MP_ISO.SlamB']},flush=True)
    finally:k.ReleaseModule()
