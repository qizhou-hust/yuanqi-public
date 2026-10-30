# 旧 CAD/CAE 资产复用盘点

**最可能是 CADBench R25.20 的源绑定 CAD/CAE 系统。** 它在 `D:/my_Works/自研CAD-CAE系统` 有原包和建模工作包；可直接阅读的 R25.20 源码副本位于 `D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench`。这不是只有蓝图：已有版本工况、真实 CalculiX worker、原始字段检查、齿轮接触诊断和源变更后结果过期实现。

历史 `evidence/step-promotion/acceptance.json` 保存两次 FE job ID、反力平衡误差约 1.54e−7/8.20e−8、旧结果 stale 和新结果 current。该证据已读并计哈希，但本次没有重跑旧求解。另一个可能记忆对象是 `modeling-workbench/unified-mechanical-intelligence`：其通用 `adapters/fea` 实际为空，registry 标 planned，不能将统一工作区本身称为已完成的 FEA 适配器。

本次只读检索、检查源码与有限纯函数探针，旧项目未修改、未启动求解器。所有路径、完整 SHA256、Python入口行号、依赖和验证状态在 [ASSET-REUSE.json](./ASSET-REUSE.json)。

| 资产 | 实际职责与复用决定 | 边界 |
|---|---|---|
| A01 CADBench R25.20 源绑定 CAE 工况与失效传播 | 限定安装板的版本化材料、支承、载荷和网格；源SHA+工况SHA双绑定；求解报告与原始工件核验；改源后旧结果stale。 复用设计输入/分析工况/观测结果分离和双哈希冻结接口模式；新M37 adapter引用现有deck与meta身份，不把安装板约束移植为齿轮默认值。 | 只支持受控安装板，不能称通用CAE意图协议。 default_case含未认证铝材和250N示例，不能默填到新任务。 |
| A02 旧 FEA 调度与完成门 | 提交前检查源绑定参数、量纲与数值范围；隔离子进程、持久作业状态；零退出码+无ERROR+完成标志+DAT存在+字段完整性。 复用dispatch前重新校验输入身份、运行后保存真实退出码及原始工件的模式；M37继续使用自己的runner适配，不另建第二调度器。 | 旧worker会求解/写新job，资产审计未执行。 完成单次solver gate不等于压力/网格/相位收敛。 |
| A03 旧结果字段完整性检查 | 核DAT最终U/RF/S时间与STA一致、集合展开、节点覆盖、单元/IP覆盖、有限值，拒绝缺行和重复行。 作为M37原始字段读取后的独立补充coverage checker；adapter必须声明所请求字段和未覆盖接触字段。 | 不解析接触CF/CSTR覆盖。 同kind只保留最后set，通用多集合必须扩展并测试，不能默认为全覆盖。 |
| A04 旧接触分支与压力峰定位 | 把CPE6的DAT面3/4/5映射回INP S1/S2/S3；按共享边界节点找活动接触分支、峰值边/圆角；全位移下二次边新投影单侧尖峰检查。 优先移植语义算法为只读adapter或显式调用稳定函数；用M37自己的INP reader提供body/surface/coordinates，避免重写齿形。 | nominal_spur_state只支持等齿数无变位，不能用于M37 z20/36。 M37 ph10只打印PMASTER位移，不能运行需全节点U的新投影检查。 采样点计数不是接触力权重；不得按次数估算load share。 全局接触重心不一定表示一个接触分支。 |
| A05 无变位直齿 Hertz 预筛选 | 名义中心距、不同齿数直齿副的解析几何、候选相位和每对全载Hertz包络；明确非ISO额定与非FEA。 可作独立解析预计算对照；M37节点C本次只读算术对拍成功。先核model applicability，再输出预期数量级、接触宽度和网格尺寸建议。 | 不支持变位、斜齿或非名义中心距。 每对全载包络不能把多对法向力相加作平衡。 不含根部弯曲刚度，不能承担完整预估器。 |
| A06 旧齿根/相位收敛与柔度凝聚 | 齿根原始积分点/固定位置结果与局部网格收敛；相位极值包络；FE逐片载荷求柔度；外部/用户给定柔度的LTCA。 复用“反力平衡与压力/齿根收敛独立”“峰值位置随网格核对”的审查思路；本轮使用M37现有root/stiffness数据，不另算旧齿形。 | 不是现成解析弯曲/单齿刚度预计算器。 gear_contact默认路径为用户刚度及耦合核，不能当独立FE或ISO真值。 旧plane/profile/轴坐标与M37不同，不直接替换。 |
| A07 模型语义、坐标、参数与DAG | CAD-neutral类型、坐标和单位/参数来源；依赖图和约束求解协议；不是通用物理求解器。 复用输入/派生/观测分离、坐标显式化、单位白名单和upstream change使下游失效的合同；用薄映射衔接新CAE意图。 | ConstraintGraph是协议/抽象边界，不把接口存在当求解能力。 UMI已有候选副本，不能同时静默sys.path回退两份。 |
| A08 MGS 建模工作包证据规则 | 原生CAD任务、独立expected、实测与重放、工件哈希、硬门不可由总分抵消。 复用证据状态与不可自证的合同方法；不将形状评分器拉入M37求解可信度门。 | M1历史55项测试与受限安装板能力不能算当前通用CAE验证。 |
| A09 gear-compiler FE探针和系统因子钩子 | 读旧whole-pair-report峰值；许用应力存在才给比值；多网格比较；外部动力/支承变形模型注册与缺数据blocked传播。 保留blocked与来源接口；M37结果由新ingester验，不能只信旧probe读到的passed字段。 | probe_fea_result转录报告passed并不独立重验raw。 峰值von Mises/许用强度比不等于ISO齿根疲劳安全系数。 |
| A10 UMI 集成工作区与 FEA 占位 | CAD、连杆、优化、齿轮的模块地图及接续规则；通用FEA adapter目录当前为空，注册为planned。 最可能是用户记得的“统一系统”之一；用registry作集成边界和资产地图，不宣称FEA adapter已完成。 | 旧历史PASS必须重新绑定目标运行时。 不要在已复制UMI gear模块和gear-compiler两处并行维护同一实现。 |
| A11 当前 M37 原几何、前处理与后处理真源 | 冻结M37齿形、CPE6网格、明确1mm单位厚度、P02 HPSTC载荷与齿根外推；L3割线刚度。 新ready adapter只读其INP/meta/raw结果；绝不为接旧系统而生成第二套几何或更改TR30/M37输入。 | 原L3相位索引缺陷另有诊断修复，baseline不可替换。 c′低载/支承/位移参考疑点保持待证，不能按接近程度调值。 |
| A12 当前 M37 语义预检与dispatch前门 | 接触面到理论点、法向、刚体自由度、加载矩、单位；CPE6二次Jacobian极值；限定profile拒未知关键字与属性；就绪后输入SHA不得变。 这是新fea-readiness adapter最直接的已验证入口；只读调用check，solver dispatch再次核同SHA；用现有反例矩阵避免另写重复门。 | ready_for_diagnostic_solve不等于模型认可。 不是通用Abaqus/CCX解析器；profile外需明确blocked。 相交筛查不是全部曲边无穿透证明。 |
| A13 当前 M37 独立接收器与定义审计 | raw artifact/退出码/物理输入身份、冻结参考、数值门；分列真实力矩平衡与理想比偏差，明确割线口径。 本地只读引用core独立gate；新层不复制数值公式或私有标准数据。公开时仅摘要projection和来源哈希，不拷核心。 | 实际力矩平衡不能替代原理想比门。 重复运行零退出码只赋予新记录资格，旧null不可补造。 |
| A14 HyperMesh 模型审计脚本 | 实体/组件/材料属性引用、接触连接、重复单元、拓扑清单；无template时只承诺TOPOLOGY_ONLY。 未来HM输入单独adapter调用；以语义门和导出deck对拍作接口，当前M37不引入HM。 | 仅查阅脚本，不代表当前能自动修复任意网格或完成GUI操作。 |
| A15 OptiStruct 运行与结果摘要 | 完成标志/ERROR/FATAL、未绑定节点与负compliance、时间线程/输入哈希比较；HyperView可提极值。 作为不同solver的raw evidence adapter，统一输出工程语义，不把不同求解器关键词混成一个通用PASS。 | check脚本只有完成/error/H3D硬门；平衡行是原文摘要，未执行向量/力矩闭合。 |
| A16 Abaqus case_spec/include 与 ODB报告 | base INP命名集/面盘点；基于JSON输出load include（当前只发CLOAD）；读各step末帧U/S简单最大值；许用/位移限值判OK/TBD/NO。 复用base deck不变、include可审查、缺limit为TBD的约定；新adapter必须先收紧支持类型/单位/坐标/接触输出。 | contacts只验证名称，write_case未生成case_contact.inp。 非CLOAD载荷会被静默省略；不能直接作为严格发算门。 ODB脚本无全反力/力矩/接触合力闭合；末帧最大值不足以认证结果。 |
| A17 名字易混的草图 solver_dispatch | 草图几何约束的分块/分区/求解报告重放调度，不是有限元solver launcher。 排除为本次FEA调度复用目标；仅参考版本化solve/replay概念。 | 不能因文件名solver_dispatch就当已有CAE dispatch gate。 |

