import copy,json,pathlib,unittest
from gearmath.tools import flagship_workflow as FW, intent

ROOT=pathlib.Path(__file__).resolve().parents[1]

class TestFlagshipWorkflow(unittest.TestCase):
    def test_three_original_structured_requirements_end_to_end(self):
        for family in ('H2','W2W','P2'):
            req=json.loads((ROOT/'data/flagships-stage0'/f'{family}.json').read_text(encoding='utf8'))['requirement']
            with self.subTest(family=family):
                compiled=intent.requirement_compile({'requirement':req})
                self.assertEqual(compiled['status'],'compiled_stage0')
                self.assertEqual(compiled['requirement_sha256'],FW.requirement_sha256(req))
                result=FW.run(compiled['workflow_call'])
                self.assertEqual(result['status'],'completed_stage0')
                self.assertTrue(result['verification']['ok'])
                self.assertFalse(result['engineering_accepted'])
                self.assertEqual(req,result['requirement'])
                if family=='W2W':
                    self.assertFalse(result['result']['candidates'][0]['thermal_ok'])
                    self.assertEqual(result['outcome'],'candidate_requires_changes')

    def test_missing_unknown_and_scope_fail_closed(self):
        req={'family':'W2W','scope':'stage0','parameters':{},'source':'explicit test'}
        r=intent.requirement_compile({'requirement':req})
        self.assertEqual(r['status'],'needs_clarification')
        self.assertTrue(r['questions'])
        bad=copy.deepcopy(req);bad['parameters']['imaginary']=5
        self.assertEqual(FW.compile_requirement(bad)['status'],'blocked_invalid_inputs')
        bad=copy.deepcopy(req);bad['scope']='strength'
        self.assertEqual(FW.compile_requirement(bad)['status'],'blocked_unsupported_scope')
        self.assertEqual(FW.run({'action':'write','requirement':req})['status'],'blocked_invalid_inputs')
        bad=copy.deepcopy(req);bad['family']=[]
        self.assertEqual(FW.compile_requirement(bad)['status'],'blocked_unsupported_scope')
