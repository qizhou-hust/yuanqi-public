from pathlib import Path
here=Path(__file__).resolve().parent
s=(here.parent/'v020-freeze-assessment-2026-11-01/browser_qa.cjs').read_text(encoding='utf8')
s=s.replace("['bottlenecks','cases','source','roadmap','freeze']","['math','units','library','workflow','roadmap']")
s=s.replace("locator('#cases')","locator('#library')").replace("name+'-cases.png'","name+'-library.png'")
(here/'browser_qa.cjs').write_text(s,encoding='utf8')
