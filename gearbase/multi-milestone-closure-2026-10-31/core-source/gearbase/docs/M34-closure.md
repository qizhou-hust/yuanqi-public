# M34 software acceptance evidence

Binding scope: `docs/顶层设计.html`, M34 (lines 496–503). The original H2 identity is `archive/m31/src/gears/solver.py::synthesize_h2` and its flagship tests, not an independently enlarged optimizer problem. That solver explicitly excludes strength from Stage0. This closure therefore does not claim a strength-qualified H2 transmission, W2W or P2 closure. Claude client connection evidence is owned by the integration task and is not claimed here.

## H2 identity and measured comparison

Run `python -m gearmath.tools.m34_closure --out output/m34/closure`. The tool imports archived solver/verifier files read-only under a separate package name, records their SHA256 values, wraps actual stage verifier calls and traces the actual old pair-evaluation source line. It does not infer the baseline from Cartesian tooth bounds or use saved solver outputs.

Frozen request: centres 80/100 mm; total ratio 10; modules 2/2.5/3 mm; beta 8–30 degrees; relative ratio tolerance .03; original default ratio seeds and original nearest-even tooth rounding. Each stage retains its seed-reachable `(module, tooth sum, pinion teeth)` domain and the original rule for retaining the seed that best explains the design. Ranking is lexicographic by total relative error, sum of retained stage errors, locked-centre volume proxy, two modules, two tooth sums and two pinion tooth counts.

Fresh comparison gives 378,216 traced old pair evaluations and 816 old stage verifier calls; the new implementation evaluates 9,948 pairs after rejecting 368,268 ratio boxes (97.37% fewer pair evaluations). Both find 9,948 feasible pairs and return the same ordered top 40, with identical stage domains. Every returned new design is independently re-evaluated using centre-distance geometry, integer tooth sums, beta bounds and the original relative-ratio predicate. On a smaller module/seed domain, full exhaustive search evaluates 520 pairs and pruning 178, with identical candidate ordering. Additional explicit seed sets are tested.

The old first-ranked result is **20/50 + 18/72**, modules 2/2 mm. The printed flagship **20/50 + 19/76** is among the returned candidates; the old test requires it to be surfaced, not first-ranked. No golden assignment is injected into ranking. The older rectangular `compile_h2` declaration remains a wider-domain interval-grid demonstration; its 307 primary-objective ties and Cartesian-size comparison are not this acceptance evidence. `search_seed_domain` is the same-problem compatibility entry point.

## Single editable source and write ownership

Product commits materialize `gears.math-source/2`; legacy edit commands are translated into source revisions. `design_store` now rejects a source-less append once a chain is source-owned, rejects source hash disagreement and rejects a legacy parameter projection that describes different inputs, provenance, selectors or editions from its source. Both memory and file backends check before mutation; file reload checks the same ownership contract. A projection-only update cannot drop the source or become a separate design owner.

Imported/optimizer records previously had a metadata-only `spec`, which the legacy edit path could interpret using the C001 default. It now materializes a complete compatibility projection from the stored source. Ordinary supported source imports can be edited without that fallback, and unchanged input provenance, evidence certificates, selectors and edition sources survive translation. Optimizer provenance is accepted only for trusted existing projections; caller edit rows must still use the public tool provenance list. Unsupported formula-family documents are blocked by the legacy model adapter rather than silently reconstructed as a C001 model; their source import/optimizer paths remain the applicable write entry points.

Low-level source-less pre-migration record compatibility remains to preserve the existing storage contract and its regression tests. This is not a second product editing document: existing source-owned chains cannot return to that form. Source hashes bind projections to exact document bytes; new source values require recomputation. No saved rating is treated as valid solely because a document count is one.

## Gradients and verification

The fresh K02/K04 matrix covers start, optimizer solution and written point for each case: 120 comparisons of formula-graph AD against central differences (`h=1e-6*max(1,abs(x))`). Error is scaled by `max(1,abs(AD),abs(FD))`, matching the existing M34 convention. Worst error is 1.2122e-8, below 1e-6. Existing finite-iteration fixed-point semantics are reused without kernel changes. These smooth-point checks do not establish differentiability at branch boundaries.

New closure tests first failed before implementation. Fresh runs pass closure, math-source, grid-prune, theta-iteration and MCP persistence tests. Windows stdio tests require `PYTHONUTF8=1` in this environment; the default cp1252 subprocess text decoder fails before testing the change. The machine-readable result is `output/m34/closure/closure.json`. Full integration, original M31 byte invariants, manifest updates and real Claude connection remain root-owned gates.

Final integration also covers get/rate/explain/sensitivity on genuinely imported
and optimizer-authored stored sources, including file reload. Protected source
provenance is trusted only when derived under the state lock from an actual
source-owned stored head; direct caller provenance claims remain blocked.
Original source-less preview-token compatibility is preserved.

Actual Claude Code 2.1.304 connected to this local server without using the mouse.
The subsequent model request was rejected with HTTP403 for insufficient account
quota; no model-initiated tools/call occurred. Thus three software gates are
verified, while the fourth usable-client gate remains partial.
