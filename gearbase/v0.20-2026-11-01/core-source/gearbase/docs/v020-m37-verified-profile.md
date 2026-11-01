# M37 verified-profile raw ingest

`gearmath.tools.fea_ingest.ingest` retains its canonical reader by default. An explicit `verified_profile=(probe_dir, solver_path)` opts into the existing v017 measured CPE6 reader registration for the pinned CalculiX 2.23 executable. This route currently accepts L2 mesh jobs only. It requires `repost=True`, attached INP, metadata, DAT and STA bytes, the bundled pack with case, expected and script hashes, and matching solver, probe, run identities and deck-derived field coverage. It re-reads actual fields and repeats the extraction; it does not alter the canonical pack or bypass the acceptance ladder.

```python
from pathlib import Path
from gearmath.tools import fea_ingest
results, attachments, source_sha = fea_ingest.load_results('raw-results.zip')
evidence = fea_ingest.ingest(
    results, Path('data/m37_fea_pack'), attachments, repost=True,
    source_sha=source_sha, verified_profile=(Path('measured-probe'), Path('ccx_2.23')),
)
```

The supplied probe and executable must match the fixed hashes in `fea_prepare.verified_profile`; mismatches fail closed. This opt-in is a Python API, not a CLI flag. `recorded` means accepted for evidence recording, not that any validation ladder level passed. Inspect the ladder and per-point results.

The ingest repost imports run in a read-only, isolated pack scope. When using the legacy pack runner directly for a future build or solve, invoke it with `python -B scripts/run_m37.py ...` so Python does not create bytecode in the registered pack. The read-only replay itself does not require `-B`.

The ingest-side Richardson method `signed-unequal-grid/1` solves the signed three-grid relation for unequal refinement ratios. It falls back to the existing assumed order outside the allowed observed-order range or for oscillation, and the receipt identifies the ingest source hash. The frozen pack's `scripts/post.py` remains unchanged; its legacy Richardson implementation must not be used as the corrected ingest assessment. Original raw outputs and the earlier uncorrected receipts remain separately preserved in the run evidence.
