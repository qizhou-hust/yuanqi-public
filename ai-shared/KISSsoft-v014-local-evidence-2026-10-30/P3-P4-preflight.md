# P3/P4 只读勘察与运行准备

本工作未启动 COM/UI，未修改安装/源数据。驱动 `run_p4_connections.py` 只执行了 `--prepare` 与 py_compile；COM 实际运行与数值结论由主进程完成。

## 阶段包完整性

`C:/Users/AAA/Downloads/gearbase-v0.14-阶段包2-2026-10-30.zip`：25308044 bytes；Python zipfile.BadZipFile: Bad offset for central directory。EOCD 出现 UTF-8 replacement bytes ef bf bd；声明目录长度146653167、偏移3220111360越界。不是普通可调整偏移的 ZIP；丢失字节不可逆。不能从此包确认 P3/P4 产品输入。主代理另有包勘察记录。

## P3 本机原生输入

安装 `D:/Program Files/KISSsoft AG/KISSsoft 2026`；UTF-16 原生文件与 rpt 可直接读，变量命名可追溯。K01-K05 对应既有 M33 生成脚本中的官方例，未改产品油品。

|例|油品|ν40/ν100 mm²/s|油温°C|FZG-A|MP试验/级|Ra1/Ra2 μm|结论|
|---|---|---|---|---|---|---|---|
|K01|Klüberoil GEM 1-220 N mit Info zum Verschleissfaktor kw|220/19|80|14|1/10|0.6/0.6|MP输入存在，仍需本轮计算|
|K02|Mobilgear 600 XP 150|150/14.7|75|12|1/10|3/3|MP输入存在，仍需本轮计算|
|K03|ISO-VG 220|220/17.5|70|12|0/0|0.6/2|MP油品试验缺失，禁止填造|
|K04|ISO-VG 46|46/6.8|70|12|0/0|0.6/0.6|MP油品试验缺失，禁止填造|
|K05|ISO-VG 46|46/6.8|70|12|0/0|0.6/0.6|MP油品试验缺失，禁止填造|

`RechSt.ScoringStandard=1` 对应本机模板 ISO/TS6336-20/21:2022 分支；必须记录计算后的 `RechSt.ScoringStandardUsed`，不能只根据输入选择器宣称标准已应用。`RechSt.MicropittingStandard=1` 对应 ISO/TS6336-22:2018；模板明确要求 `ZS.Oil.FZGtestMP*ZS.Oil.MicroPittingTest>0`。K03-K05 缺失这一真实油品试验证据，不能用换油/填10伪装基线闭合。

完整报告 `Z012Le0.RPT` 包含胶合及微点蚀；独立七点中间报告 **`Z010IntermediateMicropittinge.rpt`** 自含初始化及 A/AB/B/C/D/DE/E 的曲率、分载、动压、膜厚等。可直接 `ReportWithParameters(template, output,0,0)` 输出RTF，格式2为HTML。`Z10MICROPITTINGRPSne.rpt` 是有变量上下文依赖的fragment，应由独立七点模板调用。胶合完整fragment为 `Z010Scoringe.rpt`，左右齿面分别 `Z010ScoringRighte.rpt` / `Z010ScoringLefte.rpt`，不应假设其独立导出可用。未找到名称明确为FBT分布的独立RPT，应从安装脚本/运行后的临时结果进一步发现。

核心COM输出：`ZP[0].FBT.SB`, `ZP[0].FIT.SSint`, `ZP[0].MP_ISO.Slam`, `ZP[0].MP_ISO.SlamB`, `ZP[0].MP_ISO.lamGFY`, `ZP[0].RefMP.lamGFP`, `ZP[0].MP_ISO.CriticalPoint`, `ZP[0].MP_ISO.hYmin`。七点 `ZP[0].MP_ISO.analysisPoints[i]`、逐轮 `ZPP[j].MP_ISO.analysisPoints[i]` 字段可见下方模板证据。

## P4 模块/原生/报告

|项|COM模块|官方原生|报告/版本|
|---|---|---|---|
|轴DIN743|W010|01 Shafts.W10；14 Pinion Shaft for Gear Pair Example 01.W10|W010Le0.RPT中调用W060Le0.RPT；W060Allg.RechMeth=2 调 W060DIN743e.RPT，DIN743:2012|
|轴承ISO281|W050|01 Deep Groove.W50；02 Tapered Roller.W50|W050Le0.RPT，ISO281:2007|
|键DIN6892|M02A|08/09/10 Keys (DIN 6892 Example 1/2/3).M2A|M02ALe0.RPT；Methode=0为C:2012，=1为B:2012|
|过盈DIN7190|M010|01 Cylindrical Interference Fit.M10|M010Le0.RPT，DIN7190-1:2017|

轴和轴承输入必须有载荷位置、支承、几何、材料/轴承具体型号等；不可仅凭标准名补完整轴系。轴承输入 `Allg.Drehzahl`, `Allg.AxialKraft`, `Allg.SollLeben`；逐轴承 `Lag[i].Fr/Fa`，结果 `Lag[i].Lh_basic`, `Lag[i].Lh`, `Lag[i].a23`。轴 DIN743 需检查 `shafts`, cross-section 对象和 notch details；未构造伪轴模型。

