from pathlib import Path
import datetime,hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent/'gearbase-v020-work';OUT=HERE/'baseline';OUT.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
assert source_commit=='80117283778cf8732b5557fa15c2e41f626f92fc'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
freeze=read(HERE.parent/'v020-closure-run/code-freeze.json');assert all(sha(ROOT/p)==h for p,h in freeze.items())
commands=[('architecture',['-B','-m','gearmath.tools.architecture_guard','--json']),
 ('package-integrity',['-B','-m','gearmath.tools.package_hashes','--check']),
 ('milestones',['-B','-I','gearmath/tools/milestones.py','--json']),
 ('targeted-tests',['-B','-I','-S','-c',"import sys,unittest;sys.path.insert(0,'.');s=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_m32_architecture_guard','tests.test_v020_geometry_gate','tests.test_v020_m35_packet','tests.test_v020_bench_gold','tests.test_fea_readonly_import','tests.test_m38_ai_native']);r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())"])]
rows=[]
for label,args in commands:
 t=time.perf_counter();p=subprocess.run([sys.executable,'-X','utf8',*args],cwd=ROOT,capture_output=True)
 (OUT/(label+'.stdout.log')).write_bytes(p.stdout);(OUT/(label+'.stderr.log')).write_bytes(p.stderr)
 row={'name':label,'argv':[sys.executable,'-X','utf8',*args],'exit_code':p.returncode,'seconds':time.perf_counter()-t,
      'stdout_sha256':sha(OUT/(label+'.stdout.log')),'stderr_sha256':sha(OUT/(label+'.stderr.log'))};rows.append(row)
 if label in {'architecture','milestones'} and p.returncode==0:(OUT/(label+'.json')).write_bytes(p.stdout)
 if p.returncode:print(label,p.stderr.decode('utf8'),flush=True)
assert all(r['exit_code']==0 for r in rows),rows
assert all(sha(ROOT/p)==h for p,h in freeze.items())
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
result={'schema':'gearbase.freeze-assessment-baseline/1','date_local':'2026-11-01','timezone':'America/Los_Angeles',
 'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'version':'0.20','source_commit':source_commit,
 'passed':True,'source_unchanged':True,'frozen_python_files':len(freeze),'commands':rows,
 'historical_hosted_CI':{'source':str(HERE.parent/'v020-closure-run/HOSTED-ACCEPTANCE.json'),'sha256':sha(HERE.parent/'v020-closure-run/HOSTED-ACCEPTANCE.json'),'rerun_this_round':False},
 'scope':'Read-only baseline checks and focused tests. No new FE solve, KISSsoft solve, Claude model invocation, real gold labels or production release.'}
(OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
