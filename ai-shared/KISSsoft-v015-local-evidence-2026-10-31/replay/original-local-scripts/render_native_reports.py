"""Readable rendering of unedited KISSsoft native PPRPT; no recalculation."""
from pathlib import Path
import xml.etree.ElementTree as ET
import textwrap,json,hashlib
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
ROOT=Path(__file__).resolve().parent
pdfmetrics.registerFont(TTFont('EvidenceMono',r'C:\Windows\Fonts\consola.ttf'))
def textof(n):
    if n.tag in ['image','header','footer','tabs']:return ''
    s=n.text or ''
    for child in n:
        s+=textof(child)
        if child.tag=='br':s+='\n'
        if child.tag=='td':s+=' | '
        if child.tag=='tr':s+='\n'
        s+=child.tail or ''
    return s
rows=[]
for p in sorted((ROOT/'shaftprep').glob('*.pprpt')):
    if p.name.startswith('auto-'):continue
    doc=ET.parse(p).getroot();parts=[]
    for node in doc:
        if node.tag in ['header','footer']:continue
        t=textof(node).strip()
        if t:parts.append(t)
    body='\n'.join(parts)
    assert '<EXECUTE=' not in body and '1IF (' not in body
    stem=p.with_suffix('');p.with_suffix('.txt').write_text(body,encoding='utf8')
    pdf=p.with_suffix('.pdf');c=canvas.Canvas(str(pdf),pagesize=A4)
    c.setTitle(doc.attrib.get('title',p.stem));w,h=A4;y=h-35;page=0
    lines=['KISSsoft 2026 native report - readable text rendering',
           'Source: '+p.name,
           'No recomputation. Graphic payloads omitted; retain the native PPRPT for full layout.','']
    for line in body.splitlines():
        lines.extend(textwrap.wrap(line.expandtabs(4),width=124,replace_whitespace=False,drop_whitespace=False) or [''])
    for line in lines:
        if y<34:
            c.setFont('EvidenceMono',7);c.drawRightString(w-30,20,str(page+1));c.showPage();page+=1;y=h-35
        c.setFont('EvidenceMono',7);c.drawString(30,y,line);y-=10
    c.setFont('EvidenceMono',7);c.drawRightString(w-30,20,str(page+1));c.save()
    rows.append({'native':p.name,'native_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pdf':pdf.name,'text_chars':len(body),'pages':page+1,'is_vendor_native_pdf':False,'content_source':'unedited vendor PPRPT textual content'})
(ROOT/'native-report-rendering.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print('Rendered',len(rows),'native reports')