## 关键证据与当前验证

### A01 CADBench R25.20 源绑定 CAE 工况与失效传播

入口：`plate_analysis_case.validate / bound_case`、`mounting_plate_jobs.submit / status / verified_completed_report`、`artifact_graph`。

验证：Source directly reviewed; saved acceptance.json reports two historical FE jobs, reaction errors 1.54e-7/8.20e-8 and stale/current transition; not rerun now.

- [plate_analysis_case.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/plate_analysis_case.py) — SHA256 `31f1f7f2006073333518fed56515f1b8fe9c8538499db1fa43de8e656b69575d`
- [mounting_plate_jobs.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/mounting_plate_jobs.py) — SHA256 `cceec8ba9d24a637ba3ee3db1641216b1f458dd32aa82027a807b1fbfa3e4294`
- [artifact_graph.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/artifact_graph.py) — SHA256 `947433e2d259b43879c42ce04e1654beb2e695aa7ba61e70c33fcfafc43a428b`

依赖：Python >=3.12；UnifiedDocument/project journal；Gmsh；CalculiX 2.23；build123d/OCCT; numpy。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A02 旧 FEA 调度与完成门

入口：`engineering_jobs.validate_bound_plane / validate_bound_whole / submit_job / worker`、`fea.run_job / solver_environment`。

