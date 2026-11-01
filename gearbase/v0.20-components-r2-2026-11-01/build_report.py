from pathlib import Path
import hashlib,html,json,re,shutil,subprocess
HERE=Path(__file__).resolve().parent;CORE=HERE.parent/'gearbase-v020-work';R1=HERE.parent/'v020-freeze-assessment-2026-11-01'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
esc=lambda x:html.escape(str(x),quote=True)
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=CORE).decode().strip();assert head=='80117283778cf8732b5557fa15c2e41f626f92fc'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=CORE)
frozen=read(HERE.parent/'v020-closure-run/code-freeze.json');assert all(sha(CORE/n)==h for n,h in frozen.items())
counts=read(HERE/'library/enum-counts.json');lib=read(HERE/'library/topology-library.json');verification=read(HERE/'library/verification-log.json')
math=read(HERE/'math/math-examples.json');math_result=read(HERE/'math/math-example-results.json');sources=read(HERE/'research/sources.json')['sources'];precedents=read(HERE/'research/industrial-precedents.json')['entries']
assert counts['domains']['four_atom']['plain_ordered_sequences']==340 and counts['domains']['six_atom']['plain_ordered_sequences']==1554
assert math_result['failed']==0 and math_result['engineering_acceptance'] is False
for name,h in math_result['file_sha256'].items():assert sha(HERE/'math'/name)==h,name
assert verification['test_exit_code']==0 and counts['negative_probes_passed']==10
previous=HERE/'previous';shutil.copytree(R1/'public-stage',previous,dirs_exist_ok=True)
# Preserve the already-published, redacted prior report and its relative evidence layout.
assert sha(previous/'index.html')=='6bbc3cc7001ff71656a81d44cb8521ea9743899bf9a2b0aa1e6c50c16d2b9ba7'
for p in (R1/'public-stage').rglob('*'):
 if p.is_file():assert sha(p)==sha(previous/p.relative_to(R1/'public-stage'))
old_style=re.search(r'<style>(.*?)</style>',(R1/'public-stage/index.html').read_text(encoding='utf8'),re.S)[1]
stage4=counts['domains']['four_atom'];stage6=counts['domains']['six_atom']
rows=[]
for name,d in [('四原子类型 H/P/W/B',stage4),('六原子类型 +I/X',stage6)]:
 rows.append('<tr><td>'+esc(name)+'</td>'+''.join('<td>'+str(d['plain_by_physical_stages'][str(n)])+'</td>' for n in range(1,5))+f'<td><b>{d["plain_ordered_sequences"]}</b></td><td>保留顺序、重复；仅抽象语法域</td></tr>')
for name,d in [('四类型+P2宏（未去重写法）',stage4),('六类型+P2宏（未去重写法）',stage6)]:
 rows.append('<tr><td>'+esc(name)+'</td>'+''.join('<td>'+str(d['weighted_macro_expressions_by_physical_stages'][str(n)])+'</td>' for n in range(1,5))+f'<td>{d["weighted_macro_expressions_admitted"]}</td><td>宏按2级计；展开去重后仍为{d["expanded_unique_semantic_topologies"]}</td></tr>')
