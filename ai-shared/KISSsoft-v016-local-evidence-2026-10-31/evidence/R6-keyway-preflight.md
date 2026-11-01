# R6 single-keyway functional coverage: static preparation

No COM, GUI, or KISSsoft calculation was performed by this branch. A keyway cross-section is feasible as an explicitly assumed standard/default functional branch. It is not a verified real-part keyway or a production strength acceptance.

Exact field evidence:

* Installed `example/01 Shafts.W10` Qu[0] is a keyway, with `Kerb.Form=4`, `Passf.n=1`, `Passf.Norm=10010`, and `Passf.NutArt=0`. Its geometry is d50, b14, t5.6 and its input uses `Geo.DataFromGeometry=true` because the example has a real shaft-editor keyway object.
* Official `rpt/W060crosssectionse.RPT` lines77–94 selects the keyway branch with Kerb.Form4. NutArt0 means end milling cutter; NutArt1 means side milling cutter; other branch means keyway combined with interference fit (FKM2012). Norm10040 is **Own input**. Passf.Name is the standard-name readback. Outputs are Geo.b and Geo.t. There is no Geo.h key-height field in this report branch.
* `kui/W010_SectionDetails.kui` exposes StandardForKeyWay, KeyGrooveWidth, KeyGrooveDepth, NumberOfKeys, ManufacturingForKeyWay. Own-input width/depth are editable only when Own Input is selected, per Manual_e.pdf p582.
* `help/Manual_e.pdf` pp648–649 confirms DIN/FKM/AGMA use outer shaft diameter d for section resistance, and the standard key geometry tables include DIN6885.1/.2/.3. These method branches do not require pretending that an unspecified root radius is known. The keyway radius still remains an unverified real-part geometry attribute.

Standard geometry source:

Installed `dat/M02A-001.DAT` explicitly states DIN6885.1:1968. Its NEXT_BIGGER table gives d<=30 and >22: key **8×7**, shaft groove minimum depth4 with tolerance width.2, hub groove minimum3.3 with width.2, radius range.25–.4. Key height7 is not shaft groove depth. The example d50 has Geo.t5.6, consistent with the mean of that row's shaft groove5.5..5.7. Thus d25 standard readback may be Geo.t4.1; do not reject it because it is not4.0. This mean-depth interpretation is an inference from the official example, not a directly named manual definition.

Proposed standalone branch:

Replay solved R1b S3a section at local y130/global120, d25, solid section and existing material/load identity. Leave physical shaft stiffness/loads unchanged. Set the local strength cross-section to keyway Form4, n1, Norm10010 and NutArt0. Keep DataFromGeometry=false because this seed does not contain a corresponding keyway object in the editor. Do not invent a keyway length or slot position by inserting an editor sub-element. Read back standard name, b, t, method, x,d, notch coefficients and safety outputs after calculate/save/reload.

`Passf.Norm=10010` is supported as a valid keyway selection ID by the installed official shaft example, but its exact DIN6885.1 label must still be confirmed by Passf.Name. Existing M02A's DinIdK10010 reports DIN6885.1:1968 Default; this is corroboration across modules, not proof that their lookup tables have identical IDs. The separate rating-method selector remains `W060Allg.RechMeth=2` for the validated DIN743 branch; Norm10010 is a geometry-standard selection, not the DIN743 method ID.

Scope label: **DIN743 default single keyway functional coverage; y130/d25; standard-derived 8×7; assumed end-milled; actual part keyway geometry unverified.** Keep R6 loadcase2-on-S2 and local-hollow-di10-on-S2 as separate experiments so their differences remain attributable. If a fatigue case is desired, the source S3a's static-only setting must be intentionally changed and recorded; do not silently describe static-only output as a fatigue check.

# R4 fw: equation and graph difference closed by arithmetic

The original DIN6892:2012-08 page17 was rendered and visually checked in `R4-fw-DIN-p17.png`. It explicitly contains Eq23 fW=2*NW^-0.1 and **Figure7**; the installed KISSsoft manual refers to a differently numbered figure, so its figure number is not the source-standard figure number.

At NW250000, Eq23 gives .5770799623628854. Figure7's straight segment joins (1000,1) and (1e10,.2) on logarithmic axes. Interpolating log(fW) linearly in log(NW) gives .5761808731627712, exactly the main branch's reported native result at binary-double precision. The native difference from Eq23 is -.000899089200114167, or -.1557997606489%. Both round to .58. This establishes a precise graph-versus-equation explanation, without changing the core's Eq23 implementation to match a commercial result.
