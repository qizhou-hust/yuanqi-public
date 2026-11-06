"""Restore deduplicated review archives using Python stdlib only.
Run: python 解包并校验.py --output REVIEW_UNPACKED
All ZIPs must remain beside this script. Does not execute packaged project code.
"""
from pathlib import Path, PurePosixPath
import argparse,json,zipfile,hashlib,shutil,sys
def contained(root,relative):
    p=PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or ':' in relative or '\\' in relative:raise ValueError('Unsafe path: '+relative)
    target=root.joinpath(*p.parts).resolve()
    if not target.is_relative_to(root.resolve()):raise ValueError(relative)
    return target
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='REVIEW_UNPACKED');ap.add_argument('--archives',default=str(Path(__file__).resolve().parent));args=ap.parse_args()
    source=Path(args.archives).resolve();out=Path(args.output).resolve()
    zips={p.name:p for p in source.glob('*.zip')}
    index=source/'00_START_HERE.zip'
    with zipfile.ZipFile(index) as z:
        meta=z.read('PACKAGE_MANIFEST.json');manifest=json.loads(meta)
        expected=z.read('PACKAGE_MANIFEST.sha256').decode().split()[0]
        if hashlib.sha256(meta).hexdigest()!=expected:raise ValueError('Manifest checksum mismatch')
        for info in z.infolist():
            if info.filename.startswith('review/'):
                target=contained(out,info.filename);target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(z.read(info))
    handles={}
    try:
        for row in manifest['archives']:
            name=row['name']
            if name not in zips:raise FileNotFoundError('Missing archive: '+name)
            datahash=hashlib.file_digest(zips[name].open('rb'),'sha256').hexdigest()
            if datahash!=row['sha256']:raise ValueError('Archive checksum mismatch: '+name)
            handles[name]=zipfile.ZipFile(zips[name])
        lookup={r['sha256']:r for r in manifest['objects']}
        first={}
        for obj in manifest['objects']:
            sha=obj['sha256'];paths=obj['paths'];target=contained(out,paths[0]);target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise FileExistsError('Use an empty output directory: '+str(target))
            h=hashlib.sha256();n=0
            with target.open('wb') as f:
                for part in obj['parts']:
                    data=handles[part['archive']].read(part['entry'])
                    if hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Part checksum mismatch')
                    f.write(data);h.update(data);n+=len(data)
            if n!=obj['bytes'] or h.hexdigest()!=sha:raise ValueError('Restored object checksum mismatch: '+paths[0])
            first[sha]=target
            for rel in paths[1:]:
                alias=contained(out,rel);alias.parent.mkdir(parents=True,exist_ok=True)
                if alias.exists():raise FileExistsError(str(alias))
                shutil.copyfile(target,alias)
        for entry in manifest['files']:
            target=contained(out,entry['path'])
            if hashlib.file_digest(target.open('rb'),'sha256').hexdigest()!=entry['sha256']:raise ValueError('File checksum mismatch: '+entry['path'])
    finally:
        for z in handles.values():z.close()
    report={'status':'PASS','restored_files':len(manifest['files']),'unique_objects':len(manifest['objects']),'archives_checked':len(manifest['archives']),'output':str(out),'note':'Integrity passed; does not mean engineering capabilities passed.'}
    (out/'review/RESTORE_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('RESTORE FAILED: '+repr(exc),file=sys.stderr);sys.exit(1)

