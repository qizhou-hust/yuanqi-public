# Existing commercial evidence audit — 2026-10-31

Read-only audit of `D:/my_Works/Gears/deliverables/KISSsoft-v016-local-evidence-2026-10-31`. No COM calls, reruns, model writes, acceptance-flag changes or evidence-grade promotions. All176 manifest entries match their actual file hashes. Each of the six B case source/native hashes matches its retained run receipt; native headers and reports identify KISSsoft2026, with executable26.0.0.0 recorded for Z012. R4 records2026 and native format26.0; its receipt has no executable file-version field.

| Existing run | Actual outputs | Assessment |
|---|---|---|
| OPT3-1 K04 | SH1/2=1.001403418/1.027042111; SF1/2=1.802195366/1.404235820; KHβ=1.287494818 | Named latest B checks SH1≥1 and SF2≥1.4 pass narrowly. Original declaration1.0/1.4 also passes. **KHβ is own input, Zst.KHbVariant=1**, so this does not independently establish face-load redistribution. |
| OPT3-2 K01 | SH1/2=1.000571535/1.034400532; SF1/2=1.511914728/1.401685290; KHβ=1.032863356 | Named latest B checks and original1.0/1.4 declaration pass narrowly. Auto tip shortening actually−0.020000mm, rather than predicted−0.01984mm. |
| OPT3-3 K02 | SH1/2=1.160373016/0.950197290; SF1/2=5.761281862/4.580931662; KHβ=1.457616778 | Named latest B checks SH1≥1/SF2≥1.4 pass. Original0.95/1.3 declaration passes, SH2 margin only0.00019729. If “same as above” means SH≥1 for both gears, SH2 fails. Preserve this interpretation gap. |
| R4′ D2=270 | Native and reload m02An.D2=270; cFlag=true; Kλe=1.085; htW/htN=8.127329179/7.9mm; fw=.576180873 | Requested branch actually ran and persisted. peq shaft/hub=143.548592772/147.679324895MPa, pmax=358.871481929/369.198312236MPa. pzul403/400/473MPa. All requested component factors/results are retained in receipt. fw exactly matches recorded figure7 interpolation; differs from equation23 by−.0008990892. This is numerical attribution, not inspection of vendor implementation. |
| K04 Cf=0 | Reopened Cf0/0; Ceq13.499999999965/14.700000000005µm; Ceff19.048088771µm; XCa1.775594183 | Requested diagnostic exists and matches predicted XCa1.775594. MPoptCa=false and correction amplitude edits read back. Does not choose the user's raw-Ca versus Ceq engineering convention. |
| K01 θintS components | XWrelT=1 directly available and report displays1.000 | Attempted, **partially unresolved**. T1T, θMT and θfla,int,T remain “not exposed/empty” in requested COM fields. No reconstruction is substituted as direct evidence. |

The retained runs record calculation and reload success, no reload differences, and full-precision raw/fresh verification outputs. These are prior execution records, not freshly reproduced runs. Saved native files primarily preserve inputs; rounded reports corroborate the result labels, while high precision outputs rely on retained COM/reopen receipts.

K04 and K01 each have all five SH1/SH2/SF1/SF2/εα values within relative1e−4 of the rounded predictions in the current request. This does not extend to K01 kXmn or independently validate K04 KHβ.

K02 prediction agreement does **not** meet relative1e−4: predicted SH2=.9608432695 versus actual.950197290 is approximately−1.108%. Existing factor-diff identifies KHβ1.418552995 versus1.457616778, KFβ1.337515042 versus1.368086457, and held life/root drift. Attribution status is **partial**: named contributing factors are present and external values corroborated against raw receipts; there is no audited quantitative substitution experiment accounting for the entire residual. The user's “or attributable” exception is therefore not automatically closed. No binary engineering rejection is inferred solely from this prediction discrepancy.

Input identity is also qualified: all requested edits have matching immediate readbacks, but saved x2 is recomputed by tiny amounts: K04+.00000000210252, K01+.00000000452478, K02−.00000002418477. Current K02 report's fourteen requested fields otherwise align with retained edits/readbacks. Four K04 correction-array paths are structured in native serialization and were not independently decoded; reopened Cf/Ceq readbacks corroborate their intended effect. None of these differences is silently rounded into exact identity.

K04 method-C sensitivity already exists (KHβ1.053801689, SH1=1.106884661, SF2=1.613100921); it uses inherited virtual shaft geometry and is not a replacement for the canonical own-input case or real shaft engineering evidence.

`receipt.json` supplies full case paths, actual SHA256 values, source/native/manifest comparisons, exact outputs/edits, threshold columns, identity gaps and a selective `{path,sha256,role}` private packaging inventory. Commercial native files and reports should remain in the private full archive; public release may contain this summary and suitably redacted audit results only. No whole milestone is closed by this audit.

Audit limits: prior receipts may contain execution mistakes this read-only review cannot detect; native input persistence and report hashes do not independently prove every captured COM output. No PDF visual-layout audit or new vendor run was performed.
