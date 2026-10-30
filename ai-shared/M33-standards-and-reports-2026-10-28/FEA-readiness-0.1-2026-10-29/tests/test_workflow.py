import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fea_readiness.contracts import sha256, rule
from fea_readiness.pipeline import prepare
from fea_readiness.runner import run_checked, completion

THEORY={'kind':'hertz_line','inputs':{'q_N_per_mm':10,'R1_mm':10,'R2_mm':10,'E1_MPa':210000,'nu1':.3,'E2_MPa':210000,'nu2':.3}}

class WorkflowTests(unittest.TestCase):
    def test_theory_alone_never_ready(self):
        r=prepare({'case_id':'theory','units':'N-mm-MPa','theory':THEORY})
        self.assertFalse(r['ready_for_diagnostic_solve'])
        self.assertIn('contact',r['theory'])

    def test_units_and_invalid_theory(self):
        r=prepare({'case_id':'bad','units':'SI','theory':THEORY})
        self.assertFalse(r['ready_for_diagnostic_solve'])
        self.assertTrue(any(x['check_id']=='units' and x['status']=='FAIL' for x in r['checks']))
        t=copy.deepcopy(THEORY);t['inputs']['q_N_per_mm']=float('nan')
        r=prepare({'case_id':'bad','units':'N-mm-MPa','theory':t})
        self.assertFalse(r['ready_for_diagnostic_solve'])

    def test_completion_is_not_exit_code_alone(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'job';p.with_suffix('.dat').write_text('raw synthetic')
            p.with_suffix('.sta').write_text('2 4 1 3 2.0 1.0 0.25\n')
            self.assertTrue(completion(p,0,'Job finished',False)['complete'])
            self.assertFalse(completion(p,1,'Job finished',False)['complete'])
            self.assertFalse(completion(p,0,'*ERROR bad',False)['complete'])
            p.with_suffix('.sta').write_text('1 4 1 3 1.0 1.0 0.25\n')
            self.assertFalse(completion(p,0,'Job finished',False)['complete'])

    def test_drift_block_and_fresh_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'x.inp';inp.write_text('synthetic input')
            inp.with_suffix('.meta.json').write_text('{}')
            s={'case_id':'synthetic','units':'N-mm-MPa','theory':THEORY,'native':{'profile':'m37_l3','input':str(inp)}}
            # Explicit synthetic adapter substitute: verifies runner plumbing only, not a physical model.
            def fake(spec):return {'checks':[rule('synthetic','PASS','TEST ONLY')],'files':[str(inp),str(inp.with_suffix('.meta.json'))]}
            with patch('fea_readiness.pipeline.native_check',side_effect=fake):
                ready=prepare(s);self.assertTrue(ready['ready_for_diagnostic_solve'])
                inp.write_text('changed')
                with self.assertRaisesRegex(ValueError,'identity|drift'):
                    run_checked(s,ready,sys.executable,sha256(sys.executable),root/'run',5)
                self.assertFalse((root/'run').exists())

if __name__=='__main__':unittest.main()
