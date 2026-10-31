from pathlib import Path
import win32com.client,json,math,re
root=Path(__file__).resolve().parent
k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('W010',False);k.SetSilentMode(True);k.SetLanguage(1)
try:
    k.LoadFile(str(root/'P4-shaft-load-mapped.W10'))
    changes={'WelG.speed':900,'WelG.GewichtBeruecksichtigen':0,'WelG.ZahnradBeruecksichtigen':0}
    for f,v in changes.items():k.SetVar(f,str(v))
    power=25*900*math.pi/30/1000
    for label in ['Cylindrical gear','Coupling / Motor']:
        k.CallFuncNParam(['SetElementData',label,'powerOrTorque',str(power)])
    for label in ['P4 Support A','P4 Support B']:
        for axis in ['RXstate','RYstate','RZstate']:
            k.CallFuncNParam(['SetElementData',label,axis,'0'])
        k.CallFuncNParam(['SetElementData',label,'UYstate','1' if label.endswith('A') else '0'])
    ok=bool(k.CalculateRetVal());msg=k.Message()
    fs=['WelG.speed','shafts[0].speed','shafts[0].length','shafts[0].startPosition','shaftAdditionalData.maxBend','shafts[0].loads.string','shafts[0].supports.string','shafts[0].supportsDoc.paragraph1[0][0]','shafts[0].supportsDoc.paragraph1[0][1]','shafts[0].supportsDoc.paragraph1[1][0]','shafts[0].supportsDoc.paragraph1[1][1]']
    # GetVar exposes the serialized list including native calculated force rows.
    serialized=k.GetVar('shafts.size()')
    fields={f:k.GetVar(f) for f in fs}
    native=root/'P4-shaft-corrected-static.W10';k.SaveFile(str(native))
    k.ReportWithParameters('W010Le0.RPT',str(root/'P4-shaft-corrected-static.rtf'),0,0)
    k.LoadFile(str(native));reload_ok=bool(k.CalculateRetVal());after={f:k.GetVar(f) for f in fs}
    result={'calculate_ok':ok,'reload_ok':reload_ok,'version':k.GetKsoftVersion(),'messages':msg,'explicit_mapping':{'power_kW_from_T25_n900':power,'globals':changes},'values':fields,'reload_differences':{f:[v,after[f]] for f,v in fields.items() if after[f]!=v},'native_serialized_calculated_shaft':serialized,'status':'STATIC_CANDIDATE_ONLY; SUPPORT_DOF_AND_DIN743_SECTIONS_AND_ISO281_NOT_QUALIFIED'}
    (root/'corrected-static-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(ok,reload_ok,fields['shafts[0].speed']);print(re.findall(r'F=[^\r\n]+',serialized))
finally:k.ReleaseModule()