验证：Static source reviewed; no old full suite or solver rerun.

- [engineering_jobs.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/engineering_jobs.py) — SHA256 `f701307ba44226d56b03ff2928a2cb95082d441be926c1d7bfce7d190402a6df`
- [fea.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/fea.py) — SHA256 `081fdac176b50f618a6a417c169d673ee69fd5754541f289334ab20b359ca1ec`
- [test_contact_workflow.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/tests/test_contact_workflow.py) — SHA256 `d3134a11c24f0e14a2677be1d913d3fe600ea3a2c6eccfb01b8d8c56fade8fb9`

依赖：Python；numpy；现有CADBench齿轮/原生源模块；Linux/WSL CalculiX runtime。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A03 旧结果字段完整性检查

入口：`final_frames / input_mesh / validate_fields`。

验证：Current read-only probes pass on P02 d18 and ph10; missing-node negative fixture rejected; no FE rerun.

- [fea_integrity.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/fea_integrity.py) — SHA256 `364987e0824fda32ee58d40223943c2ffa24bc3b479638945527f25538a4b2e8`

依赖：Python standard library。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A04 旧接触分支与压力峰定位

入口：`audit_plane_contact`、`fresh_projection_check`、`nominal_spur_state`。

验证：Source and three existing tests read; historical two-patch fixture present; no tests or fresh projection executed here.

- [contact_diagnostics.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/contact_diagnostics.py) — SHA256 `1095f63e55013063329f70993a625d7c82caaf35c3478cd5ab89443606a0bd75`
- [test_contact_diagnostics.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/tests/test_contact_diagnostics.py) — SHA256 `7cdf49cfef67f306ebe1f36f83ecb680ea2e575912cb003e89961793596ef947`
- [two-patches.inp](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/tests/fixtures/two-patches.inp) — SHA256 `1e21c595626c996c369a28d984828fcc8b904e02846e81a0dd6e6df72b154875`

依赖：numpy；scipy for KDTree projection；cadbench.gear_plane_fea reader；all nodal displacement for fresh projection。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A05 无变位直齿 Hertz 预筛选

