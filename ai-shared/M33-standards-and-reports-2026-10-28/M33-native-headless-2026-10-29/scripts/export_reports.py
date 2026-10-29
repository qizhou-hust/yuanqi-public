"""Headless Word conversion of unchanged vendor RTF; no UI automation."""
from pathlib import Path
import json
import fitz
import win32com.client

ROOT=Path(__file__).resolve().parents[1]
qa=ROOT/'research'/'pdf-qa';qa.mkdir(exist_ok=True)
word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
try:
    for p in ROOT.glob('*/*.rtf'):
        if 'FAILED' in str(p):continue
        if p.with_suffix('.pdf').exists() and (p.parent/'report-validation.json').exists():continue
        doc=word.Documents.Open(str(p),ReadOnly=True,AddToRecentFiles=False)
        try:doc.ExportAsFixedFormat(str(p.with_suffix('.pdf')),17)
        finally:doc.Close(False)
        pdf=fitz.open(p.with_suffix('.pdf'));txt='\n'.join(page.get_text() for page in pdf)
        (p.parent/'report.txt').write_text(txt,encoding='utf8')
        check={'pages':len(pdf),'end_marker':'End of report' in txt,'ISO2019':'ISO 6336:2019' in txt,
               'unexpanded':'<EXECUTE=' in txt or '1IF (' in txt,
               'root_intermediates':all(x in txt for x in ['YF','YS','σF0'])}
        for i,page in enumerate(pdf):
            if i==0 or ('Tooth root' in page.get_text() and 'YF' in page.get_text()):
                page.get_pixmap(matrix=fitz.Matrix(1,1)).save(qa/(p.stem+f'-p{i+1}.png'))
        (p.parent/'report-validation.json').write_text(json.dumps(check,indent=2),encoding='utf8')
        assert check['end_marker'] and check['ISO2019'] and not check['unexpanded'],check
        print(p.stem,check,flush=True)
finally:word.Quit()
