"""Build TR30 examples 7/8 in KISSsoft. No target output is used as input."""
from pathlib import Path
import json, math, re, sys, csv
from datetime import datetime, timezone
import win32com.client

ROOT = Path(__file__).resolve().parents[1]
INSTALL = Path(r'D:\Program Files\KISSsoft AG\KISSsoft 2026')
FIELDS=json.loads(Path(__file__).with_name('fields.json').read_text(encoding='utf8'))

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')

def read(k, name):
    raw=k.GetVar(name)
    try:return float(raw)
    except (ValueError,TypeError):return raw

CASES={
 7:dict(z=[86,429],mn=1.6933333,beta=18.31,a=460.375,x=[.3615,.2863],da=[157.99,769.52],
        b=[165.1,165.1],gap=50.8,W=[60.068,289.367],span=[12,56],hf=1.25,rho=.38,
        pr=0,q=0,quality=5,quality_values=[(6.,6.,8.),(6.5,6.,8.5)],HB=[342,300],RaH=1.,RzH=6.,RaF=3.,RzF=18.,
        torque=528,speed=5400,life=30000,nu40=25,l=355.6,s=0,arrangement=0,modification=0),
 8:dict(z=[15,63],mn=4.5,beta=11.,a=182.880,x=[.5413,.4393],da=[82.19,301.55],
        b=[78.74,76.20],gap=0,W=[35.706,118.358],span=[3,9],hf=1.516,rho=.4,
        pr=.267,q=.220,quality=6,quality_values=[(9.5,11.,11.),(10.,11.,11.)],HRC=[58,58],RaH=.38,RzH=2.3,RaF=3.,RzF=18.,
        torque=1494,speed=1430,life=10000,nu40=220,l=331.724,s=67.56,arrangement=1,modification=6),
}

# KISSsoft's reference-profile editor stores the TR30 protuberance as a
# profile-height coefficient and derives Tool.pr from it.  The mapping was
# measured through the KISSsoft COM calculator (hprP=.5 -> pr=.16180713186920095 and
# hprP=1 -> pr=.55854283846324737), then inverted for the table's pr=.267.
EX8_HPRP_FOR_PR = .6325729779074764

def report_fields():
    """Names come from installed English report templates, not guessed COM names."""
    names=set()
    for name in ('Z010Geometrye.rpt','Z010ToolDatae.rpt','Z010ISOGeneralFactorse.rpt',
                 'Z010ISOBendinge.rpt','Z010ISOPittinge.rpt','Z010Materiale.rpt',
                 'Z010MainDatae.rpt'):
        p=INSTALL/'rpt'/name
        if not p.exists():continue
        b=p.read_bytes();t=b.decode('utf-16' if b[:2]==b'\xff\xfe' else 'utf8',errors='replace')
        names.update(re.findall(r'\{((?:(?:ZR|ZPP)\[[01]\]|ZP\[0\]|ZS|Zst)\.[A-Za-z0-9_.]+)\}',t))
    return sorted(names)

