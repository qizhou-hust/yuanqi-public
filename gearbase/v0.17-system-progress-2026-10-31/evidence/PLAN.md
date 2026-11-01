# v0.17 independent software work implementation plan

User request: continue D items, keep external evidence/engineering decisions explicit. Current input SHA256 04650fffa012c6e0a5a91038c960733352c9b4b5a118ddc6b0e14e7db28f7094, recovered from validated base64; nested hashes/CRCs and257registered files checked. Original direct ZIP mismatch is retained. Baseline source d67cde5c0d64db986797a7d2b83d3620ebc0b833.

Architecture: preserve the existing formula kernel and original81 test/fixture bytes. Physical equations remain L2 gear/system. Product adapters own orchestration/source projection, do not duplicate equations. Use existing design_check schema and sourced leaves; additive routes preserve legacy exact results and explicit missing-data blocking.

## Frozen acceptance and routing

- M38 remains3/4 under the user's latest gold-labelled criterion. No invented gold labels or new model calls. M34 actual-client gate deferred by user.
- M36 gate2: finite authored cylindrical-gear/shaft/bearing coupled problem; actual gear recomputation and system checks for every visited candidate; prune/search result independently compared with complete small-domain Cartesian enumeration, including ties, infeasible and missing-input cases. Demo engineering values remain authored capability probes, never silently made into C001 real inputs.
- M36 gate3: original H2/W2W/P2 and source edits must regress unchanged. A Stage0 result alone is not a full system rating, nor authorization to unfreeze M40. No automatic promotion without the original gate's actual system/edit evidence.
- Thermal: implement bracketed equilibrium iteration over existing ISO/TR14179 loss/heat functions; require all physical/model inputs. Retain failed brackets, nonconvergence and applicability limits. Integrate an additive explicit thermal route in design_check while preserving existing P_T route.
- design_check shaft/bearing backend: canonical drivetrain orchestration, preserve old static input/results; richer beam/material paths require explicit new inputs, no implicit E/G or physical constants selected as defaults. Keep model/result schemas and units stable.
- Micropitting helicalXY and FE preparation: only verified source equations/solver numbering; if source is missing, identify exact missing clauses/files instead of inventing formulae or FE results.

## Work units and file ownership

- [ ] T1 thermal worker: system/thermal_balance.py, focused tests and own doc. Root integrates design_check thermal after worker hands off an explicit contract.
- [ ] T2 drivetrain worker: system/drivetrain_check.py and product/design_check.py shaft/bearing sections plus relevant tests/docs; do not touch _thermal, shared schema, manifests or milestone files without root coordination.
- [ ] T3 optimizer worker: system/product joint finite optimization modules + focused tests/doc; use current design_check API, original sources unchanged. No changes to design_check or shared manifest/status.
- [ ] T4 root: source-bound helicalXY/FE inspection, integration, schema/units, M38 status correction in delivered evidence, executable milestone receipts.
- [ ] T5 root/reviewer: independent negative-case review, architecture/dimensions/full suite/legacy invariants, actual hosted CI, binary package+SHA256 and public delivery.

## System impact and checks

Existing design_check consumers: MCPdesign_check tool, optimize/report/flagship workflows, milestone probes, schema validators and test_sys_design_check. Risks: stale context caches across edits, unit Nmm/Nm or rpm/rps mismatch, source provenance loss, old static results changing to beam values, mislabelled partial computation as pass. Checks: direct-call equivalence, immutable caller inputs, changed source hashes, fresh candidate reevaluation, scope isolation, schema validation, explicit no-bracket/nonconvergence, full old suite. Kernel and original fixtures byte comparison are hard gates.

Chosen approach: additive explicit capabilities plus canonical L2 orchestration. Rejected: forcing old inputs through a default-material beam model, making up missing real C001/oil data, substituting archived Stage0 for full-system rating, generic optimizer/framework refactoring. No whole-milestone closure from file presence.
