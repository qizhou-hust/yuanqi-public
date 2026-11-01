# M38 P2 original Stage0 integration

`gearmath.gear.flagship_p2.stage0(inputs)` (alias `run`) accepts exactly eight
explicit keys: `n1_rpm`, `target_total_ratio`, `np_options`, `zs_range`,
`zp_range`, `m_series`, `i_tol`, `top_k`. Ranges are inclusive integer endpoints;
module values are mm. There are no engineering defaults. Missing, extra,
nonfinite, nonpositive physical values, fractional integer domains, and reversed
ranges raise `ValueError`. Tolerance zero is supported.

The original flagship is the explicit call `synthesize_p2(1440.0, 40.0)` at
`archive/m31/tests/test_solver.py:198`; its other six values come from the
original function signature at `archive/m31/src/gears/solver.py:462`:
`np_options=[3,4]`, `zs_range=[14,30]`, `zp_range=[18,60]`,
`m_series=[2,2.5,3]`, `i_tol=0.02`, `top_k=5`. These are frozen example inputs,
not production defaults. The evidence directory contains canonical input bytes,
SHA256 hashes, source hashes, a fresh archived solver output, new output, and
strict comparison results. Its `reproduce.py` reruns the comparison.

The L2 equations preserve original concentric ring teeth `zr=zs+2*zp`, ring
fixed/sun input/carrier output ratio `1+zr/zs`, assembly/phasing
`(zs+zr) mod np=0`, strict planet adjacency
`m*(zs+zp)*sin(pi/np)>m*(zp+2)`, and radial clearance `0.25m >= 0.2m-1e-12`.
SPEC constants `ha_planet=1`, `hf_ring=1.25` and minimum clearance factor 0.2
are disclosed in the report. Module variants collapse by integer stage identity;
the first feasible module supplies the displayed dimensions, preserving caller
module order. Search pairs sorted stage identities with replacement, so repeated
stages and symmetric-pair collapse match the original.

The objective is the Pareto frontier of relative ratio error and maximum stage
ratio. The complete original sort is `(error,max_ratio,zs1,zp1,np1,zs2,zp2,np2)`.
A new representative requires `max_ratio < best_max-1e-12`; `ties` counts all
in-tolerance rows in the same objective bucket rounded to nine decimals. The
report returns the complete `frontier` and exactly its first `top_k` entries in
`candidates`; no flagship rank is hardcoded. This small P2 contract scan remains
in L2 because generic kernel Pareto equality semantics would change this exact
legacy reporting contract. No general optimization framework is copied.

Both original budgets (200,000 stage checks; 6,000,000 pairs) are disclosed.
Requests exceeding them raise `ValueError` before returning a partial result;
supported results state `search.complete=true`. A normal empty feasible result
returns `ok=false`, an empty frontier, explicit reason, and complete counters.
`top_k_truncated` describes presentation truncation only.

`verify(inputs,candidate)` independently reconstructs equations without calling
the search or stage builder. It checks declared domains, phasing, strict
adjacency, module variants, dimensional fields, objective values and speeds.
It explicitly does not certify global rank or tie multiplicity; those are
checked against the independent frozen solver and small full enumeration.

Validation: `python -m unittest tests.test_flagship_p2 -v` exercises the original
flagship candidates/front/counters, reordered modules, top_k, a separate small
domain full enumeration, infeasibility, invalid requests and candidate tampering.
Production code has no archive imports. Frozen code runs only as an independent
test/evidence oracle in a subprocess.

This is geometry Stage0 only. Zero theoretical backlash requires profile shift
before manufacture. Planetary ISO 6336 strength, efficiency, thermal sizing,
M40 rating and system closure remain explicitly unimplemented; M38 equivalence
does not establish them.
