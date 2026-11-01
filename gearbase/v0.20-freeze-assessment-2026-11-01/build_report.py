from pathlib import Path
import base64,copy,hashlib,html,json,re,subprocess,datetime
HERE=Path(__file__).resolve().parent;SOURCE=HERE.parent/'gearbase-v020-work'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
esc=lambda x:html.escape(str(x),quote=True)
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
base=read(HERE/'baseline/receipt.json');assert base['passed'] and base['source_unchanged']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE).decode().strip()==base['source_commit']
arch=read(HERE/'architecture/capability-matrix.json');raw=read(HERE/'cases/challenge-results.json');catalog=read(HERE/'cases/case-catalog.json')
goal=read(HERE/'roadmap/goal-map.json');contract=read(HERE/'roadmap/freeze-contract.json');milestones=read(HERE/'baseline/milestones.json')
req=read(HERE/'architecture/evidence/requirements.stdout.json')['results'];prior=HERE.parent/'v020-closure-run'
old=read(prior/'DELIVERY-VERIFIED.json');assert old['passed']
assert len(arch['capabilities'])==26 and [c['candidate_count'] for c in raw['challenges'][:3]]==[40,15,5]
assert sum(c['blocked_count'] for c in raw['challenges'][:3])==60
assert raw['challenges'][1]['thermal_fail_count']==15 and req['summary']['optimized_responses_equal']
tests=int(re.search(r'Ran (\d+) tests',(HERE/'baseline/targeted-tests.stderr.log').read_text(encoding='utf8'))[1]);assert tests==62
modules=read(HERE/'baseline/architecture.json')['files_checked'];assert modules==146
current_summaries={
 'CAP-01':'单位/域/唯一公式输出校验；实际求值、单位错误与派生输入拒绝已运行。',
 'CAP-02':'源文档与只读投影；本轮副本改宽度后重新求值，原源未变。',
 'CAP-03':'公式链可展开；有自动微分及灵敏度实现。',
 'CAP-04':'预览、CAS/修订链及显式文件存储实现；本轮仅运行只读预览。',
 'CAP-05':'接受结构化单级直齿需求；缺项追问与未应用项回显。',
 'CAP-06':'本地MCP协议工具可调用，外部模型负责自然语言解释。',
 'CAP-07':'当前由用户先指定H2/W2W/P2，或已知单副模型。',
 'CAP-08':'固定C001工况的单副局部连续优化可复跑。',
 'CAP-09':'已有source-owned声明域优化、证据保持与独立重建验证路径。',
 'CAP-10':'本轮27组合、8可行，与重新全枚举一致。',
 'CAP-11':'圆柱副几何与所收录强度分支；本轮C001派生单副校核可运行。',
 'CAP-12':'TR30特定路径已有内齿/双斜齿分支。',
 'CAP-13':'本轮返回40个采样几何候选、原样复查。',
 'CAP-14':'本轮15个双蜗杆候选；恒摩擦效率与给定散热模型热初筛。',
 'CAP-15':'本轮5个双行星Pareto代表，整数运动学与结构限制。',
 'CAP-16':'归档/vendor中存在部分齿形和方法代码，待逐项迁入与资格验证。',
 'CAP-17':'显式载荷/材料/限值下，可调用轴、轴承、键、过盈检查。',
 'CAP-18':'有限刚性点支承的直梁模型、挠度、转角与扭转。',
 'CAP-19':'已有梁→齿向贡献接口与KHβ公式片段。',
 'CAP-20':'显式供应商参数及作者给定的有限轴承候选可核算。',
 'CAP-21':'显式损耗/热边界下的平衡与温度求根。',
 'CAP-22':'严格读取、身份绑定、提取量重贴；历史L2实际42作业，9/14通过。',
 'CAP-23':'归档有四族headless CAD、STEP与重读路线；主链尚未整体接入。',
 'CAP-24':'制造参数投影、齿轮包络图与部分BOM已有。',
 'CAP-25':'当前未找到主链计算入口；本报告给出建议接口。',
 'CAP-26':'DAG内更新、局部source/CAS与独立CAD/FE工件管理分别存在。'}