入口：`GearCase / geometry / contact_points / hertz_contact / screen`。

验证：Current nominal M37 z20/36 pitch Hertz/half-width/contact-ratio match frozen expected to relative 1e-12; physical FE not validated.

- [spur_precheck.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/spur_precheck.py) — SHA256 `d6a6a0a5c0d2a1136d569c7b1e1d8cd6be13ff2df20647cff0939a60a8a8a25c`

依赖：Python standard library。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A06 旧齿根/相位收敛与柔度凝聚

入口：`root_convergence.root_stress / study`、`plane_accuracy.phase_envelope_gate / study`、`gear_plane_fea.root_fields / convergence_gate`、`fea.condense_gear_patches`、`gear_contact.ltca`。

验证：Static source reviewed; no old full suite or solver rerun.

- [root_convergence.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/root_convergence.py) — SHA256 `8f85ef4099737368fa230f96b762dfdbbb2dfd54750095e3dc6fe44192f0929d`
- [plane_accuracy.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/plane_accuracy.py) — SHA256 `a4a254c4648fca0a5302b1e7af5bb6d29883f467ad0f3653e76aa9f4ba060af0`
- [gear_plane_fea.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/gear_plane_fea.py) — SHA256 `059b9bd1ba149a42cc32c8f87752c11c2a125c0dca36d0fbc452c2e0217f4176`

依赖：numpy/scipy；CADBench old mesh/deck contracts；Gmsh/CalculiX for actual condensation。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A07 模型语义、坐标、参数与DAG

入口：`CoordinateFrame / Parameter / SemanticContract / PersistentReference`、`validate_coordinate_basis / validate_unit_whitelist`、`DependencyGraph / SimpleDependencyGraph`。

验证：Static source reviewed; no old full suite or solver rerun.

- [contracts.py](D:/my_Works/自研CAD-CAE系统/modeling-workbench/src/modeling_core/contracts.py) — SHA256 `f19118483cf06b439c6d0225c57c123acbf15b5258ef23520d12a42e74d10074`
- [graphs.py](D:/my_Works/自研CAD-CAE系统/modeling-workbench/src/modeling_core/graphs.py) — SHA256 `0f26105b4a2e0b964bc8a38a6246a8137393e0c727e458e4cd6bc87ee4b3563e`
- [MODELING_STANDARD.md](D:/my_Works/自研CAD-CAE系统/modeling-workbench/standards/MODELING_STANDARD.md) — SHA256 `26ffd20a3d9d66101b4ae41405d2bf457055055a37f75166990d99bd7c3b8b7b`

依赖：Python >=3.10；具体CAD/backend实现另接。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A08 MGS 建模工作包证据规则

入口：`run.ps1 validate / build / verify / qualify / verify-quality`、`workbench.gates / quality`。

验证：Saved M1 report read; source hashes can be compared; no current full suite.

- [AGENTS.md](D:/my_Works/自研CAD-CAE系统/modeling-workbench/AGENTS.md) — SHA256 `65ce65c2868e1599f99f56fc1e957899dda20387fee37a2a8571288d234192c1`
- [README.zh-CN.md](D:/my_Works/自研CAD-CAE系统/modeling-workbench/README.zh-CN.md) — SHA256 `dbb1deebb6be9f666a0977bc4a4bf2a947c140d2f215f3c9e3275175ccf62d86`
- [contracts.py](D:/my_Works/自研CAD-CAE系统/modeling-workbench/workbench/contracts.py) — SHA256 `bcb7f7109c4a49d57cb956e2e1cd41b47543c9041072007b22634da2be9c1137`

依赖：R25.20 WSL runtime；CADBench/OCP；独立BenchCAD评分环境仅CAD形状评分。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A09 gear-compiler FE探针和系统因子钩子

入口：`probe_fea_result / compute_safety_factor / assess_mesh_convergence`、`register_k_v_model / register_k_hbeta_model / compute_k_v / compute_k_hbeta`。

验证：Static source reviewed; no old full suite or solver rerun.

