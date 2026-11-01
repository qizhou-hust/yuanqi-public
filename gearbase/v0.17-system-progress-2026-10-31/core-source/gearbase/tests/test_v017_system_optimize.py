"""Capability probe, never replacement engineering inputs for real C001."""
import copy
import itertools
import json
import pathlib
import importlib.util
from gearmath.gear import factor_recompute as FR
from gearmath.gear import source_optimize as SO
from gearmath.product import design_check as DC
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('system_fixture', ROOT / 'tests/test_sys_design_check.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

def probe():
    doc = FR.load_doc('C001.factors')
    si = fixture._demo_system_input()
    si['design_ref']['source_id'] = doc['id']
    p = {'objective': 'gear_blank_plus_shaft_volume_mm3', 'max_combinations': 100, 'hold_evidence': {k: 'Capability probe: retain original sourced evidence; no new qualification' for k in doc['evidence']}, 'gear': [], 'shaft': [], 'bearing': []}
    for name, mn, b in [('thin', 2, 4), ('original', 2, 30), ('large', 2.5, 30)]:
        inputs = copy.deepcopy({k: doc['inputs'][k] for k in ('m_n', 'b')})
        for k, v in [('m_n', mn), ('b', b)]:
            inputs[k].update(value=v, provenance='assumption', source='Authored capability probe geometry')
        p['gear'].append({'id': name, 'source': 'Capability probe from C001.factors', 'inputs': inputs})
    for name, d in [('weak', 8), ('economy', 20), ('strong', 34)]:
        shafts, keys = (copy.deepcopy(si['shafts']), copy.deepcopy(si['keys']))
        shafts[0]['segments'][0]['d'] = fixture.L(d, 'mm', 'Authored finite shaft diameter probe')
        keys[0]['d'] = fixture.L(d, 'mm', 'Same authored shaft/key diameter')
        if name == 'weak':
            keys[0]['l_tr'] = fixture.L(8, 'mm', 'Authored weak shaft/key probe within method domain')
        p['shaft'].append({'id': name, 'source': 'test_sys_design_check._demo_system_input (authored probe)', 'shafts': shafts, 'keys': keys})
    for name, c in [('low', 2000), ('original', 35000), ('tie', 35000)]:
        bearings = copy.deepcopy(si['bearings'])
        for bearing in bearings.values():
            bearing['C_r'] = fixture.L(c, 'N', 'Authored finite capacity probe; not a catalogue selection')
        p['bearing'].append({'id': name, 'source': 'C001 bearing method + authored capacity probe', 'bearings': bearings})
    return (doc, si, p)

def reference(doc, si, p):
    from gearmath.system.system_optimize import total_volume_mm3
    rows = []
    for gi, sh, br in itertools.product(p['gear'], p['shaft'], p['bearing']):
        d, s = (copy.deepcopy(doc), copy.deepcopy(si))
        d['inputs'].update(gi['inputs'])
        s.update(shafts=sh['shafts'], keys=sh['keys'], bearings=br['bearings'])
        r = DC.check(d, s, ['gear_rating', 'shaft', 'bearing', 'key'])
        if all((r['checks'][k]['status'] == 'pass' for k in ['gear_rating', 'shaft', 'bearing', 'key'])):
            v = SO.build_family_model(d, 'pair_model').evaluate(['V_blank']).values['V_blank']
            rows.append({'ids': [gi['id'], sh['id'], br['id']], 'objective': total_volume_mm3(gear_blank_mm3=v, shafts=sh['shafts'])})
    return sorted(rows, key=lambda r: (r['objective'], r['ids']))
LOAD_RECORDS = {'mesh': {'kind': 'mesh', 'name': 'mesh', 'x': fixture.L(50, 'mm'), 'F_tw': fixture.L(100, 'N'), 'alpha_wt_deg': fixture.L(20, 'deg'), 'beta_w_deg': fixture.L(0, 'deg'), 'd_w': fixture.L(40, 'mm'), 'theta_deg': fixture.L(0, 'deg'), 'tangential_sign': fixture.L(-1, '1'), 'axial_sign': fixture.L(1, '1')}, 'torque': {'kind': 'torque', 'name': 'torque', 'x': fixture.L(140, 'mm'), 'T': fixture.L(2000, 'N*mm')}, 'line': {'kind': 'line', 'name': 'line', 'x0': fixture.L(30, 'mm'), 'x1': fixture.L(40, 'mm'), 'F': fixture.L([0, 10, 0], 'N')}, 'point': {'kind': 'point', 'name': 'point', 'x': fixture.L(30, 'mm'), 'y': fixture.L(0, 'mm'), 'z': fixture.L(0, 'mm'), 'F': fixture.L([0, 10, 0], 'N'), 'C': fixture.L([0, 0, 0], 'N*mm')}}
from gearmath.system import shaft_line as SL
import inspect
from gearmath.system import iso281 as BRG, din6892 as KEY
REQUIRED_COMPONENT_FIELDS = [('bearing', k) for k in set(inspect.signature(BRG.bearing_life).parameters) - {'F_r', 'F_a'} | {'required_life_h'}] + [('key', k) for k in set(inspect.signature(KEY.method_c).parameters) | {'method'}] + [('shaft', k) for k in set(inspect.signature(SL.solve).parameters) | {'sections', 'bearings'}] + [('segment', k) for k in ('x0', 'x1', 'd', 'd_i')] + [('section', k) for k in ('x', 'stress_state', 'checks')]
import unittest
import tempfile
from unittest import mock

class TestFiniteSystemOptimize(unittest.TestCase):

    def test_finite_joint_search_matches_fresh_cartesian_and_preserves_inputs(self):
        import gearmath.product.system_optimize as opt
        doc, si, p = probe()
        before = copy.deepcopy((doc, si, p))
        got = opt.optimize(doc, si, p)
        assert got['status'] == 'completed', got
        assert [{'ids': r['ids'], 'objective': r['objective']} for r in got['feasible']] == reference(doc, si, p)
        assert got['best'] == got['feasible'][0]
        assert got['stats']['cartesian_combinations'] == 27
        assert got['stats']['pruned_combinations'] > 0
        assert got['stats']['cache_hits'] > 0
        assert (doc, si, p) == before
        assert len({r['candidate_sha256'] for r in got['feasible']}) == len(got['feasible'])

    def test_source_edits_invalidate_identity_and_recompute(self):
        import gearmath.product.system_optimize as opt
        doc, si, p = probe()
        a = opt.optimize(doc, si, p)
        p['bearing'][1]['source'] += ' edited'
        b = opt.optimize(doc, si, p)
        assert a['problem_sha256'] != b['problem_sha256']
        aa = {tuple(x['ids']): x for x in a['feasible']}
        bb = {tuple(x['ids']): x for x in b['feasible']}
        key = next((k for k in aa if k[-1] == 'original'))
        assert aa[key]['candidate_sha256'] != bb[key]['candidate_sha256']
        p['bearing'][1]['bearings']['B_S0_0']['C_r']['value'] = 2000
        c = opt.optimize(doc, si, p)
        assert not any((x['ids'][-1] == 'original' for x in c['feasible']))

    def test_invalid_or_unknown_is_blocked(self):
        for mutation in ['missing', 'unknown', 'oversized', 'hold', 'error']:
            with self.subTest(mutation=mutation):
                import gearmath.product.system_optimize as opt
                doc, si, p = probe()
                if mutation == 'missing':
                    p['shaft'][0]['shafts'][0]['segments'][0]['d']['value'] = None
                if mutation == 'unknown':
                    p['objective'] = 'mystery'
                if mutation == 'oversized':
                    p['max_combinations'] = 1
                if mutation == 'hold':
                    p['hold_evidence'] = {}
                if mutation == 'error':
                    p['gear'][0]['inputs']['m_n']['value'] = -1
                got = opt.optimize(doc, si, p)
                assert got['status'] == 'blocked'
                assert got['best'] is None
                assert got['errors']

    def test_all_infeasible_has_no_false_optimum(self):
        from gearmath.product.system_optimize import optimize
        d, s, p = probe()
        p['gear'] = p['gear'][:1]
        r = optimize(d, s, p)
        assert r['status'] == 'completed' and r['best'] is None and (r['feasible'] == [])
        assert r['stats']['pruned_combinations'] == 9

    def test_volume_objective_known_annular_cylinder_and_overlap_rejection(self):
        import math
        from gearmath.system.system_optimize import total_volume_mm3
        segments = [{k: fixture.L(v, 'mm') for k, v in [('x0', 0), ('x1', 100), ('d', 20), ('d_i', 10)]}]
        assert total_volume_mm3(gear_blank_mm3=100, shafts=[{'segments': segments}]) == 100 + math.pi / 4 * 300 * 100
        with self.assertRaises(ValueError):
            total_volume_mm3(gear_blank_mm3=100, shafts=[{'segments': segments * 2}])

    def test_upstream_edit_changes_all_downstream_physical_checks(self):
        from gearmath.product.system_optimize import optimize
        d, s, p = probe()
        r = optimize(d, s, p)
        rows = {tuple(v['ids']): v for v in r['feasible']}
        a, b = (rows['original', 'economy', 'original'], rows['large', 'economy', 'original'])
        for scope in ('gear_rating', 'shaft', 'bearing'):
            assert [x['value'] for x in a['checks'][scope]['items']] != [x['value'] for x in b['checks'][scope]['items']]
        assert any((x['scope'] == 'shaft/key' for x in r['rejections']))

    def test_omitted_requirements_cannot_hide_in_pruned_branch(self):
        for component, field in [('bearing', 'C_r'), ('bearing', 'required_life_h'), ('shaft', 'x_A'), ('static', 'sigma_bFK'), ('key', 'Re_shaft')]:
            with self.subTest(component=component, field=field):
                from gearmath.product.system_optimize import optimize
                d, s, p = probe()
                p['gear'] = p['gear'][:1]
                if component == 'bearing':
                    del p['bearing'][0]['bearings']['B_S0_0'][field]
                if component == 'shaft':
                    del p['shaft'][0]['shafts'][0][field]
                if component == 'static':
                    del p['shaft'][0]['shafts'][0]['sections'][0]['static'][field]
                if component == 'key':
                    del p['shaft'][0]['keys'][0][field]
                r = optimize(d, s, p)
                assert r['status'] == 'blocked' and r['errors'] and (r['best'] is None)

    def test_unknown_design_reference_cannot_hide_in_pruned_branch(self):
        from gearmath.product.system_optimize import optimize
        d, s, p = probe()
        p['gear'] = p['gear'][:1]
        p['bearing'][0]['bearings']['B_S0_0']['n']['from_design'] = 'missing_quantity'
        r = optimize(d, s, p)
        assert r['status'] == 'blocked' and r['errors']

    def test_every_required_load_field_is_blocked_even_when_gear_pruned(self):
        for kind, field in [(kind, key) for kind, row in LOAD_RECORDS.items() for key in row]:
            with self.subTest(kind=kind, field=field):
                from gearmath.product.system_optimize import optimize
                d, s, p = probe()
                p['gear'] = p['gear'][:1]
                row = copy.deepcopy(LOAD_RECORDS[kind])
                del row[field]
                p['shaft'][0]['shafts'][0]['loads'] = [row]
                r = optimize(d, s, p)
                assert r['status'] == 'blocked' and r['errors']

    def test_complete_line_load_requires_endpoints_without_point_x(self):
        from gearmath.product.system_optimize import _component_requirements
        d, s, p = probe()
        s['shafts'][0]['loads'].append(copy.deepcopy(LOAD_RECORDS['line']))
        _component_requirements(s)

    def test_every_static_requirement_is_blocked_when_gear_pruned(self):
        for field in ['load_factor', 'S_min', 'sigma_zdFK', 'sigma_bFK', 'tau_tFK']:
            with self.subTest(field=field):
                from gearmath.product.system_optimize import optimize
                d, s, p = probe()
                p['gear'] = p['gear'][:1]
                del p['shaft'][0]['shafts'][0]['sections'][0]['static'][field]
                r = optimize(d, s, p)
                assert r['status'] == 'blocked'
                assert field in r['errors'][0]['message']

    def test_every_fatigue_requirement_is_blocked_when_gear_pruned(self):
        for field in SL._DIN743_KEYS:
            with self.subTest(field=field):
                from gearmath.product.system_optimize import optimize
                d, s, p = probe()
                p['gear'] = p['gear'][:1]
                section = p['shaft'][0]['shafts'][0]['sections'][0]
                section['checks'] = fixture.L(['fatigue'], '-')
                section['fatigue'] = {k: fixture.L(1.2, '1' if k in ('S_min', 'K1_deff', 'K_sigma_zd', 'K_sigma_b', 'K_tau') else 'MPa') for k in SL._DIN743_KEYS}
                section['fatigue']['load_case'] = fixture.L('load_case_1', '-')
                del section['fatigue'][field]
                r = optimize(d, s, p)
                assert r['status'] == 'blocked'
                assert field in r['errors'][0]['message']

    def test_component_required_field_deletion_matrix(self):
        for component, field in REQUIRED_COMPONENT_FIELDS:
            with self.subTest(component=component, field=field):
                from gearmath.product.system_optimize import optimize
                d, s, p = probe()
                p['gear'] = p['gear'][:1]
                targets = {'bearing': p['bearing'][0]['bearings']['B_S0_0'], 'key': p['shaft'][0]['keys'][0], 'shaft': p['shaft'][0]['shafts'][0], 'segment': p['shaft'][0]['shafts'][0]['segments'][0], 'section': p['shaft'][0]['shafts'][0]['sections'][0]}
                del targets[component][field]
                r = optimize(d, s, p)
                assert r['status'] == 'blocked' and r['errors']

    def test_bearing_nested_required_fields_block_even_under_pruning(self):
        for field in ['rows', 'alpha_deg', 'kappa', 'ec', 'C_u']:
            with self.subTest(field=field):
                from gearmath.product.system_optimize import optimize
                d, s, p = probe()
                p['gear'] = p['gear'][:1]
                b = p['bearing'][0]['bearings']['B_S0_0']
                if field in ('rows', 'alpha_deg'):
                    b['bearing_kind'] = fixture.L('radial_roller', '-')
                    b['xy'] = fixture.L({'rows': 1, 'alpha_deg': 0}, '-')
                    del b['xy']['value'][field]
                else:
                    b['a_ISO_inputs'] = fixture.L({'kappa': 1, 'ec': 1, 'C_u': 100}, '-')
                    del b['a_ISO_inputs']['value'][field]
                r = optimize(d, s, p)
                assert r['status'] == 'blocked' and field in r['errors'][0]['message']

    def test_certificate_fault_blocks_before_pruning(self):
        for fault in ['expected_hash', 'missing_file', 'changed_bytes']:
            with self.subTest(fault=fault):
                for pruned_only in [False, True]:
                    with self.subTest(pruned_only=pruned_only):
                        with tempfile.TemporaryDirectory() as temporary_directory:
                            tmp_path = pathlib.Path(temporary_directory)
                            from gearmath.product.system_optimize import optimize
                            d, s, p = probe()
                            if pruned_only:
                                p['gear'] = p['gear'][:1]
                            cert = next((v['certificate'] for v in d['evidence'].values() if v['certificate']['kind'] == 'file'))
                            local = tmp_path / 'certificate.json'
                            local.write_bytes((ROOT / cert['ref']).read_bytes())
                            cert['ref'] = str(local)
                            if fault == 'expected_hash':
                                cert['sha256'] = '0' * 64
                            if fault == 'missing_file':
                                local.unlink()
                            if fault == 'changed_bytes':
                                local.write_bytes(local.read_bytes() + b'\nchanged\n')
                            r = optimize(d, s, p)
                            assert r['status'] == 'blocked' and r['best'] is None and r['errors']
                            assert r['stats']['design_check_calls'] == 0

    def test_valid_certificate_copy_is_verified_and_bound(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_path = pathlib.Path(temporary_directory)
            from gearmath.product.system_optimize import optimize
            import hashlib
            d, s, p = probe()
            cert = next((v['certificate'] for v in d['evidence'].values() if v['certificate']['kind'] == 'file'))
            local = tmp_path / 'certificate.json'
            local.write_bytes((ROOT / cert['ref']).read_bytes())
            cert['ref'] = str(local)
            r = optimize(d, s, p)
            assert r['status'] == 'completed'
            assert any((x['ref'] == str(local) and x['actual_sha256'] == hashlib.sha256(local.read_bytes()).hexdigest() for x in r['certificate_files']))
            assert r['hold_evidence'] == p['hold_evidence']

    def test_external_certificate_edit_during_search_discards_partial_optimum(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_path = pathlib.Path(temporary_directory)
            from gearmath.product import system_optimize as opt
            d, s, p = probe()
            cert = next((v['certificate'] for v in d['evidence'].values() if v['certificate']['kind'] == 'file'))
            local = tmp_path / 'certificate.json'
            local.write_bytes((ROOT / cert['ref']).read_bytes())
            cert['ref'] = str(local)
            original = opt.DC.check
            changed = False

            def checked(*args, **kwargs):
                nonlocal changed
                r = original(*args, **kwargs)
                if not changed:
                    local.write_bytes(local.read_bytes() + b'\nexternal edit\n')
                    changed = True
                return r
            with mock.patch.object(opt.DC, 'check', checked):
                r = opt.optimize(d, s, p)
            assert r['status'] == 'blocked' and r['best'] is None and (r['feasible'] == [])
            assert r['errors']