capabilities=[];caprows=[]
prefix='https://github.com/qizhou-hust/yuanqi-public/blob/main/gearbase/v0.20-2026-11-01/core-source/gearbase/'
for c in arch['capabilities']:
 status='blocked' if c['status']=='missing' else c['status'];label={'verified':'已验证（限定范围）','partial':'部分 / 有范围','blocked':'主链未覆盖'}[status]
 refs=[]
 for ref in c['code_refs'][:2]:
  path=Path(ref['path']);rel=path.relative_to(SOURCE).as_posix();assert path.exists()
  assert 1<=ref['line']<=len(path.read_text(encoding='utf-8-sig').splitlines())
  if rel.startswith('gearmath/'):refs.append(f'<a href="{prefix+rel}#L{ref["line"]}">{esc(rel)}:{ref["line"]}</a>')
  else:refs.append(esc(rel)+':'+str(ref['line']))
 item={'id':c['id'],'name':c['capability'],'status':status,'current':current_summaries[c['id']],'limits':c['limits'],'source_refs':c['code_refs']};capabilities.append(item)
 caprows.append(f'<tr data-status="{status}"><td><b>{esc(c["capability"])}</b></td><td><span class="pill {status}">{label}</span></td><td>{esc(item["current"])}<div class="fine">'+ '<br>'.join(refs)+f'</div></td><td>{esc(c["limits"])}</td></tr>')

titles={'H2':('两级平行斜齿','两级平行斜齿：原始H2需求'), 'W2W':('两级蜗杆','两级蜗杆：原始W2W需求'), 'P2':('两级行星','两级行星：原始P2需求'), 'C001-fixed-pair':('给定圆柱副','C001派生G1：固定齿轮对校核'), 'K01-spur-fixed-pair':('给定K01直齿副','K01：固定商业对拍输入'), 'SAME-H2-DEMAND':('同需求跨族挑战','同一H2需求：去掉预选family后能否规划？')}
observations={
 'H2':'固定H→H家族，459×824采样级组合中有9948条通过Stage0的比值/几何谓词，输出上限截取40条；40条均接入系统模板而blocked。',
 'W2W':'980对声明域组合返回15条候选；15/15热筛选失败。首选η≈0.54084、估计油温148.54°C，高于给定90°C上限；其系统评级另因模型/输入缺失blocked。',
 'P2':'485个级身份、117855对组合，2311条通过已有Stage0谓词，返回5个Pareto代表；5条系统均blocked。',
 'C001-fixed-pair':'这是源文档中b=30mm的派生G1，不是原50题C001中b=10mm的原G1。固定副gear_rating通过，其余系统/油品/制造等缺项阻断；未执行架构生成。',
 'K01-spur-fixed-pair':'固定输入计算出四个SH/SF达到给定限值；gear_rating整体仍因eps_alpha_min缺失而blocked，其他系统边界亦不完整。未执行架构生成。',
 'SAME-H2-DEMAND':'保留H2参数及来源里的600N·m@150rpm，移除family，实际调用返回blocked_unsupported_scope；完整输出/轴关系合同还被Stage0输入模式拒绝。未形成跨族候选集。'}
limits={
 'H2':'只验证零变位、名义采样几何；真实材料、刀具、载荷、支承、轴承、键与热数据不全，空间总成未验证。',
 'W2W':'效率/热使用该题明示的常摩擦与散热参数，不是详细蜗杆强度/磨损/胶合模型。15个热失败保留，不能当可交付方案。',
 'P2':'原模型提示同轴双啮合零变位导致理论零侧隙，装配需处理变位；未闭合均载、行星销/架、支承与强度。',
 'C001-fixed-pair':'同一案例的派生变体不新增工程案例；单副通过不等于C001双级整系统通过；布局/材料/载荷位置等仍需真实来源。',
 'K01-spur-fixed-pair':'缺少实际系统轴、轴承、键、过盈与热边界；不能用四个安全系数替代全部需求验收。',
 'SAME-H2-DEMAND':'没有为其他族猜摩擦、效率或轴线布局。计数是null，不是证明物理上无备选。其他旗舰使用不同需求合同，不能拿来凑三个答案。'}
