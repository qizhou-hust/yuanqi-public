# Independent whole-change review — initial pass

## Findings

1. **[P1] Preserve pre-source preview-token compatibility.** `gearmath/tools/ai_tools.py:362` adds `source_sha256: null` for a design without a saved source. This changes existing deterministic tokens even before migration. Fresh `tests.test_mcp_p0.TestTwoPhaseWrite.test_preview_is_read_only_and_token_is_sha256` fails. Add the source binding only when a source-owned head exists; keep the original shape otherwise. Do not update the historic expectation just to hide the regression.
2. **[P1] Verify evidence certificates before accepting a source front.** `gearmath/gear/source_frontier.py:130` calls schema/constraint verification but not `math_source.verify_certificates`. The report identity at lines 34–48 hashes the actual file but does not compare it with the registered expected certificate. Changing K01 evidence `Rz_H_1.certificate.sha256` to 64 zeros returns front status `ok`, point `pass`, and `is_current=True`, while the existing certificate verifier reports `certificate_hash`. Invalid evidence must block acceptance; currentness cannot certify this invalid report. Probe is recorded in `probes-initial.json`.
3. **[P1 for a full zero-invention claim] Chinese numeric reply claims bypass the scanner.** New `bench_closure.evaluate_outputs` uses inherited `bench._text_numbers`, which recognizes Arabic numeric tokens only. Replacing one rule reply with `Recommended power: 九百九十九 kW.` yields `numbers_untraceable=0`, `hallucination_gate=pass`. The existing number metric also only proves value traceability, not correct quantity assignment. The latter limitation is honestly documented; the Chinese-number omission still prevents treating the current pass as the original unrestricted zero-invented-number exit. Implement numeric-word scanning or explicitly flag unsupported numeric expressions as unverified, rather than silently passing.

## Original requirement mapping

Authority: original `docs/顶层设计.html` lines 484–558, not implementer status summaries. PLAN/LEDGER explicitly forbid reduced gates and fake engineering inputs.

| Requirement | Evidence | Status |
|---|---|---|
| M33 original 22, at least 20 formula replacements | Read original mapping and fresh 4 M33 tests; executable K01 formula inventory has 20 formula rows, K_A/Y_ST excluded | Verified bounded gate |
| M33 all TR30 examples coefficient-level E4, main chain ≤1% | Existing fresh artifacts retain example 7/8 failures; source diagnostics are not a passing numeric gate | Failed/open |
| M33 C001 recompute with individual differences explained | Fresh diagnostic reconstructs all 18 receipt values at numerical precision using vendor nine iterations; new converged iteration is different | Verified, retained evidence assumptions explicit |
| M34 one editable source per design | Both stores reject projection-only writes once source-owned; imported legacy projection edits preserve source evidence; R1 remains | Partially verified |
| M34 gradients central-difference agreement 1e-6 | Fresh closure command: 120 comparisons across K02/K04 start/solution/written points, max scaled error 1.2121151429973629e-8 | Verified at declared points and scaled-error metric |
| M34 H2 same result, fewer evaluations | Fresh archived Stage0 execution: identical stage domains, all top40 rank signatures, 9948 feasible matches, 378216→9948 pair evaluations; small domain 520→178 | Verified for original geometry-only Stage0 problem |
| M34 Claude Desktop / Code real connection usable | Actual Claude Code 2.1.304 transcript contains initialize/tools-list; request returns HTTP403 quota before model tools/call | Connection verified; usability open |
| M36 C001 gear/shaft/bearing/key single graph | Existing reports retain missing system inputs, no new complete system evidence | Not closed |
| M36 system optimization vs enumeration; three flagship/edit regression | Gear-only finite enumeration is not a system oracle; no new original flagship closure evidence | Not verified |
| M38 zero invented numbers | 40-case rule run has 0/713 value-untraceable Arabic numeric occurrences; R3 blocks generalization | Partial |
| M38 three flagship requirements end-to-end | No full evidence reviewed | Not verified |
| M38 clean environment connected in ten minutes | Existing machine Claude attempt is not a clean-machine timed installation | Not verified |
| M38 first multi-model report | Model runs pending at initial review | Not verified |
| M38 benchmark gold deliverable | All 40 gold labels remain pending; accuracy and label-based recall/precision correctly null | Open deliverable |
| M39 full high-speed failure modes | Thermal and coupled micro-pitting temperature inputs not supplied; replay of old output temperatures is not a new speed-case calculation | Open |
| M39 volume/center-distance/safety front | Exact nondominance of declared finite K01 axes; feasible-only filtering verified; R2 | Partial pending provenance fix |
| M39 tolerance feasibility report | Explicit authored unweighted scenarios; fail and blocked remain in denominator, no probability claim | Verified bounded capability, pending R2 |

No complete M33/M34/M36/M38/M39 milestone can currently be claimed from this evidence. No extra strength gate is imposed on geometry-only H2, and no second Claude client is required by the slash wording. M39 calculation capability does not require every safety result to pass; a blocked missing calculation is still not capability evidence.

## Fresh validation

- Focused new suites: 24 tests pass.
- `python -m gearmath.tools.m34_closure --out ../milestones-multi-run/review/m34`: pass; full machine evidence retained.
- Six source/MCP/optimization regression modules: 137 tests, one failure, two skips with `PYTHONUTF8=1`. Failure is R1. An initial run without UTF8 also had four Windows cp1252 decoding errors, resolved by UTF8 rerun. Log: `ownership-mcp-regression.txt`.
- R2/R3 reproductions: `probes-initial.json`.
- Source edits: none. Only review reports/evidence were written.

## System impact

The largest risk surface is source ownership across MemoryStore/FileStore, legacy preview/commit, import/optimizer records, persisted reloads, and preview-token invalidation. The selected 137-test regression spans those consumers. Source-front identity propagates into accepted finite/scenario results; hashing bytes without validating the expected certificate is insufficient. Benchmark adapter integrity prevents altered compiler outputs, but lexical traceability must remain distinct from semantic extraction accuracy and actual provider attestation.

## Where This Review May Be Wrong

- The first pass read implementer artifacts after receiving contextual claims; the substantive conclusions above were checked against raw source, original gates, fresh tests, and counterexamples. Model/provider run identity is not independently attested by this review.
- H2 agreement is verified for the frozen default plus two alternate seed split sets, not every possible input to the new public helper. Wider caller/API fuzzing was not performed.
- Root status/CI/package edits and final model outputs were pending. This is not approval of a later package; rerun relevant gates and inspect final manifests after integration.