- [fea_probe.py](D:/my_Works/Gears/gear-compiler/stage0/tools/fea_probe.py) — SHA256 `a5567564efd2e7ef2a77baa40568a10cbfb19004abab3b4917b70887e7a14c2d`
- [system_hooks.py](D:/my_Works/Gears/gear-compiler/stage0/src/gears/system_hooks.py) — SHA256 `a8f783b77d61028e8639ff72b5a46f98c6ddef1e30965ee09e13f555666ceb12`
- [test_fea_probe.py](D:/my_Works/Gears/gear-compiler/stage0/tests/test_fea_probe.py) — SHA256 `2f2d961a356b6d0088ce94d65bc569d935681e88b1654ec6212ec8ca467a8e14`

依赖：Python standard library；旧spatial_pair_fea输出schema；真实外部数据及provenance。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A10 UMI 集成工作区与 FEA 占位

入口：`program/registry/modules.json`、`adapters/fea/`。

验证：Static source reviewed; no old full suite or solver rerun.

- [README.md](D:/my_Works/自研CAD-CAE系统/modeling-workbench/unified-mechanical-intelligence/README.md) — SHA256 `f6f0bfecaedbb3bcf449ce72c690a8ef8a4b641ffcc376724912bfd03f9f8351`
- [MODULES.md](D:/my_Works/自研CAD-CAE系统/modeling-workbench/unified-mechanical-intelligence/program/registry/MODULES.md) — SHA256 `bd2b1d062c4a9539ec723a33a97a45948e67e2a501469e48e8cc179acffd3d16`
- [modules.json](D:/my_Works/自研CAD-CAE系统/modeling-workbench/unified-mechanical-intelligence/program/registry/modules.json) — SHA256 `00c6fabe7d7df1f63de85b0f2f45cd003f1ffcc7828048c80d8fa40064805fa5`

依赖：目标运行时与领域模块。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A11 当前 M37 原几何、前处理与后处理真源

入口：`SpurGear / PairGeo / build_L2 / build_L3`、`Deck`、`post.hertz_line / post_L2 / post_L3`。

验证：Original M37 L0/L1 accepted numerical gates; highest contiguous L1; L2/L3 remain unaccepted; source/input identities previously checked.

- [gear_geom.py](D:/my_Works/Gears/parallel-v09-2026-10-29/m37/M37-FEA题目包/scripts/gear_geom.py) — SHA256 `82a6188b725230386f8b8a6a01b6579598fe3d1874809f9e282b2e5a41a28ef2`
- [mesh_gmsh.py](D:/my_Works/Gears/parallel-v09-2026-10-29/m37/M37-FEA题目包/scripts/mesh_gmsh.py) — SHA256 `e14b9aa31afbac992dff657b34e837f419164b7dda0c371311bcf329a0059609`
- [inp_writer.py](D:/my_Works/Gears/parallel-v09-2026-10-29/m37/M37-FEA题目包/scripts/inp_writer.py) — SHA256 `6a346e8f0150968762d2ed4cb1aa42b5ae8ea1c0c427852899bcaa256682c6be`

依赖：gmsh；Python；CalculiX when solving。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A12 当前 M37 语义预检与dispatch前门

入口：`read_deck / active_bounds / rigid_check / audit`、`jacobian_check / overlap_screen`、`check_before_solve.check`。

验证：Current-session semantic/pre-solve matrix evidence exists; this asset search does not rerun it.

- [semantic_preflight.py](D:/my_Works/Gears/parallel-v09-2026-10-29/preprocessing-work/m37-preflight/semantic_preflight.py) — SHA256 `0fe46411bc696e2e3607c9695320847286f35065bf5f7d553360fa6e72f9c064`
- [extended_preflight.py](D:/my_Works/Gears/parallel-v09-2026-10-29/preprocessing-work/extended_preflight.py) — SHA256 `c375e0997e22405b50515513ed121b4800dd923c8444dd7880d44eb35201f049`
- [check_before_solve.py](D:/my_Works/Gears/parallel-v09-2026-10-29/preprocessing-work/check_before_solve.py) — SHA256 `3aa9d026288512193cfcaccc2648f2e2e5f592a72bff51d225ff885ecdb4e25f`

依赖：numpy/scipy per imported modules；现有M37 meta/INP；固定known profile。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

### A13 当前 M37 独立接收器与定义审计

入口：`ingest_fea_results.good_job / artifact_errors / physical_input_errors / assess_l3`、`model_definition_audit.audit_l2 / audit_l3`。

