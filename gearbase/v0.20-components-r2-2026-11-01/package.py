from pathlib import Path
import base64,hashlib,json,shutil,subprocess,zipfile
HERE=Path(__file__).resolve().parent;CORE=HERE.parent/'gearbase-v020-work';DEST=HERE.parent/'deliverables';STAGE=HERE/'public-stage'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=CORE)
pres=read(HERE/'source-preservation.json');assert pres['core_unchanged']
assert all(sha(CORE/n)==h for n,h in pres['frozen_python_sha256'].items())
build=read(HERE/'build-receipt.json');assert build['html_sha256']==sha(HERE/'index.html')
assert all(sha(HERE/n)==h for n,h in build['evidence_sha256'].items())
qa=read(HERE/'browser-qa/receipt.json');assert qa['passed'] and qa['html_sha256']==sha(HERE/'index.html')
review=read(HERE/'review/architecture-claims-review.json');assert review['passed'] and not review.get('open_findings',[])
assert review['html_sha256']==sha(HERE/'index.html')
exclude_dirs={'public-stage','public-repository','__pycache__','.git'}
exclude_top={'packages.json','public-publication.json','release-payload.json','draft-release.json','DELIVERY-VERIFIED.json','public-remote-verified.zip'}
entries=[]
for p in sorted(HERE.rglob('*')):
 rel=p.relative_to(HERE)
 if any(x in exclude_dirs for x in rel.parts) or rel.as_posix() in exclude_top:continue
 if not p.is_file():continue
 if p.suffix.lower() not in {'.html','.md','.json','.csv','.py','.cjs','.png','.log','.txt','.sha256','.jsonl'}:raise RuntimeError('Unexpected package file: '+str(rel))
 assert not p.read_bytes().startswith((b'%PDF-',b'\x7fELF',b'MZ'))
 assert 'intake-private' not in rel.parts and rel.as_posix() not in {'previous/cases/case-catalog.json','previous/cases/inventory.json','previous/cases/challenge-results.json','previous/cases/K01-spur-fixed-pair-raw.json'}
 entries.append((p,rel.as_posix()))
rows=[{'path':n,'bytes':p.stat().st_size,'sha256':sha(p)} for p,n in entries];assert len({r['path'] for r in rows})==len(rows)
DEST.mkdir(exist_ok=True);archive=DEST/'gearbase-v0.20-component-architecture-r2.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p,n in entries:z.write(p,n)
 z.writestr('DELIVERY-MANIFEST.json',json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 z.writestr('DISTRIBUTION.txt','Public architecture report revision2 and mathematical/counting analysis; original core remains v0.20. No installed new plugin or engineering release. Prior assessment is a previously redacted public copy. Read index.html and README.md.\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for r in rows:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
 for n in z.namelist():assert (STAGE/n).resolve().is_relative_to(STAGE.resolve())
 z.extractall(STAGE)
digest=sha(archive);archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
encoded=base64.b64encode(archive.read_bytes());assert hashlib.sha256(base64.b64decode(encoded,validate=True)).hexdigest()==digest
archive.with_suffix('.zip.b64.txt').write_bytes(encoded)
single=DEST/'gearbase-v0.20-component-architecture-r2.html';shutil.copyfile(HERE/'index.html',single)
packages={'public':{'path':str(archive),'sha256':digest,'bytes':archive.stat().st_size,'files':len(rows)},
 'html':{'path':str(single),'sha256':sha(single),'bytes':single.stat().st_size,'notice':'Offline standalone report view; full evidence links require ZIP layout.'}}
(HERE/'packages.json').write_text(json.dumps(packages,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(packages,ensure_ascii=False,indent=2))
