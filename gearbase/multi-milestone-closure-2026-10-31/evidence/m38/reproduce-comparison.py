"""Re-evaluate immutable M38 model files; retain command exits and byte hashes."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path('D:/my_Works/Gears/gearbase-multi-work')
OUT=Path(__file__).resolve().parent
MODELS=OUT.parent/'m38-models'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def hashes(): return {p.name:sha(p) for p in sorted(MODELS.glob('*.json'))}

before=hashes()
entries={}
for name in ('terra','sol','rules'):
    command=[sys.executable,'-m','gearmath.tools.bench_closure']
    if name!='rules': command+=['--model-output',str(MODELS/(name+'-output.json'))]
    command+=['--out',str(OUT/name)]
    completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if completed.returncode:
        print(completed.stdout); print(completed.stderr,file=sys.stderr)
        raise SystemExit(completed.returncode)
    report=load(OUT/name/'report.json')
    entries[name]=dict(command=command,exit_code=completed.returncode,
                       stdout=completed.stdout,stderr=completed.stderr,
                       metrics=report['metrics'],case_count=len(report['per_case']),
                       system=report['system'],report_sha256=sha(OUT/name/'report.json'),
                       outputs_sha256=sha(OUT/name/'outputs.json'))
after=hashes()
if before!=after: raise SystemExit('Immutable model or receipt changed')
limits=[
 'Models were requested via collaboration.spawn_agent: gpt-6.1-terra and gpt-6.1-sol, both medium effort.',
 'Provider-specific build identifiers are opaque. Identity is run-recorded, not provider-attested; matching receipt hashes establish file integrity only.',
 'The comparison is not blind. The sol receipt discloses a read of intent.py including requirement_compile before output generation, without calling it; initial reads also exposed pending empty gold metadata.',
 'The recorded sol start timestamp follows the initial source reads. The original immutable receipt retains this deviation.',
 'Model extraction and reply are followed by the real deterministic compiler in this rerun; saved model outputs are reused rather than regenerated.',
 'No engineer correctness gold exists. Compile semantic accuracy and clarification recall/precision are null; this cannot rank semantic model quality.',
 'Zero untraceable numbers means numerical traceability to input, registered derivation or public constant. It does not prove semantic assignment, engineering correctness, extraction completeness or free-text question consistency.',
 'Matching outcome counts and tool clarification self-consistency do not establish equal model semantic quality.',
 'This report covers the benchmark and first recorded multi-model comparison only; it does not certify full M38, clean-machine timing, strength rating or system closure.'
]
source_files=('gearmath/tools/bench_closure.py','gearmath/tools/bench.py','gearmath/tools/intent.py',
              'gearmath/tools/nlp_templates.py','data/bench/v1/requirements.json')
comparison=dict(schema='gearbase.m38-recorded-model-comparison/1',
                created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_sha256={f:sha(ROOT/f) for f in source_files},
                immutable_inputs_sha256=before,immutable_inputs_after_sha256=after,
                immutable_inputs_unchanged=True,entries=entries,
                model_identity='run-recorded, not provider-attested',blind=False,
                engineer_gold_available=False,semantic_accuracy=None,
                limitations=limits,
                all_commands_exit_zero=all(r['exit_code']==0 for r in entries.values()))
(OUT/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
lines=['# M38 recorded model comparison','',
       'Fresh deterministic evaluation of both saved model runs and the rule baseline. All three real CLI commands exited 0. Model outputs and receipt bytes were retained unchanged.','',
       '| System | Cases | Numbers checked | Untraceable | Rate | Tool questions asked/required | Semantic accuracy | CLI exit |',
       '|---|---:|---:|---:|---:|---:|---|---:|']
for name,r in entries.items():
    m=r['metrics']; q=m['clarification_selfcheck_fields']
    lines.append(f"| {name} | {r['case_count']} | {m['numbers_checked']} | {m['numbers_untraceable']} | {m['hallucinated_number_rate']} | {q['asked']}/{q['required']} | null | {r['exit_code']} |")
lines += ['', 'Each run produced 12 pending-confirmation compilations, 21 clarification requests, three invalid-input blocks and four unsupported-scope blocks. No inconsistent tool-question case was found.','',
          'The models were routed using `collaboration.spawn_agent` with requested presets `gpt-6.1-terra` and `gpt-6.1-sol`, both medium effort. The deterministic rules baseline is not a third model.','',
          '## Interpretation and protocol limits','']+['- '+x for x in limits]+['',
          '## Frozen model and receipt SHA256','', '| File | SHA256 |','|---|---|']
lines += [f'| `{name}` | `{digest}` |' for name,digest in before.items()]
lines += ['', '## Reproduce','',
          '`python ../milestones-multi-run/m38/reproduce-comparison.py` from the source checkout reruns the three CLI commands. `comparison.json` records command arguments, exit codes, exact metrics, output hashes and evaluation-source hashes. Per-system `report.json` and `outputs.json` preserve the complete results.','']
(OUT/'MODEL-COMPARISON.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({k:dict(exit_code=v['exit_code'],metrics=v['metrics']) for k,v in entries.items()},indent=2))
