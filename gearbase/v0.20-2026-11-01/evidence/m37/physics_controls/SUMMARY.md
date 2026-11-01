# Bounded physical load control, P08 and P03 d18

Two actual headless CalculiX 2.23 controls are complete. Exact resultant moment removes part of P08's stress deficit, but the deficit persists. The load-patch moment defect is real and is not a sufficient explanation of the FE/ISO discrepancy. No acceptance tolerance, reference result, canonical matrix artifact, or product source was changed. These derived cases do not replace canonical evidence.

## Predeclared intervention

`predeclared.json` was written before either solve. For each existing d18 mesh, retain geometry, material, fixed constraints, patch node membership, force direction, and total normal force. Only replace positive scalar nodal weights on the existing patch. The HPSTC point defines target moment directly: M = px*Fy - py*Fx. No stress or ISO reference enters weight selection.

Choose positive weights w_i' proportional to w_i*exp(lambda*q_i), where q_i is the scaled difference between node moment per unit normal force and target. Bisection imposes sum(w_i')=1 and sum(w_i'*moment_i)=target. This is the minimum relative-entropy change from the original patch weights subject to these two constraints. It represents a nonuniform compressive patch redistribution and is a controlled discretization study, not proof that the physical contact pressure follows this distribution.

Both targets are inside the existing patch's scalar moment convex hull, so mesh refinement and negative nodal forces are unnecessary. P08's five weights range from 0.01915 to 0.48434; P03's from 0.04307 to 0.42411. Every nodal force is parallel to the original compressive normal. All INP text outside CLOAD is equal before and after. Normal force is 106.41777725 N per 1 mm thickness.

## Measured results

| Quantity | P08 d18 | P03 d18 passing control |
|---|---:|---:|
| Original moment, N mm | 2995.9983924 | 2002.0309718 |
| HPSTC / derived moment, N mm | 3000.0000000 | 2000.0000000 |
| Original first-principal root surface stress, MPa | 108.5717258 | 142.9316788 |
| Derived first-principal root surface stress, MPa | 109.8421951 | 142.0425123 |
| Stress change | +1.17017% | -0.62209% |
| ISO reference stress retained, MPa | 127.2284561 | 142.8213961 |
| Derived FE / ISO | approximately 0.86335 | approximately 0.99455 |
| Derived force equilibrium relative residual | 1.5812e-8 | 1.3591e-8 |
| Reaction + applied moment residual, N mm | -1.0618e-5 | -1.3698e-5 |

Input force residuals are zero at stored arithmetic precision. Input moment residuals are 0 and -2.27e-13 N mm. The solver's finite-precision DAT reaction output accounts for the much larger, still small, displayed reaction residuals. Both runs have strict reader accepted status and passed deck preflight. Peak surface locations did not change. Surface stress uses the existing no-smoothing Gauss-point extrapolation method, unchanged from canonical extraction.

P08's original root bending-moment defect is about -2.145%, despite a global moment error of only -0.1334%. Correcting it raises calculated root stress by 1.170%, leaving roughly a 13.67% deficit against the frozen reference. P03 moves slightly below its reference. Thus correcting the patch moment is physically necessary to remove this confounder, but cannot be presented as numerical qualification or closure of the systematic discrepancy. This study stops after its two predeclared jobs. It does not establish mesh convergence, support independence, or a cause for the remaining difference.

## Provenance and reproducibility

Approved ELF SHA256: `31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862`. `solver_allowance.verify` checked exact bytes and origin proof immediately before each run. WSL launch additionally checked binary SHA256, used one OpenMP thread, and bounded each run by 120 seconds. The full command, permission result, strict output-read result, and raw DAT/STA/log hashes are in each derived `.record.json`. Source mesh/meta/DAT/record hashes were frozen in `predeclared.json` and all eight matched after solving (`results.json`). The script hash is recorded there as well.

To reproduce from PowerShell, set `$env:PYTHONUTF8='1'`, then run `python D:/my_Works/Gears/v020-closure-run/m37/physics_controls.py` and `python D:/my_Works/Gears/v020-closure-run/m37/physics_controls.py --run`. This writes only the derived evidence directory. The existing approved runtime and original matrix are required.

## Where This Review May Be Wrong

- Matching force and moment is an exact low-order physical control, but a nonuniform patch also changes higher spatial load moments. The measured change is attributable to the declared patch redistribution; it is not a universal sensitivity coefficient for root moment.
- The existing stress extrapolation is reused, rather than independently rederived here. The prior source-bound independent review agreed with canonical extraction. A different independently verified surface recovery method could alter the residual comparison.
- A single mesh for each case does not resolve remaining support, geometry-model, or discretization effects. No statement that ISO omits radial/compressive stress is made; ISO YS accounts for a complex stress system.
