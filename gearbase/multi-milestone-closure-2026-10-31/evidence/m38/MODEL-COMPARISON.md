# M38 recorded model comparison

Fresh deterministic evaluation of both saved model runs and the rule baseline. All three real CLI commands exited 0. Model outputs and receipt bytes were retained unchanged.

| System | Cases | Numbers checked | Untraceable | Rate | Tool questions asked/required | Semantic accuracy | CLI exit |
|---|---:|---:|---:|---:|---:|---|---:|
| terra | 40 | 681 | 0 | 0.0 | 138/138 | null | 0 |
| sol | 40 | 684 | 0 | 0.0 | 138/138 | null | 0 |
| rules | 40 | 721 | 0 | 0.0 | 140/140 | null | 0 |

Each run produced 12 pending-confirmation compilations, 21 clarification requests, three invalid-input blocks and four unsupported-scope blocks. No inconsistent tool-question case was found.

The models were routed using `collaboration.spawn_agent` with requested presets `gpt-6.1-terra` and `gpt-6.1-sol`, both medium effort. The deterministic rules baseline is not a third model.

## Interpretation and protocol limits

- Models were requested via collaboration.spawn_agent: gpt-6.1-terra and gpt-6.1-sol, both medium effort.
- Provider-specific build identifiers are opaque. Identity is run-recorded, not provider-attested; matching receipt hashes establish file integrity only.
- The comparison is not blind. The sol receipt discloses a read of intent.py including requirement_compile before output generation, without calling it; initial reads also exposed pending empty gold metadata.
- The recorded sol start timestamp follows the initial source reads. The original immutable receipt retains this deviation.
- Model extraction and reply are followed by the real deterministic compiler in this rerun; saved model outputs are reused rather than regenerated.
- No engineer correctness gold exists. Compile semantic accuracy and clarification recall/precision are null; this cannot rank semantic model quality.
- Zero untraceable numbers means numerical traceability to input, registered derivation or public constant. It does not prove semantic assignment, engineering correctness, extraction completeness or free-text question consistency.
- Matching outcome counts and tool clarification self-consistency do not establish equal model semantic quality.
- This report covers the benchmark and first recorded multi-model comparison only; it does not certify full M38, clean-machine timing, strength rating or system closure.

## Frozen model and receipt SHA256

| File | SHA256 |
|---|---|
| `sol-output.json` | `62a013215079698a30db4a6e729739629a80712a947ba12d79ba785a5dd143fb` |
| `sol-receipt.json` | `5b2cb10a599e56c0938185916ac39a10d7698f2fc79f6b31332e2c8012b432a3` |
| `terra-output.json` | `af78c2e84e4210e661d50943b1aa1cb25663fc3930a90c2e2ff69c064a02cffc` |
| `terra-receipt.json` | `63bfec5547dc274e3340c42b334296a5824c9b1ed6c8c4bff6fcdb03f1881765` |

## Reproduce

`python ../milestones-multi-run/m38/reproduce-comparison.py` from the source checkout reruns the three CLI commands. `comparison.json` records command arguments, exit codes, exact metrics, output hashes and evaluation-source hashes. Per-system `report.json` and `outputs.json` preserve the complete results.