units=[
 {'id':'H','short':'圆柱副','title':'H · 平行轴外啮合圆柱齿轮副','symbol':'单个齿轮副 / atomic stage',
 'input':'旋转输入 φ、ω、τ','output':'旋转输出 φ、ω、τ','mount':'安装/反力为装配投影义务；不能由两个动力端口推定三维支承已闭合。',
 'core_math':'i_abs=z₂/z₁；方向、相位与损耗由具名方法给出',
 'parameters':'齿数、法向模数、压力角、螺旋角、变位、齿宽、刀具、材料/工况、方法与来源。',
 'outputs':'工作几何、传动关系、损耗/载荷、已支持的SH/SF等；各输出绑定公式与域。',
 'budget':'展开齿轮级1；直齿/斜齿在更具体的配方与参数层继续区分。',
 'current':'现有圆柱数学可复用，类型插件拟新增','limits':'复用现有L2/math-source，不以C001默认工况替代新需求。三维载荷/轴承/箱体需显式装配与数据。'},
 {'id':'W','short':'蜗杆副','title':'W · 蜗杆输入、蜗轮输出的单元','symbol':'方向与工况敏感的原子单元',
 'input':'旋转输入 / worm','output':'旋转输出 / wheel','mount':'蜗杆/蜗轮支承、反力与热连接另有义务；当前draft不是完整wrench-to-housing接口。',
 'core_math':'ω₂=σ·ω₁/i；正驱损耗、反驱与静摩擦分开',
 'parameters':'齿数/头数、模数/导程角、轴关系、材料副、摩擦/润滑/温度、载荷、正反驱方法。',
 'outputs':'运动关系、可评价工况的功率/热与载荷；详细承载/磨损/胶合须有独立模型。',
 'budget':'展开齿轮级1；W→W保持允许，不能用末级蜗杆偏好删去所有双蜗杆。',
 'current':'已有W2W简化初筛，完整工程模型未齐','limits':'η不是固定默认值；自锁域不可用负效率或正效率倒数反算。详细三维反力与工程资格仍开放。'},
 {'id':'P','short':'单行星排','title':'P · 固定环、太阳输入、行星架输出','symbol':'原始三端口 + 显式固定边界',
 'input':'太阳轮 S','output':'行星架 C','mount':'齿圈R固定：ωR=0，但τR通常非零；必须保留反力投影和安装绑定义务。',
 'core_math':'zS(ωS−ωC)+zR(ωR−ωC)=0',
 'parameters':'齿数、角色/固定构件、几何与共工作中心约束、行星数、均载/支承、材料与方法。',
 'outputs':'运动与力矩关系、环上反力、已有几何；销轴/架/环柔度和均载评级独立补齐。',
 'budget':'一个行星排计1齿轮级；内部多个啮合和行星数另记，不能把啮合种数当级数。',
 'current':'Stage0与理想数学样例；详细系统仍受限','limits':'其他固定/输入/输出配置使用不同semantic ID；未固定环时自由度不同，不可只填一个ratio。'},
 {'id':'P2','short':'双级行星宏','title':'P2 · 两个固定角色P顺序插接','symbol':'P₁ → P₂，局部展开',
 'input':'P₁太阳输入','output':'P₂行星架输出','mount':'两个固定圈的反力保留为边界/投影义务；schema尚不等于完整typed mount/wrench力学连接。',
 'core_math':'由子P方程组合；总比i=i₁·i₂是派生量',
 'parameters':'两个子P的作者输入、内部连接、同轴/安装关系、固定环边界与依赖版本。',
 'outputs':'展开图、逐级状态、总比与两个反力；子模型能力共同限制复合能力。',
 'budget':'UI节点1、齿轮级2；P2→H→W共4齿轮级；再接丝杆则另记终端转换。',
 'current':'本轮复合manifest草案，不是已安装插件','limits':'仅当展开图、角色和约束相同，才与平铺P→P去重。共同齿圈/复合行星等不能偷偷并为同一宏。'},
 {'id':'SC','short':'丝杆螺母','title':'SC · 旋转—直线转换单元','symbol':'转动端 / 平动端 / 约束反力',
 'input':'旋转端 φ、ω、τ','output':'平动端 x、v、F','mount':'须表达推力支承、螺母防转与反力路径；旋转丝杆和旋转螺母是不同角色配置。',
 'core_math':'v=lead·ω/(2π rad)；正反驱与摩擦域独立',
 'parameters':'导程/头数、根径/有效径、材料、摩擦/润滑、支承与全行程、载荷谱；滑动与滚珠不同模型。',
 'outputs':'推力/速度/驱动扭矩与损耗、屈曲/转速/寿命等各项能力状态。',
 'budget':'本轮齿轮级0、终端转换1；limit_basis必须明确是齿轮级还是总串联级。',
 'current':'本轮理想四端口数学样例，主链未实现','limits':'理想功率关系不证明自锁、PV/磨损或滚珠疲劳寿命；无来源时返回blocked。'},
 {'id':'SUP','short':'轴与支承','title':'SUP · 轴、轴承、连接与箱体附属组件','symbol':'结构 / 安装 / 热的装配关系',
 'input':'轴载荷 / 安装接口','output':'反力 / 挠度 / 校核','mount':'形成完整负载路径；不出现在H/P/W/B字母序列里不代表可以省略。',
 'core_math':'平衡、变形与各已支持方法；一维与三维范围分开',
 'parameters':'轴段、支承位置/定位、真实材料、目录C/C0、配合、连接、刚度与热边界。',
 'outputs':'支反力、挠度/转角、轴/轴承/键/过盈检查，进一步反馈齿向与布局。',
 'budget':'齿轮级0；零件、支承、轴与装配复杂度单独统计。',
 'current':'已有有限系统核算；完整自动装配未闭合','limits':'当前draft的reaction_obligations是接口义务，完整结构安装/三维载荷恢复与箱体资格仍需实现。'}]