cases=[];chrows=[]
for c in raw['challenges']:
 kind=c['challenge_kind'];fixed=kind=='fixed_pair_rating_not_generation' or 'fixed-pair' in c['id'];same=c['id']=='SAME-H2-DEMAND'
 item={'id':c['id'],'short_title':titles[c['id']][0],'title':titles[c['id']][1],
 'requirement_summary':c['requirement_summary'],'candidate_count':c['candidate_count'],'unique_topology_count':c['unique_topology_count'],
 'full_system_pass_count':c['full_system_pass_count'],'count_label':'给定固定副（非生成）' if fixed else '实际返回候选',
 'evidence_class':'本轮确定性复跑；不代表真实工程签署','status_class':'blocked','status_label':'接口不支持' if same else '系统被阻断',
 'equivalence_group_id':c['equivalence_group_id'],'observation':observations[c['id']],'limits':limits[c['id']],
 'comparability':'保持该来源合同，只检验去family后的跨族入口；没有与W2W/P2混用条件。' if same else '本题有独立需求合同；与另两旗舰不可当作同一需求备选。' if c['id'] in {'H2','W2W','P2'} else '固定输入/派生版本的数值校核；不是从同一外部需求自动规划。',
 'card_summary':f'{c["candidate_count"]}个给定副；系统阻断' if fixed else '移除family后接口阻断，数量未定义' if same else f'{c["candidate_count"]}候选 / 1固定架构 / 全系统blocked',
 'evidence_ref':'cases/challenge-results.json#'+c['id']}
 if c['id']=='W2W':item.update(status_label='热筛选失败 + 系统阻断',status_class='failed')
 cases.append(item)
 n='未定义' if c['candidate_count'] is None else '给定1对，非生成' if fixed else str(c['candidate_count'])
 t='未计数' if c['unique_topology_count'] is None else str(c['unique_topology_count'])
 stage='未生成' if same else '固定副数值校核' if fixed else f'{c["kinematic_pass_count_checked"]}条返回候选运动学通过；仅Stage0'
 system='接口不支持，未生成方案' if same else f'{c["blocked_count"]} blocked；完整系统通过0'
 lim='15/15热fail；首选148.54°C&gt;90°C；空间未验证' if c['id']=='W2W' else esc(limits[c['id']])
 chrows.append(f'<tr><td><b>{esc(c["id"])}</b></td><td>{n}</td><td>{t}</td><td>{stage}</td><td>{system}</td><td>{lim}</td></tr>')

intake=read(HERE/'intake-private/POD-stored-cells.json');sheet=intake['sheets'][0]
assert len(sheet['rows'])==20 and not [x for row in sheet['rows'][1:] for x in row['cells'] if x['cell'].startswith('C') and x['value'] not in (None,'')]
intake_meta={'schema':'gearbase.intake-metadata/1','source_filename':'POD需求确认.xlsx','source_sha256':intake['source_sha256'],
 'read_only':True,'source_unchanged':True,'sheet':'Sheet1','field_label_rows':19,'requirement_range':'C2:C20','populated_requirement_cells':0,
 'status':'blank_requirement_template_not_a_validated_engineering_case','formal_case_added':False,
 'method':'Stored OOXML values checked; no workbook edited or recalculated. Private cell extract not included in the public package.'}
save(HERE/'intake-metadata.json',intake_meta)

inventory_rows=[
 ('C001–C050 派生基准','50个自编派生实例；50/50理想无损运动学校核通过','类型、齿数/比与单位的回归；本轮使用显式披露的archive数学桥','不是50个真实工程整机；非空间/强度验收'),
 ('H2 / W2W / P2','3个固定架构的原始需求；本轮60个返回候选逐项尝试系统检查','分族Stage0、缺项与失败发现','不同需求，不是同需求3方案'),
 ('K01–K05','5个固定啮合副商业对照身份；多轮修订不重复计数','方法口径、参数与安全系数差异','不是5套完整齿轮箱的生产验证'),
 ('TR30','8个标准算例身份；私有转录仅本地目录保留','几何/材料/强度分支的数值参照','完整E4仍未验收；不得公开标准数字库'),
 ('外部引用','4个CAD参考、2个报告的物理试验参考、1个外部解例','单项独立资料与对照入口','存在引用不等于已复现实物或全系统通过'),
 ('语言与能力回归','40题语言评测待独立标注；1个有限联合能力fixture','追溯/编译/拒绝/小域全枚举','不能充当真实工程题或独立金标'),
 ('工作区补充索引','FE索引25题；旧包57个重复案例/引用；部分PDF/图纸未解析','后续入库线索，扫描范围已记录','不能与齿轮需求案例简单相加；旧benchcad索引JSON解析失败'),
 ('POD需求表（本轮补查）','1张19项需求模板；C2:C20全为空','可作为直线执行器需求采集入口','尚无输入值，不新增真实工程案例或金标')]
