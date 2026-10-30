"""Create a scoped source/evidence zip; never redistribute research downloads."""
import hashlib
import json
import zipfile
from datetime import datetime,timezone
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1];dist=root/'dist';dist.mkdir(exist_ok=True)
    paths=[root/p for p in ['README.md','STATUS.md','STATUS.json','pyproject.toml']]
    for d in ['fea_readiness','tests','tools','docs','examples','artifacts/m37-final']:
        paths.extend(p for p in (root/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    paths.extend(root/p for p in ['research/LITERATURE-AND-OPEN-SOURCE.md','research/sources.json','research/repositories.json',
        'asset-audit/ASSET-REUSE.md','asset-audit/ASSET-REUSE.json','artifacts/unit-tests.txt','artifacts/hertz.json','artifacts/beam.json',
        'artifacts/wheel-smoke.json'])
    paths.extend(dist.glob('*.whl'))
    entries=[]
    for p in sorted(set(paths)):
        b=p.read_bytes();entries.append({'path':p.relative_to(root).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    manifest={'schema':'fea-readiness.release-manifest/0.1','version':'0.1.0','generated_utc':datetime.now(timezone.utc).isoformat(),
              'scope':'Explicit allowlist; excludes third-party cache, old source copies, temporary/obsolete replays','files':entries}
    (root/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    zpath=dist/'fea-readiness-0.1.0.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for entry in entries:z.write(root/entry['path'],entry['path'])
        z.write(root/'release-manifest.json','release-manifest.json')
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        for entry in entries:
            b=z.read(entry['path']);assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256']
    result={'zip':str(zpath),'members':len(entries)+1,'bytes':zpath.stat().st_size,'sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),
            'crc_and_every_member_hash_pass':True}
    (dist/'package-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result))

if __name__=='__main__':main()
