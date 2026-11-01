# K02 shifted helical manufacturing review preparation

**HOLD: incomplete; not for manufacture; external review not completed.**

Source: `data/kisssoft/K02-helical.json`; SHA256 `3e9571540e9ac2d680067cbdd1a03c17ca782b38b3f9711b42c80a8335d542aa`
Formula model SHA256: `df40c5a703bd2d90248f3c0650a0ce39cb3885b746f96c2ec26766072447e686`

The SVG contains dimensioned diameter envelopes and axial widths only. The audited archived tooth authority rejects nonzero profile shift. No tooth curves are fabricated.
Source tip diameters are used explicitly (including shortening), not replaced by basic-rack tip formulas. ISO 21771 original text remains not_in_evidence. DIN 3961:1978 grade is retained without conversion.

| Quantity | Value | Unit | Source locator / formula |
|---|---:|---|---|
| m_n | 1.5 | mm | com['ZS.Geo.mn'] |
| alpha_n | 0.3490658504 | rad | com['ZS.Geo.alfn'] |
| beta | 0.2443460953 | rad | com['ZS.Geo.beta'] |
| z_1 | 27 | 1 | com['ZR[0].z'] |
| x_1 | 0.3255 | 1 | com['ZR[0].x.nul'] |
| b_1 | 21 | mm | com['ZR[0].b'] |
| da_1 | 45.69235199 | mm | com['ZR[0].da.nul'] |
| haP_1 | 1 | 1 | com['ZR[0].Tool.RefProfile.haP'] |
| hfP_1 | 1.25 | 1 | com['ZR[0].Tool.RefProfile.hfP'] |
| rhofP_1 | 0.38 | 1 | com['ZR[0].Tool.RefProfile.rhofP'] |
| A_sn_e_1 | -0.044 | mm | report.A_sn_e_1 (line 1555) |
| A_sn_i_1 | -0.064 | mm | report.A_sn_i_1 (line 1555) |
| DIN3961_grade_1 | 6 | 1 | report.Q_grade_1 (line 111) |
| reported_f_pt_1 | 7 | um | report.f_pt_1 (line 1738; DIN source, not ISO conversion) |
| reported_f_pbT_1 | 7 | um | report.f_pbT_1 (line 1742; DIN source, not ISO conversion) |
| reported_f_falpha_1 | 6 | um | report.f_falpha_1 (line 1758; DIN source, not ISO conversion) |
| reported_f_Hbeta_1 | 9 | um | report.f_Hbeta_1 (line 1774; DIN source, not ISO conversion) |
| z_2 | 104 | 1 | com['ZR[1].z'] |
| x_2 | 0.07388831908 | 1 | com['ZR[1].x.nul'] |
| b_2 | 20 | mm | com['ZR[1].b'] |
| da_2 | 163.9733911 | mm | com['ZR[1].da.nul'] |
| haP_2 | 1 | 1 | com['ZR[1].Tool.RefProfile.haP'] |
| hfP_2 | 1.25 | 1 | com['ZR[1].Tool.RefProfile.hfP'] |
| rhofP_2 | 0.38 | 1 | com['ZR[1].Tool.RefProfile.rhofP'] |
| A_sn_e_2 | -0.08 | mm | report.A_sn_e_2 (line 1555) |
| A_sn_i_2 | -0.13 | mm | report.A_sn_i_2 (line 1555) |
| DIN3961_grade_2 | 6 | 1 | report.Q_grade_2 (line 111) |
| reported_f_pt_2 | 8 | um | report.f_pt_2 (line 1738; DIN source, not ISO conversion) |
| reported_f_pbT_2 | 8 | um | report.f_pbT_2 (line 1742; DIN source, not ISO conversion) |
| reported_f_falpha_2 | 6 | um | report.f_falpha_2 (line 1758; DIN source, not ISO conversion) |
| reported_f_Hbeta_2 | 8 | um | report.f_Hbeta_2 (line 1774; DIN source, not ISO conversion) |
| alpha_t | 20.56170535 | deg | geo.alpha_t |
| beta_b | 13.1400591 | deg | geo.beta_b |
| d_1 | 41.73985199 | mm | geo.d.1 |
| db_1 | 39.08079327 | mm | geo.db.1 |
| df_1 | 38.96635199 | mm | mfg.df.1 |
| s_n_1 | 2.711611424 | mm | mfg.sn.1 |
| s_ne_1 | 2.667611424 | mm | mfg.sn.e.1 |
| s_ni_1 | 2.647611424 | mm | mfg.sn.i.1 |
| d_2 | 160.7757262 | mm | geo.d.2 |
| db_2 | 150.5334259 | mm | geo.db.2 |
| df_2 | 157.2473911 | mm | mfg.df.2 |
| s_n_2 | 2.436873937 | mm | mfg.sn.2 |
| s_ne_2 | 2.356873937 | mm | mfg.sn.e.2 |
| s_ni_2 | 2.306873937 | mm | mfg.sn.i.2 |

## Open manufacturing gaps

- G1: audited tooth_authority rejects nonzero shift; shifted helical flank/root/cutter envelope absent
- G2: DIN 3961:1978 grade 6 retained; ISO 1328 grade/requirements not authorized
- G3: bore/hub/keyway, datum scheme, fits, dimensional tolerances and surface finish unspecified
- G4: material/heat-treatment manufacturing specification and inspection acceptance need approval
- G5: helix hand and coordinate convention not explicit in source; no hand inferred from absolute beta
- G6: measurement span k and ball diameter not evidenced; Wk/MdK inspection plan pending
- G7: external process reviewer, issues closure and signature absent

A complete manufacturing drawing requires the missing geometry and engineering inputs before external process approval. Hash verification checks reproducibility, not engineering independence or signatures.