invrows=''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in inventory_rows)
msnotes={'M32':'数学内核和原契约关闭；不是整机产品验收','M33':'例7/8指认的几何数值范围计完成；完整E4仍开放','M34':'来源与优化部分可用；真实模型客户端调用按决定暂缓','M35':'制造准备产物可用；完整图纸与真实工艺审阅尚缺','M36':'有限联合优化门通过；真实C001与旗舰系统仍缺输入/模型','M37':'严格记录已落实；L2失败、用途资格未授予','M38':'数字追溯/部分评测可运行；独立金标40题仍空','M39':'部分失效/热/前沿能力；完整高速代表例仍缺边界','M40':'详细新传动族仍冻结；本轮未改变'}
msrows=''.join(f'<tr><td><b>{m["milestone"]}</b></td><td>{m["done"]}/{m["gate_items"]}</td><td>{msnotes[m["milestone"]]}</td></tr>' for m in milestones['milestones'])
counter=[]
def crow(name,a,b,note):counter.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in (name,a,b,note))+'</tr>')
ra,rb=req['requirements'];oa,ob=req['optimization_responses'];sa=oa['solution'];sb=ob['solution']
for name,key,unit in [('转矩','torque_Nm','N·m'),('转速','speed_rpm','rpm'),('寿命','life_h','h')]:crow(name,str(ra[key])+' '+unit,str(rb[key])+' '+unit,'明确新需求；只有部分字段进入rating_edit，未全部进入模板优化')
crow('空间上限 a / b',f'{ra["max_center_distance_mm"]} / {ra["max_face_width_mm"]} mm',f'{rb["max_center_distance_mm"]} / {rb["max_face_width_mm"]} mm','编译器列为post_checks，未成为模板硬约束')
crow('优化结果 b / a',f'{sa["x"]["b"]:.6f} / {sa["objectives"]["center_distance_mm"]:.6f} mm',f'{sb["x"]["b"]:.6f} / {sb["objectives"]["center_distance_mm"]:.6f} mm','相同点；B空间上限并未满足，不可按原需求放行')
crow('IR / feasible',oa['problem_ir_sha256'][:12]+'… / True',ob['problem_ir_sha256'][:12]+'… / True','模板域内的可行性；不是原需求全约束通过')
sh=[next(x['value'] for x in r['checks'] if x['quantity']=='S_H_1') for r in req['rating_responses']]
crow('独立rating_edit的SH1',f'{sh[0]:.8f}',f'{sh[1]:.8f}','实际转矩已进入该单副校核，结果显著下降')

road=[]
for i,s in enumerate(goal['slices'],1):
 name=s['name'];outputs=s['output'];gates=s['acceptance_gate'][:3]
 if s['id']=='R1':
  name='先贯通真实需求与有效约束，再稳定系统合同'
  outputs=['新转矩/转速/限值进入同一source-owned sizing/rating，未消费项明确阻断或后检查；统一README、MCP自报与包版本',*outputs]
  gates=['保留本轮40→400N·m反例：输入改变后实际评价响应改变；空间/安全限值被消费或明确不支持，不能误用模板feasible',*gates[:2]]
 def joined(v,limit=3):return '；'.join(str(x) for x in v[:limit])
 road.append(f'<article class="road-step"><div class="step-no">{i:02d}</div><div><div class="road-meta"><span class="pill proposed">建议切片 {s["id"]}</span><span class="pill historical">尚未实施</span></div><h3>{esc(name)}</h3><p>{esc(s["value"])}</p><div class="road-spec"><div><strong>输入</strong>{esc(joined(s["input"]))}</div><div><strong>交付</strong>{esc(joined(outputs))}</div><div><strong>可执行验收</strong>{esc(joined(gates))}</div><div><strong>外部数据 / 前置</strong>{esc(joined(s["external_engineering"]))}</div></div><p class="ref" style="margin-top:12px">依赖：{esc(joined(s["dependencies"]))}<br>软件可独立推进：{esc(joined(s["software_independent"]))}</p></div></article>')
