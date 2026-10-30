"""Read-only independent INP/DAT audit. No imports from the supplied FEA package.

Writes only MODEL-DEFINITION-AUDIT.json in this script's directory.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / 'm37/M37-FEA题目包'
OUT = Path(__file__).resolve().parent
SOURCES = {}


def read(path):
    path = Path(path)
    data = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = {
        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return data.decode('utf-8-sig')


def load(path):
    return json.loads(read(path))


def deck(path):
    text = read(path)
    blocks = []
    step = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith('**'):
            continue
        if s.startswith('*'):
            parts = [x.strip().upper() for x in s.split(',')]
            if parts[0] == '*STEP':
                step += 1
            block = {'keyword': parts[0], 'parameters': {}, 'line': lineno, 'step': step, 'rows': []}
            for x in parts[1:]:
                k, _, v = x.partition('=')
                block['parameters'][k] = v or True
            blocks.append(block)
        else:
            blocks[-1]['rows'].append({'line': lineno, 'values': [x.strip() for x in s.split(',') if x.strip()]})
    nodes = {}
    nsets = {}
    for b in blocks:
        if b['keyword'] == '*NODE':
            nodes.update({int(r['values'][0]): list(map(float, r['values'][1:])) for r in b['rows']})
        if b['keyword'] == '*NSET':
            assert not b['parameters'].get('GENERATE'), 'Explicit independent parser does not support GENERATE'
            nsets[b['parameters']['NSET']] = [int(x) for r in b['rows'] for x in r['values']]
    return {'blocks': blocks, 'nodes': nodes, 'nsets': nsets, 'text': text}


def blocks(d, keyword):
    return [b for b in d['blocks'] if b['keyword'] == keyword]


def common(d):
    return {
        'node_count': len(d['nodes']),
        'all_node_z_zero': all(p[2] == 0 for p in d['nodes'].values()),
        'element_type_counts': dict(collections.Counter({b['parameters']['TYPE']: sum(len(q['rows']) for q in blocks(d, '*ELEMENT') if q['parameters']['TYPE'] == b['parameters']['TYPE']) for b in blocks(d, '*ELEMENT')})),
        'solid_sections': [{'line': b['line'], 'elset': b['parameters']['ELSET'], 'thickness_mm': float(b['rows'][0]['values'][0])} for b in blocks(d, '*SOLID SECTION')],
        'elastic': [{'line': b['line'], 'E_MPa': float(b['rows'][0]['values'][0]), 'nu': float(b['rows'][0]['values'][1])} for b in blocks(d, '*ELASTIC')],
        'steps': [{'line': b['line'], 'parameters': b['parameters']} for b in blocks(d, '*STEP')],
        'explicit_nlgeom': any('NLGEOM' in b['parameters'] for b in blocks(d, '*STEP')),
    }


def dat(path):
    out, current, time = [], None, None
    for lineno, line in enumerate(read(path).splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        try:
            nums = [float(x.replace('D', 'E')) for x in s.split()]
        except ValueError:
            m = re.search(r'\btime\s+([+\-\d.Ee]+)', s)
            if m:
                time = float(m.group(1))
            current = {'header': s.lower(), 'line': lineno, 'time': time, 'rows': []}
            out.append(current)
        else:
            if current:
                current['rows'].append({'line': lineno, 'values': nums})
    return out


def select(ds, header, time=None):
    found = [x for x in ds if header in x['header'] and (time is None or x['time'] == time)]
    assert found, (header, time)
    return found[-1]


def nodal(block):
    rows = block['rows']
    assert all(len(r['values']) == 4 for r in rows), block['header']
    result = {int(r['values'][0]): r['values'][1:] for r in rows}
    assert len(result) == len(rows), 'Repeated node IDs in independent nodal parse'
    return result


def load_rows(d):
    return [(int(r['values'][0]), int(r['values'][1]), float(r['values'][2])) for b in blocks(d, '*CLOAD') for r in b['rows']]


def resultant(nodes, fs, origin=(0., 0.)):
    fx = math.fsum(v[0] for v in fs.values())
    fy = math.fsum(v[1] for v in fs.values())
    moment = math.fsum((nodes[n][0]-origin[0])*f[1] - (nodes[n][1]-origin[1])*f[0] for n, f in fs.items())
    return {'Fx_N_per_mm': fx, 'Fy_N_per_mm': fy, 'Mz_Nmm_per_mm': moment}


def load_forces(d):
    fs = collections.defaultdict(lambda: [0., 0., 0.])
    for n, dof, value in load_rows(d):
        fs[n][dof-1] += value
    return dict(fs)


def without_cload(d):
    return [(b['keyword'], b['parameters'], [r['values'] for r in b['rows']]) for b in d['blocks'] if b['keyword'] != '*CLOAD']


def audit_l2():
    case = load(PACK / 'cases/L2_yfs_matrix.json')
    entries = []
    for div in (8, 12, 18):
        paths = [ROOT/f'm37-results/runs/L2/L2_P02_d{div}.inp', ROOT/f'm37-diag-p02/L2_P02_d{div}_clipped.inp']
        decks = [deck(p) for p in paths]
        for variant, p, d in zip(('original', 'clipped'), paths, decks):
            meta = load(p.with_suffix('.meta.json'))
            raw = dat(p.with_suffix('.dat'))
            rf_block = select(raw, 'forces (fx,fy,fz) for set fixed')
            rf = nodal(rf_block)
            fixed = d['nsets']['FIXED']
            assert set(rf) == set(fixed)
            y30 = meta['geometry_check']['point_30deg'][1]
            rinner = meta['geometry_check']['rf'] - case['model']['rim_thickness_in_m'] * meta['m']
            half = 3*math.pi/meta['point']['z']
            groups = collections.Counter()
            for n in fixed:
                x, y, _ = d['nodes'][n]
                if abs(math.hypot(x, y)-rinner) < 1e-7:
                    groups['inner_arc_including_corners'] += 1
                elif abs(math.atan2(x, y)-half) < 1e-7:
                    groups['right_radial_cut_excluding_corners'] += 1
                elif abs(math.atan2(x, y)+half) < 1e-7:
                    groups['left_radial_cut_excluding_corners'] += 1
                else:
                    groups['unclassified'] += 1
            loads = load_forces(d)
            L0, L30 = resultant(d['nodes'], loads), resultant(d['nodes'], loads, (0., y30))
            R0, R30 = resultant(d['nodes'], rf), resultant(d['nodes'], rf, (0., y30))
            fn = math.hypot(L0['Fx_N_per_mm'], L0['Fy_N_per_mm'])
            nominal = meta['load_point'][0]*L0['Fy_N_per_mm']-(meta['load_point'][1]-y30)*L0['Fx_N_per_mm']
            entries.append({
                'variant': variant, 'div': div, 'inp': str(p.relative_to(ROOT)),
                'input': common(d), 'fixed_node_count': len(fixed), 'fixed_geometry': dict(groups),
                'fixed_inner_radius_mm': rinner, 'fixed_radial_half_angle_rad': half,
                'boundaries': blocks(d, '*BOUNDARY'),
                'load_node_count': len(loads), 'load_origin': L0, 'load_30deg_neutral': L30,
                'load_magnitude_N_per_mm': fn, 'load_to_intended_Fn_ratio': fn/meta['Fn_per_b'],
                'load_to_nominal_point_moment_ratio': L30['Mz_Nmm_per_mm']/nominal,
                'reaction_origin': R0, 'reaction_30deg_neutral': R30, 'raw_RF_header_line': rf_block['line'],
                'force_balance_rel': math.hypot(R0['Fx_N_per_mm']+L0['Fx_N_per_mm'], R0['Fy_N_per_mm']+L0['Fy_N_per_mm'])/fn,
                'moment_balance_rel_origin': abs(R0['Mz_Nmm_per_mm']+L0['Mz_Nmm_per_mm'])/abs(L0['Mz_Nmm_per_mm']),
                'moment_balance_rel_30deg_neutral': abs(R30['Mz_Nmm_per_mm']+L30['Mz_Nmm_per_mm'])/abs(L30['Mz_Nmm_per_mm']),
                'only_CLOAD_semantic_difference_between_variants': without_cload(decks[0]) == without_cload(decks[1]),
                'meta_load_patch_length_mm': meta.get('diagnostic_load', {}).get('integrated_length_mm', meta['load_patch_length']),
            })
    return entries


def expand_boundary(d, b):
    out = {}
    for row in b['rows']:
        v = row['values']
        ns = [int(v[0])] if v[0].isdigit() else d['nsets'][v[0].upper()]
        for n in ns:
            for dof in range(int(v[1]), int(v[2])+1):
                key = (n, dof)
                assert key not in out, ('duplicate boundary', key)
                out[key] = float(v[3]) if len(v) > 3 else 0.
    return out


def audit_l3():
    p = ROOT/'m37-results/runs/L3/L3_C001_G1_ph10_d12.inp'
    d = deck(p)
    meta = load(p.with_suffix('.meta.json'))
    raw = dat(p.with_suffix('.dat'))
    master, = d['nsets']['PMASTER']
    pb = {n for n, xyz in d['nodes'].items() if abs(math.hypot(*xyz[:2])-meta['rbore1']) < 1e-7}
    dependents = set()
    equation_errors = []
    max_coef_error = 0.
    for b in blocks(d, '*EQUATION'):
        assert b['rows'][0]['values'] == ['2']
        terms = [v for r in b['rows'][1:] for v in r['values']]
        assert len(terms) == 6
        n, dof, coef, mn, mdof, mcoef = int(terms[0]), int(terms[1]), float(terms[2]), int(terms[3]), int(terms[4]), float(terms[5])
        expected = d['nodes'][n][1]/meta['rbore1'] if dof == 1 else -d['nodes'][n][0]/meta['rbore1']
        if n not in pb or n == master or coef != 1 or mn != master or mdof != 2 or (n, dof) in dependents:
            equation_errors.append(b['line'])
        max_coef_error = max(max_coef_error, abs(mcoef-expected))
        dependents.add((n, dof))
    bc0, bc1, bc2 = blocks(d, '*BOUNDARY')
    initial = expand_boundary(d, bc0)
    closure = expand_boundary(d, bc1)
    final = expand_boundary(d, bc2)
    all_pb_dofs = {(n, dof) for n in pb for dof in (1, 2)}
    free = all_pb_dofs - dependents - set(final)
    assert not (dependents & set(final))
    assert initial == final
    assert free == {(master, 2)}
    assert set(closure) == {(master, 2)}
    meta_coordinate_error = max(math.dist(d['nodes'][int(n)][:2], xy) for n, xy in meta['wbore_xy'].items())
    cl = load_forces(d)
    torque = resultant(d['nodes'], cl)['Mz_Nmm_per_mm']
    times = sorted({b['time'] for b in raw if 'displacements (vx,vy,vz) for set pmaster' in b['header']})
    values = []
    prev = None
    for t in times:
        ub = select(raw, 'displacements (vx,vy,vz) for set pmaster', t)
        rb = select(raw, 'forces (fx,fy,fz) for set wbore', t)
        cb = select(raw, 'total surface force', t)
        nb = select(raw, 'center of gravity and mean normal', t)
        mb = select(raw, 'moment about the center of gravity', t)
        ab = select(raw, 'area,  normal force', t)
        u = nodal(ub)[master]
        rf = nodal(rb)
        assert set(rf) == set(d['nsets']['WBORE'])
        contact, = [r['values'] for r in cb['rows']]
        cg_normal, = [r['values'] for r in nb['rows']]
        area_n_s, = [r['values'] for r in ab['rows']]
        mcg, = [r['values'] for r in mb['rows']]
        reaction = resultant(d['nodes'], rf, meta['O2'])
        cx, cy = meta['O2']
        contact_m_o2 = contact[5]-(cx*contact[1]-cy*contact[0])
        stage_fraction = t-1
        nominal_t = stage_fraction*meta['T_per_b']
        nominal_fn = stage_fraction*meta['Fn_per_b']
        delta = -u[1]/meta['rbore1']*meta['rb1']*1000
        secant = nominal_fn/delta
        item = {
            'time': t, 'step2_load_fraction': stage_fraction,
            'raw_lines': {'PMASTER_U': ub['line'], 'WBORE_RF': rb['line'], 'contact_F_M0': cb['line'], 'contact_CG_mean_normal': nb['line'], 'contact_MCG': mb['line'], 'contact_area_normal_shear': ab['line']},
            'PMASTER_displacement_mm': u, 'delta_LOA_um': delta,
            'applied_nominal_T_Nmm_per_mm': nominal_t, 'ideal_Fn_N_per_mm': nominal_fn,
            'contact_force_moment_global': contact, 'contact_cg_mean_normal': cg_normal,
            'contact_area_normal_shear': area_n_s,
            'contact_Mz_about_wheel_center': contact_m_o2,
            'WBORE_reaction_about_wheel_center': reaction,
            'wheel_force_balance_rel': math.hypot(reaction['Fx_N_per_mm']-contact[0], reaction['Fy_N_per_mm']-contact[1])/math.hypot(contact[0], contact[1]),
            'wheel_moment_balance_rel': abs(reaction['Mz_Nmm_per_mm']-contact_m_o2)/abs(contact_m_o2),
            'pinion_contact_moment_vs_applied_rel': abs(contact[5]-nominal_t)/nominal_t,
            'wheel_reaction_vs_ideal_ratio_rel': abs(abs(reaction['Mz_Nmm_per_mm'])-nominal_t*meta['rb2']/meta['rb1'])/(nominal_t*meta['rb2']/meta['rb1']),
            'normal_scalar_vs_ideal_Fn_rel': abs(abs(area_n_s[1])-nominal_fn)/nominal_fn,
            'printed_normal_scalar_minus_F_dot_mean_normal': area_n_s[1]-math.fsum(contact[i]*cg_normal[i+3] for i in range(3)),
            'printed_Mcg_minus_shifted_Mz': mcg[2]-(contact[5]-(cg_normal[0]*contact[1]-cg_normal[1]*contact[0])),
            'secant_from_undeformed_reference_N_per_mm_um': secant,
            'incremental_chord_from_previous_output_N_per_mm_um': None if prev is None else (nominal_fn-prev['ideal_Fn_N_per_mm'])/(delta-prev['delta_LOA_um']),
        }
        values.append(item)
        prev = item
    return {'inp': str(p.relative_to(ROOT)), 'input': common(d), 'master_node': master,
            'master_coordinate_mm': d['nodes'][master], 'pinion_bore_node_count': len(pb),
            'wheel_bore_node_count': len(d['nsets']['WBORE']),
            'equation_count': len(dependents), 'equation_error_lines': equation_errors,
            'equation_coefficient_max_abs_rounding_difference': max_coef_error,
            'dependent_DOF_conflicts_with_final_boundary': [],
            'step2_remaining_pinion_bore_DOF': [[master, 2]],
            'boundary_blocks': [bc0, bc1, bc2],
            'initial_and_final_boundary_semantically_equal': initial == final,
            'closure_prescribed_master_y_mm': closure[(master, 2)],
            'CLOAD_full_torque_Nmm_per_mm': torque,
            'meta_WBORE_coordinates_max_difference_mm': meta_coordinate_error,
            'outputs': values}


def main():
    l2 = audit_l2()
    l3 = audit_l3()
    expected = load(PACK/'expected/L3_C001_G1.json')
    comparison = load(ROOT/'m37-diag-p02/comparison.json')
    vals = expected['values']
    low_load = (vals['line_load']['value']/100)**.25
    for rel in ('scripts/cases.py', 'scripts/inp_writer.py', 'scripts/ccx_io.py', 'scripts/post.py', 'scripts/study.py', 'expected/L2_yfs_matrix.json', 'cases/L3_C001_G1.json'):
        read(PACK/rel)
    read(ROOT/'m37-diag-p02/diagnostic-controller.py')
    read(OUT/'sources/Dhondtguido--CalculiX/doc/CalculiX.tex')
    read(OUT/'sources/Dhondtguido--CalculiX/src/printoutcontact.f')
    read(Path(__file__))
    result = {
        'schema': 'm37.model-definition-independent-audit/v1',
        'scope': 'Read-only audit of existing P02 original/clipped decks and existing ph10; no source, result or gate changes; no solves.',
        'method': 'Independent stdlib parser; supplied FEA package is read only and not imported.',
        'acceptance_effect': 'NONE; M37 remains unaccepted. Low-load reference is OPEN_DEFINITION_QUESTION.',
        'L2_P02': l2, 'L3_ph10': l3,
        'L2_clipped_existing_convergence_report': comparison,
        'L3_reference_definition': {
            'line_load_N_per_mm': vals['line_load']['value'],
            'c_prime_th_CB': vals['c_prime_th_CB'], 'c_prime_ISO': vals['c_prime_ISO'],
            'c_gamma_alpha_th': vals['c_gamma_alpha_th'], 'c_gamma_alpha_ISO': vals['c_gamma_alpha_ISO'],
            'low_load_factor_arithmetic_only': low_load,
            'low_load_reference_status': 'OPEN_DEFINITION_QUESTION; arithmetic proximity does not authorize changing reference or acceptance gates.',
            'supplied_notes_are_author_claims': expected['notes']},
        'official_contact_definition': {
            'provenance': 'Official-source location supplied by sibling audit; local pinned source directly read and hashed by this audit. Not treated as a numerical validation of the installed binary.',
            'commit': '9e4fc4a856259ebfae0d7a2659c2c4a8030fe542',
            'url': 'https://github.com/Dhondtguido/CalculiX/blob/9e4fc4a856259ebfae0d7a2659c2c4a8030fe542/src/printoutcontact.f#L179',
            'definition': 'CF is the selected slave surface resultant; M0 uses current coordinates co+vold; mean normal is area-averaged and not renormalized. Last normal-force scalar is total resultant F dot mean normal, not integral pressure magnitude or ideal T/rb.',
        },
        'source_files': SOURCES,
    }
    out = OUT/'MODEL-DEFINITION-AUDIT.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
          'L2': [{k: r[k] for k in ('variant','div','fixed_node_count','fixed_geometry','load_to_nominal_point_moment_ratio','force_balance_rel','moment_balance_rel_origin','moment_balance_rel_30deg_neutral','only_CLOAD_semantic_difference_between_variants')} for r in l2],
          'L3_constraints': {k: l3[k] for k in ('pinion_bore_node_count','wheel_bore_node_count','equation_count','equation_error_lines','equation_coefficient_max_abs_rounding_difference','CLOAD_full_torque_Nmm_per_mm')},
          'L3_outputs': l3['outputs']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
