# Final focused independent review — v0.17

## Findings and disposition

**No remaining reproduced blocker in the reviewed production changes.** All five issue classes found in the initial review are now corrected and independently rechecked: high-overlap modified-pinion coefficient (76), exact modified-wheel boundary (72), low-overlap modified-pinion boundary (57), missing downstream inputs hidden by pruning, and unverified source certificate integrity. Historical findings remain in REVIEW.md; this file and final-probes.json supersede their open statuses.

The frozen PLAN.md supports **M36 gate 2 for the bounded authored cylindrical/shaft/bearing/key demonstration only**. It does not establish real C001 input completion or a universal optimizer. **M36 gate 3 remains partial**: Stage0 topology regressions and static source edits do not establish full worm/planetary system rating. M40 remains frozen and M38 remains 3/4.

## Fresh verification

- An independently written complete Cartesian loop recalculated all 27 combinations through fresh design_check calls: 8 passed, 19 failed, zero blocked. The optimizer's eight feasible rows, exact objectives, ordering, and ties matched. The winning IDs are `original / economy / original`, objective **206968.12401849555 mm³**, tied with the explicitly authored alternative bearing ID. Caller inputs remained unchanged. Search used 17 design_check calls, pruned 15 combinations, visited 12, and reused four exact cached results.
- The original deleted `C_r` and deleted mesh-load `F_tw` reproductions now block even when all descendants would be gear-pruned.
- Corrupt registered certificate SHA256 now blocks both the ordinary domain and the all-pruned domain **before any design_check call**. A read-only mock changing the bytes of a referenced certificate also blocks before any design_check call. The code verifies every candidate's certificates before search, records actual file SHA256 values in problem/candidate identities, and re-verifies before publishing results. The focused test run additionally passed missing-file and mid-search evidence-change cases; partial optima are discarded.
- Exact helical source reproductions now return XY=0.3 for equation (76), XY=0.7333333333333333 at equation (72)'s inclusive gEU, and XY=1 at equation (57)'s inclusive gD. Source pages 29–34 were visually reviewed earlier; no scans are distributed with this review. Seven-point K02 comparison remains unchanged and does not qualify the other profile families as E5.
- Explicit `thermal.method = null` blocks. Legacy thermal rating and explicit equilibrium integration tests pass. Earlier independent viscosity/mesh equation plus secant calculation differed from the bracket solver by 6.286e-9 °C under a requested 1e-8 °C tolerance; the 140 °C viscosity extrapolation boundary remains enforced.
- Fresh combined focused pytest execution: **162 passed in 10.77 seconds**. It included the five new v0.17 test files, thermal integration, original design_check, and original drivetrain tests. The first ad hoc enumeration probe used an incorrect result-envelope key and failed with KeyError; the corrected probe used explicit subcheck statuses and completed all 27 evaluations.

Production file SHA256 identities and exact probe outputs are recorded in **final-probes.json**. No production source was edited by this reviewer.

## Architecture and limits

The product optimizer orchestrates existing source-owned gear recomputation and system checks; the volume calculation remains in the system layer. Its cache is local to one call and keyed by exact document/system/scope content. Static drivetrain wrappers preserve the original functions and do not introduce implicit E/G or expose the full beam model through the old product schema. Thermal equilibrium is an additive explicit route, retains failure statuses, and does not claim maximum input-power rating. No new formula-evidence promotion was justified by this software review.

The root agent reported a remaining **test-harness integration action** after this run: converting pytest-only optimizer cases to standard-library unittest discovery without losing their assertions. This is not yet verified here. The frozen production-source findings above are resolved, but freeze should include the converted cases actually running in the repository's required no-dependency test command.

FEA preparation, original kernel/81-fixture byte checks, repository-wide tests, hosted CI and final packaging are outside this focused final review. No readiness claim is inferred for those areas.

## Where This Review May Be Wrong

- The source tree remains active; verify the SHA256 values in final-probes.json against the final production snapshot and rerun affected checks if they differ.
- Full enumeration independently verifies search/pruning/ranking but invokes the same established physical functions. It is not independent engineering validation of those equations.
- Literal printed micropitting equations contain discontinuities. This review preserves their printed inequalities and coefficients; an authenticated erratum could change the required interpretation.
