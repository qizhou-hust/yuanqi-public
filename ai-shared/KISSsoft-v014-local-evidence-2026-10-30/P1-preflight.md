# P1 TR30例7 fsh0：只读证据分析

状态：原件身份和当前KHβ比载荷重建 VERIFIED；独立fsh0导出及TR30双斜齿归一化语义 OPEN。本分路没有启动KISSsoft COM/GUI，没有修改历史输入；使用主代理当前复算JSON。采用 verify-gear-rating-cross-tool 与PDF技能核查字段和标准扫描页。

## 原件与运行

- 原生文件：D:/my_Works/Gears/M33-TR30-7-8-2026-10-29/TR30-example-7/TR30-example-7.Z12
- 实测SHA256：ba9205dda2b8fcd9f7a6bb5eb40ed7c66924782b886a455fa4b1b95839787f8e，与冻结要求及历史validation.json一致。
- 当前运行：D:/my_Works/Gears/kisssoft-v014-run/P1-TR30-example7-unchanged/run.json；generated_utc=2026-10-31T02:32:29.914511+00:00；edits=[]；calculate_return=true；module=Z012；version=2026。
- 历史证据：原件同目录TR30-example-7.pdf、TR30-example-7.rtf、report.txt、high-precision-values.csv、run.json。CSV176–177行为fsh/fsh00；comparison.csv第91行fsh0未提取、第98行fsh已提取。
- 后来的parallel-v09-2026-10-29/m33-kisssoft/ex7-base-native/run.json属于材料变体，fsh=1.4030094487056353，不能替代本次冻结源值1.402989614077725。

## 可读字段及当前值

以下路径均为当前run.json的values对象；缺失字段另明确来源。

| 字段 | 值 |
|---|---:|
| ZP[0].Ft | 6884.284732098091 N |
| ZS.KA / ZS.Kgam | 1 / 1 |
| ZP[0].KV.KV | 1.6837191321758298 |
| ZR[0].b | 215.89999999999998 mm，UI含槽总宽 |
| ZPP[0].Fuss.b | 82.54999999999998 mm，单侧计算宽bB |
| ZP[0].KHdat.fsh | 1.402989614077725 μm，fsh·B1 |
| ZP[0].KHdat.fsh00 | 1.402989614077725 μm，fsh |
| ZP[0].KHdat.B1 | 1 |
| ZP[0].KHdat.FaktorK | 0.48 |
| ZP[0].KHdat.Stutzwirku | 1，with stiffening |
| ZP[0].KHdat.l / S / dsh | 355.6 / 0 / 63.5 mm |
| ZP[0].KHdat.Fby | 3.2648404937760804 μm |
| ZP[0].KV.cgbet | 16.383849921262264 N/mm/μm |
| ZP[0].KHb | 1.3809487351110064 |

当前未导出ZR[0].PfeilNutB、Zst.fshFlag，二者从冻结Z12 UTF16原文及历史run.json读取为50.8 mm、false。当前ZP[0].b登记not exposed/empty，不能冒充直接总宽字段。

本机官方模板 D:/Program Files/KISSsoft AG/KISSsoft 2026/rpt/Z010ISOGeneralFactorse.rpt 第120行将KHdat.fsh对应fsh·B1，第121行将fsh00对应fsh。尾部00不是标准下标0。例7因B1=1两者相等，例8因B1=0.1二者差10倍。

## 原标准及本机手册目读

标准原件：D:/my_Works/Gears/M33-evidence-2026-10-28/standards/core/ISO 6336-1-2019.pdf。本轮渲染扫描页并目读：

