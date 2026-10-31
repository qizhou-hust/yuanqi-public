# KISSsoft v0.15 local evidence

Read RESULTS.txt and summary.json first. This is a partial closure with explicit open items, not a blanket validation.

- case-index.json maps modules, native files, and per-case run.json records.
- sources/ contains byte-preserved source inputs; source-map.json maps original paths to archive paths and SHA256.
- cases/ contains canonical calculations only. P5 A is P5-A-tip-coefficient-input. Earlier P5 flag experiments and invalid Rz-cache reports are excluded.
- R1/R2 PDF and TXT are readable text renderings of unchanged vendor .pprpt reports. Embedded graphics remain in the PPRPT. They are not vendor-exported PDF layouts.
- Z012 PDF/TXT use rendering copies that remove only a leaked literal HTML cell tag. Original RTFs and native files are unchanged; cleanup counts and hashes are recorded.
- R3 is a force/deflection diagnostic. Its native files are not DIN743 strength acceptance artifacts.
- Original scripts preserve original local paths and execution provenance. For another PC, use native files and the small headless replay utility; a compatible KISSsoft 2026 license/COM installation and user database record are required.
- R1 depends on user record W000/W010OBER/20000, Rz6.3. Back up and merge user databases through the vendor database tool; never blindly overwrite an existing UDB. RA0.76 was inherited from the copied roughness record and is not an inferred Ra/Rz relationship.
- No proprietary standards PDF or manual excerpt is included. The supplied v0.15 stage ZIP failed integrity checks and was never extracted or used.

Headless replay (Windows Python with pywin32):

    python replay/headless_replay.py cases/P5-B-auto/P5-B-auto.Z12 Z012

No mouse/keyboard APIs are used. GetModule(module, False) and SetSilentMode(True) keep calculation headless. The utility recalculates in memory and does not overwrite the native file. Some requested graph/table outputs still have no verified headless export interface and are explicitly open.

MANIFEST.sha256 checks every packaged file except itself. The adjacent ZIP.sha256 checks the complete binary ZIP; download it as binary, not through a text relay.