验证：22 L3 records checked; 21 non-MORTAR numerical jobs strictly eligible after actual repeats; four numerical criteria still fail; highest L1.

- [ingest_fea_results.py](D:/my_Works/Gears/parallel-v09-2026-10-29/core-work/gearbase/gearmath/tools/ingest_fea_results.py) — SHA256 `3627cd7116d7fcc62a92cc084957a239c5ed16e8dd61cedf404c55bed4856161`
- [m37_contract_hashes.json](D:/my_Works/Gears/parallel-v09-2026-10-29/core-work/gearbase/gearmath/tools/m37_contract_hashes.json) — SHA256 `015aacfbc1354748fe141bddc038642d4ed29512c86bcc093a3644d5bf140647`
- [model_definition_audit.py](D:/my_Works/Gears/parallel-v09-2026-10-29/preprocessing-research/model_definition_audit.py) — SHA256 `5a9c5bf175248348af9c87b48e28a816e10b18c94ab8c1e9613ae2205dd7d34b`

依赖：Python standard library；冻结expected和现有raw文件。来源：User local frozen core; contains private standard numerical data; local-only reference, no redistribution.

### A14 HyperMesh 模型审计脚本

入口：`hmbatch.exe -tcl hm_model_audit.tcl; HM_MODEL/HM_REPORT/HM_TEMPLATE`。

验证：Static source reviewed; no old full suite or solver rerun.

- [SKILL.md](C:/Users/AAA/.codex/skills/hypermesh-optistruct-2026/SKILL.md) — SHA256 `691da55185477ae38c94902fbd15b5e6f3874711067b8dbf69d50f8ae01b9387`
- [hm_model_audit.tcl](C:/Users/AAA/.codex/skills/hypermesh-optistruct-2026/scripts/hm_model_audit.tcl) — SHA256 `b5d2cf03a203b0f618cf48b1312353f5bd00e22577d993231163d524b4bec90e`

依赖：Licensed Altair HyperMesh 2026；对应solver template；ASCII batch staging path。来源：User-installed local Codex skill scripts; no explicit reuse license found; Altair runtime is external licensed software.

### A15 OptiStruct 运行与结果摘要

入口：`check_optistruct_run.ps1 -OutPath -NlOutPath -H3dPath`、`compare_optistruct_runs.ps1`、`hv_result_extrema.tcl`。

验证：Static source reviewed; no old full suite or solver rerun.

- [check_optistruct_run.ps1](C:/Users/AAA/.codex/skills/hypermesh-optistruct-2026/scripts/check_optistruct_run.ps1) — SHA256 `06e1482a5a1351dbc20e3a29ca917a8e3a6d2ffbda2bf24ddf127a34d61816e8`
- [compare_optistruct_runs.ps1](C:/Users/AAA/.codex/skills/hypermesh-optistruct-2026/scripts/compare_optistruct_runs.ps1) — SHA256 `7a97850e3400f69e59a43b40c3ef0ad2426e6ac1ab8601fe31c1dc464fd3ba12`
- [hv_result_extrema.tcl](C:/Users/AAA/.codex/skills/hypermesh-optistruct-2026/scripts/hv_result_extrema.tcl) — SHA256 `b52f9e692123073ff0d8c22ae54a8cdfc6c05b9de8e88d8a1b369d531140e00f`

依赖：PowerShell；OptiStruct OUT/STAT/FEM；HyperView for H3D extrema。来源：User-installed local Codex skill scripts; proprietary runtime not included.

### A16 Abaqus case_spec/include 与 ODB报告

入口：`inventory / ensure_names / emit_step / write_case`、`postprocess_odb.main`、`make_csv_report.classify`。

验证：Current missing-set rejection probe passed; current DLOAD in-memory probe demonstrates silent omission. No Abaqus run.

- [SKILL.md](C:/Users/AAA/.codex/skills/hyperworks-abaqus-ai-fea/SKILL.md) — SHA256 `5988253a5026ebb8ecb84a4ab4506336dd13c8c533b2196d8a4f38f1ea805b81`
- [generate_abaqus_case.py](C:/Users/AAA/.codex/skills/hyperworks-abaqus-ai-fea/scripts/generate_abaqus_case.py) — SHA256 `08d681d5d0a16d036bab4139a7e2237943fa4806f80d71eecc284cadffa1d7df`
- [postprocess_odb.py](C:/Users/AAA/.codex/skills/hyperworks-abaqus-ai-fea/scripts/postprocess_odb.py) — SHA256 `4396c57d996d443d29ca79e2a4b76778d33fef8a29bb06b49946f2bf1814dcee`

