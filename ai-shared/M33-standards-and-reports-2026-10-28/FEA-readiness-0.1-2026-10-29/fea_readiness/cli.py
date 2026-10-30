import argparse
import sys
from .contracts import load_json,write_json
from .pipeline import prepare
from .theory import precalculate
from .review import review
from .runner import run_checked

def main():
    p=argparse.ArgumentParser(description='Headless FEA preparation and diagnostic review; no engineering auto-acceptance')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['precalculate','prepare','review']:
        q=sub.add_parser(name);q.add_argument('input');q.add_argument('--output',required=True)
    q=sub.add_parser('run');q.add_argument('input');q.add_argument('--prepared',required=True)
    q.add_argument('--solver',required=True);q.add_argument('--solver-sha256',required=True)
    q.add_argument('--run-dir',required=True);q.add_argument('--timeout',type=float,default=300)
    a=p.parse_args()
    try:
        value=load_json(a.input)
        if a.command=='precalculate':r=precalculate(value);code=0
        elif a.command=='prepare':r=prepare(value);code=0 if r['ready_for_diagnostic_solve'] else 2
        elif a.command=='review':
            r=review(value);code=0 if not r['failed'] and not r['unknown'] else 2
        else:
            r=run_checked(value,load_json(a.prepared),a.solver,a.solver_sha256,a.run_dir,a.timeout)
            print('process_complete='+str(r['complete'])+'; engineering_accepted=False')
            return 0 if r['complete'] else 2
        write_json(a.output,r);print(a.output);return code
    except Exception as e:
        print(f'{type(e).__name__}: {e}',file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
