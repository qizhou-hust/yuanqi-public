"""Fresh Windows portable acceptance; stdlib only. Outputs may contain private data."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
SHA = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); args = ap.parse_args()
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    start=time.monotonic(); receipt={'started_utc':utc(),'host':sys.platform,'steps':[],'limit_seconds':600,'client':'MCP stdio test client, not Claude','source_url':URL,'expected_sha256':SHA,'ok':False}
    def step(name, action):
        t=time.monotonic(); row={'name':name,'started_utc':utc()}; receipt['steps'].append(row)
        try: action()
        except Exception as e: row['error']=repr(e); raise
        finally: row.update(ended_utc=utc(),elapsed_seconds=round(time.monotonic()-t,3))
    def command(name, cmd, env, cwd):
        def action():
            remaining=600-(time.monotonic()-start)
            if remaining<=0: raise TimeoutError('600 second limit exceeded')
            p=subprocess.run(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=remaining)
            (out/(name+'.stdout.log')).write_bytes(p.stdout); (out/(name+'.stderr.log')).write_bytes(p.stderr)
            if p.returncode: raise RuntimeError(f'{name} exited {p.returncode}')
        step(name,action)
    try:
        if sys.platform!='win32': raise RuntimeError('Windows required')
        zipfile=out/'python-3.12.10-embed-amd64.zip'
        def download():
            with urllib.request.urlopen(URL,timeout=120) as r, zipfile.open('wb') as f:
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk: break
                    f.write(chunk)
            digest=hashlib.sha256(zipfile.read_bytes()).hexdigest(); receipt['actual_sha256']=digest
            if digest!=SHA: raise ValueError('embedded Python SHA256 mismatch')
        step('download_verify',download)
        portable=out/'portable'; env=os.environ.copy(); env['PYTHONUTF8']='1'
        command('build',[sys.executable,'-I',str(ROOT/'packaging/windows/build_portable.py'),'--python-version','3.12.10','--sha256',SHA,'--embed-zip',str(zipfile),'--out',str(portable),'--include-private'],env,ROOT)
        py=portable/'python/python.exe'; app=portable/'gearbase'; isolated=env.copy()
        isolated['PATH']=str(Path(os.environ['SystemRoot'])/'System32')+os.pathsep+os.environ['SystemRoot']
        for key in ('PYTHONPATH','PYTHONHOME','HOME','USERPROFILE'): isolated.pop(key,None)
        isolated['HOME']=str(out/'empty-home'); isolated['USERPROFILE']=str(out/'empty-home'); (out/'empty-home').mkdir(exist_ok=True)
        command('doctor',[str(py),'-I',str(app/'gearmath/tools/doctor.py'),'--json'],isolated,app)
        doctor=json.loads((out/'doctor.stdout.log').read_text(encoding='utf-8'))
        if not doctor['ok'] or not any(x['check']=='mcp_handshake' and x['ok'] for x in doctor['checks']): raise RuntimeError('doctor MCP check failed')
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'gear_list_inputs','arguments':{}}}]
        def mcp():
            payload=''.join(json.dumps(r)+'\n' for r in requests).encode(); (out/'mcp.requests.jsonl').write_bytes(payload)
            p=subprocess.run([str(py),'-I',str(app/'mcp_server.py'),'--state-dir',str(out/'state')],input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=app,env=isolated,timeout=max(1,600-(time.monotonic()-start)))
            (out/'mcp.stdout.jsonl').write_bytes(p.stdout); (out/'mcp.stderr.log').write_bytes(p.stderr)
            if p.returncode: raise RuntimeError(f'MCP exit {p.returncode}')
            responses={v['id']:v for v in (json.loads(x) for x in p.stdout.decode('utf-8').splitlines()) if 'id' in v}
            if set(responses)!={1,2,3} or any('error' in v for v in responses.values()) or not responses[1]['result']['protocolVersion'] or not responses[2]['result']['tools'] or not responses[3]['result']['structuredContent']['result'] or responses[3]['result'].get('isError'): raise RuntimeError('MCP response validation failed')
        step('mcp_stdio',mcp)
        receipt['ok']=time.monotonic()-start<600
        if not receipt['ok']: raise TimeoutError('600 second limit exceeded')
    except Exception as e: receipt['error']=repr(e)
    finally:
        receipt.update(ended_utc=utc(),elapsed_seconds=round(time.monotonic()-start,3))
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(json.dumps(receipt,indent=2))
    return 0 if receipt['ok'] else 1
if __name__=='__main__': sys.exit(main())
