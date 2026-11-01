# Focused independent v0.17 review

Basis: ../PLAN.md frozen acceptance, source code and tests, local ISO/TS 6336-22:2018 PDF pages 30–34 viewed directly. This is a focused same-model subagent review, not external engineering validation. No source scans redistributed.

## Findings

1. **P1, corrected and rechecked:** helical modified-pinion high-overlap tail used the plus/plateau coefficient, whereas printed equation (76) uses the minus/weak coefficient. At ea=1.5, ga=6, gB=2, gD=4, gY=5.5, expected XY=0.3. Current implementation now returns 0.3; regression added.
2. **P2, corrected and rechecked:** modified-wheel high-overlap exact gEU boundary originally entered equation (73), but equation (72) includes equality and (73) is strict. Current implementation returns 0.7333333333333333 at gEU=6−0.2 sin(0.2), with the printed discontinuity immediately after the boundary retained; regression added.
3. **P2, corrected and rechecked:** optimizer preflight accepted omitted required downstream fields on a branch pruned at the gear stage. Reproduction: `d,s,p=tests.test_v017_system_optimize.probe(); p['gear']=p['gear'][:1]; del p['bearing'][0]['bearings']['B_S0_0']['C_r']; optimize(d,s,p)`. Result was `completed`, errors empty, 9 pruned combinations. A second reproduction deleted `p['shaft'][0]['shafts'][0]['loads'][0]['F_tw']`. Both now block with exact missing-field errors. Per-kind load validation has been added; original false-completion behavior is no longer reproduced.
4. **P2, corrected and rechecked:** PDF29 equation (57) modified-pinion low-overlap plateau includes gY=gD. `_spur_one_end` used strict `<gD`, yielding 2/3 rather than 1 at gD=4 for ga=6, gB=2, ea=1.5, eb=0.8, beta_b=0.2. The defect also reached interpolation through the low endpoint factor. Current reproduction returns 1. Wheel branch equation (52) has a different strict inequality and remains unchanged.
5. **P1, open:** optimizer does not verify source certificate hashes. Change `d['evidence']['E']['certificate']['sha256']='0'*64` in `probe()`: `MS.verify_certificates(d)` correctly reports `certificate_hash`, yet optimization returns completed with an optimum and empty errors. Thin-only gear domain also completes despite the corrupt certificate. A read-only mock appending one newline to the referenced certificate file's `Path.read_bytes()` result yields eight certificate mismatches while optimization still completes with unchanged problem and candidate hashes. Call certificate verification before pruning. Once actual bytes are verified against the recorded SHA, the existing document hash can bind that evidence transitively; do not claim current identities cover unchecked referenced bytes.

## Verified

- Equations (60)–(70), (71)–(75), and (77) visually checked against local PDF pages; coefficient and boundary issues above corrected. Interpolation evaluates the two endpoint overlap ratios 0.8 and 1.2, not the current overlap ratio in both endpoint factors.
- Focused thermal, drivetrain, helical, optimizer, original design_check and original drivetrain tests: 54 passed before corrections. Corrected helical plus thermal product integration: 7 passed.
- Subsequent combined focused run: 62 passed, including added omitted-input regressions. A green run did not cover omitted mesh-load F_tw or the equation (57) equality, which were independently reproduced afterward.
- Final pre-certificate-fix combined focused run: **149 passed in 3.48s**. All helical and omitted downstream input findings above had been corrected at this point. Certificate failures were reproduced afterward.
- Independent thermal equation/secant calculation uses no production thermal or viscosity helpers: 56.5849205486015 °C, versus bracket solver 56.5849205548875 °C, difference 6.286e-9 °C against requested 1e-8 °C. Fixed-loss closed form remains 70 °C.
- Bearing churning and smooth-OD windage loss branches converged on authored numerical probes. Existing tests check no bracket, invalid inputs, nonconvergence, explicit temperature limits, units, and legacy P_T behavior.
- A 40–141 °C bracket with temperature-dependent mesh viscosity returns invalid, explicitly retaining the 140 °C extrapolation limitation. First console printing failed because cp1252 could not encode the Chinese reason; a repeated JSON-escaped print confirmed the result.
- Static drivetrain adapter delegates to the pre-existing static/section/bearing functions and maintains separate direct beam orchestration requiring explicit material inputs. This is compatibility integration, not full-beam exposure through product schema.
- K02 compares seven XY points and five loaded-point pressures with the original external reference. Endpoints retain zero pressure and undefined film safety. This does not independently qualify the other profile families or promote E5.

## Not Verified

- Full repository suite, byte identity of original 81 fixtures/kernel, hosted CI and release package are root-agent verification work and are not inferred from these focused tests.
- M36 gate 3 full H2/W2W/P2 system rating and source-edit behavior is not established by Stage0 regression or static adapter integration. M40 stays frozen; M38 stays 3/4 per PLAN.md.
- Independent engineering validation of thermal models and unloaded-endpoint policy remains outside this numerical implementation review.

## Where This Review May Be Wrong

- Files are actively edited by other agents; results refer to the observed snapshot. Re-run repros and tests before freeze.
- Printed equations (73)–(76) have discontinuities inconsistent with a visually smooth sketch. This review follows the printed equations literally; a confirmed erratum could change that interpretation.
- Optimizer missing-input expectations follow the explicit frozen plan and code preflight claim. A narrower contract allowing omitted inputs on proven infeasible branches would need to be stated before treating the reproduced behavior as acceptable.