byid={s['id']:s for s in sources}
def link(sid,label=None):
 s=byid[sid];return f'<a href="{esc(s["url"])}">{esc(label or s["title"])}</a>'
vendor_rows=''.join([
 '<tr><td>KISSsoft / KISSdesign / System Module</td><td>组件与装配、变体、系统数据；脚本/COM参数研究。</td><td>部件→系统拓扑、复用装配、统一工况。<br>'+link('KISS-SYSTEM-MODELING','官方建模')+' · '+link('KISS-SKRIPT-COM','自动化')+'</td><td>公开页不证明无限穷尽综合、全局最优或本机已许可；不能称它只有手工。</td></tr>',
 '<tr><td>Romax</td><td>参数化系统、多属性优化、流程自动化与批量运行。</td><td>系统级多属性流程与设计探索。<br>'+link('ROMAX-PARAMETRIC-AUTOMATION','官方产品简介')+' · '+link('ROMAX-BATCH-2026','2026.1批量研究')+'</td><td>API服务页面不能替代桌面接口契约或本机实测；此处不比较速度/精度优劣。</td></tr>',
 '<tr><td>Modelica / 1D物理连接</td><td>位势相容、flow零和、固定边界允许反力。</td><td>借鉴连接语义，保留位置/反力与方程编译。<br>'+link('MODELICA-CONNECTION-SEMANTICS','连接规范')+' · '+link('MODELICA-ROTATIONAL-FLANGE','旋转端口')+'</td><td>不等于gearbase已有DAE、动态积分或三维结构求解。</td></tr>'
])
prec_rows=[]
for p in precedents:
 url=p['source_urls'][0];name=p['manufacturer']+' '+p['product_family'];desc=p['verified_family_precedent']
 # Short original Chinese summaries; complete, qualified metadata remains in the JSON annex.
 brief={'precedent-sew-s':'S基本结构有螺旋齿→蜗杆的顺序资料；不覆盖全部现售变体。','precedent-sew-p':'前级斜齿/锥斜齿与行星组合，产品表含4/5级。','precedent-sew-pxe':'锥斜齿前级与行星组合，产品族表列3/4级。','precedent-nord-maxxdrive':'平行轴斜齿产品族具有2～4级选项，需按子系列区分。','precedent-neugart-ple':'同轴行星产品族有1/2/3级选项，逐级角色尚不明确。'}[p['id']]
 prec_rows.append(f'<tr><td><a href="{esc(url)}">{esc(name)}</a></td><td>{esc(brief)}</td><td>厂商产品族 / 部分结构路径</td><td>具体型号内部角色、完整工况与可复算参考解仍为空</td></tr>')
