# Narrow integration review

## Finding

**P2, corrected and independently rechecked:** saved L3 preparation declarations previously failed verification after an unchanged JSON round trip because coverage element-type maps had integer keys in memory and string keys in JSON. The preparer now returns a normalized JSON representation. All eight actual saved manifests were loaded from disk and passed `P.verify` against their original inputs and measured solver/probe identities. A new saved-contact-declaration regression passes. **All reproduced findings in this review and REVIEW-FINAL.md are closed.**

## Verified

- Standard-library discovery runs **17 optimizer test methods successfully**. A custom unittest result observed 109 subTest events; subtracting three nested outer wrappers and adding nine nonparameterized methods gives **115 leaf cases**. Thus the earlier pending unittest-discovery action is closed. No pytest runtime was used by that execution.
- Standard-library discovery now runs **5 FEA preparer tests successfully** (0.458 seconds), including the saved-contact JSON roundtrip, zero-dependency guard, exact-path module loading, unknown solver version, isolated registry, and identity rejection checks.
- The actual bundled solver SHA256 is `31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862`. Raw INP/DAT/STA hashes match the registered probe identities. Direct independent DAT parsing finds 20 elements and 180 unique stress rows, plus 20 elements and 180 coordinate rows; each element has keys 1–9.
- The opt-in isolated reader accepts the actual raw probe output. The canonical reader still lacks the (`2.23`,`CPE6`) entry and its complete bytes equal git HEAD. `verified_profile` does not change sys.path. The existing zero-dependency doctor guard passes.
- All eight selected jobs prepare with registration `ready` under the explicit profile and keep CONTACT FILE `undecided`. Both in-memory and saved-JSON verification pass. These are preparation coverage results, not contact-solution acceptance or gear validation.
- No `.pyc` files exist under data after the final probe. The canonical strict reader remains byte-identical to git HEAD and its original 2.23 registration block is preserved.
- Five of the six previously recorded production file hashes remain identical. The design_check header docstring changed; independently reversing only that header line reconstructs the exact prior reviewed SHA256 `75ef275aa3a1d90e542184e1ad6e3ba4ec3ab5d629e4a067b125ee2a86bf614a`. Current SHA256 is `4f2f776d05bca8c4ba9e2effaf7fcd5659eb198bdc415f31d4c728b57de5e81d`; no executable change is present.

Exact hashes and measured results are in integration-probes.json. Hosted CI status was reported by the root agent and is not independently verified in this note.

## Where This Review May Be Wrong

- Active edits may supersede these identities; re-run the roundtrip and manifest checks on the final snapshot.
- The raw patch verifies CPE6 output key coverage for the measured solver, not stress accuracy or nonlinear gear contact behavior.
- The 115 count describes leaf case executions; unittest itself correctly reports 17 methods and should not be described as reporting 115 methods.
