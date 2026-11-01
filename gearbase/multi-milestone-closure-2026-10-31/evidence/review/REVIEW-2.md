# Scoped re-review 2

R1 is fixed: source ownership is included in preview tokens only when a source-owned head exists. Existing legacy token bytes pass the unchanged historical test. Source-only changes continue to invalidate tokens.

R2 is fixed: source_frontier validates source schema and registered evidence certificates at entry, before each candidate/scenario calculation, and in is_current. Tests cover wrong expected hash, absent file, changed actual bytes, and a valid copied certificate without changing originals.

Fresh command with PYTHONUTF8=1: `python -m unittest tests.test_mcp_p0 tests.test_m34_closure tests.test_m39_source_frontier tests.test_m38_bench_closure -q` — 39 tests pass.

R3's original Chinese-number omission is fixed: 九百九十九 is now scanned and rejected without a source; 一万 produces a source span for 10000; 千瓦 does not create a spurious 1000 source; Arabic displayed decimals retain their original token precision. Numeric NaN in parsed_requirement is untraceable. However the expanded tracer has four demonstrated lexical gaps, saved in probes-followup.json:

- ASCII minus before Chinese cardinal is dropped: input 999 permits output -九百九十九.
- Mixed magnitude is split into independent sources: input 15万 permits output 10000 instead of representing 150000.
- 一万亿 is miscomputed as 1000100000000 instead of 1000000000000, permitting the wrong numeric output.
- ISO/TS 6336-20 is not excluded as an identifier, allowing output 6336 kW. The metric explicitly promises standard identifiers are excluded.

These are lexical-value traceability errors, separate from the intentionally unassessed semantic-field correctness. Correctly parse supported numeric forms or reject unsupported forms as untraceable; do not silently create incorrect sources. Free-text NaN/Infinity currently contributes zero numeric occurrences; report that limitation or flag nonfinite numeric expressions explicitly.

The actual-model files were reevaluated without modifying them: sol 684 checked / zero untraceable; terra 681 / zero; each covers all 40 cases. Accuracy and label-based clarification precision/recall remain null. Hash-bound receipts pass integrity checks. Sol receipt expressly records accidental implementation/empty-gold-block exposure and cannot support a blind-evaluation claim. Provider build is opaque and identity is requested/run-recorded rather than provider-attested. Recomputed reports are sol-output-review.json and terra-output-review.json.

## Where This Review May Be Wrong

- Additional numeral forms may be outside the intended bounded grammar; unsupported forms must be rejected or reported rather than parsed into plausible wrong sources.
- The independent re-evaluation verifies receipt integrity and executable scoring, not independent provider attestation or semantic answer accuracy.
- Flagship port, clean-machine CI and final delivery changes are pending a separate review. This report approves none of those future changes and does not close a full milestone.