键：用户 d25、8×7、A型l32/ltr24、t1=4、Re 800/355/350、KA1.25、T25 已映射到配置；读 `m02A*.pzul/peq/Resulteq/Result*`。`M_tzul` 没有从模板确认直接COM字段，不能造字段；可由已确认 pzul、支承面积与直径透明复算并与原生等效分支比较。峰值Mmax/NL未给，不应把源例的15000Nm最小安全作为用户结果；配置对此保留警示。D.3 52526Nm仅输出值没有完整几何/材料，不能构建等价原生例。

过盈：已准备A1-A4配置，p输入例通过显式厚壁圆筒弹性柔度转换为U，作为自定义公差输入 `m01allg.eigenTol=true; m01w.tol.min=max=U; m01n.tol.min=max=0`；不是把压力写入输出字段。转换使用 `U_um = 1000*p*DF*[(((DaA/DF)^2+1)/((DaA/DF)^2-1)+νA)/EA + (((DiI/DF)^2+1)/(1-(DiI/DF)^2)-νI)/EI] + gF*(RzI+RzA)`。

**实际运行待验证**：本机嵌合量 `m01allg.s` 应为4.8μm才符合gF=.4；否则不能称附录A等价。内件E215000与双方ν.3按共用钢契约列入配置 open，需原标准核对。外载荷设0以隔离压力应力；因此滑移安全不作有限值结论。保留原生屈服安全与等效应力，可由本机压力推导纯转矩容量。脚本逐项记录SetVar前/后、计算消息、原生hash、RTF/HTML、重载结果。

执行（仅主代理独占COM时）：

`python D:/my_Works/Gears/kisssoft-v014-run/run_p4_connections.py --run D:/my_Works/Gears/kisssoft-v014-run/P4-connections-config.json`

## 官方模板摘录

以下摘录来自本机安装，仅证明变量与分支存在，不代表COM调用成功或数值闭合。

### Z012Le0.RPT

```text
280: 		1IF(%i) {RechSt.MicropittingStandard == 1 && (RechSt.RechenMeth != 4 && RechSt.RechenMeth != 7)}
284: 1<EXECUTE=Z010Micropittinge.rpt>
315: 		1IF (%i) {AND(OR(ZS.AGMArech != 0; AND(RechSt.RechenMeth != 4; ZP[0].FBT.SB+ZP[0].FIT.SSint > -2));RechSt.ScoringStandard != 3)}
318: 1<EXECUTE=Z010Scoringe.rpt>
320: 			1IF (%i) {RechSt.ScoringStandard !=3}
```

### Z010IntermediateMicropittinge.rpt

```text
43: 1%s %s                                                                                         %i             	   {GETSTRING(6520, Calculation in Point)}  {"(0:A, 1:AB, 2:B, 3:C, 4:D, 5:DE, 6:E, -1:No Point)"} {ZP[#mesh].MP_ISO.CriticalPoint}
54: 1Safety against micropitting                                [Sλ(B)]                           %10.3f               {ZP[#mesh].MP_ISO.SlamB}
81: <EXECUTE=Z10MICROPITTINGRPSne.rpt>
98: <EXECUTE=Z10MICROPITTINGRPSne.rpt>
```

### Z010Scoringe.rpt

```text
41: 9  X<SUB>S</SUB> = 0.2 according to ISO/TS 6336-20/21:2022
78: 5Calculation method according to                            %s	{"ISO/TS 6336-20/21:2022"}
146: 					1IF (%i) {RechSt.ScoringStandardUsed==1 || RechSt.ScoringStandardUsed==2}
343: 5Calculation method according to                            %s	{"ISO/TS 6336-20/21:2022"}
374: 				1IF (%i) {RechSt.ScoringStandardUsed==1 || RechSt.ScoringStandardUsed==2}
535: 5Calculation method according to                            %s {"ISO/TS 6336-20/21:2022"}
566: 				1IF (%i) {RechSt.ScoringStandardUsed==1 || RechSt.ScoringStandardUsed==2}
```

### M02ALe0.RPT

