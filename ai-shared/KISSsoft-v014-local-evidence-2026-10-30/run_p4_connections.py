"""Prepared without COM execution. Run only from the COM-owning process/session.

python run_p4_connections.py --prepare
python run_p4_connections.py --run P4-connections-config.json
Results distinguish calculation/reload success from numeric agreement.
"""
from pathlib import Path
import argparse, json, math, hashlib

ROOT = Path(__file__).resolve().parent
INSTALL = Path(r'D:/Program Files/KISSsoft AG/KISSsoft 2026')


def dump(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare():
    cases = []
    key = {'m02Aa.Methode': 0, 'm02Aa.iANZ': 1, 'm02Aa.phiFak': 1,
           'm02Aa.Mnenn': 25, 'm02Aa.StossFak': 1.25,
           'm02Aw.dWa': 25, 'm02Aw.di': 0,
           'm02Ak.bKeil': 8, 'm02Ak.hKeil': 7,
           'm02Ak.b': 8, 'm02Ak.h': 7,
           'm02Aw.lW': 24, 'm02An.lN': 24, 'm02Aw.t1MaxW': 4,
           'm02Aa.TRmin': 0}
    for c, rp in [('w', 800), ('n', 355), ('k', 350)]:
        key.update({f'm02A{c}.mat.DBID': 19999, f'm02A{c}.mat.Rp': rp,
                    f'm02A{c}.mat.typ': 2})
    cases.append({'id': 'P4-key-method-C', 'module': 'M02A',
                  'source': str(INSTALL/'example/08 Keys (DIN 6892 Example 1).M2A'),
                  'template': 'M02ALe0.RPT', 'ext': '.M2A', 'set': key,
                  'open': ['Maximum torque/peak-count unspecified: source Mmax/NL retained and logged; judge equivalent-load branch separately.',
                           'Key form A database ID not mapped; ltr=24 entered directly. Verify effective supporting height=3 mm after calculation.',
                           'Rm and component material classification inherited: method C Rp-driven equivalent branch requires verification.',
                           'D.3 Mt=52526 Nm has no complete geometry/material input; no fabricated native case.'],
                  'get': ['m02Aa.Methode','m02Aa.Meq','m02Aa.Mmax','m02Aa.NL','m02Aw.htW',
                          'm02Aw.peq','m02Aw.pzul','m02Aw.Resulteq','m02Aw.ResultW',
                          'm02An.peq','m02An.pzul','m02An.Resulteq','m02An.ResultN',
                          'm02Ak.peq','m02Ak.pzul','m02Ak.Resulteq','m02Ak.ResultP']})
    # Pressure-controlled cases are translated into diametral interference by
    # elastic thick-cylinder compliance, independently of commercial results.
    for label, di, da, ea, rei, rea, sp, p, u in [
        ('A1',0,100,215000,200,300,1.1,90,None),
        ('A2',0,100,215000,200,300,1.1,None,75),
        ('A3',10,125,70000,300,150,1.2,50,None),
        ('A4',10,125,70000,300,150,1.2,None,65)]:
        df, ei, nu, embedding = 50, 215000, 0.3, 0.4*(6+6)
        compliance = (((da/df)**2+1)/((da/df)**2-1)+nu)/ea + (((di/df)**2+1)/(1-(di/df)**2)-nu)/ei
        actual_u = u if u is not None else p*df*compliance*1000+embedding
        x = {'m01allg.df':df,'m01w.di':di,'m01n.da':da,'m01allg.l':40,
             'm01allg.eigenTol':True,'m01allg.VarAussenD':False,
             'm01w.tol.min':actual_u,'m01w.tol.max':actual_u,
             'm01n.tol.min':0,'m01n.tol.max':0,
             'm01my.axial':0.12,'m01my.umfang':0.12,'m01sollSi.Ru':1.5,
             'm01sollSi.ReW':sp,'m01sollSi.ReN':sp,
             'm01allg.n':0,'m01allg.FA':0,'m01allg.Fr':0,'m01allg.Mb':0,
             'm01M.nenn':0,'m01allg.cb':1,
             'm01w.tempB':20,'m01n.tempB':20}
        for c,e,rp in [('w',ei,rei),('n',ea,rea)]:
            x.update({f'm01{c}.mat.DBID':19999,f'm01{c}.mat.E':e,
                      f'm01{c}.mat.ny':nu,f'm01{c}.mat.Rp':rp,
                      f'm01{c}.oberfl.rz':6, f'm01{c}.werkstofffestigkeit':1})
        cases.append({'id':f'P4-fit-{label}','module':'M010',
                      'source':str(INSTALL/'example/01 Cylindrical Interference Fit.M10'),
                      'template':'M010Le0.RPT','ext':'.M10','set':x,
                      'reference':{'p_input_MPa':p,'U_input_um':u,'translated_U_um':actual_u,
                                   'expected_elastic_p_MPa':(actual_u-embedding)/(df*compliance*1000),
                                   'embedding_um':embedding,'inner_E_MPa':ei},
                      'open':['Inner E=215000 and both nu=.3 carried from common steel contract; verify appendix A original before equivalence claim.',
                              'gF field not exposed in source: compare reported m01allg.s with 4.8um; reject numeric equivalence if different.',
                              'Zero external load isolates pressure/stress; sliding safety is undefined/infinite. Torque capacity may be derived from native pressure.',
                              'Rm, hypothesis and elastic-plastic flag inherited and recorded; compare yield branch only until contract is complete.'],
                      'get':['m01allg.s','m01allg.hypoIndex','m01allg.elastplastFlag',
                             'm01allg.uebermass[0]','m01r.p[0]','m01r.abmass[0]',
                             'm01w.SiRe[0]','m01n.SiRe[0]',
                             'm01w.sigmaVa[0]','m01n.sigmaVi[0]','m01M.grenz[0]']})
    dest=ROOT/'P4-connections-config.json'
    dump(dest,{'status':'PREPARED_NOT_COM_EXECUTED','cases':cases})
    print(dest)


def run(config):
    import win32com.client
    k = win32com.client.Dispatch('KISSsoftCOM2026.KISSsoft')
    for c in json.loads(Path(config).read_text(encoding='utf-8'))['cases']:
        folder=ROOT/c['id'];folder.mkdir(exist_ok=True)
        record={'case':c,'scope':'mapped user inputs on vendor seed; inspect retained inputs and open items', 'set_log':[]}
        try:
            k.GetModule(c['module'],False);k.SetSilentMode(True);k.SetLanguage(1)
            record['version']=k.GetKsoftVersion()
            record['source_sha256']=hashlib.sha256(Path(c['source']).read_bytes()).hexdigest()
            record['license']=bool(k.CheckLicense(c['module']))
            k.LoadFile(c['source'])
            for name,v in c['set'].items():
                before=k.GetVar(name);s=str(v).lower() if isinstance(v,bool) else str(v)
                ret=k.SetVar(name,s)
                if ret is False: raise RuntimeError(f'SetVar failed: {name}')
                record['set_log'].append({'var':name,'before':before,'set':s,'readback':k.GetVar(name)})
            for function in c.get('call_funcs', []):
                record.setdefault('call_funcs', []).append({'name':function,'return':k.CallFunc(function)})
            record['calculate_ok']=bool(k.CalculateRetVal());record['messages']=k.Message()
            fields=list(dict.fromkeys(list(c['set'])+c['get']))
            values={};errors={}
            for n in fields:
                try: values[n]=k.GetVar(n)
                except Exception as ex: errors[n]=str(ex)
            record['values']=values;record['get_errors']=errors
            native=folder/(c['id']+c['ext']);k.SaveFile(str(native))
            record['sha256']=hashlib.sha256(native.read_bytes()).hexdigest()
            for fmt,ext in [(0,'.rtf'),(2,'.html')]:
                k.ReportWithParameters(c['template'],str(folder/(c['id']+ext)),0,fmt)
            k.LoadFile(str(native));record['reload_ok']=bool(k.CalculateRetVal())
            record['reload_messages']=k.Message();record['reload_values']={n:k.GetVar(n) for n in values}
            record['reload_differences']={n:[v,record['reload_values'][n]] for n,v in values.items() if v!=record['reload_values'][n]}
        except Exception as ex: record['error']=str(ex)
        finally:
            dump(folder/'result.json',record)
            k.ReleaseModule()
        print(c['id'],record.get('calculate_ok'),record.get('error'),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--run')
    args=ap.parse_args()
    if args.prepare:prepare()
    elif args.run:run(args.run)
    else:ap.print_help()