checks=[('verified','本轮通过','源码与266个冻结Python字节不变；包完整性、146模块架构边界与62项定向测试通过。'),
 ('verified','本轮通过','三族60候选逐项检查、同需求跨族拒绝与需求优化反例已留原始输出；没有补写工程金标。'),
 ('historical','历史凭据','四项托管CI、678/678旧回归、1379项核心测试及明确可选跳过，引用前轮绑定提交；本轮未全量重跑。'),
 ('partial','试用前需读','模板实际适用域与未应用字段必须显著展示；README/MCP版本自报仍有漂移，下一包优先统一。'),
 ('blocked','工程放行未满足','真实系统输入、完整图纸/工艺审阅、独立金标、油品来源与FE资格均保留开放，不以演示数据关闭。')]
checkhtml=''.join(f'<div class="check-row"><span class="pill {cl}">{esc(label)}</span>{esc(text)}</div>' for cl,label,text in checks)
usage='''<p>在完整本地包的 <code>gearbase</code> 根目录运行。核心为Python工作台；CAD/FE和可选优化适配器另有依赖范围。</p><pre><code># 只读：单副校核（使用已存在的C001_G1基线，不是新需求自动设计）
python -X utf8 -B -c "from gearmath.tools.ai_tools import call; import json; print(json.dumps(call('gear_rate', {}), ensure_ascii=False, indent=2))"

# 只读：有限27组合的联合优化能力示例
python -X utf8 -B -m gearmath.tools.system_closure --inputs data/system-optimization/v017-capability-probe.json --out ../trial-joint-output

# stdio MCP服务：等待JSON-RPC，默认进程内状态
python -X utf8 -B -I mcp_server.py

# 本轮案例挑战：需要冻结的Git检出及脚本所列历史资料，不是仅解压HTML即可求解
python -X utf8 -B cases/run_challenges.py --source ../gearbase-v020-work</code></pre><p class="ref">前两个入口和本地MCP往返已在本轮实际执行；最后一条在报告附件目录调用，要求source为指定提交的Git检出，且历史数据仍可访问。普通ZIP解压不含Git身份，不能直接当完整审计复跑环境。连接真实模型客户端另按既有检查单验收，当前仍按用户决定暂缓。持久状态参数与全部试用配方见 <a href="architecture/ARCHITECTURE.md">架构审计</a>。</p>'''
references=goal['external_primary_sources']
refhtml='；'.join(f'<a href="{esc(r["url"])}">{esc(r["title"])}</a>' for r in references)
evidence=[('当前源码基线','原v0.20核心，未作本轮产品改动；源文件与原冻结清单一致。','baseline/receipt.json'),
 ('本轮能力审计','26项能力、代码行、当前响应定位与未验证范围。','architecture/capability-matrix.json'),
 ('本轮架构与入口发现','需求反例、真实接口与适用域、版本/权限边界。','architecture/findings.json'),
 ('本轮案例挑战','三旗舰、固定副与同需求探针；不同分母独立记录。','cases/challenge-results.json'),
 ('本轮案例盘点','去重、旧包字节重复、扫描范围、私有源说明。','cases/inventory.json'),
 ('终局目标到切片映射','原需求、差距、8项输入/输出/验收/依赖。','roadmap/goal-map.json'),
 ('真实入口边界探针','未知输出/空间/拓扑字段、来源标签语义和40题未标注状态。','roadmap/boundary-probes.json'),
 ('POD表格补充提取','19项空白要求，不计作已验证工程案例；私有单元格提取另存。','intake-metadata.json'),
 ('历史原始验证凭据','FE、商业对拍与托管CI是前轮固定哈希的证据；没有本轮重求解。','historical/DELIVERY-VERIFIED.json')]
