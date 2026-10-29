"""Export full vendor reports, audit inputs and compare unchanged gearbase v0.8.

The private v0.8 core provides the previously image-reviewed table transcription.
No KISSsoft result is fed back into the transparent model.
"""
from pathlib import Path
import argparse,csv,json,math,sys,hashlib
from collections import Counter
import fitz,win32com.client
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

ROOT=Path(__file__).resolve().parents[1]
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def csvout(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b,tol=1e-9):return isinstance(a,(int,float)) and abs(a-b)<=tol

def input_value(key,i,n,v):
    r=f'ZR[{i}].';p='ZP[0].';g=lambda s:v[s]
    direct={'z':r+'z','m_n':'ZS.Geo.mn','a_w':p+'a','W_k':r+'KM.Wk.E','k':r+'KM.k',
      'x':r+'x.nul','d_a':r+'da.nul','gap':r+'PfeilNutB','edge':r+'Faseb','tip_chamfer':r+'Fased',
      'rho_fP':r+'Tool.RefProfile.rhofP','pr':r+'Tool.pr','q':r+'Tool.q','C_a':r+'Ca','C_f':r+'Cf',
      'h_fP_pre':r+'Tool.RefProfile.hfP','Q':r+'Vqual','f_pT':r+'Tol.fp','f_falpha':r+'Tol.ff','f_Hbeta':r+'Tol.fHb',
      'Ra_H':r+'RAH','Rz_H':r+'RZH','Ra_F':r+'RAF','Rz_F':r+'RZF',
      'E':r+'mat.E','nu':r+'mat.ny','yield_stress':r+'mat.Rp','rho':r+'mat.rho',
      'K_A':'ZS.KA','K_gamma':'ZS.Kgam','bearing_span':p+'KHdat.l','bearing_offset':p+'KHdat.S',
      'shaft_diameter':p+'KHdat.dsh','S_Hmin':'ZS.SSi_fix.Flanke','S_Fmin':'ZS.SSi_fix.Fuss',
      'nu_40':'ZS.Oil.nu40','n_1':'ZR[0].nnominal','life_hours':'ZS.H'}
    if key in direct:return g(direct[key]),direct[key]
    if key in ('alpha_n','beta'):
        f='ZS.Geo.'+('alfn' if key=='alpha_n' else 'beta');return math.degrees(g(f)),f+' rad -> deg'
    if key=='b':return g(r+'b')-g(r+'PfeilNutB'),r+'b - PfeilNutB (total active width)'
    if key=='b_per_helix':return (g(r+'b')-g(r+'PfeilNutB'))/2,r+'(b - gap)/2'
    if key=='b_eff':return g(p+'bMin')*(2 if n==7 else 1),p+'bMin * number of helices'
    if key=='s_pr':return g(r+'Tool.pr')-g(r+'Tool.q'),r+'Tool.pr - Tool.q'
    if key=='h_fP':return g(r+'BP_f.hfP'),r+'BP_f.hfP (derived final rack)'
    if key=='tool_pr_angle':return math.degrees(g(r+'Tool.RefProfile.alf_prP')),r+'Tool.RefProfile.alf_prP rad -> deg'
    if key=='T_1':return g('ZR[0].Tnominal')/1000,'ZR[0].Tnominal Nm -> kNm'
    if key=='hand':return ('Double helical' if g('ZS.PfeilZahn')==1 else ('Left' if g(r+'Schrage')==1 else 'Right')),'ZS.PfeilZahn / '+r+'Schrage'
    if key=='case_hardness':return f"{g(r+'mat.haerte'):g} "+('HB' if g(r+'mat.haerteDim')==0 else 'HRC'),r+'mat.haerte, mat.haerteDim'
    if key=='core_hardness':return f"{g(r+'mat.haerteCore'):g} HRC",r+'mat.haerteCore / Dim=1'
    if key=='material':return {2.0:'V (alloy steel)',3.0:'Eh'}[g(r+'mat.typ')],r+'mat.typ and treatment (vendor report confirmed)'
    if key=='material_quality':return {1.0:'ML',2.0:'MQ'}[g(r+'mat.isoclass')],r+'mat.isoclass (ML=1 verified in material UI)'
    if key=='shot_peen':return 'No' if g(r+'KugelGestrahlt')=='false' else 'Yes',r+'KugelGestrahlt'
    if key=='limited_pitting':return 'Yes' if g('ZS.KleinAnz')==1 else 'No','ZS.KleinAnz'
    if key=='profile_compensated':return 'No' if g('ZS.ArtProfKorr')==0 else 'Yes','ZS.ArtProfKorr'
    if key=='f_ZCa_input':return 'manufacturers experience' if g(p+'Flanke.fZCaVariant')==1 else 'other',p+'Flanke.fZCaVariant'
    if key=='reverse_bending':return 'No' if g(r+'Fuss.Kwb')==1 else 'other',r+'Fuss.Kwb=1'
    if key=='favourable_contact':return 'Yes' if g(p+'KHdat.LageDesT')==1 else 'No',p+'KHdat.LageDesT'
    if key=='helix_modification':return {0.0:'None (No. 1)',6.0:'Helix + Crowning (No. 5)'}[g(p+'KHdat.FlankenLin')],p+'KHdat.FlankenLin'
    if key=='arrangement':return {0.0:'a',1.0:'b'}[g(p+'KHdat.Belastung')],p+'KHdat.Belastung'
    if key=='K_V_method':return 'Method B' if g('Zst.KVFlag')=='false' else 'external','Zst.KVFlag; full report Method B'
    if key=='K_Hbeta_method':return 'Method C' if g('Zst.KHbVariant')==0 else 'other','Zst.KHbVariant; full report Method C'
    if key in ('Z_NT_end','Y_NT_end'):return {0.0:.85,2.0:1.0}[g('ZS.OptCond')],'ZS.OptCond (full report life-factor endpoint)'
    if key=='blank_type':return 'Solid' if g(r+'diCalc')==0 and g(p+'KV.CR')==1 else 'other',r+'diCalc=0; KV.CR=1; Fuss.YB=1'
    if key=='f_sh_method':return 'As Formula (59)' if g('Zst.fshFlag')=='false' else 'external','Zst.fshFlag=false; method C built-in solid shaft formula'
    if key=='f_ma_method':return 'As Formula (66)' if g('Zst.fmaFlag')=='false' else 'external','Zst.fmaFlag=false; report fma includes B2'
    if key=='shaft_inside_diameter':return 0.0,'method-C dsh solid circular-shaft formula; no separate dshi field exposed'
    if key=='N_M':return 1,'Default one mesh; report NL = abs(n) * 60 * H; verified from report'
    if key in ('flank_finish','root_finish'):
        if n==7:return 'As cut','Tool.type=reference rack, q=0; no finishing stock'
        return ('Cut pre-finishing and ground finishing' if key=='flank_finish' else 'As cut pre-finishing'),'Tool.finishing=false, q=0.220; full report pre-machining and remaining undercut'
    raise KeyError(key)

