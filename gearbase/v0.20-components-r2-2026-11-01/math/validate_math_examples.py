"""Finite mathematical examples only; never a product or engineering acceptance gate.

Requires Python 3 and jsonschema. Imports no GearBase product modules. Schema
checks concern draft artifact shape; the numeric examples use independent,
explicit SI-valued equations rather than executing the plugin expression strings.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parent


def canonical_hash(obj):
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)


def compare(actual, expected, path="result"):
    if isinstance(expected, dict):
        for key, value in expected.items():
            if key.endswith("_between"):
                number = actual[key[:-8]]
                assert value[0] < number < value[1], (path, key, number, value)
            else:
                assert key in actual, (path, "missing", key)
                compare(actual[key], value, path + "." + key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), (path, actual, expected)
        for i, (a, b) in enumerate(zip(actual, expected)):
            compare(a, b, f"{path}[{i}]")
    elif isinstance(expected, bool) or isinstance(expected, str):
        assert actual == expected, (path, actual, expected)
    else:
        assert close(actual, expected), (path, actual, expected)


def evaluate(case):
    p, kind = case["inputs"], case["kind"]
    if kind == "signed_gear":
        wb, tb = p["omega_a"] / p["i"], -p["i"] * p["tau_a"]
        return dict(omega_b=wb, tau_b=tb, power_residual_W=p["tau_a"] * p["omega_a"] + tb * wb)
    if kind == "power_not_effort":
        effort = p["tau_b"] + p["i"] * p["tau_a"]
        return dict(power_residual_W=p["tau_a"] * p["omega_a"] + p["tau_b"] * p["omega_b"], effort_residual_Nm=effort, decision="reject_ideal_effort" if not close(effort, 0) else "accept_ideal_effort")
    if kind == "planetary":
        k = p["z_r"] / p["z_s"]
        wc = (p["omega_s"] + k * p["omega_r"]) / (1 + k)
        tr, tc = k * p["tau_s"], -(1 + k) * p["tau_s"]
        return dict(omega_c=wc, tau_r=tr, tau_c=tc, power_residual_W=p["tau_s"] * p["omega_s"] + tr * p["omega_r"] + tc * wc, torque_residual_Nm=p["tau_s"] + tr + tc)
    if kind == "free_ring":
        outputs = [(p["omega_s"] + p["k"] * wr) / (1 + p["k"]) for wr in p["possible_omega_r"]]
        assert len(set(outputs)) > 1
        return dict(possible_omega_c=outputs, decision="blocked_missing_ring_boundary")
    if kind == "planetary_bad_rates":
        residual = p["omega_s"] + p["k"] * p["omega_r"] - (1 + p["k"]) * p["omega_c"]
        return dict(willis_residual_s_inv=residual, decision="reject_conflicting_boundaries" if not close(residual, 0) else "consistent")
    if kind == "planetary_macro":
        i1, i2 = 1 + p["k1"], 1 + p["k2"]
        mid, ts2 = p["omega_input"] / i1, i1 * p["tau_input"]
        out, tc2 = mid / i2, -i2 * ts2
        rings = [p["k1"] * p["tau_input"], p["k2"] * ts2]
        assert close(p["tau_input"] + sum(rings) + tc2, 0)
        return dict(i_total=i1 * i2, omega_mid=mid, omega_output=out, tau_second_sun=ts2, tau_output=tc2, ring_reactions_into_gear=rings, power_residual_W=p["tau_input"] * p["omega_input"] + tc2 * out, gear_reduction_stages=2, mesh_interfaces=2 * (p["n_planets1"] + p["n_planets2"]))
    if kind == "worm_domain":
        gamma, rho_k, rho_s = (math.radians(p[k]) for k in ("gamma_deg", "rho_k_deg", "rho_s_deg"))
        forward = math.tan(gamma) / math.tan(gamma + rho_k)
        raw_back = math.tan(gamma - rho_k) / math.tan(gamma)
        return dict(eta_forward=forward, raw_eta_back=raw_back, raw_eta_back_negative=raw_back < 0, static_lock_screen=gamma <= rho_s, decision="blocked_static_mode" if gamma <= rho_k else "backdrive_sliding_model_available")
    if kind == "screw_four_port":
        a = p["h"] * p["lead_m"] / (2 * math.pi)
        vs = p["v_nut"] + a * (p["omega_screw"] - p["omega_nut"])
        fs = p["force_screw_into"]
        ts, tn, fn = -a * fs, a * fs, -fs
        power = ts * p["omega_screw"] + tn * p["omega_nut"] + fs * vs + fn * p["v_nut"]
        return dict(v_screw_m_s=vs, tau_nut_into_Nm=tn, tau_screw_into_Nm=ts, force_nut_into_N=fn, power_residual_W=power, velocity_residual_m_s=vs - p["v_nut"] - a * (p["omega_screw"] - p["omega_nut"]))
    if kind == "screw_friction":
        lead_angle = math.atan(p["lead_m"] / (math.pi * p["d_m"]))
        alpha, mu = math.radians(p["normal_half_angle_deg"]), p["mu_kinetic"]
        rho = math.atan(mu / math.cos(alpha))
        ideal = p["axial_force_N"] * p["lead_m"] / (2 * math.pi)
        required = p["axial_force_N"] * p["d_m"] / 2 * math.tan(lead_angle + rho)
        eta = ideal / required
        eta_expanded = math.tan(lead_angle) * (math.cos(alpha) - mu * math.tan(lead_angle)) / (math.cos(alpha) * math.tan(lead_angle) + mu)
        assert close(eta, eta_expanded)
        return dict(lead_angle_deg=math.degrees(lead_angle), friction_angle_deg=math.degrees(rho), torque_ideal_Nm=ideal, torque_raise_Nm=required, eta=eta, torque_raise_greater_than_ideal=required > ideal, reverse_sliding_unavailable=lead_angle <= rho)
    if kind == "ordered_losses":
        def chain(stages):
            speeds, speed = [], p["omega_input"]
            for stage in stages:
                speeds.append(speed)
                speed /= stage["ratio"]
            torque, records = p["tau_output"], []
            for stage, win in reversed(list(zip(stages, speeds))):
                delivered, drag = torque, stage["Tc"] + stage["b"] * win
                torque = delivered / stage["ratio"] + drag
                loss = stage["Tc"] * abs(win) + stage["b"] * win ** 2
                assert close(torque * win - delivered * win / stage["ratio"], loss)
                records.append(dict(input_speed_s_inv=win, input_torque_Nm=torque, delivered_torque_Nm=delivered, loss_W=loss))
            return speed, torque, sum(r["loss_W"] for r in records), list(reversed(records))
        ab, ba = chain([p["stage_A"], p["stage_B"]]), chain([p["stage_B"], p["stage_A"]])
        assert close(ab[0], ba[0]) and not close(ab[2], ba[2])
        return dict(i_total=p["omega_input"] / ab[0], output_power_W=p["tau_output"] * ab[0], loss_A_then_B_W=ab[2], loss_B_then_A_W=ba[2], motor_torque_A_then_B_Nm=ab[1], motor_torque_B_then_A_Nm=ba[1], stages_A_then_B=ab[3], stages_B_then_A=ba[3], decision="preserve_order")
    if kind == "counts":
        gears = len(p["two_stage_planetary_planets"]) + p["extra_gear_pairs"]
        conv = p["terminal_conversions"]
        return dict(gear_reduction_stages=gears, top_level_plugin_nodes=1 + p["extra_gear_pairs"] + conv, expanded_leaf_plugin_nodes=gears + conv, assembly_accessories=0, mesh_interfaces=2 * sum(p["two_stage_planetary_planets"]) + p["extra_gear_pairs"], mesh_families=2 * len(p["two_stage_planetary_planets"]) + p["extra_gear_pairs"], terminal_conversions=conv, passes_gear_basis=gears <= p["stage_limit"], passes_gear_plus_terminal_basis=gears + conv <= p["stage_limit"])
    if kind == "port_type":
        return dict(decision="reject_port_domain_mismatch" if p["left_domain"] != p["right_domain"] else "compatible_domain")
    if kind == "rotation_matrix":
        r = p["R"]
        determinant = sum(r[0][i] * (r[1][(i + 1) % 3] * r[2][(i + 2) % 3] - r[1][(i + 2) % 3] * r[2][(i + 1) % 3]) for i in range(3))
        orthogonal = all(close(sum(r[k][i] * r[k][j] for k in range(3)), float(i == j)) for i in range(3) for j in range(3))
        return dict(det=determinant, orthogonal=orthogonal, decision="valid_SO3" if orthogonal and close(determinant, 1) else "reject_not_SO3")
    if kind == "axis_layout":
        a, b = p["direction_a"], p["direction_b"]
        assert close(sum(x*x for x in a), 1) and close(sum(x*x for x in b), 1)
        assert close(abs(sum(x*y for x, y in zip(a, b))), 1), "this fixture is the parallel-axis branch"
        d = [y - x for x, y in zip(p["origin_a"], p["origin_b"])]
        cross = [d[1]*a[2]-d[2]*a[1], d[2]*a[0]-d[0]*a[2], d[0]*a[1]-d[1]*a[0]]
        distance = math.sqrt(sum(x*x for x in cross))
        angle = math.degrees(math.acos(max(-1, min(1, sum(x*y for x, y in zip(a, b))))))
        return dict(shaft_angle_deg=angle, axis_distance_m=distance, decision="reject_direct_shaft_connection" if not close(distance, 0) else "coaxial")
    if kind == "thermal":
        return dict(total_energy_residual_W=p["dissipation_W"] + p["heat_into_W"], thermal_power_into_W=p["heat_into_W"], decision="do_not_multiply_temperature_by_heat_flow")
    if kind == "rpm_bridge":
        rate = 2 * math.pi * p["n_rpm"] / 60
        return dict(omega_rad_s=rate, power_W=p["tau_Nm"] * rate, wrong_power_if_rev_s_is_rad_s_W=p["tau_Nm"] * p["n_rpm"] / 60, error_factor=2 * math.pi)
    if kind == "power_direction":
        pa, pb = p["tau_a"] * p["omega_a"], p["tau_b"] * p["omega_b"]
        assert close(pa + pb, 0) and close(p["omega_a"] - p["i"] * p["omega_b"], 0)
        return dict(power_a_W=pa, power_b_W=pb, drive_port="a" if pa > 0 else "b", decision="select_by_power_not_speed_sign")
    if kind == "static_friction":
        needed = p["tau_a"] + p["tau_b"] / p["i"]
        feasible = abs(needed) <= p["static_threshold_input_Nm"]
        return dict(required_friction_Nm=needed, feasible=feasible, decision="holding_within_synthetic_bound" if feasible else "holding_not_established")
    raise AssertionError("unknown mathematical example kind: " + kind)


def manifest_references(manifests):
    ids = {p["id"] for p in manifests}
    assert len(ids) == len(manifests)
    for plugin in manifests:
        declared = set(plugin["parameters"])
        for name, parameter in plugin["parameters"].items():
            for index, predicate in enumerate(parameter["domain"]):
                parameter_domain_references(predicate, declared, f"{plugin['id']}.parameters.{name}.domain[{index}]")
        port_ids = [p["id"] for p in plugin["ports"]]
        assert len(port_ids) == len(set(port_ids))
        for port in plugin["ports"]:
            for quantity in port["variables"].values():
                assert quantity["name"] not in declared
                declared.add(quantity["name"])
        for quantity in plugin["local_symbols"]:
            assert quantity["name"] not in declared
            declared.add(quantity["name"])
        equations = {e["id"] for e in plugin["equations"]}
        assert len(equations) == len(plugin["equations"])
        for equation in plugin["equations"]:
            tree = ast.parse(equation["expr"], mode="eval")
            free = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - {"pi", "rad", "tan"}
            assert free == set(equation["variables"]), (plugin["id"], equation["id"], free, equation["variables"])
            assert free <= declared
        for mode in plugin["modes"]:
            assert set(mode["equation_refs"]) <= equations
            assert set(mode["causal_inputs"] + mode["causal_outputs"]) <= declared
        for capability in plugin["capabilities"]:
            if capability["evidence_state"] == "VERIFIED":
                assert capability["evidence_scope"] != "none" and capability["evidence_refs"]
        if "decomposition" in plugin:
            for child in plugin["decomposition"]["children"]:
                assert child["plugin_ref"] in ids
                for binding in child["parameters"].values():
                    assert binding["from_parameter"] in plugin["parameters"]


class DomainContractError(ValueError):
    pass


def parameter_domain_references(predicate, parameter_names, context):
    """Check numeric predicate AST only; source/notes are never token-scanned.

    Domain strings are comparisons joined with and/or. Numeric arithmetic,
    declared parameter identifiers and pi/rad constants are supported. Natural
    language, calls, attributes, containers and string literals are rejected.
    This checks syntax/references, not dimensions, truth or satisfiability.
    """
    try:
        tree = ast.parse(predicate, mode="eval")
    except (SyntaxError, TypeError) as exc:
        raise DomainContractError(f"{context}: unsupported_domain_syntax") from exc
    allowed = (ast.Expression, ast.Compare, ast.BoolOp, ast.BinOp, ast.UnaryOp,
               ast.Name, ast.Load, ast.Constant, ast.And, ast.Or,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.UAdd, ast.USub,
               ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise DomainContractError(f"{context}: unsupported_domain_syntax:{type(node).__name__}")
        if isinstance(node, ast.Constant) and (isinstance(node.value, bool) or not isinstance(node.value, (int, float)) or not math.isfinite(node.value)):
            raise DomainContractError(f"{context}: non_numeric_domain_literal")
        if isinstance(node, ast.BoolOp) and not all(isinstance(value, (ast.Compare, ast.BoolOp)) for value in node.values):
            raise DomainContractError(f"{context}: domain_requires_comparisons")
    if not isinstance(tree.body, (ast.Compare, ast.BoolOp)):
        raise DomainContractError(f"{context}: domain_requires_comparisons")
    free = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} - {"pi", "rad"}
    missing = free - parameter_names
    if missing:
        raise DomainContractError(f"{context}: undeclared_domain_symbols:{','.join(sorted(missing))}")


class ProvenanceReferenceError(ValueError):
    pass


def ir_provenance_references(suite):
    """Register existing draft-artifact IDs; performs no network compilation."""
    plugins = {plugin["id"]: plugin for plugin in suite["plugin_manifests"]}
    registry = set()

    def register(instance_id, plugin_id, ancestors=()):
        if plugin_id in ancestors:
            raise ProvenanceReferenceError("recursive draft decomposition: " + plugin_id)
        plugin = plugins[plugin_id]
        registry.update(instance_id + "." + equation["id"] for equation in plugin["equations"])
        decomposition = plugin.get("decomposition", {})
        for field in ("internal_boundaries", "internal_connections"):
            registry.update(instance_id + "." + item["id"] for item in decomposition.get(field, []))
        for child in decomposition.get("children", []):
            register(instance_id + "." + child["id"], child["plugin_ref"], ancestors + (plugin_id,))

    source, ir = suite["network_source_example"], suite["compiled_ir_example"]
    for node in source["nodes"]:
        register(node["id"], node["plugin_ref"])
    for field in ("boundaries", "connections"):
        registry.update(source["id"] + "." + item["id"] for item in source[field])
    references = [("residual_refs", reference) for reference in ir["residual_refs"]]
    for index, assignment in enumerate(ir["assignments"]):
        references.extend((f"assignments[{index}].source_equation_refs", reference) for reference in assignment["source_equation_refs"])
    for context, reference in references:
        if reference not in registry:
            raise ProvenanceReferenceError(f"{context}: undeclared_provenance_reference:{reference}")
    return dict(registered_ids=len(registry), checked_ir_references=len(references))


def main():
    schema = json.loads((ROOT / "component-contract.json").read_text(encoding="utf-8"))
    suite = json.loads((ROOT / "math-examples.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, callback):
        try:
            observed = callback()
            checks.append(dict(id=name, status="passed", observed=observed))
        except Exception as exc:
            checks.append(dict(id=name, status="failed", error=f"{type(exc).__name__}: {exc}"))

    validator = jsonschema.Draft202012Validator(schema)
    check("schema_is_valid_draft2020_12", lambda: jsonschema.Draft202012Validator.check_schema(schema))
    for plugin in suite["plugin_manifests"]:
        check("shape:" + plugin["id"], lambda p=plugin: validator.validate(p))
    for name, definition in [("network_source_example", "networkSource"), ("compiled_ir_example", "compiledIR"), ("projection_example", "projection")]:
        sub_schema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/" + definition}
        check("shape:" + name, lambda n=name, s=sub_schema: jsonschema.Draft202012Validator(s).validate(suite[n]))
    check("manifest_symbol_and_reference_consistency", lambda: manifest_references(suite["plugin_manifests"]))
    check("ir_provenance_reference_consistency", lambda: ir_provenance_references(suite))

    def domain_must_reject(predicate, expected_error):
        probe = copy.deepcopy(suite["plugin_manifests"])
        probe[-1]["parameters"]["first_z_r"]["domain"] = [predicate]
        try:
            manifest_references(probe)
        except DomainContractError as exc:
            assert expected_error in str(exc), str(exc)
            return dict(rejected_predicate=predicate, reason=str(exc))
        raise AssertionError("invalid parameter domain was accepted")
    check("reject_unbound_macro_parameter_domain", lambda: domain_must_reject("z_r > z_s", "undeclared_domain_symbols:z_r,z_s"))
    check("reject_parameter_domain_prefix_collision", lambda: domain_must_reject("first_z_s_unbound > 0", "undeclared_domain_symbols:first_z_s_unbound"))
    check("reject_natural_language_in_parameter_domain", lambda: domain_must_reject("positive ring teeth required", "unsupported_domain_syntax"))

    def stale_provenance_must_reject():
        observed = []
        for index, stale in ((0, "P2.p1.ring_fixed"), (1, "P2.p2.ring_fixed")):
            probe = copy.deepcopy(suite)
            probe["compiled_ir_example"]["assignments"][index]["source_equation_refs"][1] = stale
            try:
                ir_provenance_references(probe)
            except ProvenanceReferenceError as exc:
                assert "undeclared_provenance_reference:" + stale in str(exc), str(exc)
                observed.append(dict(rejected_reference=stale, reason=str(exc)))
            else:
                raise AssertionError("stale IR provenance alias was accepted: " + stale)
        return observed
    check("reject_undeclared_fixed_ring_provenance_aliases", stale_provenance_must_reject)

    def hash_links():
        assert suite["network_source_example"]["plugin_lock_sha256"] == canonical_hash(suite["plugin_lock_example"])
        assert suite["compiled_ir_example"]["source_sha256"] == canonical_hash(suite["network_source_example"])
        assert suite["compiled_ir_example"]["unit_catalog_sha256"] == canonical_hash(suite["unit_catalog_example"])
        assert suite["projection_example"]["compiled_ir_sha256"] == canonical_hash(suite["compiled_ir_example"])
        for row, manifest in zip(suite["plugin_lock_example"]["plugin_versions"], suite["plugin_manifests"]):
            assert row["id"] == manifest["id"] and row["content_sha256"] == canonical_hash(manifest)
        changed = copy.deepcopy(suite["network_source_example"])
        changed["nodes"][0]["parameters"]["first_z_s"]["value"] += 1
        assert canonical_hash(changed) != suite["compiled_ir_example"]["source_sha256"]
    check("versioned_projection_hash_links_and_changed_source", hash_links)

    def must_reject(instance, definition="pluginManifest"):
        local = {"$defs": schema["$defs"], "$ref": "#/$defs/" + definition}
        assert list(jsonschema.Draft202012Validator(local).iter_errors(instance)), "malformed object was accepted"
    bad_rate = copy.deepcopy(suite["plugin_manifests"][0])
    bad_rate["ports"][0]["variables"]["flow"]["unit"] = "rpm"
    check("reject_rpm_substituted_for_angular_velocity", lambda: must_reject(bad_rate))
    bad_macro = copy.deepcopy(suite["plugin_manifests"][-1])
    bad_macro["stage_accounting"]["local_gear_reduction_stages"] = 1
    check("reject_macro_local_stage_double_count", lambda: must_reject(bad_macro))
    bad_source = copy.deepcopy(suite["network_source_example"])
    bad_source["results"] = {"output_speed": 5}
    check("reject_results_in_source_envelope", lambda: must_reject(bad_source, "networkSource"))
    bad_query = copy.deepcopy(suite["network_source_example"])
    del bad_query["query"]["limit_basis"]
    check("reject_missing_stage_count_basis", lambda: must_reject(bad_query, "networkSource"))

    for case in suite["cases"]:
        def run(c=case):
            observed = evaluate(c)
            compare(observed, c["expected"])
            return observed
        check("math:" + case["id"], run)

    failures = [c for c in checks if c["status"] != "passed"]
    result = dict(schema="gearbase.component-math-example-results/0.1-draft", classification="mathematical_examples_only", engineering_acceptance=False, product_modules_imported=False, product_gates_run=False, baseline_commit=suite["baseline_commit"], file_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ["component-contract.json", "math-examples.json", "MATH-DESIGN.md", "validate_math_examples.py"]}, checks=checks, passed=len(checks)-len(failures), failed=len(failures), limitations=["finite point examples and draft artifact shape only", "no implemented network compiler, DAE solver or engineering rating tested", "fixed-ring reaction names are preserved but typed mount/wrench binding remains OPEN", "positive results do not certify strength, life, thermal, backdrive safety, geometry or release readiness"])
    (ROOT / "math-example-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["classification", "engineering_acceptance", "passed", "failed"]}))
    for failure in failures:
        print(json.dumps(failure, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
