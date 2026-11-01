# Finite nearest-feasible editing (v0.19)

`gearmath.product.nearest_feasible_edit.propose` and the listed read-only MCP
`nearest_feasible_edit` tool find the closest supported joint combination to a
user-requested combination. They evaluate the explicit finite `system_optimize`
domain against the source-owned rating, shaft, bearing and key checks. They do
not edit the source, write design state, or issue a `gear_commit` token.

All four arguments are required: `design_doc`, `system_input`, `domain`, `request`.
`domain` has the existing finite joint declaration fields `objective`,
`max_combinations`, `hold_evidence`, `gear`, `shaft`, `bearing`; component records,
units, evidence and physical parameters remain explicit. Its legacy volume
objective is evaluated and retained as engineering context, but does not rank
nearest edits or break their ties. The Cartesian domain must fit both the caller's
bound and the evaluator's 10,000-combination hard limit.

An example request (IDs must exist in the supplied domain):

```json
{
  "target": {"gear": "requested-gear", "shaft": "requested-shaft", "bearing": "requested-bearing"},
  "metric": {
    "kind": "weighted_hamming",
    "weights": {"gear": "1", "shaft": "2", "bearing": "0.1"}
  },
  "constraints": {"pass_scopes": ["gear_rating", "shaft", "bearing", "key"]},
  "source": "User-declared selection and change costs"
}
```

This metric sums the weight of each axis whose candidate record ID differs from
the target. Positive weights are exact decimal **strings**, parsed as rational
numbers; booleans, numbers, NaN, zero, omitted weights and unsupported metrics
are rejected. Target IDs must be nonempty strings present in the domain. No
implicit numerical distance between mechanical dimensions is asserted.

The result includes every feasible combination in `(exact distance, IDs)` order,
`nearest` as its deterministic first record, and `ties` containing every record
at the exact minimum. `distance` is an integer or rational string (e.g. `31/10`),
not a rounded float. Distinct IDs with identical physics still count as distinct
catalogue choices. `target_feasible` distinguishes an existing feasible target
(distance zero) from an infeasible one. Completed evaluation with `nearest:null`
means this finite domain has no feasible combination. Blocked checks, missing
inputs or invalid certificates return `blocked` and never a proposed candidate.

`problem_sha256` binds the authoritative evaluator result (including source,
system input, full domain and validated certificate identities) and the exact
request. An optional `expected_problem_sha256` re-evaluates freshly and returns
`rejected_stale_proposal` if that identity changed. Invalid/replaced certificate
bytes block evaluation. This identity is a read-only comparison receipt, not
write authorization. Existing edit/preview/commit contracts remain unchanged.

The fresh 27-combination capability test independently evaluates the complete
Cartesian product using `design_check.check`, calculates rational distances and
compares every feasible record and exact tie. It also dispatches the real tool
through `mcp_server.py` JSON-RPC `tools/call` and checks certificate/stale/invalid
input cases:

```powershell
python -I -S -m unittest discover -s tests -p test_v019_nearest_feasible_edit.py
```

Scope: categorical finite cylindrical joint choices only. It supplies neither a
continuous nearest point nor missing physical inputs, external evidence,
real C001 engineering completion, or full-system gate3 closure.