roadmap=[
 ('A0','稳定数学单元契约与计数政策','端口/变量/单位/角色、域、能力和证据；把原子、宏、实例与工况分开。','单元schema与语义规则、单位桥、阶段预算及反力义务。','零速、固定环、类型/单位、反驱域和宏预算反例全部有预期拒绝；shape通过不得冒充物理通过。'),
 ('A1','先包装H，复用已有数学核','把现有圆柱source/rating/优化装配为单元消费者，不重写公式。','一个显式输入的H实例、有效输入/约束报告与已有数值基线。','新T/n/限值真正进入同一模型；保留上一轮40→400N·m反例；没有未解释默认工况。'),
 ('A2','实现受限网络编译与复合P2','类型/角色/自由度检查，固定边界局部消元后进入DAG。','有符号n/T/P/损耗/反力；P2展开图；未支持模式明确blocked。','理想H/P/P2数学参考、端口平衡、零速和欠约束通过；不宣称完整W/P工程或通用DAE。'),
 ('A3','发布版本化组合配方库','先登记4类型的340抽象架构；四类型≤2级20条先作审阅短名单，扩展六类型则为42条，分母分别保留。','库索引、宏/规范签名、拒绝账本、能力域、先例关联与版本锁。','计数闭式/枚举一致，级序不合并，宏不增虚假架构；未核先例open；W→W不被偏好规则暗删。'),
 ('A4','实现需求→查库→参数设计','从同一个输出合同筛结构，显式确定驱动工况，再分配比值和求离散参数。','不同架构的参数备选、硬约束/裕量与缺口，不只是一堆齿数点。','同需求小域独立全枚举对拍；所有必需需求有consumer或blocked；部分评级不冒充全系统可行。'),
 ('A5','纵向闭合支承、布局与丝杆终端','H→H真实样板先行；装配/空间与热、轴承轴连接统一，再接SC。','一个同源系统实例及负载路径，变更后CAD/FE/制造状态失效与重建。','修改级序/齿数/导程后下游正确更新；真实支承和空间可复核；缺参不补造。'),
 ('A6','逐族提高工程资格与案例覆盖','W/P/B/I/X及滑动/滚珠丝杆分别建立物理域；组合库积累完整真实案例。','具名方法/标准/供应商对照、真实参数方案及合格用途证据。','按适用范围独立验证；保留FE失败与外部金标/工艺要求；不能用组合库数量替代工程资格。')]
road_rows=[]
for no,title,action,deliver,gate in roadmap:
 road_rows.append(f'<article class="road-step"><div class="step-no">{no}</div><div><span class="pill proposed">建议实施切片，尚未产品化</span><h3>{esc(title)}</h3><p>{esc(action)}</p><div class="road-spec"><div><strong>交付</strong>{esc(deliver)}</div><div><strong>验收</strong>{esc(gate)}</div></div></div></article>')
schema_example={k:math['plugin_manifests'][-1][k] for k in ['schema','id','version','status','owner_layer','role','stage_accounting','decomposition','reaction_obligations']}
topologies=[{'id':e['candidate_id'],'sequence':e['letter_word'],'semantic_signature':e['semantic_signature'],'precise_industrial_precedent_verified':False} for e in lib['entries'] if e['base_four_atom_member']]
assert len(topologies)==340 and all(e['industrial_precedent']['state']=='OPEN' for e in lib['entries'])
source_list=[]
for s in sources:
 source_list.append(f'<div class="evidence-item"><strong><a href="{esc(s["url"])}">{esc(s["title"])}</a></strong><span class="ref">{esc(s["id"])} · {esc(s.get("publisher","官方来源"))} · 核查2026-11-01</span></div>')