```text
3: 1IF (%i == 0)                                                               {m02Aa.Methode}
35: 5Equivalent effective surface pressure (N/mm²)                     [peq]                %10.2f              {m02Aw.peq}
111: 1Permissible surface pressure (N/mm²)                              [pzul]               %10.2f              {m02Aw.pzul}
113: 5Safety factor, equivalent load (fw pzul/peq)                      [SFeq]               %10.2f              {m02Aw.Resulteq}
114: 5Safety, maximum load (fL pzul/pmax)                               [SFmax]              %9.2f               {m02Aw.Resultmax}
115: 1Minimal safety                                                    [SF]                 %10.2f              {m02Aw.ResultW}
188: 1Permissible surface pressure (N/mm²)                              [pzul]               %10.2f              {m02An.pzul}
190: 5Safety factor, equivalent load (fw pzul/peq)                      [SFeq]               %10.2f              {m02An.Resulteq}
191: 5Safety, maximum load (fL pzul/pmax)                               [SFmax]              %9.2f               {m02An.Resultmax}
192: 1Minimal safety                                                    [SF]                 %10.2f              {m02An.ResultN}
216: 1Permissible surface pressure (N/mm²)                              [pzul]               %10.2f              {m02Ak.pzul}
218: 5Safety factor, equivalent load (fw pzul/peq)                      [SFeq]               %10.2f              {m02Ak.Resulteq}
219: 5Safety, maximum load (fL pzul/pmax)                               [SFmax]              %9.2f               {m02Ak.Resultmax}
220: 1Minimal safety                                                    [SF]                 %10.2f              {m02Ak.ResultP}
223: 1Safety = minimum (pzul/peq, fL pzul/pmax)
228: 1IF (%i == 1)                                                               {m02Aa.Methode}
351: 5Equivalent effective surface pressure (N/mm²)                     [peq]                %10.2f              {m02Aw.peq}    
355: 1Permissible surface pressure (N/mm²)                              [pzul]               %10.2f              {m02Aw.pzul}
358: 5Safety factor, equivalent load (fw pzul/peq)                      [SFeq]               %10.2f              {m02Aw.Resulteq}
359: 5Safety, maximum load (fL pzul/pmax)                               [SFmax]              %9.2f               {m02Aw.Resultmax}
360: 1Minimal safety                                                    [SF]                 %10.2f              {m02Aw.ResultW}
448: 5Equivalent effective surface pressure (N/mm²)                     [peq]                %10.2f              {m02An.peq}    
452: 1Permissible surface pressure (N/mm²)                              [pzul]               %10.2f              {m02An.pzul}
455: 5Safety factor, equivalent load (fw pzul/peq)                      [SFeq]               %10.2f              {m02An.Resulteq}
456: 5Safety, maximum load (fL pzul/pmax)                               [SFmax]              %9.2f               {m02An.Resultmax}
457: 1Minimal safety                                                    [SF]                 %10.2f              {m02An.ResultN}
486: 5Equivalent effective surface pressure (N/mm²)                     [peq]                %10.2f / %10.2f     {m02Aw.peq} {m02An.peq}   
490: 1Permissible surface pressure (N/mm²)                              [pzul]               %10.2f              {m02Ak.pzul}
493: 5Safety factor, equivalent load (fw pzul/peq)                      [SFeq]               %10.2f              {m02Ak.Resulteq}
494: 5Safety, maximum load (fL pzul/pmax)                               [SFmax]              %9.2f               {m02Ak.Resultmax}
495: 1Minimal safety                                                    [SF]                 %10.2f              {m02Ak.ResultP}
500: 1Safety = minimum (fw pzul/peq, fL pzul/pmax)
```

### M010Le0.RPT

```text
40: 5 Largest interference (µm)                                      [Po]                 %10.1f                   {m01allg.uebermass[2]}
41: 5 Smallest interference (µm)                                     [Pu]                 %10.1f                   {m01allg.uebermass[1]}
51: 5Interference (µm)                                               [P]                  %6.1f (%6.1f..%6.1f) {m01allg.uebermass[0]}{m01allg.uebermass[1]}{m01allg.uebermass[2]}
52: 5Embedding (µm)                                                  [s]                  %10.2f                   {m01allg.s}
57: 5Pressure stress by
60: 5 - Interference (working) (N/mm²)                               [p]                  %6.2f (%6.2f..%6.2f) {m01r.p[0]}{m01r.p[1]}{m01r.p[2]}
72: 1IF(%i == 0)                                                              {m01allg.hypothese}
```

## 首轮COM结果后的只读诊断及v2输入修正

主代理已运行首轮：4过盈 Calculate=true，但Rz6被数据库10060覆写4.8，s=3.84。A1压力91.548而非90，不算输入等价。安装 `kdb/M000.KDB` 的M000OBER表 Own Input ID19999（首条int32值，后续10010/10020与已知粗糙度级吻合）提供修正证据。v2显式选择DBIndex19999后输入Rz6。

键Methode0从官方rpt硬确认C；首轮false且结果未更新，不能归为已算。安装 `dat/M02A-001.DAT` 的 IN_OUT m02Ak.d 用NEXT_BIGGER查表；源d130未改，v2修正d25以选30这一行的8×7/t1=4。`kui/M02A_Geometry.kui` 证明数据对话框使用CallFunc ReadFromList。v2配置调用它，待主代理确认输出htW=3、peq34.7222。源材料轴Rm600<Rp800，现引用用户P4.1共用轴σB1000修正；毂源Rm200<Rp355仍冲突且缺用户Rm，键源Rm680>=Rp350。若软件强制校验必须保留真实阻断，不能填造。

所有v2案例ID带mapped-v2后缀保留首轮失败历史。输入文件 `P4-connections-config-mapped-v2.json`，同一驱动可运行。QA/QI可透明派生DF/DaA与DiI/DF；K/xi须核对标准定义，不能把近义原生字段当成同一定义。新增原始字段m01allg.pF/zeta/qpaqa来自官方模板，分别为塑性配合压力/塑性直径比/塑性与非塑性比，须保留名称。
