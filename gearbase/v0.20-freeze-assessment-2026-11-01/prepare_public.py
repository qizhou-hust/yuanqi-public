from pathlib import Path
import copy,hashlib,json,re,shutil
HERE=Path(__file__).resolve().parent;OUT=HERE/'public-stage';OUT.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
allowed_roots={'baseline','architecture','cases','roadmap','historical','browser-qa','review'}
allowed_top={'index.html','README.md','report-data.json','freeze-manifest.json','build-receipt.json','PLAN.md','intake-metadata.json','run_baseline.py','browser_qa.cjs','build_report.py','report.template.html'}
excluded_cases={'case-catalog.json','challenge-results.json','inventory.json','K01-spur-fixed-pair-raw.json','artifact-manifest.json','artifact-manifest.sha256','verification.json'}
copied=[]
for p in sorted(HERE.rglob('*')):
 rel=p.relative_to(HERE)
 if any(x in {'public-stage','intake-private','__pycache__','.git','public-browser-qa'} for x in rel.parts):continue
 if not p.is_file() or not (rel.parts[0] in allowed_roots or rel.as_posix() in allowed_top):continue
 if rel.parts[0]=='cases' and p.name in excluded_cases:continue
 if p.name=='initial-overflow.json':continue
 if p.suffix.lower() not in {'.json','.md','.html','.py','.cjs','.log','.txt','.png'}:raise RuntimeError('Unexpected public type: '+str(rel))
 q=OUT/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);copied.append(rel.as_posix())
changes=[]
catalog=read(HERE/'cases/case-catalog.json')
for e in catalog['entries']:
 if not e['category'].startswith('synthetic_'):
  keep={'id','title','category','entity_unit','source_binding','associated_sources','limitations','scope','evidence_status','full_system_pass','model_ready_for_same_demand_generation','explicit_null_fields','missing_or_unqualified'}
  for key in list(e):
   if key not in keep:e.pop(key)
  e['public_data_boundary']='Identity/title/category/source hash and assessment only; original standard/commercial/external source values excluded.'
catalog['distribution']='PUBLIC_REDACTED_DERIVATIVE'
catalog['private_origin_sha256']=sha(HERE/'cases/case-catalog.json')
catalog['redaction_notice']='Private standard/commercial input contracts and non-authored external source value bodies are omitted; authored synthetic demands remain explicitly synthetic.'
save(OUT/'cases/public-case-catalog.json',catalog)
challenge=read(HERE/'cases/challenge-results.json')
for c in challenge['challenges']:c.pop('source_fields',None)
challenge['distribution']='PUBLIC_REDACTED_DERIVATIVE';challenge['private_origin_sha256']=sha(HERE/'cases/challenge-results.json')
challenge['redaction_notice']='Fixed-pair source_fields omitted. Current calculated values/statuses, fixed-family demands and limits retained. No commercial native/report or standard transcription copied.'
save(OUT/'cases/public-challenge-results.json',challenge)
inventory=read(HERE/'cases/inventory.json')
source_rows=inventory.pop('sources');inventory['source_file_inventory_count']=len(source_rows)
inventory['distribution']='PUBLIC_REDACTED_DERIVATIVE';inventory['private_origin_sha256']=sha(HERE/'cases/inventory.json')
inventory['redaction_notice']='Full per-source inventory remains private; source counts, provenance, scan boundary and workspace-survey assessment retained.'
save(OUT/'cases/public-inventory.json',inventory)
mapping={'cases/case-catalog.json':'cases/public-case-catalog.json','cases/challenge-results.json':'cases/public-challenge-results.json','cases/inventory.json':'cases/public-inventory.json'}
for original,public in mapping.items():changes.append({'private_source':original,'private_source_sha256':sha(HERE/original),'public_derivative':public,'public_derivative_sha256':sha(OUT/public)})
# Keep the K01 raw capture private; publish only statuses/missing-field diagnostics here.
system_path='architecture/evidence/system.stdout.json';system=read(HERE/system_path)
k=system['results']['design_checks']['K01-spur'];r=k['result']
k['result']={key:r[key] for key in ['schema','package_version','design_id','design_sha256','system_input_id','system_input_sha256','scope_requested','computation','evidence_qualification'] if key in r}
k['result']['checks']={name:{key:v[key] for key in ['status','missing','input_errors','reason','computation'] if key in v} for name,v in r['checks'].items()}
k['result']['public_redaction']='Original commercial assumptions/source annotations and detailed raw check bodies omitted; statuses/missing fields retained.'
save(OUT/system_path,system)
changes.append({'private_source':system_path,'private_source_sha256':sha(HERE/system_path),'public_derivative':system_path,'public_derivative_sha256':sha(OUT/system_path)})
for original,new in [('artifact-manifest.json','PRIVATE-SOURCE-ARTIFACT-MANIFEST.json'),('verification.json','PRIVATE-SOURCE-VERIFICATION.json')]:
 shutil.copyfile(HERE/'cases'/original,OUT/'cases'/new)
