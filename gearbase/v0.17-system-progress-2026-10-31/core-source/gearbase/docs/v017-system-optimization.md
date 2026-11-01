# v0.17 finite cylindrical system optimization

`gearmath.product.system_optimize.optimize(design_doc, system_input, problem)` is
an additive finite capability probe. The problem explicitly supplies nonempty
gear, shaft/key and bearing axes, an objective, a Cartesian size limit and a
rationale for every held evidence entry. It accepts matching cylindrical
`pair_model` documents with source-owned factor recomputation selectors. No
input documents, fixtures, kernel formulas or limits are changed by the search.

The three axes contain records with unique `id` and nonempty `source`:

- `gear`: `inputs`, a patch of existing `m_n`, `b`, `z_1`, `z_2`, `x_1`, `x_2`, `beta` source leaves.
- `shaft`: complete `shafts` and `keys` lists, including explicit two-support geometry, loads, section material and safety limits.
- `bearing`: a complete `bearings` dictionary, retaining bearing IDs referenced by shafts, methods, loads, speed and required life.

The only objective is `gear_blank_plus_shaft_volume_mm3`. Gear blank volume is
`geo.volume` (`V_blank`) from the existing gear model; the new L2 system module
adds annular-cylinder volumes of explicit shaft segments in mm. It checks
positive, ordered nonoverlapping segments. The objective excludes bearing/key
volume, cost, housings and tooth-space removal. Capacity candidate records do
not constitute bearing envelope, bore compatibility or packaging verification.
The demo includes authored capacity records, not catalogue recommendations.

Gear safety/geometry, shaft section safety, bearing life and key checks all
use the existing `design_check.check` API. Each new call gets a fresh context.
Gear failure safely rejects every descendant combination; shaft/key failure
rejects all bearing descendants. Passing descendants undergo a bearing check
which freshly solves shaft loads. Every component record is schema checked before pruning. Required fields are
checked against canonical L2 signatures and section contracts; omitted supports,
material/safety fields, capacity/life fields and unknown design references are
blocked even under a rejected gear branch. Per-kind load requirements come
from canonical mesh/point/torque/line constructor signatures (with the existing
d_w adapter naming); line loads require x0/x1 rather than a point x. Deletion
matrices cover every required component/load/static/fatigue field, including
nested roller xy and modified-life fields. Shaft/bearing references must match.
Explicit bearing load overrides are blocked so that loads remain shaft-derived.
Null source leaves are blocked before pruning. Runtime missing, unconfirmed,
error or invalid-domain checks block the run; partial optima are discarded.
The result distinguishes a completed empty feasible set from a blocked search.

File evidence certificates are verified with canonical `MS.verify_certificates`
before pruning, for every candidate source document and again before returning
a result. Actual file hashes are recorded in `certificate_files` and included
in problem/candidate identity. Missing files, expected-hash mismatch and changed
bytes block with no optimum; changes during the search discard partial results.
Tests modify only temporary external certificate copies.

The same-run subproblem cache hashes the complete design document, complete
system input and exact scope list. It excludes record labels because labels do
not affect those computations. Candidate hashes include full records and their
sources; changing provenance therefore changes candidate identity even when
physical values coincide. No persistent cache survives another invocation.
Ranking uses the exact numeric objective followed by lexicographic candidate
IDs; equal-volume alternatives remain in the complete feasible list.

`max_combinations` must be explicitly supplied and cannot exceed 10,000. This
is bounded exhaustive finite coordination with staged rejection and exact
reuse, not a continuous or global gearbox optimizer, ratio-allocation solver,
or a claim about unseen catalogue/geometry domains.

The executable probe in `tests/test_v017_system_optimize.py` derives its design
from the unchanged `C001.factors` source and its system inputs from the existing
`test_sys_design_check._demo_system_input` fixture. All added geometry/capacity
values are explicitly marked authored capability inputs. They do not repair
real C001 missing A6 inputs or resolve pending engineering decisions. Held
K_Hbeta/material/life/root evidence and source assumptions remain held; system
recomputation does not feed stiffness into K_Hbeta. No evidence level is raised.

Current-session evidence is in `../v017-system-run/system-opt/`: complete input,
staged result, independent original Cartesian reference and SHA256 receipt.
The reference freshly calls all four requested scopes for each of 27 tuples,
using no staged/cache shortcut. Its entire feasible ranking and first optimum
match the staged result: eight feasible alternatives, first IDs
`original/economy/original`, volume 206968.12401849555 mm³. Tests also verify
analytic shaft volume, ties, all-infeasible domains, caller immutability,
source/capacity edits, propagated gear edits and missing/unknown/oversized/error
blocking, including omitted required fields under a pruned branch. The dependency-free `python -X utf8 -I -S` unittest run passes 56 test
methods: 17 new optimizer methods (115 assertion cases including subTest
matrices) plus 39 original system/flagship/edit methods. No pytest dependency
or skipped optimizer cases are needed for the core gate. RED was observed before either new production module existed;
review-driven omitted-field, load and nested requirement failures were also
observed before correction.

The observed staged counts are three gear-only calls, six shaft/key calls,
eight bearing calls, four exact bearing cache hits, twelve full tuples visited
and fifteen safely rejected descendants. Eight objective evaluations ran.
`design_check_calls` counts actual API invocations (17). Named evaluation
counters count scopes requested, not internal formula operations. Bearing
calls also freshly solve shaft loads; these are not cached shaft evaluations
or a replay benchmark. No timing speedup is claimed.

This supplies bounded finite evidence for M36 gate2 only. It does not establish
real C001 full-system acceptance, full-system worm/planetary ratings, the other
M36 gates, or permission to unfreeze M40. Original H2/W2W/P2 and edit tests remain
separate required regressions; no original tolerance or fixture was modified.