- PDF52/印44，7.2.2，式39后：参考圆横向比载荷Fm/b=Ft*KA*Kγ*KV/b。
- PDF58/印50，7.5.1：本条双斜齿b=2bB；两轮宽取小值，使用排除倒角等影响的齿根有效宽。
- PDF59/印51，式43：KHβ=1+Fβy*cγβ/[2*(Fm/b)]，适用全宽接触分支。
- PDF65/印57，式60：双斜齿fsh=(Fm/b)*2*k_unit*[B*+K′*l*s/d1²*(d1/dsh)^4-0.3+0.3]*(bB/d1)^2；单一啮合B*=1.5；外因子明确有2，式后回指7.2.2。
- PDF137/印129，表F.1：fsh0是单位比载荷下的轴变形，单位μm·mm/N；表中没有单独的双斜齿fsh0归一化等式。TR30表内印μm不能直接当严格量纲。

图像位于D:/my_Works/Gears/kisssoft-v014-run/P1-ISO6336-1-PDF52.png，同前缀另有PDF58、59、65、137。

本机Manual_e.pdf PDF216 §15.1.7规定双斜齿UI输入宽为两半加槽。原报告report.txt第109–121行也显示总宽215.90、槽50.80、计算单侧宽82.55。因此标准b=215.9-50.8=165.1=2*82.55；ZR[0].b不能直接作为标准b。

## 精确值与独立重建

Fm=Ft*KA*Kγ*KV=11591.201914779513 N。

| 归一化口径 | 比载荷 N/mm | fsh/比载荷 μm·mm/N | 状态 |
|---|---:|---:|---|
| 标准总接触宽b=165.1 mm | 70.20715878122056 | 0.019983569174900226 | DERIVED_STANDARD_TOTAL_WIDTH |
| 将式60外因子2并入单侧比载荷Fm/bB，bB=82.55 | 140.41431756244114 | 0.009991784587450111 | DERIVED_PER_HELIX_NORMALIZATION |

由当前导出的Fβy、cγβ、KHβ独立按式43反解Fm/b=Fβy*cγβ/[2*(KHβ-1)]=70.20715878122054 N/mm，与总宽值机器舍入内相等。分支判据Fβy*cγβ/[2*(Fm/b)]=0.3809487351110064<1成立。若把全Fm除半宽用于式43，则KHβ=1.190474367555503，实际输出是1.3809487351110064。

故KISSsoft本例KHβ计算链与标准总宽比载荷一致，可通过中间量重建验证。当前没有软件直接导出的fsh0。如果外部合同定义fsh0=fsh/(7.2.2标准比载荷)，则所得值为0.0199835691749。0.00999178458745是把式60因子2吸收到单侧比载荷后的另一个归一化系数；它接近TR30印0.010，但这一吻合不证明软件直接输出或明确采用该fsh0语义。标准表F.1没有明确解决这个符号约定差异，TR30来源差异继续OPEN。

## 无需改参的最小诊断

P1已有足够证据重建KHβ比载荷，无需新增改参运行。可在隔离自定义报告中同时输出已确认字段、总宽与单侧两种派生表达式，明确标DERIVED。改变宽度或扭矩会影响KV等多个量，不建议为fsh0符号语义试参；已有例8即可证明fsh/fsh00字段映射。没有确认原生fsh0字段或双斜齿归一化选择开关，禁止猜字段或按目标值选宽。

## 主路P2自动a参考

本机 D:/Program Files/KISSsoft AG/KISSsoft 2026/help/Manual_e.pdf PDF215 §15.1.5：中心距单位右侧复选框选中=保持a，未选=从变位系数总和计算a。

PDF152 §10.5.2支持CallFunc(BSTR name)与CallFuncNParam(VARIANT paramArray)，但特殊计算名字清单需厂家提供。PDF155示范CalculatePathOfContactForPairKS是接触分析命令，并非中心距。未发现官方自动a具体命令，不应臆造CalculateFunction。

冻结原生Z12 UTF16内有Zst.SpezVar2=true、Zst.SumXspez=false，但没有证实其对应中心距复选框，不能据此修改。若主路用ISO几何从已知x总和派生a，应将其登记为派生输入并保留公式、数值和前后读回，不称软件自动a。