payload=read(HERE/'report-data.json');payload['distribution']='public_redacted_derivative'
payload['original_local_source_file_sha256']=payload.pop('source_evidence_files')
payload['distributed_evidence_sha256']={mapping.get(n,n):sha(OUT/mapping.get(n,n)) for n in payload['original_local_source_file_sha256']}
for c in payload['cases']:c['evidence_ref']=c['evidence_ref'].replace('cases/challenge-results.json','cases/public-challenge-results.json')
save(OUT/'report-data.json',payload)
text=(HERE/'index.html').read_text(encoding='utf8')
for original,public in mapping.items():text=text.replace('href="'+original+'"','href="'+public+'"')
encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
text=re.sub(r'(<script id="report-data" type="application/json">).*?(</script>)',lambda m:m[1]+encoded+m[2],text,flags=re.S)
text=text.replace('</header>','</header><p class="ref" style="padding:12px 5px 0">公开阅读派生：受限标准/商业来源数值已剥离，计算摘要与失败保留。<a href="PUBLIC-DERIVATION.json">派生与来源哈希记录</a>；完整本地审计材料另存。</p>',1)
(OUT/'index.html').write_text(text,encoding='utf8')
source_data=read(HERE/'report-data.json')
assert payload['fresh_targeted_tests']==source_data['fresh_targeted_tests'] and payload['milestones']==source_data['milestones']
for a,b in zip(payload['cases'],source_data['cases']):assert all(a[k]==b[k] for k in a if k!='evidence_ref')
public_receipt=read(HERE/'build-receipt.json');public_receipt.update(distribution='public_redacted_derivative',private_build_receipt_sha256=sha(HERE/'build-receipt.json'),public_transform_producer_sha256=sha(Path(__file__)),html_sha256=sha(OUT/'index.html'),data_sha256=sha(OUT/'report-data.json'))
save(OUT/'build-receipt.json',public_receipt)
notice='\n\n## This is the public derivative\n\nUse `index.html` to read offline. `cases/public-*.json` replace the three private audit files. Private original hashes are preserved as provenance, not assertions that excluded originals are present here. See PUBLIC-DERIVATION.json. Original-source review receipts remain original-bound; public transformation has separate hash and browser checks. The report data are preserved summaries, not new solver outputs.\n'
(OUT/'README.md').write_text((HERE/'README.md').read_text(encoding='utf8')+notice,encoding='utf8')
save(OUT/'PUBLIC-DERIVATION.json',{'schema':'gearbase.public-assessment-derivation/1','producer_sha256':sha(Path(__file__)),
 'private_html_sha256':sha(HERE/'index.html'),'public_html_sha256':sha(OUT/'index.html'),'private_report_data_sha256':sha(HERE/'report-data.json'),'public_report_data_sha256':sha(OUT/'report-data.json'),
 'public_inputs':changes,'excluded_private_files':['intake-private/','cases/K01-spur-fixed-pair-raw.json',*mapping],
 'preserved':['all26capability statuses and limits','6challenge conclusions and counts','original milestone statuses','core freeze identity','counterexample numeric results','all failures and unknowns'],
 'source_reviews':'Original source-bound review receipts describe private HTML/data. This transform changes links/distribution metadata only; new public browser checks bind exact public HTML.'})
assert not (OUT/'cases/case-catalog.json').exists() and not (OUT/'cases/K01-spur-fixed-pair-raw.json').exists()
assert all(not e.get('field_sources') for e in catalog['entries'] if not e['category'].startswith('synthetic_'))
for p in OUT.rglob('*'):
 if p.is_file():assert p.suffix.lower() not in {'.pdf','.xlsx','.z12','.w10','.w010','.exe','.dll','.so','.bz2'}
print(json.dumps({'public_stage':str(OUT),'files':sum(p.is_file() for p in OUT.rglob('*')),'html_sha256':sha(OUT/'index.html'),'redacted_cases':len(mapping)},ensure_ascii=False))
