from pathlib import Path
import base64,hashlib,json,subprocess,sys,urllib.request,zipfile
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent/'github-uploader'))
from uploader_core import Runner
class AuthRunner(Runner):
 def run(self,args,**kw):
  args=list(args)
  if str(args[0])==str(self.git):args=[args[0],'-c','credential.helper=','-c','credential.helper=!gh auth git-credential']+args[1:]
  return super().run(args,**kw)
def gh(*args):return subprocess.check_output(['gh',*args]).decode('utf8').strip()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
REPO='qizhou-hust/yuanqi-public';PREFIX='gearbase/v0.20-components-r2-2026-11-01';TAG='gearbase-v020-components-r2-2026-11-01'
def main():
 p=json.loads((HERE/'packages.json').read_text(encoding='utf8'));archive=Path(p['public']['path']);assert sha(archive)==p['public']['sha256']
 r=AuthRunner(log=lambda s:print(s,flush=True));r.check();meta=r.api('repos/'+REPO);assert meta['visibility']=='public' and meta['permissions']['push']
 work=HERE/'public-repository'
 if not work.exists():r.run([r.git,'clone','--depth','1','--filter=blob:none','--no-checkout','https://github.com/'+REPO+'.git',str(work)])
 r.run([r.git,'fetch','--depth','1','origin','main'],cwd=work);parent=r.run([r.git,'rev-parse','FETCH_HEAD'],cwd=work);r.run([r.git,'read-tree',parent],cwd=work)
 with zipfile.ZipFile(archive) as z:
  content={n:z.read(n) for n in z.namelist()};assert z.testzip() is None
 stage=HERE/'public-stage'
 for n in ['DELIVERY-MANIFEST.json','DISTRIBUTION.txt']:(stage/n).write_bytes(content[n])
 files=sorted(p for p in stage.rglob('*') if p.is_file());names=[PREFIX+'/'+p.relative_to(stage).as_posix() for p in files]
 for f in files:assert content[f.relative_to(stage).as_posix()]==f.read_bytes(),'stage changed after package: '+str(f)
 hashes=r.run([r.git,'hash-object','-w','--no-filters','--stdin-paths'],cwd=work,input_text='\n'.join(f.resolve().as_posix() for f in files)+'\n').splitlines();assert len(hashes)==len(files)
 r.run([r.git,'update-index','-z','--index-info'],cwd=work,input_text=''.join('100644 '+h+'\t'+n+'\0' for n,h in zip(names,hashes)))
 tree=r.run([r.git,'write-tree','--missing-ok'],cwd=work)
 commit=r.run([r.git,'-c','user.name=qizhou-hust','-c','user.email=166229238+qizhou-hust@users.noreply.github.com','commit-tree',tree,'-p',parent],cwd=work,input_text='Publish component architecture revision2 with mathematical contracts and bounded composition library\n')
 changed=[n for n in r.run([r.git,'diff-tree','--no-commit-id','--name-only','-z','-r',commit],cwd=work).split('\0') if n];assert all(n.startswith(PREFIX+'/') for n in changed)
 r.run([r.git,'push','origin',commit+':refs/heads/main'],cwd=work)
 notes='Architecture report revision2, mathematics first: typed transmission components, recursive macros, versioned bounded composition library and requirement-based selection. Four atomic semantic types up to4 expanded gear stages yield340 abstract ordered structures; six types yield1554. Two-stage planetary macro counts2 and adds no new canonical structure after expansion. Mathematical examples, schema/ref checks and enumeration tests are analysis only, not installed product plugins. Vendor/1D primary-source facts and5 industrial product-family precedents are qualified; no universal industrial coverage or production qualification. Core v0.20 and prior assessment unchanged.\n\nZIP SHA256: '+p['public']['sha256']
 payload=HERE/'release-payload.json';payload.write_text(json.dumps({'tag_name':TAG,'target_commitish':commit,'name':'Gearbase architecture revision2: mathematical components and composition library','body':notes,'draft':True,'prerelease':True,'make_latest':'false'}),encoding='utf8')
 release=json.loads(gh('api',f'repos/{REPO}/releases','-X','POST','--input',str(payload)));(HERE/'draft-release.json').write_text(json.dumps(release,indent=2),encoding='utf8')
 assets=[archive,archive.with_suffix('.zip.sha256'),archive.with_suffix('.zip.b64.txt'),Path(p['html']['path'])]
 for a in assets:gh('release','upload',TAG,str(a),'--repo',REPO)
 endpoint=f"repos/{REPO}/releases/{release['id']}";release=json.loads(gh('api',endpoint))
 for a in assets:
  remote=next(v for v in release['assets'] if v['name']==a.name);assert remote['digest']=='sha256:'+sha(a) and remote['size']==a.stat().st_size
 release=json.loads(gh('api',endpoint,'-X','PATCH','-F','draft=false'));assert not release['draft']
 for a in assets:
  remote=next(v for v in release['assets'] if v['name']==a.name)
  with urllib.request.urlopen(remote['browser_download_url'],timeout=60) as response:body=response.read()
  assert hashlib.sha256(body).hexdigest()==sha(a)
  if a.suffix=='.txt':assert hashlib.sha256(base64.b64decode(body,validate=True)).hexdigest()==p['public']['sha256']
 for name in ['index.html','report-data.json','source-preservation.json','library/enum-counts.json']:
  with urllib.request.urlopen(f'https://raw.githubusercontent.com/{REPO}/{commit}/{PREFIX}/{name}',timeout=30) as response:body=response.read()
  assert hashlib.sha256(body).hexdigest()==sha(stage/name)
 out={'schema':'gearbase.architecture-r2-publication/1','repository':REPO,'commit':commit,'prefix':PREFIX,'release_url':release['html_url'],
 'report_url':f'https://github.com/{REPO}/blob/main/{PREFIX}/index.html','readme_url':f'https://github.com/{REPO}/blob/main/{PREFIX}/README.md',
 'html_download_url':next(v['browser_download_url'] for v in release['assets'] if v['name']==Path(p['html']['path']).name),
 'zip_url':next(v['browser_download_url'] for v in release['assets'] if v['name']==archive.name),'public_zip_sha256':p['public']['sha256'],
 'all_assets_anon_byte_verified':True,'same_name_sha256_and_base64_verified':True,'report_and_data_anon_byte_verified':True}
 (HERE/'public-publication.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
