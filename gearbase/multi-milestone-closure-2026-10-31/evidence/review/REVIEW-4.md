# Independent review 4 — final scoped correction check

## Conclusion

No remaining actionable finding was found within this final scoped recheck. All concrete findings from REVIEW-3 are verified corrected. This closes those code-review findings, not the original complete milestone gates or a later delivery artifact.

## Fresh evidence

`PYTHONUTF8=1 python -m unittest tests.test_m34_source_reads tests.test_mcp_p0 tests.test_mcp_p1 tests.test_m34_closure tests.test_bench_chinese_numbers tests.test_m38_bench_closure tests.test_flagship_workflow tests.test_flagship_w2w tests.test_flagship_p2 tests.test_m39_source_frontier -q` ran **90 tests, zero failures/errors**. Log: round4-tests.txt.

Independent original reproductions and directed negatives are retained in probes-final.json. The actual model-output files were read and scored again without editing them; scoring-final.json records rules 721/0, sol 684/0, terra 681/0 numerical occurrences/untraceable occurrences. Each model has all 40 cases. Gold accuracy and label-based clarification precision/recall remain null.

## Finding disposition

| Finding | Disposition | Verification |
|---|---|---|
| Legacy token bytes changed without a source head | Closed | Historical P0 token assertion passes; source-only invalidation test passes |
| Corrupt/missing/changed certificate accepted by source frontier | Closed | Expected hash validation precedes candidate/scenario acceptance and currentness; M39 tests pass |
| Stored-source read rejects standard_constant/optimizer inputs | Closed | get/rate/explain/sensitivity trust is derived only from the actual stored source-owned head under the existing lock. Fresh get returns ok and rate pass for imported source. Tests compare values/gradients to source model, persistence restart, unchanged store, and later preview/commit. Direct/stateless protected provenance and named design plus overrides remain rejected |
| Chinese/mixed numeric subfragments create false sources | Closed for the reviewed forms | Whole-token scanner retains original spans and signs; Unicode minus, 负999, 1e3万, 零万, 1,000, 一万亿 and 15万 now have correct values. Unsupported 1,00 / 15五 / 999负 / repeated units and NaN/Infinity are untraceable. ISO/TS and DIN identifiers produce no input numeric sources. Original Arabic displayed precision is retained |
| W2W original thermal boundary flips | Closed | Original arithmetic sequence restored; all 15 candidate payloads match exactly at the recorded boundary. Candidate 9 is thermal_ok=False in both original and port |
| Malformed family raises TypeError | Closed | List-valued family returns blocked_unsupported_scope |
| Tiny positive W2W denominators cause uncaught divide-by-zero | Closed | Derived thermal denominators are validated and arithmetic/nonfinite failures rejected; recorded underflow inputs return blocked_invalid_inputs |

## Approved bounded behavior

The three original structured Stage0 requirements execute through the production compile/workflow tool. The result remains read-only, retains the authored requirement and hash, reports engineering_accepted=False, and does not silently supply missing engineering parameters. H2 and P2 geometry-only scope and absent strength/full-system capabilities remain explicit. W2W can compute its original simplified thermal failure and reports candidate_requires_changes rather than acceptance. The source-store trust fix authorizes existing validated source content without allowing the direct caller to impersonate optimizer or standard_constant provenance.

The numeric benchmark establishes **value traceability under the declared lexical/derivation/constant metric**, not semantic correctness of quantity assignment, engineering gold accuracy, proof over arbitrary language, or independent provider attestation. Published constants can legitimately share a value with an incorrect semantic assignment; this review does not relabel that limitation as accuracy. Sol receipt already discloses non-blind implementation exposure. No model answers or gold labels were changed by this review.

## Remaining original gates and delivery scope

M33 all-example TR30 E4, M36 complete system capabilities and M39 high-speed full failure/thermal capability remain separate outstanding requirements. M34 Claude client usability and the fresh-machine timed portable connection depend on root's actual client/CI evidence. Package/manifest/CI integration after this snapshot has not been approved by this scoped review. Regenerate source-bound frontier identity after final executable-source edits.

## Where This Review May Be Wrong

- Whole-token tests cover the demonstrated supported and malformed forms, not every possible natural-language expression; the metric remains explicitly lexical rather than semantic correctness.
- Stored-source tests cover the exercised C001 import/optimizer and persistence paths. This is not blanket support certification for every possible external model family.
- Root integration and CI continue concurrently. This report must be bound to the reviewed source snapshot and cannot certify later edits or uninspected package contents.
