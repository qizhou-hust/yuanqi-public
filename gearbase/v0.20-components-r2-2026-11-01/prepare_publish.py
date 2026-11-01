from pathlib import Path
HERE=Path(__file__).resolve().parent
s=(HERE.parent/'v020-freeze-assessment-2026-11-01/publish.py').read_text(encoding='utf8')
s=s.replace("PREFIX='gearbase/v0.20-freeze-assessment-2026-11-01';TAG='gearbase-v020-assessment-2026-11-01'","PREFIX='gearbase/v0.20-components-r2-2026-11-01';TAG='gearbase-v020-components-r2-2026-11-01'")
s=s.replace('Publish v0.20 system assessment and case-driven preliminary freeze evidence','Publish component architecture revision2 with mathematical contracts and bounded composition library')
start=s.index(" notes='v0.20 system assessment:")
end=s.index("\n payload=",start)
s=s[:start]+" notes='Architecture report revision2, mathematics first: typed transmission components, recursive macros, versioned bounded composition library and requirement-based selection. Four atomic semantic types up to4 expanded gear stages yield340 abstract ordered structures; six types yield1554. Two-stage planetary macro counts2 and adds no new canonical structure after expansion. Mathematical examples, schema/ref checks and enumeration tests are analysis only, not installed product plugins. Vendor/1D primary-source facts and5 industrial product-family precedents are qualified; no universal industrial coverage or production qualification. Core v0.20 and prior assessment unchanged.\\n\\nZIP SHA256: '+p['public']['sha256']"+s[end:]
s=s.replace('Gearbase v0.20 system assessment and preliminary freeze','Gearbase architecture revision2: mathematical components and composition library')
s=s.replace("['index.html','report-data.json','PUBLIC-DERIVATION.json','cases/public-case-catalog.json']","['index.html','report-data.json','source-preservation.json','library/enum-counts.json']")
s=s.replace("schema':'gearbase.assessment-publication/1'","schema':'gearbase.architecture-r2-publication/1'")
(HERE/'publish.py').write_text(s,encoding='utf8')
print('Revision2 publisher prepared; older report and release unchanged.')