source_list.insert(0,'<p>下列为官方资料核查，证明文档中给出的建模/产品事实；本轮没有试调用厂商API或复现其计算精度。完整范围与不支持的推论见 <a href="research/sources.json">sources.json</a>。所引用PDF仅保留URL与简短摘要，不复制标准或厂商手册原件。</p>')
preservation={'schema':'gearbase.architecture-r2-source-preservation/1','source_version':'0.20','source_commit':head,'core_unchanged':True,'frozen_python_file_count':len(frozen),
 'frozen_python_sha256':frozen,'prior_private_html_sha256':sha(R1/'index.html'),'prior_public_html_sha256':sha(R1/'public-stage/index.html'),
 'previous_report_copy_exact':True,'product_models_added':False,'product_acceptance_gates_run':False,'physical_models_thawed':False,'new_FE_or_KISSsoft_run':False}
save(HERE/'source-preservation.json',preservation)
data={'schema':'gearbase.component-architecture-report/2','report_revision':2,'date_local':'2026-11-01','timezone':'America/Los_Angeles','source_version':'0.20','source_commit':head,
 'classification':'top_level_architecture_and_analysis_not_product_plugin_release','core_modified':False,
 'alphabet':['P','H','B','W'],'topologies':topologies,'units':units,'counts':{k:{'by_stage':v['plain_by_physical_stages'],'ordered':v['plain_ordered_sequences'],'macro_raw':v['weighted_macro_expressions_admitted'],'macro_unique':v['expanded_unique_semantic_topologies']} for k,v in counts['domains'].items()},
 'math_checks_passed':math_result['passed'],'math_checks_failed':math_result['failed'],'industrial_product_families':len(precedents),'precise_topology_industrial_matches_recorded':0,
 'evidence_sha256':{n:sha(HERE/n) for n in ['library/enum-counts.json','library/topology-library.json','library/verification-log.json','math/component-contract.json','math/math-examples.json','math/math-example-results.json','math/MATH-DESIGN.md','research/sources.json','research/industrial-precedents.json','research/METHODS-COMPARISON.md']}}
save(HERE/'report-data.json',data)
template=(HERE/'report.template.html').read_text(encoding='utf8').replace('四家族','四类型').replace('六家族','六类型')
values={'STYLE':old_style,'COUNT_ROWS':'\n'.join(rows),'COMPONENT_CONTRACT_EXAMPLE':esc(json.dumps(schema_example,ensure_ascii=False,indent=2)),
 'VENDOR_ROWS':vendor_rows,'PRECEDENT_ROWS':'\n'.join(prec_rows),'ROADMAP':'\n'.join(road_rows),'SOURCE_LIST':'\n'.join(source_list),
 'PAYLOAD':json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')}
for key,value in values.items():assert '@@'+key+'@@' in template;template=template.replace('@@'+key+'@@',value)
assert not re.search(r'@@[A-Z_]+@@',template)
(HERE/'index.html').write_text(template,encoding='utf8')
status={'schema':'gearbase.architecture-r2-status/1','source_version':'0.20','report_revision':2,'core_unchanged':True,'source_commit':head,'product_plugin_api_implemented':False,
 'production_frozen':False,'prebuilt_library':'analysis-only abstract candidates; not mature engineering solutions','four_type_structures':340,'six_type_structures':1554,
 'two_stage_macro_counts_as':2,'math_checks_passed':math_result['passed'],'enumeration_unit_tests':12,'enumeration_negative_probes':10,
 'new_whole_milestone_closed':False,'prior_report_conclusions_unchanged':True,'M40':'existing frozen physical qualification scope unchanged',
 'next_slice':'A0 mathematical contract then A1 reuse existing H calculations, before online multi-topology design'}
save(HERE/'STATUS.json',status)
save(HERE/'build-receipt.json',{'schema':'gearbase.component-report-build/1','passed':True,'producer_sha256':sha(Path(__file__)),'template_sha256':sha(HERE/'report.template.html'),
 'html_sha256':sha(HERE/'index.html'),'data_sha256':sha(HERE/'report-data.json'),'evidence_sha256':data['evidence_sha256'],'source_commit':head})
print(json.dumps({'passed':True,'html_sha256':sha(HERE/'index.html'),'structures4':len(topologies),'structures6':len(lib['entries']),'math_checks':math_result['passed']},ensure_ascii=False))
