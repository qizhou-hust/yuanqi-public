"""Create audit artifacts only, without modifying the reviewed source tree."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = Path(r"D:\my_Works\Gears\gearbase-v020-work")
EVIDENCE = HERE / "evidence"
HEAD = "80117283778cf8732b5557fa15c2e41f626f92fc"


def ref(path, line, end=None):
    return {"path": str(ROOT / path), "line": line, "end_line": end or line}


def run(case, pointer):
    return {"path": str(EVIDENCE / f"{case}.stdout.json"), "json_pointer": pointer}


metadata = {
    "schema": "gearbase.freeze-architecture-assessment/1",
    "review_date": "2026-11-01",
    "source_root": str(ROOT), "git_head": HEAD, "package_version": "0.20",
    "review_mode": "delegated local evidence audit; not an independent model certification",
    "external_standard": "用户目标：速度/扭矩/空间/轴关系 → 自动类型/级数/传动比分配 → 方案选择 → 齿轮/轴承/轴/箱体/丝杆螺母 → 优化/FE/CAD/图纸；自然语言编辑；数学真源全链更新",
    "scope": "只读代码取证及4组当前会话安全入口 smoke；未执行 GUI、鼠标、FE 求解、原 M31 全套回归或外部客户端模型请求",
    "source_mutation": False,
    "evidence_policy": "verified 仅对明确限定能力成立；partial 可包含已运行的子能力及未完成集成；missing 指当前 gearmath 主链未找到目标能力，不等于归档/供应商库完全无相关代码",
    "commands": str(EVIDENCE / "commands.json"),
    "environment_inventory": str(EVIDENCE / "environment-inventory.json"),
}

findings = [
    {
        "id": "ARC-01", "priority": "P1", "classification": "verified_product_gap_with_explicit_disclosure",
        "title": "需求编译产生两条不相连的载荷与优化路径，feasible 不代表新需求通过",
        "standard": "优化模型必须接收同一份用户载荷、寿命、材料、安全阈值和空间限制；未应用项不可算作需求验收。",
        "observed": "40→400 N·m、1000→3000 rpm、10000→30000 h、材料说明与空间上限一起改变，template_call、Problem IR、完整 optimize_nlp 结果均相同；单独 rating_edit 的校核数值改变。模板由 c001_g1 固定工况生成，生命周期/材料未应用，空间限制在 post_checks。",
        "witness": {"optimized_b_mm": 21.30069604155817, "optimized_center_distance_mm": 57.120694849135454,
                    "second_requirement_max_b_mm": 5.0, "second_requirement_max_a_mm": 20.0,
                    "template_feasible": True, "rating_SH1_before": 0.9414217847337382, "rating_SH1_after": 0.29770370786593453,
                    "problem_ir_sha256": "63e34ba3bf2f582ed080d294c4047d2cdf62b39a663b95875f70f84359053e52"},
        "impact": "直接把 compiler 的 template_call 接给优化器，候选即使 feasible 仍会违反实际载荷/空间需求。返回已用 unapplied/post_checks/applicability 明示界限，不能称为静默丢参或数学优化器错误。",
        "code_refs": [ref("gearmath/tools/intent.py", 186, 229), ref("gearmath/tools/nlp_templates.py", 14, 20), ref("gearmath/gear/problem.py", 11, 65)],
        "runtime_refs": [run("requirements", "/results")],
        "recommendation": "下一产品切片优先级 P0：建立 full_requirement→source-owned sizing 的单一路径，实际载荷/限值进入问题声明；寿命与材料若无可用数值证据即阻断；用本反例验证 T/n/空间变化能改变模型或可行性。保留当前模板为明确命名的 C001 演示。",
        "current_disposition": "冻结基线不修改；记录为目标交付阻断",
    },
    {
        "id": "ARC-02", "priority": "P1", "classification": "verified_interface_scope_and_static_gap",
        "title": "多候选来自预选固定拓扑的参数搜索，尚非自动传动拓扑规划",
        "standard": "由轴关系/输入输出约束自动选择类型、级数与级比分配，并比较多种拓扑。",
        "observed": "通用编译只收单级 spur；stages=2/helical 被 blocked_unsupported_scope，axis_relation 被 unknown_argument 拒绝。旗舰 schema 要求调用者先选择 H2/W2W/P2，H2 输入先指定两个中心距，P2/W2W 固定两级类型。joint optimizer 只遍历调用者编写的 gear×shaft×bearing 有限轴。",
        "impact": "已有候选列表可辅助固定问题选型；不能从任意空间与轴关系自动产生平行轴、交错轴、行星、蜗杆和混合级的方案架构。",
        "code_refs": [ref("gearmath/tools/intent.py", 21, 49), ref("gearmath/tools/intent.py", 153, 161), ref("gearmath/tools/flagship_workflow.py", 3, 26), ref("gearmath/gear/flagship_h2.py", 1, 28), ref("gearmath/product/system_optimize.py", 129, 194)],
        "runtime_refs": [run("requirements", "/results/unsupported_multistage_helical"), run("requirements", "/results/unknown_axis_relation"), run("flagships", "/results")],
        "recommendation": "在已闭合的单副产品切片后补独立 topology IR 与类型/级数规划器；把固定拓扑的尺寸搜索和跨拓扑规划分开验收。",
        "current_disposition": "目标能力缺失；不是现有 Stage0 合同违约",
    },
    {
        "id": "ARC-03", "priority": "P1", "classification": "verified_runtime_completion_gap",
        "title": "原始旗舰与真实示例的系统级校核仍因缺数据或不支持分支阻断",
        "standard": "选中方案后有可复现的齿轮、轴、轴承与连接件系统校核。",
        "observed": "当前运行 H2/W2W/P2 分别返回40/15/5个 Stage0 候选，三者 system_status 都 blocked，模板缺项计数93/62/61；W2W/P2明确缺全族强度与啮合力/均载模型。C001仅 gear_rating pass，manufacturing/scuffing/micropitting/shaft/bearing/key/thermal blocked；K01制造参数pass，其余请求检查blocked。",
        "impact": "Stage0 可生成几何/运动学初选，不能以有候选或工作流 completed_stage0 作为系统通过；缺项列表是工程数据补齐边界。",
        "code_refs": [ref("gearmath/product/flagship_system.py", 1, 17), ref("gearmath/product/flagship_system.py", 581, 607), ref("gearmath/product/design_check.py", 875, 962), ref("gearmath/tools/design_check_tool.py", 9, 28)],
        "runtime_refs": [run("flagships", "/results"), run("system", "/results/summary/design_check_statuses")],
        "recommendation": "先把一个有真实支承/轴承/材料/限值来源的圆柱系统示例补齐为完整可试用切片；W2W/P2保持强度与载荷模型阻断，不用测试演示数据替代真实输入。",
        "current_disposition": "目标交付阻断；当前 blocked 行为符合不补默认值约定",
    },
    {
        "id": "ARC-04", "priority": "P1", "classification": "verified_ssot_subset_and_static_integration_gap",
        "title": "数学真源与DAG内重算已成立，但未贯通FE/CAD/供应商全链",
        "standard": "作者输入只有一个权威文档，编辑后所有下游数值、几何、FE与证据身份一致更新。",
        "observed": "C001 math-source 副本中 b=30→33 后，source/model hash及29个数值变更，原文档与 evidence 分区保持不变；投影派生行不可写。FE ingest 明确 graph_admission.admitted=false；CAD 位于独立 archived math-source/unified_document/STEP 路径，新 gearmath math-source 仅生成数值回执/参数表。轴梁至KHβ仍只是机制接口桩/有限贡献，非完整自动反馈。",
        "impact": "不能把唯一输出公式、哈希和数值图重算解释成 CAD 特征、FE 网格/求解结果、厂商证据及制造输出都自动更新且重新合格。",
        "code_refs": [ref("gearmath/kernel/graph.py", 132, 168), ref("gearmath/gear/math_source.py", 88, 122), ref("gearmath/tools/fea_ingest.py", 1, 16), ref("gearmath/tools/architecture_guard.py", 1, 6), ref("gearmath/system/shaft_beam.py", 16, 18), ref("gearmath/gear/beam_face.py", 7, 36), ref("archive/m31/src/cadbench/unified_document.py", 194, 205)],
        "runtime_refs": [run("system", "/results/summary/source_changed_values"), run("system", "/results/summary/external_evidence_held_unchanged")],
        "recommendation": "定义同一 source revision 驱动下游投影的身份、失效与重建协议；分别验收数学计算、CAD读回、FE入图资格和供应商证据，不以哈希存在替代各域资格。",
        "current_disposition": "数值SSOT可用；全链集成未完成",
    },
    {
        "id": "ARC-05", "priority": "P1", "classification": "verified_static_cad_release_gap_not_current_runtime_test",
        "title": "原生齿轮STEP资产可恢复，但完整装配与制造图纸尚未交付",
        "standard": "选定传动方案能输出含轴、轴承、箱体及必要支架/载体的装配和可制造图纸。",
        "observed": "archived realize_revision 明示 native_assembly=partial，缺 shafts/bearings/housing/carrier，assembly_drawing=blocked、零件图仅检查SVG；四族headless workflow只声明 source→job→STEP。v0.20 M35 packet仅K02直径包络/宽度审查准备，manufacturing_release=false；受审 tooth_authority 拒非零变位，斜齿只给工作渐开线面而非完整滚切齿根。",
        "impact": "能读取源码/旧几何证据不等于当前新架构已有一键整箱体CAD或制造放行；需要按具体族与变位范围恢复并读回验证。",
        "code_refs": [ref("archive/m31/src/gears/realize.py", 147, 187), ref("archive/m31/src/gears/integration/family_workflow.py", 1, 27), ref("archive/m31/src/cadbench/tooth_authority.py", 1, 25), ref("archive/m31/src/cadbench/gear_native_wp.py", 1, 6), ref("gearmath/tools/m35_packet.py", 1, 31), ref("gearmath/tools/m35_packet.py", 97, 101)],
        "runtime_refs": [],
        "recommendation": "按单副可制造几何→轴/轴承/箱体装配→图纸逐层补齐合同；不把 diameter envelope 图纸称为真实齿面/齿根或制造图。",
        "current_disposition": "本审计未启动CAD运行或GUI；以代码声明与调用链定位缺口",
    },
    {
        "id": "ARC-06", "priority": "P2", "classification": "verified_protocol_only_external_client_unverified",
        "title": "MCP服务器当前可用，真实模型自然语言闭环仍未在本轮验证",
        "standard": "用户可用自然语言创建/修改设计并完成工具调用与可复核结果。",
        "observed": "当前 stdio initialize/list/resources/prompts/tools-call 成功，17个默认列出工具；gear_rate、preview、explain与错误阻断正常。requirement_compile接受结构化object，不是自由文本解析器；自然语言解释依赖外部模型。保存文档曾记录Claude Code连接后模型HTTP403且无模型发起tools/call；本轮未连接任何外部客户端。",
        "impact": "协议往返证明服务器，不证明真实用户端配置、账户模型调用或自然语言任务完成。",
        "code_refs": [ref("gearmath/tools/ai_tools.py", 604, 660), ref("gearmath/tools/intent.py", 39, 49), ref("docs/M38-closure.md", 19, 43), ref("docs/M34-closure.md", 33, 38)],
        "runtime_refs": [run("mcp", "/results/summary")],
        "recommendation": "单独记录真实客户端的发现、实际模型tools/call、数值来源与预览/写回结果；本轮不据历史403断言当前账户仍失败。",
        "current_disposition": "服务器verified；外部模型自然语言端到端not_verified",
    },
    {
        "id": "ARC-07", "priority": "P2", "classification": "verified_usability_and_identity_mismatch",
        "title": "入口文档与运行身份过时，易误判当前能力和运行方法",
        "standard": "冻结包的版本与试用入口应可准确识别当前实现。",
        "observed": "VERSION=0.20且HEAD已核；README仍自称v0.11/665 tests并把legacy概括为不可运行；实际存在 archive/m31 分段恢复及m31_regression适配入口。MCP initialize实际自报gearmath-prototype version=0.5；接入指南仍列13个工具和未实连状态，与当前17工具及另文档记录不一致。",
        "impact": "用户难以找到当前入口或判断看到的是旧演示/新主链/原M31恢复路线；错误版本号也削弱日志定位。legacy目录本身并未因此被证明可直接运行，新入口实际针对archive staged tree。",
        "code_refs": [ref("VERSION", 1), ref("README.md", 1, 10), ref("README.md", 44, 48), ref("gearmath/tools/m31_runtime.py", 243, 283), ref("gearmath/tools/m31_regression.py", 72, 81), ref("gearmath/tools/ai_tools.py", 628, 635), ref("docs/接入指南-ClaudeDesktop与Code.md", 88, 93)],
        "runtime_refs": [run("mcp", "/results/summary/server_info")],
        "recommendation": "下一包生成一个随VERSION与工具注册表一致的当前入口页，按新主链、固定演示、归档恢复三类说明真实可执行命令与能力限制；本审计不改根README。",
        "current_disposition": "冻结可用性finding；报告附当前试用命令",
    },
    {
        "id": "ARC-08", "priority": "P2", "classification": "verified_authority_boundary_not_exploit_claim",
        "title": "CAS/token和caller provenance是状态/来源声明，不是身份审批",
        "standard": "自然语言/代理写入边界应明确区分一致性、用户身份与工程审批。",
        "observed": "gear_commit核对基线sha、版本、token与edit后即可提交；用户身份/人工批准未作为认证对象。provenance允许调用者填写user/evidence/assumption/agent_proposed，不能由标签本身证明谁输入或证据真实。optimize_and_commit的列出开关只控制discovery，call分发不受该开关影响，confirm=true来自调用参数。",
        "impact": "这些机制能防陈旧写入、重复权威源和不一致参数，不能自动证明已获真人批准或认证的证据来源；不能据此声称远程越权漏洞，部署权限由宿主MCP客户端与外层策略承担。",
        "code_refs": [ref("gearmath/tools/ai_tools.py", 54, 54), ref("gearmath/tools/ai_tools.py", 405, 455), ref("gearmath/tools/ai_tools.py", 536, 547), ref("gearmath/tools/optimize_commit.py", 1, 11), ref("gearmath/tools/optimize_commit.py", 29, 37)],
        "runtime_refs": [run("mcp", "/results/summary/preview_status")],
        "recommendation": "产品文案把CAS写成并发一致性；若需身份/工程审批，以外部可核验的批准记录绑定source revision，不能把provenance字符串或confirm参数当身份凭据。无需为本finding扩展攻击实验。",
        "current_disposition": "仅界限澄清；未执行任何commit或攻击实验",
    },
]


def cap(cid, name, status, evidence, code, runtime, limit):
    return {"id": cid, "capability": name, "status": status, "evidence_status": evidence,
            "code_refs": code, "runtime_refs": runtime, "limits": limit}


caps = [
    cap("CAP-01", "通用DAG、唯一公式输出、单位/取值域/标准版次/方法选择校验", "verified", "code_and_current_smoke",
        [ref("gearmath/kernel/graph.py", 132, 168), ref("gearmath/kernel/graph.py", 200, 228), ref("gearmath/kernel/graph.py", 246, 358), ref("gearmath/kernel/units.py", 1, 11)],
        [run("mcp", "/results/summary")], "已验证正常求值、派生输入拒绝及错单位拒绝；本轮没有穷举全部公式/循环/版次负例。units的唯一性是该kernel契约，归档/CAD及系统标量接口未统一成一个跨域量对象。"),
    cap("CAP-02", "数学源文档、不可写派生投影与编辑后数值重算", "verified", "code_and_current_smoke",
        [ref("gearmath/gear/math_source.py", 63, 122), ref("gearmath/tools/design_store.py", 1, 11), ref("gearmath/tools/design_store.py", 79, 101)],
        [run("system", "/results/summary/source_changed_values")], "当前math-source副本编辑b可重算29个值，旧文档未改；未证明全部下游工件都受同一真源驱动。"),
    cap("CAP-03", "解释链与自动微分/灵敏度", "partial", "explain_smoked_derivative_code_inspected",
        [ref("gearmath/kernel/graph.py", 330, 357), ref("gearmath/kernel/graph.py", 365, 385), ref("gearmath/tools/ai_tools.py", 579, 601)],
        [run("mcp", "/results/replies/10")], "S_H1 explain当前实跑；本轮未单独执行灵敏度或AD/FD全回归，固定点导数策略亦未做全域复核。"),
    cap("CAP-04", "预览、设计修订、CAS与可选持久化", "partial", "preview_smoked_commit_static_only",
        [ref("gearmath/tools/ai_tools.py", 374, 455), ref("gearmath/tools/design_store.py", 129, 206)],
        [run("mcp", "/results/summary")], "preview不保存已验证；commit与文件状态恢复本轮按只读约束未执行。默认纯内存；token非身份审批。"),
    cap("CAP-05", "结构化需求编译与缺项追问", "partial", "code_and_current_smoke",
        [ref("gearmath/tools/intent.py", 86, 229)], [run("requirements", "/results/compiler_responses")],
        "仅单级直齿模板；实际载荷只进入rating_edit，寿命/材料unapplied、空间post_checks；不能独立完成用户全需求。"),
    cap("CAP-06", "自由自然语言创建/修改及真实AI客户端闭环", "partial", "server_protocol_verified_client_not_verified",
        [ref("gearmath/tools/intent.py", 39, 49), ref("gearmath/tools/ai_tools.py", 604, 660), ref("docs/M38-closure.md", 19, 43)],
        [run("mcp", "/results/summary")], "本地MCP可用；自由文本由外部模型解释，真实模型发起tools/call本轮未验证；历史403只作历史记录。"),
    cap("CAP-07", "由转速/扭矩/空间/轴关系自动规划类型和级数", "missing", "interface_counterexample_and_core_search",
        [ref("gearmath/tools/intent.py", 21, 49), ref("gearmath/tools/intent.py", 153, 161), ref("gearmath/tools/flagship_workflow.py", 3, 26)],
        [run("requirements", "/results/unsupported_multistage_helical"), run("requirements", "/results/unknown_axis_relation")],
        "未找到gearmath跨类型/级数/轴关系规划器；已有H2/W2W/P2先指定拓扑，不能等同自动规划。"),
    cap("CAP-08", "单级尺寸优化模板", "verified", "current_bounded_optimization_smoke",
        [ref("gearmath/tools/nlp_templates.py", 14, 20), ref("gearmath/gear/problem.py", 11, 65)],
        [run("requirements", "/results/optimization_responses")], "verified仅指固定C001载荷、单个声明离散组合的局部连续求解；非用户新需求验收或全局最优。"),
    cap("CAP-09", "作者源文档驱动的声明优化与重算写回", "partial", "code_inspected_current_full_solver_path_not_smoked",
        [ref("gearmath/gear/source_optimize.py", 103, 112), ref("gearmath/gear/source_optimize.py", 259, 322), ref("gearmath/gear/source_optimize.py", 329, 395), ref("gearmath/tools/declared_tool.py", 12, 21)],
        [], "存在比stage_sizing更完整的source-owned路径与独立重建验证；白名单/已声明文档/hold_evidence，不能直接接任意新需求；本轮未重跑其完整优化。"),
    cap("CAP-10", "固定圆柱系统 gear×shaft×bearing 联合搜索", "verified", "current_exact_fixture_and_fresh_enumeration",
        [ref("gearmath/product/system_optimize.py", 129, 267), ref("gearmath/tools/system_closure.py", 12, 44)],
        [run("system", "/results/system_closure")], "27个作者测试组合、8可行、17次design_check，与fresh枚举一致；优化齿坯+轴体积，排除轴承包络/价格/箱体/反馈，非真实C001交付。"),
    cap("CAP-11", "外啮合直齿/斜齿副几何与ISO 6336强度", "partial", "spur_smoked_helical_static_paths",
        [ref("gearmath/gear/formulas.py", 22, 30), ref("gearmath/gear/rating.py", 30, 52), ref("gearmath/gear/source_optimize.py", 103, 112), ref("gearmath/gear/kisssoft_multi.py", 1, 18)],
        [run("mcp", "/results/summary/gear_rate_baseline"), run("system", "/results/summary/design_check_statuses")],
        "C001副当前pass；K系列/显式系数装配包含helical路径。本轮没有重跑每族所有对标或证明任意几何可用；公开gear_rate以C001_G1/none圆柱模型为入口。"),
    cap("CAP-12", "内齿与双斜齿特殊公式分支", "partial", "code_inspected_not_current_smoked",
        [ref("gearmath/gear/internal_gear.py", 1, 18), ref("gearmath/gear/double_helical.py", 1, 29), ref("gearmath/gear/tr30_full58.py", 234, 281)],
        [], "TR30特定构造路径确有分支，不能因P2全系统未实现就说内齿强度公式完全没有；尚非通用行星均载/制造模型。"),
    cap("CAP-13", "H2两级斜齿Stage0候选与复查", "verified", "current_original_fixture_smoke",
        [ref("gearmath/gear/flagship_h2.py", 1, 28), ref("gearmath/tools/flagship_workflow.py", 35, 49)],
        [run("flagships", "/results/H2/summary")], "40个有界采样几何候选，首选复算；无全强度/轴/轴承/热评级，system仍blocked且93缺项。"),
    cap("CAP-14", "W2W两级蜗杆Stage0候选/效率/热初筛", "partial", "current_original_fixture_smoke",
        [ref("gearmath/gear/flagship_w2w.py", 39, 82), ref("gearmath/product/flagship_system.py", 14, 17)],
        [run("flagships", "/results/W2W/summary")], "15候选，首选candidate_requires_changes；恒摩擦效率/给定对流模型；强度、磨损、胶合、啮合力与完整系统评级未收录。"),
    cap("CAP-15", "P2两级行星整数几何/Pareto", "partial", "current_original_fixture_smoke",
        [ref("gearmath/gear/flagship_p2.py", 87, 139), ref("gearmath/product/flagship_system.py", 14, 17)],
        [run("flagships", "/results/P2/summary")], "5候选，结构约束与运动学可算；未实现行星载荷分配/浮动构件载荷/全系统强度，system blocked。"),
    cap("CAP-16", "锥齿/齿条/交错轴斜齿/准双曲面通用主链", "missing", "core_interface_and_module_inventory_only",
        [ref("gearmath/tools/flagship_workflow.py", 3, 12), ref("gearmath/product/design_check.py", 141, 164), ref("archive/m31/src/gears/benchmark/spine.py", 16, 16)],
        [], "missing指gearmath用户需求→优化→rating/CAD全链。archive/vendor含rack/bevel/crossed-helical局部代码，不能以文件存在当已集成，也不能声称全仓库无代码。"),
    cap("CAP-17", "齿轮载荷→轴截面DIN743/轴承ISO281/键DIN6892/过盈DIN7190", "partial", "current_fixture_and_real_case_blocking_smoke",
        [ref("gearmath/product/design_check.py", 1, 14), ref("gearmath/system/drivetrain_check.py", 242, 410)],
        [run("system", "/results/system_closure"), run("system", "/results/summary/design_check_statuses")],
        "有限显式测试数据贯通；真实C001/K01和三旗舰缺真实输入阻断，不是自动完成轴与轴承设计/选型。"),
    cap("CAP-18", "多支承轴梁、挠度、转角与扭转", "partial", "code_inspected_not_current_smoked",
        [ref("gearmath/system/shaft_beam.py", 1, 18), ref("gearmath/product/design_check.py", 476, 562)],
        [], "Euler-Bernoulli/Timoshenko直梁、刚性点支承、点/均布载荷；无轴承/箱体弹性、临界转速；本轮未执行梁专门回归。"),
    cap("CAP-19", "轴/轴承/箱体变形自动反馈KHβ再优化", "partial", "bounded_contribution_static_not_full_feedback",
        [ref("gearmath/gear/beam_face.py", 7, 36), ref("gearmath/system/drivetrain_check.py", 417, 420), ref("gearmath/tools/system_closure.py", 33, 36)],
        [], "已有轴弯曲+外部扭转贡献函数和KHβ标准公式，但beam_face明确非完整f_sh/KHβ；联合优化排除该自动反馈。"),
    cap("CAP-20", "轴承目录自动筛选与供应商数据闭环", "partial", "explicit_input_implementation_only",
        [ref("gearmath/product/flagship_system.py", 41, 45), ref("gearmath/system/iso281.py", 199, 244), ref("gearmath/product/system_optimize.py", 132, 136)],
        [run("system", "/results/system_closure/optimized/stats")], "支持显式C/C0/XY等数据及用户列出的有限候选；本轮未找到从任意需求自动筛厂商完整目录并认证属性的主链。"),
    cap("CAP-21", "热平衡与系统损耗", "partial", "code_inspected_and_stage0_heat_smoked",
        [ref("gearmath/product/design_check.py", 775, 845), ref("gearmath/system/thermal_balance.py", 1, 27)],
        [run("flagships", "/results/W2W/summary")], "有显式loss model/温度括区求根；不推测缺失箱体散热/密封搅油项，未自动生成完整热模型。"),
    cap("CAP-22", "FE准备、严格回读与结果证据归档", "partial", "code_inspected_no_new_fe_run",
        [ref("gearmath/tools/fea_prepare.py", 33, 87), ref("gearmath/tools/fea_ingest.py", 1, 16), ref("gearmath/tools/fea_ingest.py", 71, 84)],
        [], "有限M37读回/身份/覆盖等门存在，graph_admission=false；本轮不重跑FE、不升格任何门状态。"),
    cap("CAP-23", "归档CAD四族headless生成、STEP与读回", "partial", "static_runtime_adapter_and_code_only",
        [ref("gearmath/tools/m31_runtime.py", 243, 283), ref("archive/m31/src/gears/integration/family_workflow.py", 1, 27), ref("archive/m31/src/cadbench/gear_native.py", 144, 184)],
        [], "可恢复原M31有限四族路线；有依赖/几何适用域/齿数预算。当前审计未生成或读回新CAD，不把旧回归计数当生产主链证据。"),
    cap("CAP-24", "完整齿轮箱装配、箱体设计与制造图纸", "missing", "explicit_code_contract_gap",
        [ref("archive/m31/src/gears/realize.py", 170, 187), ref("gearmath/tools/m35_packet.py", 23, 31), ref("gearmath/tools/m35_packet.py", 97, 101)],
        [], "有齿轮部件几何、BOM子集、包络图与制造参数投影，但整套轴承轴箱体装配、完整零件/装配制造图未交付。"),
    cap("CAP-25", "丝杆/螺母及齿轮到直线执行器全链", "missing", "core_module_and_interface_search_only",
        [ref("gearmath/product/design_check.py", 45, 52), ref("gearmath/tools/intent.py", 21, 49), ref("gearmath/tools/flagship_workflow.py", 3, 12)],
        [], "gearmath主链未发现power-screw/nut/效率自锁/屈曲等执行器模型入口；本结论非全硬盘或其它项目搜索。"),
    cap("CAP-26", "一份数学真源驱动FE/CAD/供应商/图纸全链更新", "missing", "source_ownership_verified_cross_domain_bridge_not_found",
        [ref("gearmath/gear/math_source.py", 88, 122), ref("gearmath/tools/fea_ingest.py", 1, 16), ref("gearmath/tools/architecture_guard.py", 1, 6), ref("archive/m31/src/cadbench/math_source.py", 137, 163)],
        [run("system", "/results/summary")], "DAG内重算与独立归档CAD文档可分别存在；未发现统一revision消费者/失效/再资格链。跨域模型适用性也不是哈希能自动保证。"),
]

for obj in (findings, caps):
    for row in obj:
        for r in row["code_refs"]:
            assert Path(r["path"]).is_file(), r
            lines = Path(r["path"]).read_text(encoding="utf-8-sig").splitlines()
            assert 1 <= r["line"] <= r["end_line"] <= len(lines), r

(HERE / "findings.json").write_text(json.dumps({**metadata, "findings": findings}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(HERE / "capability-matrix.json").write_text(json.dumps({**metadata, "status_vocabulary": ["verified", "partial", "missing"], "capabilities": caps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Source snippets preserve line-numbered evidence and producer hashes separately
# from narrative. They do not replace the frozen files or their package manifest.
snippets = []
seen = set()
for row in findings + caps:
    for r in row["code_refs"]:
        key = (r["path"], r["line"], r["end_line"])
        if key in seen:
            continue
        seen.add(key)
        p = Path(r["path"])
        lines = p.read_text(encoding="utf-8-sig").splitlines()
        snippets.append({**r, "file_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                         "excerpt": "\n".join(f"{i}: {lines[i-1]}" for i in range(r["line"], r["end_line"] + 1))})
(EVIDENCE / "source-snippets.json").write_text(json.dumps({"git_head": HEAD, "snippets": snippets}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"findings": len(findings), "capabilities": len(caps), "source_snippets": len(snippets), "outputs": ["findings.json", "capability-matrix.json", "evidence/source-snippets.json"]}))