def output_value(key,i,n,v):
    r=f'ZR[{i}].';m=f'ZPP[{i}].';p='ZP[0].'
    direct={'d':r+'d','d_a':r+'da.nul','d_b':r+'dB','x_E':r+'x.E','x_EV':r+'x_PM.i',
      'd_f':r+'df.E','d_Ff':r+'dNf0.E','d_Nf':m+'dNf.E','d_w':m+'dw','F_t':p+'Ft',
      'K_Falpha':p+'KFa','K_Fbeta':p+'KFb','K_Halpha':p+'KHa','K_Hbeta':p+'KHb','K_V':p+'KV.KV',
      'S_F':m+'Fuss.SFnorm','S_H':m+'Flanke.SH','Y_B':r+'Fuss.YB','Y_DT':p+'Fuss.YDT',
      'Y_F':m+'Fuss.YF','Y_NT':r+'Fuss.YNT','Y_N':r+'Fuss.YNT','Y_RrelT':r+'Fuss.YR','Y_S':m+'Fuss.YS',
      'Y_ST':'ZS.Yst','Y_X':r+'Fuss.YX','Y_beta':p+'Fuss.Ybet','Y_drelT':m+'Fuss.Ydrel',
      'Z_B':'ZPP[0].Flanke.ZBD','Z_D':'ZPP[1].Flanke.ZBD','Z_beta':p+'Flanke.Zbet','Z_E':p+'Flanke.ZE',
      'Z_eps':p+'Flanke.Zeps','Z_H':p+'Flanke.ZH','Z_L':m+'Flanke.ZL','Z_NT':r+'Flanke.ZNT','Z_N':r+'Flanke.ZNT',
      'Z_R':m+'Flanke.ZR','Z_V':m+'Flanke.ZV','Z_W':m+'Flanke.ZW','Z_X':r+'Flanke.ZX',
      'eps_alpha':p+'Eps.a','eps_beta':p+'Eps.b','eps_gamma':p+'Eps.G',
      'sigma_F0':m+'Fuss.sigF0','sigma_F':m+'Fuss.sigF','sigma_Flim':r+'mat.limf','sigma_FP':m+'Fuss.sigFP',
      'sigma_H':m+'Flanke.sigHBD','sigma_H0':p+'Flanke.sigH0','sigma_Hlim':r+'mat.limh','sigma_HP':m+'Flanke.sigHP',
      'c_gamma_alpha':p+'KV.cg','c_prime':p+'KV.cStr','m_red':p+'KV.mRed','N_res':p+'KV.n',
      'c_gamma_beta':p+'KV.cgbet','F_bx':p+'KHdat.Fbx','F_by':p+'KHdat.Fby',
      'y_alpha':p+'KV.ya','y_beta':p+'KHdat.yb','f_Hbeta5':p+'KHdat.fHb5','f_sh':p+'KHdat.fsh00',
      'f_ZCa':p+'Flanke.fZCa','f_e':p+'Fuss.feps'}
    if key in direct:return v.get(direct[key]),direct[key]
    if key=='v_w':return v['ZPP[0].dw']*math.pi*v['ZR[0].nnominal']/60000,'pi * dw1 * n1 / 60000'
    if key=='f_pb':return max(v[f'ZR[{j}].Tol.fpe'] for j in (0,1)),'max(Tol.fpe)'
    if key=='f_ma':return v[p+'KHdat.fma']/v[p+'KHdat.B2'],'KHdat.fma / B2 (undo report multiplication)'
    if key=='f_sh0':return None,'Not exposed; double-helical width convention remains unresolved'
    return None,'Unmapped quantity'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--gearbase',type=Path,default=ROOT.parent/'gearbase-v0.8-work'/'gearbase');args=ap.parse_args()
    sys.path.insert(0,str(args.gearbase))
    from gearmath.gear.tr30_full58 import compare_full,quantum_tolerance
    source=args.gearbase/'data'/'tr30'/'examples-5-8.json'
    cases=[c for c in json.loads(source.read_text(encoding='utf8'))['cases'] if c['example_number'] in (7,8)]
    word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
    results=[]
    try:
      for c in cases:
        n=c['example_number'];folder=ROOT/f'TR30-example-{n}';stem=folder/f'TR30-example-{n}'
        run=json.loads((folder/'run.json').read_text(encoding='utf8'));v=run['reload_values']
        doc=word.Documents.Open(str(stem.with_suffix('.rtf')),ReadOnly=True,AddToRecentFiles=False)
        try:doc.ExportAsFixedFormat(str(stem.with_suffix('.pdf')),17)
        finally:doc.Close(False)
        pdf=fitz.open(stem.with_suffix('.pdf'));text='\n'.join(p.get_text() for p in pdf)
        (folder/'report.txt').write_text(text,encoding='utf8')
        validation=dict(pages=len(pdf),contains_end='End of report' in text,
           contains_2019='ISO 6336:2019' in text,unexpanded='<EXECUTE=' in text or '1IF (' in text)
        assert validation['contains_end'] and validation['contains_2019'] and not validation['unexpanded']
        csvout(folder/'high-precision-values.csv',[{'variable':k,'value':format(x,'.17g') if isinstance(x,float) else x} for k,x in sorted(v.items())])
        inputs=[]
        for raw in c['raw_inputs']:
          for i,expected in enumerate(raw['values']):
            row=dict(quantity=raw['key'],gear=i+1 if len(raw['values'])==2 else '',unit=raw['unit'],table_value=expected,
                     printed_page=raw['citation']['printed_page'],table_location=raw['citation']['location'])
            if expected is None:row.update(status='not_applicable',actual='',mapping='TR30 dash')
            else:
              try:
                actual,mapping=input_value(raw['key'],i,n,v)
                same=close(actual,expected) if isinstance(expected,(float,int)) else actual==expected
                status='matched' if same else 'mismatch'
                if not same and (raw['reference_only'][i] or raw['key']=='h_fP') and isinstance(actual,(float,int)):
                    q=10**(-raw['decimals'][i]);status='derived_matches_printed' if abs(actual-expected)<=q/2+1e-12 else 'mismatch'
                row.update(status=status,actual=actual,mapping=mapping)
              except KeyError as exc:row.update(status='unverified',actual='',mapping=str(exc))
            inputs.append(row)
        csvout(folder/'input-audit.csv',inputs)
        gm=compare_full(n,rz_source='printed_rz' if n==8 else None)
        dump(folder/'gearmath-v0.8-diagnostic.json',gm)
        gmrows={r['quantity']:r for r in gm['rows']}
        from gearmath.gear.tr30_full58 import _OUTPUT_ALIASES
        rows=[]
        for raw in c['raw_outputs']:
          for i,ref in enumerate(raw['values']):
            q=_OUTPUT_ALIASES.get(raw['key'],raw['key'])+(f'_{i+1}' if len(raw['values'])==2 else '')
            actual,mapping=output_value(raw['key'],i,n,v);g=gmrows.get(q,{})
            row=dict(quantity=q,source_quantity=raw['key'],unit=raw['unit'],tr30_printed=ref,
                     kisssoft=actual,gearmath=g.get('actual'),kisssoft_mapping=mapping,
                     printed_page=raw['citation']['printed_page'],gearmath_status=g.get('status'))
            if isinstance(actual,(float,int)) and isinstance(ref,(float,int)):
                d=actual-ref;tol=quantum_tolerance(raw['display'][i],ref)
                row.update(kisssoft_minus_tr30=d,strict_abs_001_and_rel_005=abs(d)<=.01+1e-12 and abs(d)<=.005*abs(ref)+1e-12,
                           printed_quantum_tolerance=tol,printed_quantum_match=abs(d)<=tol+1e-12)
                if isinstance(g.get('actual'),(float,int)):row['kisssoft_minus_gearmath']=actual-g['actual']
            rows.append(row)
        csvout(folder/'comparison.csv',rows);dump(folder/'comparison.json',rows)
        summary=dict(case=n,accepted=False,input_audit=dict(Counter(x['status'] for x in inputs)),
            strict_input_closure=False,ancillary_assumption='TR30 does not specify a tip-relief length. Native linear relief uses LCa=0.5*mn so Ca=13 is retained; sensitivity at LCa=1*mn is separate. This does not grant strict-input acceptance.',
            report_validation=validation,reload_ok=run['reload_calculate_return'],reload_differences=run['reload_differences'],
            values_extracted=len(v),unavailable_optional_template_fields=run['errors'],
            printed_quantum_failures=[r['quantity'] for r in rows if r.get('printed_quantum_match') is False],
            unmapped_results=[r['quantity'] for r in rows if r['kisssoft'] is None],
            strict_pass=sum(r.get('strict_abs_001_and_rel_005') is True for r in rows),comparison_rows=len(rows),
            reference_transcription_sha256=sha(source),native_sha256=sha(stem.with_suffix('.Z12')))
        dump(folder/'validation.json',summary);results.append(summary)
        appendix(folder,n,v,inputs,rows,summary)
        print(json.dumps({k:x for k,x in summary.items() if k!='unavailable_optional_template_fields'},ensure_ascii=False),flush=True)
    finally:word.Quit()
    dump(ROOT/'verification-summary.json',dict(M33_accepted=False,cases=results))