def build(number):
    c=CASES[number]; folder=ROOT/f'TR30-example-{number}';folder.mkdir(exist_ok=True)
    k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False)
    k.SetSilentMode(True);k.SetLanguage(1)
    edits=[]
    def setv(name,value,reason='TR30 original input table'):
        value=str(value).lower() if isinstance(value,bool) else str(value)
        before=k.GetVar(name);k.SetVar(name,value)
        edits.append(dict(name=name,before=before,requested=value,after=k.GetVar(name),reason=reason))
    def set_quality(i, fp, ff, fhb):
        """Set only the three ISO 1328 inputs supplied by TR30.

        QualityValue/QualityCheck are parallel arrays in the Z12 COM API;
        setting the individual pseudo-index variables is silently ignored.
        """
        pre=f'ZR[{i}].'
        vals=[float(x) if x.strip() else 0.0 for x in k.GetVar(pre+'QualityValue').split(',')]
        checks=[x.strip().lower() == 'true' for x in k.GetVar(pre+'QualityCheck').split(',')]
        for idx,val in ((14,fp),(21,ff),(24,fhb),(45,fp*math.cos(at))):
            vals[idx]=val; checks[idx]=True
        setv(pre+'QualityValue',','.join(str(x) for x in vals),'TR30 quality table: fpT, ffalpha and fHbeta')
        setv(pre+'QualityCheck',','.join('true' if x else 'false' for x in checks),'TR30 quality table: fpT, ffalpha and fHbeta')
    try:
        k.LoadFile(str(INSTALL/'example'/'01 Spur (ISO 6336).Z12'))
        for name,value in {
          'calculation.description':f'ISO TR 6336-30 2022 Example {number} - UNACCEPTED',
          'calculation.comment':'Original printed inputs. No tuning to match reference outputs.',
          'RechSt.RechenMethID':10029,'ZS.Geo.mn':c['mn'],'ZS.Geo.beta':math.radians(c['beta']),
          'ZS.Geo.alfn':math.radians(20),'ZP[0].a':c['a'],'ZS.KA':1,'ZS.Kgam':1,'ZS.H':c['life'],
          'ZS.Pnominal':c['torque']*c['speed']*2*math.pi/60000,'ZR[0].nnominal':c['speed'],'ZR[0].Tnominal':c['torque'],
          'ZS.PfeilZahn':int(number==7),'ZS.OptCond':0 if number==7 else 2,
          'ZS.KleinAnz':int(number==7),
          'ZS.ArtProfKorr':0,'ZP[0].KHdat.FlankenLin':c['modification'],
          'ZP[0].Flanke.fZCaVariant':1,
          'ZP[0].KHdat.Belastung':c['arrangement'],'ZP[0].KHdat.LageDesT':1,
          'ZP[0].KHdat.l':c['l'],'ZP[0].KHdat.S':c['s'],'ZP[0].KHdat.dsh':63.5,
          'Zst.lsdFlag':True,
          'Zst.KVFlag':False,'Zst.KHaFlag':False,'Zst.KHbVariant':0,
          'Zst.da_fix':True,'RechSt.TolISO1328v1995':False,
          'Zst.fmaFlag':False,'Zst.fshFlag':False,'ZS.SSi_fix.Fuss':1,'ZS.SSi_fix.Flanke':1,
          'ZP[0].AXTolID':10010,'ZP[0].Aa.E':0,'ZP[0].Aa.i':0,
          'ZS.Oil.SchmierTypID':19999,'ZS.Oil.SchmierTyp':f'TR30 example {number}: nu40 input; other oil properties are ancillary defaults',
          'ZS.Oil.nu40':c['nu40'],
        }.items():setv(name,value)
        al=math.radians(20);be=math.radians(c['beta']);at=math.atan(math.tan(al)/math.cos(be))
        for i in (0,1):
            pre=f'ZR[{i}].'
            data={'z':c['z'][i],'x.nul':c['x'][i],'b':c['b'][i]+c['gap'],'PfeilNutB':c['gap'],
                  'PfeilNutBFlag':False,'Schrage':1-i,'Vqual':c['quality'],'Qpre':c['quality'],
                  'ZDTolID':10010,'As.E':0,'As.i':0,
                  'KM_SP.k':c['span'][i],'KM.k':c['span'][i],'Ada.E':0,'Ada.i':0,
                  'da.nul':c['da'][i],'kFlag':False,'kFaktorFlag':False,
                  'Faseb':0,'Fased':0,'KopfKant':0,'sR_Automatic':False,'di':0,'dRing':0,'bs':c['b'][i]+c['gap'],'KugelGestrahlt':False,
                  'Ca':13,'Cf':0,'RZH':c['RzH'],'RZF':c['RzF'],'RAH':c['RaH'],'RAF':c['RaF'],'RZFlag':1,
                  'Corr.rechts[0].type':1,'Corr.rechts[0].flank':0,'Corr.rechts[0].active':True,
                  'Corr.rechts[0].activeForVariant':True,'Corr.rechts[0].variant':-1,
                  'Corr.rechts[0].C':13,'Corr.rechts[0].factor1':.5,
                  'NLFlag':0,'NLVorgabe':0,'Tool.type':2,'Tool.RefProfile.DBID':10400,
                  'Tool.RefProfile.hfP':c['hf'],'Tool.RefProfile.haP':1,'Tool.RefProfile.rhofP':c['rho'],
                  'Tool.RefProfile.hprP':EX8_HPRP_FOR_PR if number==8 else 0,
                  'Tool.RefProfile.alf_prP':math.radians(10) if number==8 else 0,
                  'Tool.finishing':False if number==8 else True,'Tool.q':c['q'],'Tool.qTol':0,
                  'mat.DBID':19999,'mat.bez':f'TR30 example {number} '+('V alloy steel ML' if number==7 else 'Eh MQ'),
                  'mat.comment':'Original TR30 table properties; material limits from ISO 6336-5 Table 1',
                  'mat.E':206000,'mat.ny':.3,'mat.rho':7830,'mat.Rp':1000 if number==7 else 689.5,
                  'mat.isoclass':1 if number==7 else 2,'mat.typ':2 if number==7 else 3,
                  'mat.behandlung':2 if number==7 else 4,
                  'mat.haerte':c.get('HB',c.get('HRC'))[i],'mat.haerteDim':0 if number==7 else 1,
                  'mat.haerteCore':c['HB'][i] if number==7 else 30,'mat.haerteCoreDim':0 if number==7 else 1,
                  'mat.limh':1500 if number==8 else 600,'mat.limf':500 if number==8 else 240}
            for name,value in data.items():setv(pre+name,value,'TR30 input; angle, width, power and tool-profile conversions documented in script')
            for e in edits:
                if e['name']==pre+'Corr.rechts[0].factor1':
                    e['reason']='Ancillary native representation: TR30 gives Ca but no relief length. LCa=0.5*mn; sensitivity at 1*mn is separately checked. Not a source-table input.'
            set_quality(i,*c['quality_values'][i])
        ok=k.CalculateRetVal();initial_attempts=[dict(ok=bool(ok),messages=k.Message())]
        print('initial',number,ok,initial_attempts[-1]['messages'],flush=True)
        if not ok:
            k.SaveFile(str(ROOT/'research'/f'failed-initial-{number}.Z12'))
            ok=k.CalculateRetVal();print('initial repeat',number,ok,k.Message(),flush=True)
            initial_attempts.append(dict(ok=bool(ok),messages=k.Message()))
            if not ok:raise RuntimeError('Initial calculation failed')
        for i in (0,1):
            # TR30's measured span is an input. KISSsoft accepts tooth-thickness
            # allowance instead: Wk = Wk_nominal + As*cos(alpha_n). x2 is derived
            # by KISSsoft from a and x1; its table value is printed in parentheses.
            allowance=(c['W'][i]-read(k,f'ZR[{i}].KM.Wk.nul'))/math.cos(al)
            for side in ('E','i'):
                setv(f'ZR[{i}].As.{side}',allowance,'Exact mapping of TR30 measured span, not a fit to output stress')
        if number==7:
            for i in (0,1):
                hv=read(k,f'ZR[{i}].HardnessHV')
                setv(f'ZR[{i}].mat.limh',1.313*hv+188,'ISO 6336-5:2016 Table 1 V alloy ML, KISSsoft converted HV')
                setv(f'ZR[{i}].mat.limf',.423*hv+104,'ISO 6336-5:2016 Table 1 V alloy ML, KISSsoft converted HV')
        ok=k.CalculateRetVal();msg=k.Message()
        if not ok:raise RuntimeError('Final calculation failed')
        more=['HardnessHB','HardnessHV','HardnessHRC','CoreHV','RZH','RZF','RAH','RAF','mat.haerte','mat.haerteDim',
              'mat.DBID','mat.bez','mat.typ','mat.behandlung','Tool.pr','Tool.q','Tool.RefProfile.hprP',
              'x.E','x.i','x_PM.i','KM.Wk.nul','KM.Wk.E','KM.Wk.i','KM.k','PfeilNutB','Fuss.YNT','Flanke.ZNT',
              'Tol.fp','Tol.fpe','Tol.ff','Tol.fHb','QualityValue','QualityCheck',
              'diCalc','Tool.RefProfile.alf_prP','Tool.RefProfile.haP','Tool.RefProfile.hfP',
              'Tool.RefProfile.rhofP','BP_f.hfP','As.E','As.i','df.E','df.i','dNf0.E','dNf.E']
        fields=list(dict.fromkeys(FIELDS+report_fields()+[f'ZR[{i}].{v}' for i in (0,1) for v in more]+[e['name'] for e in edits]))
        values={};errors={}
        for f in fields:
            try:
                v=read(k,f)
                if v=='':errors[f]='Not exposed by this module/configuration'
                else:values[f]=v
            except Exception as exc:errors[f]=str(exc)
        native=folder/f'TR30-example-{number}.Z12'
        k.SaveFile(str(native))
        k.ReleaseModule()
        k=win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft');k.GetModule('Z012',False)
        k.SetSilentMode(True);k.SetLanguage(1);k.LoadFile(str(native))
        reload_ok=bool(k.CalculateRetVal());reload_msg=k.Message()
        reloaded={f:read(k,f) for f in values}
        differences={f:dict(before=v,after=reloaded[f]) for f,v in values.items()
                     if not (math.isclose(v,reloaded[f],rel_tol=1e-10,abs_tol=1e-10)
                             if isinstance(v,float) and isinstance(reloaded[f],float) else v==reloaded[f])}
        k.ReportWithParameters('Z012Le0.RPT',str(folder/f'TR30-example-{number}.rtf'),0,0)
        write_json(folder/'run.json',dict(case=number,generated_utc=datetime.now(timezone.utc).isoformat(),
                                          runtime_version=k.GetKsoftVersion(),input=c,initial_calculation_attempts=initial_attempts,
                                          calculate_return=ok,messages=msg,edits=edits,values=values,errors=errors,
                                          reload_calculate_return=reload_ok,reload_messages=reload_msg,reload_values=reloaded,reload_differences=differences,
                                          diagnostics={'x_from_Wk':[(c['W'][i]-c['mn']*math.cos(al)*(math.pi*(c['span'][i]-.5)+c['z'][i]*(math.tan(at)-at)))/(2*c['mn']*math.sin(al)) for i in (0,1)],
                                                       'Wk_table':c['W'],'span_table':c['span'],'quality_values':c['quality_values'],
                                                       'tool_pr_target':c['pr']}))
        print('reload',number,reload_ok,'differences',differences,flush=True)
        print(json.dumps({'case':number,'ok':ok,'messages':msg,'errors':errors,'selected':{x:values.get(x) for x in ['ZR[1].HardnessHV','ZR[0].mat.bez','ZR[0].Tnominal','ZP[0].KHb','ZPP[0].Fuss.YF','ZPP[0].Fuss.YS','ZPP[0].Fuss.sigF0']}}),flush=True)
    finally:k.ReleaseModule()

if __name__=='__main__':
    for n in map(int,sys.argv[1:] or [7,8]):build(n)
