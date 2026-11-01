from unittest.mock import patch
from gearmath.product import design_check as DC
from gearmath.system import drivetrain_check as DT
from tests.test_sys_design_check import _doc, _demo_system_input


def test_product_uses_canonical_static_backend():
    with patch.object(DT, 'legacy_static_solve', wraps=DT.legacy_static_solve) as solve, \
         patch.object(DT, 'legacy_section_check', wraps=DT.legacy_section_check) as section, \
         patch.object(DT, 'legacy_bearing_life', wraps=DT.legacy_bearing_life) as bearing:
        result = DC.check(_doc('C001'), _demo_system_input(), ['shaft', 'bearing'])
    assert solve.call_count == 1
    assert section.call_count > 0
    assert bearing.call_count > 0
    assert result['checks']['shaft']['items']
from copy import deepcopy
from tests.test_sys_design_check import L


def test_fresh_static_results_after_source_edits():
    si = _demo_system_input()
    first = DC.check(_doc('C001'), si, ['shaft', 'bearing'])
    changed = deepcopy(si)
    changed['shafts'][0]['segments'][0]['d'] = L(40.0, 'mm')
    changed['shafts'][0]['loads'][1]['T'] = L(150000.0, 'N*mm')
    second = DC.check(_doc('C001'), changed, ['shaft', 'bearing'])
    assert DC.validate_result(second) == []
    assert first['checks']['shaft']['items'][0]['value'] != second['checks']['shaft']['items'][0]['value']
    assert DC.check(_doc('C001'), si, ['shaft'])['checks']['shaft']['items'] == first['checks']['shaft']['items']


def test_bearing_only_uses_shared_reaction_without_sections():
    si = _demo_system_input()
    si['shafts'][0]['sections'] = None
    result = DC.check(_doc('C001'), si, ['bearing'])
    assert result['checks']['bearing']['status'] == 'pass'
    assert result['checks']['shaft']['status'] == 'not_in_scope'
    assert DC.validate_result(result) == []
from tests.test_m36_drivetrain_check import c001_spec


def test_authored_beam_demo_exercises_canonical_entry():
    result = DT.check(spec=c001_spec())
    assert result['shaft']['max_deflection']['radial'] > 0
    assert result['sections'][0]['static']['S'] > 0
    assert result['bearings']['A']['L10h'] > 0