依赖：Python；Abaqus Python odbAccess for ODB; licensed Abaqus executable separate。来源：User-installed local Codex skill scripts; no explicit source license found; Abaqus runtime proprietary and separate.

### A17 名字易混的草图 solver_dispatch

入口：`solve_report / verify_report`。

验证：Static source reviewed; no old full suite or solver rerun.

- [solver_dispatch.py](D:/my_Works/Gears/gear-compiler/stage0/freeze/CAD-R25.20-offline-freeze/app/src/cadbench/gcs_integration/solver_dispatch.py) — SHA256 `6ac047cc92b1e439476c06dcdbcf41c903a7728b6b60260a8612f9dd4aca545e`

依赖：CADBench GCS integration。来源：User local internal project source; no explicit redistribution license found in inspected project root/metadata.

## 不应重复实现的部分

当前 M37 的 `gear_geom.py / mesh_gmsh.py / inp_writer.py / cases.py / post.py` 保持唯一来源。新 readiness 包应读取现有 INP/meta，封装已有 `check_before_solve.check` 和冻结独立接收器；不要改用旧 CADBench 几何来替代，也不要把理论参考重新写一遍。

旧 `spur_precheck` 本次用 m=2、z=20/36、b=30、T=25 Nm、E=206000、ν=0.3 复算节点 C：Hertz 半宽、峰值和接触比与 M37 冻结 expected 在 1e−12 相对容差内一致。它适合名义几何数量级对照；不证明减薄齿形、当前接触状态或刚度定义。弯曲/刚度没有发现能直接替代 M37 的通用解析模块：旧 LTCA 仍要求用户刚度或外部柔度，FE凝聚必须真实求解。

旧 `fea_integrity.validate_fields` 本次只读通过 P02 d18、ph10 的已请求 U/RF/S 字段；独立缺节点反例被拒绝。它不覆盖 CF/CSTR，也不自动支持同一种输出的多个集合。接触拓扑算法有价值，但新投影检查要求全节点位移；当前 ph10 DAT 只输出 PMASTER 位移，不能假称已可执行该检查。

限定检索未发现现成通用 `cae-intent-spec` 或 FEA `solver-dispatch-gate`。已有的是安装板的 `cadbench-plate-analysis-case/0.1`、gear bound settings、Abaqus `case_spec` 和 M37 profile 预检。文件 `gcs_integration/solver_dispatch.py` 实际是草图约束分解调度，不能拿来充当 FEA 发算门。

Abaqus include 生成器需要收紧后才可接严格门：本次内存反例证实 DLOAD 被接受后未输出任何载荷；contacts 只查面名，未生成接触 include。不要因技能文档描述了完整流程就把脚本实际职责扩张。所有此类缺口只记录，未修改旧代码。

重复副本的逐文件哈希比较在 JSON。即使相同也只选一处来源引用；不同则先固定源身份，禁止通过多处 `sys.path` 回退合并能力。不要搬运整个 vendor/runtime，旧历史测试数也不能换算成新包验证通过。

## 来源与分发

内部旧项目与本机技能没有在本次检查的根目录/pyproject中发现明确再分发许可，按内部资产引用。CalculiX、Gmsh、OCCT、Altair 和 Abaqus 的来源/许可证独立于内部 Python 脚本；本次不打包任何运行时。冻结 gearbase core 含私有标准数值，仅本地引用，不公开复制。

## Where This Review May Be Wrong

1. 检索限于已指定源码与少量相关目录，可能遗漏未解压档案、WSL-only 或不同名称实现。若用户记得具体文件/界面名，应再按该线索查 manifest。
2. 历史验收记录不是本次重跑证据；真正复用旧CAD/solver执行链前，仍须恢复固定环境并对目标接口重验。
3. 当前纯算术与字段完整性探针不能证明通用模型正确性，也未完成全部依赖许可证复核。