evhtml=''.join(f'<div class="evidence-item"><strong>{esc(title)}</strong><span>{esc(desc)}</span><br><a href="{esc(path)}">{esc(path)}</a></div>' for title,desc,path in evidence)
hist=HERE/'historical';hist.mkdir(exist_ok=True)
for name in ['DELIVERY-VERIFIED.json','HOSTED-ACCEPTANCE.json']:(hist/name).write_bytes((prior/name).read_bytes())
payload={'schema':'gearbase.system-assessment-report/1','date_local':'2026-11-01','timezone':'America/Los_Angeles','baseline_commit':base['source_commit'],
 'source_version':'0.20','report_revision':1,'core_modified':False,'new_whole_milestone_closed':False,
 'fresh_targeted_tests':tests,'fresh_architecture_modules':modules,'capabilities':capabilities,'cases':cases,
 'case_counting_rule':'Do not sum different demands, derivatives or FE/language/reference units as real engineering cases.',
 'benchmark50':{'count':50,'provenance':'synthetic_derived_benchmark','ideal_kinematics_passed':50,'solver_path':'typed kernel with explicitly disclosed archived mathematical bridge','full_system_verified':False},
 'POD_intake':intake_meta,'milestones':[{'id':m['milestone'],'done':m['done'],'total':m['gate_items'],'note':msnotes[m['milestone']]} for m in milestones['milestones']],
 'external_primary_sources':references,'roadmap_status':'proposed_not_implemented','source_evidence_files':{p:sha(HERE/p) for _,_,p in evidence}}
save(HERE/'report-data.json',payload)
freeze={'schema':'gearbase.preliminary-freeze/1','date_local':'2026-11-01','timezone':'America/Los_Angeles','source_version':'0.20','source_commit':base['source_commit'],
 'classification':'engineering_trial_baseline_with_explicit_scope','production_frozen':False,'source_modified':False,
 'core_python_files':read(prior/'code-freeze.json'),'current_checks':base,'case_challenge_sha256':sha(HERE/'cases/challenge-results.json'),
 'capability_matrix_sha256':sha(HERE/'architecture/capability-matrix.json'),'goal_map_sha256':sha(HERE/'roadmap/goal-map.json'),
 'scope_contract_sha256':sha(HERE/'roadmap/freeze-contract.json'),'known_open_items':['requirement to source sizing coverage','README and MCP version drift','general topology planning','real engineering case completion','full system SSOT and CAD/FE invalidation','FE L2 qualification failure','independent real gold and manufacturing review'],
 'claude_model_client':'deferred_by_user','M40':'unchanged_frozen','new_physical_models_added':False,'engineering_decisions_invented':False}
save(HERE/'freeze-manifest.json',freeze)
template=(HERE/'report.template.html').read_text(encoding='utf8')
tokens={'MODULES':str(modules),'TESTS':str(tests),'MILESTONE_ROWS':msrows,'CAPABILITY_ROWS':'\n'.join(caprows),
 'COUNTEREXAMPLE_ROWS':'\n'.join(counter),'FE_IMAGE':'data:image/png;base64,'+base64.b64encode((prior/'m37/matrix-summary.png').read_bytes()).decode('ascii'),
 'INVENTORY_ROWS':invrows,'CHALLENGE_ROWS':'\n'.join(chrows),'SCREW_REFS':refhtml,'ROADMAP_STEPS':'\n'.join(road),
 'FREEZE_CHECKS':checkhtml,'USAGE_CONTENT':usage,'EVIDENCE_LIST':evhtml,
 'PAYLOAD':json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')}
for token,value in tokens.items():
 assert '@@'+token+'@@' in template,token
 template=template.replace('@@'+token+'@@',value)
assert not re.search(r'@@[A-Z_]+@@',template)
(HERE/'index.html').write_text(template,encoding='utf8')
save(HERE/'build-receipt.json',{'schema':'gearbase.assessment-build/1','passed':True,'source_commit':base['source_commit'],
 'producer_sha256':sha(Path(__file__)),'template_sha256':sha(HERE/'report.template.html'),'html_sha256':sha(HERE/'index.html'),
 'data_sha256':sha(HERE/'report-data.json'),'capabilities':len(capabilities),'challenge_cards':len(cases),'candidate_system_blocked':60,'core_unchanged':True})
print(json.dumps(read(HERE/'build-receipt.json'),ensure_ascii=False,indent=2))
