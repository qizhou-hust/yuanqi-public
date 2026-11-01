# M36/M39 original-gate review and bounded implementation

2026-10-31. This change advances M39 and does not mark M36 or M39 complete.
The binding exits remain `docs/顶层设计.html` M36/M39; no substitute flagship or
synthetic C001 materials are used to pass those exits.

## Original gate inventory

| Original exit | Current evidence / result |
| --- | --- |
| M36 C001 gears, shaft, bearing, key in one graph | Blocked. Existing unified report passes gear rating but shaft load location/static strengths, bearing reactions and real key material data remain absent. System-input also records inconsistent support geometry. This work does not supply fabricated material values. |
| M36 system optimum agrees with small full enumeration | Not claimed. The added enumeration is a gear candidate front, not a system gear/shaft/bearing optimization or its oracle. |
| M36 H2/W2W/P2 and editing regression agreement | Not claimed by this work; original flagship identity must be preserved. |
| M39 high-speed full failure-mode check | Open. K01/K02 native oil inputs are available; this is not restricted to K04/K05. However the existing micro-pitting adapter imports bulk and seven local flash temperatures from native **outputs**, and the flash adapter imports the scuffing temperature output. Those isolated formula comparisons do not recompute a speed-modified case. K01 unified input lacks micro local/temperature inputs and thermal data. Native oil data alone does not close this coupled calculation. |
| M39 volume / center-distance / safety front | Implemented and exercised as an exact front of an explicitly finite, authored subset of the existing K01 problem. No global continuous-front claim. |
| M39 tolerance feasibility report | Implemented for explicit unweighted scenarios, including blocked outcomes in the denominator. The shipped ±0.1 mm width / ±0.001 profile-shift scenarios are authored capability probes, not measured production tolerances or manufacturing probabilities. |

The high-speed exit says “可完成…校核”, so an evaluated numeric failure would
still demonstrate calculation capability; a blocked/temperature replay result
cannot. This assessment does not add a requirement that every safety result pass.
Thermal remains in scope: `thermal: null` cannot be treated as an efficiency or
heat-balance check. Backlash and modification assumptions likewise must remain
visible before a full-M39 claim.

## Implementation and semantics

`gearmath.gear.source_frontier.finite_frontier` accepts the existing source document,
problem declaration, explicit candidate axes and explicit tolerance offsets in
declaration units. The original declaration validates ranges, held evidence,
limits, tip-shortening route and resolution. Missing values are rejected rather
than filled. Every candidate is a new source document; `verify_writeback` rebuilds
the model and checks all unified and declared constraints at zero acceptance
tolerance. A separate source rebuild computes the three front coordinates.
The generic kernel's nondominance filter handles min volume / min center distance /
max `min(SF1,SF2,SH1,SH2)`. This raw safety coordinate does not replace the four
individual safety acceptance limits. Equal objective tuples remain nondominated.

Manufacturing offsets deliberately bypass nominal design bounds: the perturbed
geometry is checked against physics and the same acceptance constraints, with
each fail or blocked result retained. No nominal-fail candidate enters the front.
Scenario fractions are `number pass / all scenarios`, with no probability model
and no proof over the continuous tolerance box. The implementation does not
introduce a stochastic optimizer or a new gear equation.

The report binds parent source, declaration, axes/scenarios, executable package
sources and referenced local evidence-file contents by SHA256. `is_current` rejects
old conclusions after any of those change. Held evidence is preserved and its
limitations remain in each verification report. All candidate documents and hashes,
acceptance results, scenario values and front indices are retained for review.

## Reproduction and observed result

```
python -m gearmath.tools.m39_frontier --out ../milestones-multi-run/system-modes
python -m pytest tests/test_m39_source_frontier.py tests/test_m39_tribology.py tests/test_m39_kisssoft_v014.py tests/test_sys_design_check.py -q
```

The first run enumerated all 12 explicit candidates: nine feasible points on the
three-objective front and three ratio-infeasible candidates excluded. Each point
has three scenario evaluations. The nine feasible points have 3/3 pass; excluded
points have 0/3. The targeted suite passed 91 tests. These results are capability
evidence for the stated finite problem, not a released high-speed gearbox.

The evidence directory contains `source.json`, `declaration.json`, `spec.json`,
`frontier.json` and fresh original `baseline.json` unified reports for C001/K01.
Regenerate after concurrent implementation edits before packaging, because source
identity changes invalidate the previous report. No historical M31 golden was edited.
