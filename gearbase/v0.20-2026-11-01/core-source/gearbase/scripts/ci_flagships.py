"""Actual stdio MCP replay of the three original authored Stage0 requirements.

This protocol client verifies the software pipeline, not a Claude model session.
All input fields are frozen authored parameters; no engineering defaults added.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,queue,subprocess,sys,threading,time
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt={'schema':'gearbase.m38-flagship-mcp/1','started_at':stamp(),'client':'deterministic stdio protocol client; not Claude','scope':'original Stage0 only','engineering_accepted':False,'cases':[]}
    proc=subprocess.Popen([sys.executable,'-X','utf8','-I',str(ROOT/'mcp_server.py')],cwd=args.out,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
    lines=queue.Queue()
    def read():
        for line in proc.stdout:lines.put(line)
        lines.put(None)
    threading.Thread(target=read,daemon=True).start()
    rpc=[];seq=0
    def call(method,params):
        nonlocal seq
        seq+=1;request={'jsonrpc':'2.0','id':seq,'method':method,'params':params}
        rpc.append({'at':stamp(),'direction':'request','message':request})
        proc.stdin.write(json.dumps(request,ensure_ascii=False,allow_nan=False)+'\n');proc.stdin.flush()
        raw=lines.get(timeout=60)
        if raw is None:raise RuntimeError('MCP server exited before response')
        response=json.loads(raw);rpc.append({'at':stamp(),'direction':'response','message':response})
        assert response.get('id')==seq and 'error' not in response,response
        return response['result']
    def tool(name,arguments):
        r=call('tools/call',{'name':name,'arguments':arguments})
        assert not r.get('isError'),r
        return json.loads(r['content'][0]['text'])
    try:
        receipt['initialize']=call('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'gearbase-original-flagship-replay','version':'1'}})
        tools=call('tools/list',{})['tools'];receipt['tool_names']=[t['name'] for t in tools]
        assert {'requirement_compile','flagship_workflow'}<=set(receipt['tool_names'])
        for family in ('H2','W2W','P2'):
            path=ROOT/'data'/'flagships-stage0'/(family+'.json')
            doc=json.loads(path.read_text(encoding='utf8'));req=doc['requirement']
            compiled=tool('requirement_compile',{'requirement':req})
            assert compiled['status']=='compiled_stage0',compiled
            result=tool('flagship_workflow',compiled['workflow_call'])
            assert result['status']=='completed_stage0' and result['verification']['ok'] is True,result
            assert result['engineering_accepted'] is False and result['persisted'] is False
            assert result['requirement_sha256']==compiled['requirement_sha256']
            if family=='W2W':assert result['outcome']=='candidate_requires_changes' and result['result']['candidates'][0]['thermal_ok'] is False
            (args.out/(family+'.json')).write_text(json.dumps({'compiled':compiled,'run':result},ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
            receipt['cases'].append({'family':family,'input_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'requirement_sha256':result['requirement_sha256'],'status':result['status'],'outcome':result['outcome'],'verification':result['verification'],'engineering_accepted':False})
        receipt['passed']=True
    finally:
        proc.stdin.close()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        (args.out/'stderr.txt').write_text(proc.stderr.read(),encoding='utf8')
        (args.out/'rpc.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rpc),encoding='utf8')
        receipt.update(completed_at=stamp(),elapsed_seconds=time.monotonic()-start,server_exit_code=proc.returncode)
        (args.out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert proc.returncode==0
    print(json.dumps(receipt,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
