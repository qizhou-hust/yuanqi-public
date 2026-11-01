"""Explicit frozen benchmark vectors; refresh is an intentional golden update."""
from __future__ import annotations
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
SEEDS=ROOT/'data/registry/vector-seeds-v1.json'
SCHEMA='gearbase.vector-seeds/1'


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


def source_bindings(root=ROOT):
    """Bind only each benchmark's own raw data, never generated registry outputs."""
    def load(path):return json.loads((root/path).read_text(encoding='utf-8'))
    def raw(path):return hashlib.sha256((root/path).read_bytes()).hexdigest()
    result={'C001-G1':{p:raw(p) for p in ('data/m31/golden/C001/derived-candidate.json','data/m31/golden/C001/gear-rating.json')}}
    for n in range(1,9):
        path='data/tr30/examples-1-4.json' if n<=4 else 'data/tr30/examples-5-8.json'
        case=next(c for c in load(path)['cases'] if c['example_number']==n)
        binding={path+'#example='+str(n):_hash(case)}
        if n in (7,8):
            for p in sorted((root/f'data/kisssoft/tr30-7-8/example-{n}').rglob('*')):
                if p.is_file() and p.suffix in {'.csv','.json'}:binding[p.relative_to(root).as_posix()]=raw(p.relative_to(root))
        result['TR30-ex'+str(n)]=binding
    from gearmath.gear.kisssoft_multi import CASES
    for case in ('K01-spur',)+CASES:
        path='data/kisssoft/'+case+'.json'
        binding={path:raw(path)}
        if case!='K01-spur':
            path='data/kisssoft/K02-K05-extras.json'
            binding[path+'#case='+case]=_hash(load(path)['cases'][case])
        else:
            path='data/kisssoft/K01-spur.known-divergences.json';binding[path]=raw(path)
        result['KISSsoft-'+case.split('-')[0]]=binding
    return result


def _targets(ex):
    for fid,t in sorted(ex['library'].items()):yield ('library',None,fid),t
    for cid,c in sorted(ex['cases'].items()):
        for fid,t in sorted(c['targets'].items()):yield ('case',cid,fid),t


def _identity(f):return json.loads(json.dumps(asdict(f),sort_keys=True))


def capture(ex,bindings=None):
    return {'schema':SCHEMA,'source_bindings':source_bindings() if bindings is None else bindings,
            'targets':[{'key':list(key),'formula':_identity(t['formula']),'vectors':copy.deepcopy(t['vectors'])} for key,t in _targets(ex)]}


def _vector_key(v):return tuple(v[k] for k in ('case','basis','source'))


def _check_pairs(live,old,label):
    """Permit platform tails only; this does not replace vector replay tolerances."""
    if not isinstance(live,dict) or not isinstance(old,dict) or set(live)!=set(old):
        raise ValueError('vector numeric signature drift: '+label)
    for name,pair in live.items():
        frozen=old[name]
        if any(not isinstance(p,list) or len(p)!=2 or not isinstance(p[1],str) for p in (pair,frozen)):
            raise ValueError('invalid vector numeric pair: '+label+'/'+name)
        if pair[1]!=frozen[1]:raise ValueError('vector unit drift: '+label+'/'+name)
        try:
            finite=all(type(p[0]) in (int,float) and math.isfinite(p[0]) for p in (pair,frozen))
        except (OverflowError,TypeError):finite=False
        if not finite:raise ValueError('non-finite or invalid vector number: '+label+'/'+name)
        if abs(pair[0]-frozen[0])>1e-12*max(1.0,abs(frozen[0])):
            raise ValueError('material vector numeric drift: '+label+'/'+name)


def apply(ex,seeds=None):
    seeds=json.loads(SEEDS.read_text(encoding='utf-8')) if seeds is None else seeds
    if seeds.get('schema')!=SCHEMA:raise ValueError('invalid vector seed schema')
    current=source_bindings()
    for bid,binding in seeds['source_bindings'].items():
        if current.get(bid)!=binding:raise ValueError('benchmark source drift; explicitly refresh vector seeds: '+bid)
    frozen={tuple(t['key']):t for t in seeds['targets']}
    if len(frozen)!=len(seeds['targets']):raise ValueError('duplicate frozen vector target')
    seen=set()
    for key,t in _targets(ex):
        seen.add(key);seed=frozen.get(key)
        if seed is None or seed['formula']!=_identity(t['formula']):raise ValueError('missing or changed vector formula; explicitly refresh seeds: '+str(key))
        rows={_vector_key(v):v for v in seed['vectors']}
        if len(rows)!=len(seed['vectors']) or len(t['vectors'])!=len(rows):raise ValueError('vector inventory drift: '+str(key))
        packed=[]
        for live in t['vectors']:
            old=rows.get(_vector_key(live))
            if old is None or live['case'] not in seeds['source_bindings']:raise ValueError('vector source drift: '+str(key))
            # Inputs and chain expected are the frozen independent test fixture.
            # External direct references and tolerance/metadata must still agree exactly.
            _check_pairs(live.get('inputs'),old.get('inputs'),str(key)+'/inputs')
            _check_pairs(live.get('expected'),old.get('expected'),str(key)+'/expected')
            omit={'inputs','expected'} if live['basis']=='chain_replay' else {'inputs'}
            if {k:v for k,v in old.items() if k not in omit}!={k:v for k,v in live.items() if k not in omit}:raise ValueError('vector reference/tolerance drift: '+str(key))
            packed.append(copy.deepcopy(old))
        t['vectors']=packed
    if seen!=set(frozen):raise ValueError('frozen vector target inventory drift')
    return ex


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--refresh',action='store_true',required=True);p.add_argument('--out',type=Path,default=SEEDS);a=p.parse_args()
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    from gearmath.tools import benchmarks as BM
    doc=capture(BM.extract(frozen=False))
    a.out.write_bytes((json.dumps(doc,ensure_ascii=False,indent=1)+'\n').encode('utf-8'))
    print(str(a.out))

if __name__=='__main__':main()
