"""Remove leaked HTML cell tags from a rendering copy of vendor RTF only.

Native RTF/Z12 stay byte-for-byte unchanged. Hidden Word converts the copy.
"""
from pathlib import Path
import hashlib,json
import win32com.client,fitz
ROOT=Path(__file__).resolve().parent
names=['P5-A-tip-coefficient-input','P5-B-auto']+sorted(p.name for p in ROOT.glob('M39-*') if p.is_dir())
word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
rows=[]
try:
    for name in names:
        p=ROOT/name/(name+'.rtf');original=p.read_bytes()
        count=original.count(b'<TD CENTER>');clean=original.replace(b'<TD CENTER>',b'')
        assert count>0
        copy=ROOT/'render-sources'/(name+'.rtf');copy.parent.mkdir(exist_ok=True);copy.write_bytes(clean)
        doc=word.Documents.Open(str(copy),ReadOnly=True,AddToRecentFiles=False)
        try:doc.ExportAsFixedFormat(str(p.with_suffix('.pdf')),17)
        finally:doc.Close(False)
        d=fitz.open(p.with_suffix('.pdf'));t='\n'.join(x.get_text() for x in d)
        assert '<TD' not in t and '<EXECUTE=' not in t and 'End of report' in t
        p.with_suffix('.txt').write_text(t,encoding='utf8')
        assert p.read_bytes()==original
        rows.append({'case':name,'original_rtf_sha256':hashlib.sha256(original).hexdigest(),'rendering_copy_sha256':hashlib.sha256(clean).hexdigest(),'rendering_copy':str(copy.relative_to(ROOT)),'operation':'Remove literal leaked HTML token <TD CENTER> only; no numeric text changes; original vendor RTF unchanged','removed_token_count':count,'pdf_pages':len(d),'pdf_sha256':hashlib.sha256(p.with_suffix('.pdf').read_bytes()).hexdigest()})
finally:word.Quit()
(ROOT/'report-rendering-cleanup.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Rendered',len(rows),'reports from copies; vendor originals unchanged.')
