"""Headless CalculiX launch for the bounded M37 profile; never touches desktop input."""
import math
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from .contracts import finite, sha256, write_json
from .pipeline import prepare

def completion(stem,returncode,log,timed_out):
    stem=Path(stem);rows=[]
    if stem.with_suffix('.sta').exists():
        for line in stem.with_suffix('.sta').read_text(errors='replace').splitlines():
            vals=line.split()
            try:
                if len(vals)==7:rows.append([float(v.replace('D','E')) for v in vals])
            except ValueError:pass
    last=rows[-1] if rows else []
    final=bool(last and all(math.isfinite(x) for x in last) and last[0]==2 and math.isclose(last[4],2.,abs_tol=1e-6) and math.isclose(last[5],1.,abs_tol=1e-6))
    error_free=not re.search(r'\*ERROR|fatal|segmentation fault',log,re.I)
    finished='Job finished' in log
    dat=stem.with_suffix('.dat');raw=dat.is_file() and dat.stat().st_size>0
    return {'returncode':returncode,'timed_out':timed_out,'final_step_complete':final,'error_free':error_free,
            'finished_marker':finished,'dat_present':raw,
            'complete':type(returncode) is int and returncode==0 and not timed_out and final and error_free and finished and raw,
            'scope':'Process and final step only; raw field completeness and physical acceptance require result review'}

def run_checked(spec,prepared,executable,executable_sha256,run_dir,timeout_s=300):
    timeout_s=finite(timeout_s,'timeout_s',True)
    if not prepared.get('ready_for_diagnostic_solve'):raise ValueError('Preparation is not ready')
    fresh=prepare(spec)
    if not fresh['ready_for_diagnostic_solve'] or fresh['identity']!=prepared['identity']:
        raise ValueError('Input/code/adapter identity drift or failed recheck; prepare again')
    exe=Path(executable).resolve()
    if not exe.is_file() or sha256(exe)!=executable_sha256:raise ValueError('Solver executable identity mismatch')
    folder=Path(run_dir).resolve();folder.mkdir(parents=True,exist_ok=False)
    source=Path(spec['native']['input']).resolve();staged=folder/'job.inp'
    shutil.copy2(source,staged);shutil.copy2(source.with_suffix('.meta.json'),folder/'job.meta.json')
    for src,dst in [(source,staged),(source.with_suffix('.meta.json'),folder/'job.meta.json')]:
        if sha256(dst)!=fresh['identity']['files'][str(src)]:raise ValueError('Staged input identity drift')
    write_json(folder/'preparation.json',fresh)
    started=datetime.now(timezone.utc).isoformat();t=time.monotonic();timed_out=False;code=None
    env=os.environ.copy();env['OMP_NUM_THREADS']='2'
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    with (folder/'solver.log').open('wb') as log:
        try:
            proc=subprocess.run([str(exe),'-i','job'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,
                                timeout=timeout_s,shell=False,env=env,**options)
            code=proc.returncode
        except subprocess.TimeoutExpired:timed_out=True
        except OSError as e:log.write(str(e).encode())
    report=completion(folder/'job',code,(folder/'solver.log').read_text(errors='replace'),timed_out)
    report.update({'schema':'fea-readiness.run/0.1','started_utc':started,'wall_s':time.monotonic()-t,
        'input_sha256':sha256(staged),'solver_sha256':executable_sha256,'command':[str(exe),'-i','job'],
        'engineering_accepted':False,'outputs':{p.name:sha256(p) for p in folder.iterdir() if p.is_file()},
        'binding_sha256':fresh['identity']['binding_sha256']})
    write_json(folder/'run.json',report)
    return report