def appendix(folder,n,v,inputs,rows,summary):
    styles=getSampleStyleSheet();story=[]
    def para(t,style='BodyText'):story.append(Paragraph(t,styles[style]));story.append(Spacer(1,7))
    def table(data,widths):
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([
          ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dfe9f3')),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),
          ('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'TOP'),
          ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t);story.append(Spacer(1,10))
    para(f'TR30 example {n}: high-precision appendix','Title')
    para('KISSsoft 2026 / ISO 6336:2019. M33 remains UNACCEPTED. Pair with the complete vendor PDF/RTF and native Z12. Values below are COM readbacks after saving, releasing, reopening and recalculating. CSV retains 17 significant digits.')
    keys=[('YF','Fuss.YF'),('YS','Fuss.YS'),('sigmaF0 (MPa)','Fuss.sigF0'),('sigmaF (MPa)','Fuss.sigF'),('sigmaFP (MPa)','Fuss.sigFP'),('SF','Fuss.SFnorm'),('sigmaH (MPa)','Flanke.sigHBD'),('sigmaHP (MPa)','Flanke.sigHP'),('SH','Flanke.SH')]
    table([['Quantity','Gear 1','Gear 2']]+[[label]+[f'{v[f"ZPP[{i}].{f}"]:.12g}' for i in (0,1)] for label,f in keys],[140,170,170])
    if n==7:
        para('Hardness conversion settings','Heading2')
        para('Material = Own Input; through-hardened alloy steel; ML (mat.isoclass=1, verified in material UI). Entered surface hardness unit is HBW (mat.haerteDim=0). Gear 1 is 342 HBW; gear 2 is 300 HBW. No HV value was substituted for the table input.')
        table([['Quantity','Gear 1','Gear 2']]+[[f]+[f'{v[f"ZR[{i}].{f}"]:.12g}' for i in (0,1)] for f in ('mat.haerte','HardnessHB','HardnessHV','mat.limh','mat.limf')],[140,170,170])
        para('The gear-module readbacks are 359.8106259863 HV and 315.6233561284 HV. These two points equal HB/0.9505 numerically; this observation does not establish the vendor algorithm. The help page describes ISO 18265:2014 Table A.1 for the material-window conversion, whose adjacent-point interpolation gives 315.5555555556 HV at 300 HB. These are recorded as different paths; no claim of equivalence is made.')
        para('Material limits were explicitly entered from the ISO 6336-5 V-alloy ML formulas using the module HV: sigmaHlim=1.313*HV+188; sigmaFlim=0.423*HV+104. KISSsoft independently calculates geometry, factors and stresses; this is not a fully independent material-limit validation.')
    else:
        para('Protuberance tool and roughness','Heading2')
        data=[['Quantity','Gear 1','Gear 2']]
        for label,f in [('Pre-cut hfP','Tool.RefProfile.hfP'),('Final hfP (derived)','BP_f.hfP'),('Tool rho_fP','Tool.RefProfile.rhofP'),('Tool hprP','Tool.RefProfile.hprP'),('Protuberance pr (mm)','Tool.pr'),('Finishing stock q (mm)','Tool.q'),('Flank Rz (um)','RZH'),('Root Rz (um)','RZF')]:
            data.append([label]+[f'{v[f"ZR[{i}].{f}"]:.12g}' for i in (0,1)])
        table(data,[140,170,170])
        para('Tool angle = 10 degrees; residual undercut = pr - q = 0.047 mm. Tool.type=2 (reference profile), Tool.finishing=false: the root remains as pre-cut while the flank is finished. Flank Rz is the printed 2.3 um; it has not been replaced by 6*Ra=2.28 um.')
        para('The printed rack values are redundant: pre-cut hfP=1.516 with q=0.220 mm generates final hfP=1.373058451548, which prints as 1.373. Both primary inputs are preserved; the final value is disclosed as a calculated quantity. The tool-height coefficient is an input-coordinate conversion in KISSsoft, inverted from COM tool-geometry evaluations to obtain pr=0.267 mm; it was not fitted to stress results.')
    story.append(PageBreak());para('Input preservation and comparison limits','Heading1')
    para('All original table rows are listed in input-audit.csv, including dashes and method selections. Measured span is mapped to tooth-thickness allowance by As=(Wtable-Wnominal)/cos(alpha_n). Both allowance limits are set equal; the four spans read back exactly. The parenthesized x2 values are dependent geometry values and agree at the printed precision. For example 7, KISSsoft width includes the 50.8 mm gap: 215.9 mm overall, 165.1 mm active total, 82.55 mm per helix.')
    para('An unresolved representation assumption remains: TR30 gives tip relief Ca=13 um but no relief length or shape. KISSsoft overwrites the derived Ca field unless a native modification is present. These files use symmetric linear relief, C=13 um, LCa=0.5*mn, with profile-deflection compensation still disabled. LCa=1*mn is checked separately for sensitivity of every mapped comparison output. Neither length is attributed to TR30, and strict input closure remains false.')
    para('Oil nu40 is entered exactly (25 / 220 mm2/s). Other oil thermal, scuffing and micropitting settings inherited from the vendor seed are ancillary defaults absent from TR30; those extra report sections are not TR30 validation evidence. Surface-condition assumptions and any unavailable software quantities remain explicit; M33 is not accepted.')
    para('Rows below show remaining differences against printed reference values using the pre-existing v0.8 display-quantum diagnostic. The strict absolute 0.01 AND relative 0.5% columns are separately preserved in comparison.csv. Neither diagnostic grants acceptance.')
    fails=[r for r in rows if r.get('printed_quantum_match') is False]
    table([['Quantity','TR30 printed','KISSsoft','Difference']]+[[r['quantity'],str(r['tr30_printed']),f"{r['kisssoft']:.10g}",f"{r['kisssoft_minus_tr30']:.8g}"] for r in fails],[140,95,130,115])
    para('Full line-by-line comparison (including gearmath v0.8 with its original formulas and material conversion) is in comparison.csv / comparison.json. f_sh0 is not exposed in this extraction; no derived convention was silently substituted. Input checks: '+str(summary['input_audit'])+'. Reopen numeric changes: '+str(len(summary['reload_differences']))+'.')
    para('COM calculation messages were empty, but opening example 7 in the GUI displayed informational warnings about fZCa selection, high circumferential speed/lubrication, scuffing method range and feasibility of span measurement on gear 2. The original table values were retained. Example 8 required an initial second calculation without changing inputs; final and reopened calculations returned true. See run.json for each attempt.')
    SimpleDocTemplate(str(folder/'high-precision-appendix.pdf'),pagesize=(595.28,841.89),rightMargin=48,leftMargin=48,topMargin=44,bottomMargin=44).build(story)

if __name__=='__main__':main()
