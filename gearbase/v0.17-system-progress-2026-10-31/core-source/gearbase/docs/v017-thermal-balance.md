# v0.17 thermal balance

`gearmath.system.thermal_balance.solve(spec)` finds an oil temperature in an explicitly supplied Celsius bracket by bisection of ISO/TR 14179-1 heat rejection minus specified losses. Power is kW, A_c m², k kW/(m²·°C). Required keys: `A_c`, `k`, `ambient_C`, `bracket_C` (two temperatures), `temperature_tolerance_C`, `residual_tolerance_kW`, `max_iterations`, and `loss_model` with `fixed_kW` and `components` list. No physical defaults are chosen. Both tolerances must be met for an interior root; an endpoint satisfying residual tolerance is accepted.

Temperature-dependent components require `loss_model.viscosity` with `nu_40`, `nu_100` (cSt). Supported component dictionaries:

* `type: mesh`, plus `K`, `V`, `T1`, `n1`, `beta_w`, `M`.
* `type: bearing_churning`, plus `f0`, `n`, `d_m`, `M3`.
* `type: windage_smooth_od`, plus `f_g`, `n`, `D`, `L`.

These use the existing registered micropitting viscosity curve and thermal functions, including their domain restrictions. `fixed_kW` represents explicitly authored total remaining losses. The caller is responsible for completeness and applicability of the selected physical model. No loss mechanism or coefficient is inferred. Results have `status` of `converged`, `no_bracket`, `nonconvergence`, or `invalid`; failures do not imply a valid thermal rating. Bracket and residuals support diagnosis. Endpoint signs alone do not establish uniqueness of roots.

Verification: synthetic fixed 2 kW, A_c=2 m², k=0.02, ambient 20 °C gives the independent closed-form result 70 °C. A separate mesh/viscosity numerical root comparison uses independently coded bisection in the test. These are numerical checks only, not independent external engineering validation or E5 evidence. The ISO/TR formula registrations retain their original evidence levels and limitations. This solver computes equilibrium for the supplied load/loss model, not a maximum thermal input-power rating.

Product integration: thermal.method={value:"equilibrium",unit:"-",source:"..."}. Every scalar or aggregate is a sourced system-input leaf. Required temperature_limit_C uses degC, bracket_C uses degC, temperature_tolerance_C usesK, A_c usesm^2 and k useskW/(m^2*K); loss_model uses the component units above. Unknown/null methods and mixed units block; an absent method preserves the original power-rating route. No temperature limit is inferred.
