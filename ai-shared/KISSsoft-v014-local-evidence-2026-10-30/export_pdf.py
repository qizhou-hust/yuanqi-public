from pathlib import Path
import json,sys
import win32com.client,fitz
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parent
word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
records=[]
try:
    for p in sorted(root.glob('P*/*.rtf')):
        pdf=p.with_suffix('.pdf')
        if pdf.exists() and pdf.stat().st_mtime>=p.stat().st_mtime:continue
        d=word.Documents.Open(str(p),ReadOnly=True,AddToRecentFiles=False)
        try:d.ExportAsFixedFormat(str(pdf),17)
        finally:d.Close(False)
        doc=fitz.open(pdf);t='\n'.join(page.get_text() for page in doc)
        p.with_suffix('.txt').write_text(t,encoding='utf8')
        r={'file':str(pdf),'pages':len(doc),'characters':len(t),'unexpanded_directives':'<EXECUTE=' in t or '1IF(' in t,'has_end':'End of report' in t}
        records.append(r);print(p.parent.name,p.stem,len(doc),flush=True)
        if p.stem.startswith('P') and 'requested-edits' not in p.stem:
            pix=doc[0].get_pixmap(matrix=fitz.Matrix(.85,.85));pix.save(str(pdf.with_suffix('.preview.png')))
finally:word.Quit()
(root/'pdf-validation.json').write_text(json.dumps(records,indent=2),encoding='utf8')
