# M33 原型系数及 C001 差异复算

运行 `python -m gearmath.tools.m33_closure --output output/m33/closure.json`。本报告只覆盖两条原始门，TR30 全例 E4 尚未通过。

## 原型 22 项

来源：`gearmath/gear/m31_case.py` 的 `RECEIPT_EVIDENCE` 21 项，加同文件 `K_A` 工况输入；与 `docs/分路设计报告/L2-formula-library.md` 第 45 行核对。现有 K01 图用显式公式选择器逐项求值（K01 是公式可执行性载体，不代表全部适用域或全例 E4）。公式 20 项，`K_A` 是工况输入、`Y_ST` 是标准常数，均不计公式。

| 原型量 | 原收据映射 | 当前公式 ID | 实算值 |
|---|---|---|---:|
| K_A | case input | input_exception | — |
| K_V | contact/dynamic_factor | dyn.K_V | 1.0245577966565589 |
| K_Hbeta | contact/face_load_factor | ld.K_Hbeta | 1.0539719516336228 |
| K_Halpha | contact/transverse_load_factor | ld.K_Halpha | 1.0 |
| K_Falpha | root/transverse_load_factor | ld.K_Falpha | 1.0 |
| Z_L | contact/lubricant_factor | surface.Z_L | 1.0199972222923663 |
| Z_V | contact/velocity_factor | surface.Z_V | 0.9741767483906335 |
| Z_R | contact/roughness_factor | surface.Z_R | 0.9801364473354708 |
| Z_W | contact/work_hardening_factor_pinion | surface.Z_W.neutral | 1.0 |
| Z_X | contact/size_factor | surface.Z_X | 1.0 |
| Z_NT_1 | contact/life_factor_pinion | life.Z_NT.1 | 0.9301998270622773 |
| Z_NT_2 | contact/life_factor_wheel | life.Z_NT.2 | 0.9624712547252343 |
| Y_ST | root/stress_correction_factor_reference | input_exception | — |
| Y_NT_1 | root/life_factor_pinion | life.Y_NT.1 | 0.9015612172465877 |
| Y_NT_2 | root/life_factor_wheel | life.Y_NT.2 | 0.9218698696002628 |
| Y_drelT_1 | root/relative_notch_sensitivity_pinion | rf.Y_drelT.1 | 0.9966286114660069 |
| Y_drelT_2 | root/relative_notch_sensitivity_wheel | rf.Y_drelT.2 | 0.9945578158370568 |
| Y_RrelT_1 | root/relative_surface_factor_pinion | rf.Y_RrelT.1 | 0.956738365558955 |
| Y_RrelT_2 | root/relative_surface_factor_wheel | rf.Y_RrelT.2 | 0.956738365558955 |
| Y_X | root/size_factor_pinion | rf.Y_X.common | 0.99 |
| Y_B | root/rim_thickness_factor_pinion | rf.Y_B.common | 1.0 |
| Y_DT | root/deep_tooth_factor | rf.Y_DT | 1.0 |

## C001 新链对 M31

新链读取 C001.factors 契约并重算，下表数值为未圆整输出。对每轮以新图求得相同 G、zn、H，从 π/6 按旧 vendor `_tooth_root_geometry` 连续迭代 9 次；以所得角代入同一新图重算并比较 M31 收据。诊断替换仅在复制模型内进行，不改变生产公式。新链默认按相邻两次差 < 1e-14 收敛。九次重算 18 项均与收据相对及绝对 1e-12 范围相符，表明齿根的细小差异来自迭代终止口径，而非输入调节；其余浮点量差为数值运算精度量级。

| 项 | M31 | 新链 | 新减旧 | 九次迭代减旧 | 解释 |
|---|---:|---:|---:|---:|---|
| Z_H | 2.49457317139 | 2.49457317139 | 8.882e-16 | 8.882e-16 | same chain; floating point evaluation order |
| Z_E | 189.811700438 | 189.811700438 | -2.842e-14 | -2.842e-14 | same chain; floating point evaluation order |
| Z_eps | 0.889823502526 | 0.889823502526 | -5.551e-16 | -5.551e-16 | same chain; floating point evaluation order |
| Z_B | 1.05722457388 | 1.05722457388 | -2.22e-16 | -2.22e-16 | same chain; floating point evaluation order |
| sigma_H_1 | 1046.22727276 | 1046.22727276 | 4.547e-13 | 4.547e-13 | same chain; floating point evaluation order |
| sigma_H_2 | 989.597951662 | 989.597951662 | 7.958e-13 | 7.958e-13 | same chain; floating point evaluation order |
| S_H_1 | 1.19081483146 | 1.19081483146 | -6.661e-16 | -6.661e-16 | same chain; floating point evaluation order |
| S_H_2 | 1.27315831246 | 1.27315831246 | -1.11e-15 | -1.11e-15 | same chain; floating point evaluation order |
| K_Fbeta | 2.24010540661 | 2.24010540661 | 0 | 0 | same chain; floating point evaluation order |
| Y_F_1 | 1.60886163457 | 1.60886000414 | -1.63e-06 | -5.107e-15 | root theta iteration: vendor nine steps vs converged fixed point |
| Y_F_2 | 1.41745004263 | 1.41744993459 | -1.08e-07 | -4.441e-15 | root theta iteration: vendor nine steps vs converged fixed point |
| Y_S_1 | 1.8104349453 | 1.81043563296 | 6.877e-07 | 1.776e-15 | root theta iteration: vendor nine steps vs converged fixed point |
| Y_S_2 | 1.94670948196 | 1.94670953931 | 5.735e-08 | 2.22e-15 | root theta iteration: vendor nine steps vs converged fixed point |
| sigma_F_1 | 179.761282019 | 179.761168127 | -0.0001139 | 5.684e-14 | root theta iteration: vendor nine steps vs converged fixed point |
| sigma_F_2 | 170.29560623 | 170.295598266 | -7.964e-06 | 8.527e-14 | root theta iteration: vendor nine steps vs converged fixed point |
| S_F_1 | 4.50642384679 | 4.50642670196 | 2.855e-06 | -1.776e-15 | root theta iteration: vendor nine steps vs converged fixed point |
| S_F_2 | 4.87820056327 | 4.87820079141 | 2.281e-07 | -2.665e-15 | root theta iteration: vendor nine steps vs converged fixed point |
| K_V | 1.03916605182 | 1.03916605182 | 0 | 0 | same chain; floating point evaluation order |

逐轮 θ、G、zn、H 及齿根中间值见机器报告。C001 链仍保留 KHβ、部分材料/寿命系数为明确标注的证据输入，并包含油基等假设；该对照不证明全部系数已经按 C001 材料计算，也不构成产品强度放行。

## TR30 例7、8 未闭合

例7 首差为 σFlim2：ISO 18265 表 A.1 的 HB→HV 插值与 TR30 表值口径不一致，影响 σFlim2、σHlim2 及其下游 σFP2；相同 HV 的 KISSsoft 对照不能证明对原表一致，σFP2 尚有未归因余差。例8 σHP1/2 首差来自 Rz 的 6Ra 与印刷 Rz 口径不同；σF0_1、σF_2 先在齿根应力链出现，KISSsoft 同向超出印刷值而彼此接近，不能据此判原表错误。详情与实际失败行见 `milestones-multi-run/m33/full58-current.json` 和 `docs/M33-验收报告.md`。解释差异不等于数值通过。
