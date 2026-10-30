"""Build standalone interactive geometric evidence without desktop input."""
from pathlib import Path
import json, hashlib
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.offline import get_plotlyjs

ROOT=Path(__file__).resolve().parent; OUT=ROOT/'geometry-review'; OUT.mkdir(exist_ok=True)
GEOM=ROOT/'m37-preflight/geometry'
COL={'PFL':'#d44b2a','WFL':'#087f99','OTHER':'#b0bac7'}

def line_trace(points,name,color,width=2,legend=True):
    return go.Scatter3d(x=[p[0] if p else None for p in points],y=[p[1] if p else None for p in points],
        z=[p[2] if p else None for p in points],mode='lines',name=name,line=dict(color=color,width=width),
        showlegend=legend,hoverinfo='skip')

def add_geo(fig,col,geo,pressure=None,zoom=False):
    def add(trace):fig.add_trace(trace,row=1,col=col)
    for tag in ['OTHER','PFL','WFL']:
        points=[]; vx=[];vy=[];vz=[];ii=[];jj=[];kk=[]
        for e in geo['boundary_edges']:
            if e['tag']!=tag:continue
            xy=e['points_mm']
            if zoom and not any(-4<p[0]<8 and 17<p[1]<25 for p in xy):continue
            for z in [-.5,.5]:points.extend([[p[0],p[1],z] for p in xy]+[None])
            if tag!='OTHER':
                for p,q in zip(xy,xy[1:]):
                    off=len(vx)
                    for a,z in [(p,-.5),(q,-.5),(q,.5),(p,.5)]:vx.append(a[0]);vy.append(a[1]);vz.append(z)
                    ii.extend([off,off]);jj.extend([off+1,off+2]);kk.extend([off+2,off+3])
        add(line_trace(points,{'OTHER':'外边界','PFL':'小轮接触候选面','WFL':'大轮接触候选面'}[tag],COL[tag],1 if tag=='OTHER' else 4,col==1))
        if vx:add(go.Mesh3d(x=vx,y=vy,z=vz,i=ii,j=jj,k=kk,color=COL[tag],opacity=.35,hoverinfo='skip',showlegend=False))
    for k,pair in enumerate(geo['contact_pairs']):
        p=pair['theoretical_point_mm'];add(go.Scatter3d(x=[p[0]],y=[p[1]],z=[.6],mode='markers',
            marker=dict(color='#8e3bc2',size=6,symbol='diamond'),name='理论接触点',showlegend=(col==1 and k==0),
            text=[f'点{k}；间隙 {pair["nearest_point_gap_mm"]:.7g} mm'],hoverinfo='text'))
        for side,color in [('pinion','#d44b2a'),('wheel','#087f99')]:
            near=pair[side];p=near['point_mm'];v=near['outward_normal'];scale=.35 if zoom else 2.5
            add(go.Cone(x=[p[0]],y=[p[1]],z=[.7],u=[scale*v[0]],v=[scale*v[1]],w=[0],
                anchor='tail',sizemode='absolute',sizeref=scale*.45,colorscale=[[0,color],[1,color]],showscale=False,
                name='接触外法向',hovertext=f'{side} 外法向；距理论点 {near["distance_mm"]:.6g} mm',hoverinfo='text'))
    if not zoom:
        rows=geo['boundary_conditions'][2]['rows'];seen={r['node']:r['point_mm'] for r in rows}
        add(go.Scatter3d(x=[p[0] for p in seen.values()],y=[p[1] for p in seen.values()],z=[0]*len(seen),
            mode='markers',marker=dict(size=2.3,color='#267447'),name='最终步约束节点',showlegend=col==1,
            text=[f'节点 {n}' for n in seen],hoverinfo='text'))
        for load in geo['loads']:
            p=load['point_mm'];v=[0,0];v[load['dof']-1]=np.sign(load['value'])*4
            add(go.Cone(x=[p[0]],y=[p[1]],z=[1],u=[v[0]],v=[v[1]],w=[0],anchor='tail',sizemode='absolute',sizeref=1.7,
                colorscale=[[0,'#202d47'],[1,'#202d47']],showscale=False,name='载荷',
                hovertext=f'节点 {load["node"]} / DOF{load["dof"]} / {load["value"]:.7g} N',hoverinfo='text'))
    if pressure:
        for e in pressure[:8]:
            pts=e['edge_points_mm'];p=np.array(pts[2]);
            add(go.Scatter3d(x=[p[0]],y=[p[1]],z=[.8],mode='markers',
                marker=dict(color=e['pmax_MPa'],size=7,cmin=0,cmax=5500,colorscale='Magma'),
                name='接触压力位置',showlegend=False,text=[f'单元 {e["element"]}：{e["pmax_MPa"]:.7g} MPa'],hoverinfo='text'))

def scene(zoom=False):
    return dict(xaxis=dict(title='x / mm',range=[-4,8] if zoom else [-40,40]),
        yaxis=dict(title='y / mm',range=[17,25] if zoom else [-25,95]),zaxis=dict(title='厚度 / mm',range=[-1,1]),
        aspectmode='data',camera=dict(eye=dict(x=.45,y=-.75,z=2.5)),bgcolor='#fafcff')

def main():
    geos={name:json.loads((GEOM/f'{name}.json').read_text()) for name in ['original_ph00','periodic_ph00','periodic_ph10']}
    fig=make_subplots(rows=1,cols=2,specs=[[{'type':'scene'},{'type':'scene'}]],subplot_titles=['原 ph00：接触面误选到大轮背侧','修复 ph00：覆盖实际在啮齿'])
    for col,key in enumerate(['original_ph00','periodic_ph00'],1):add_geo(fig,col,geos[key])
    fig.update_layout(scene=scene(),scene2=scene(),height=660,margin=dict(l=0,r=0,t=45,b=0),legend=dict(orientation='h',y=-.03),paper_bgcolor='white')
    ext=json.loads((ROOT/'extended-preflight.json').read_text());phase=next(r for r in ext['phases'] if r['phase']==10)
    fig2=make_subplots(rows=1,cols=1,specs=[[{'type':'scene'}]])
    add_geo(fig2,1,geos['periodic_ph10'],phase['active_pressure_elements'],True)
    fig2.update_layout(scene=scene(True),height=640,margin=dict(l=0,r=0,t=10,b=0),legend=dict(orientation='h',y=-.03),paper_bgcolor='white')
    h1=fig.to_html(full_html=False,include_plotlyjs=False,div_id='comparison',config={'displaylogo':False,'responsive':True})
    h2=fig2.to_html(full_html=False,include_plotlyjs=False,div_id='tip',config={'displaylogo':False,'responsive':True})
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>M37 · 前处理三维审查</title><link rel="icon" href="data:,"><style>
body{font:15px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;background:#eef2f7;color:#233149;margin:0}main{max-width:1450px;margin:auto;padding:24px}h1{font-size:27px;margin:0}header p{margin:5px 0 17px;color:#52627b}.card{background:white;border:1px solid #dce3eb;border-radius:12px;padding:18px;margin:15px 0}.note{background:#fff6dd;border-left:4px solid #c99b2c;padding:10px 15px}.meta{font-size:12px;color:#61718a;overflow-wrap:anywhere}.tab{border:1px solid #9baec4;border-radius:6px;background:white;color:#233149;padding:9px 18px;cursor:pointer;margin-right:8px}.tab.active{background:#233149;color:white}.facts{display:flex;gap:14px;flex-wrap:wrap}.facts div{flex:1;min-width:190px;background:#f5f8fc;padding:12px;border-radius:8px}.facts strong{display:block;font-size:21px}h2{font-size:19px;margin:5px 0}#tip-panel{display:none}a{color:#166e9c}
</style><script>'''+get_plotlyjs()+'''</script><main><header><h1>M37 · 前处理三维审查</h1><p>接触候选面 · 理论接触点 · 外法向 · 约束节点 · 载荷位置</p></header>
<div class="note">源模型为 CPE6 二维平面应变。以下沿厚度方向挤出 1 mm，仅辅助核对定义；不是三维应力分析，也不替代数值验收。</div>
<div class="card"><button class="tab active" id="compare-tab" onclick="showPanel('compare')">ph00 修复前后</button><button class="tab" id="tip-tab" onclick="showPanel('tip')">ph10 齿端检查</button><span>拖动旋转 · 滚轮缩放 · 悬停读数 · 图例开关</span></div>
<section id="compare-panel" class="card"><h2>周期齿号不能直接做算术平均</h2><p>原模型把跨周期的齿号 −35、0 平均到背面。修复仅改变接触面的齿号选择，保留原啮合相位与理论点。</p>'''+h1+'''<div class="facts"><div>原 ph00–09<strong>10 / 10 被拦截</strong>接触面距理论点错误、法向不符</div><div>修复 16 相位<strong>16 / 16 局部预检通过</strong>几何、刚体约束、载荷和单位检查</div><div>判定范围<strong>前处理检查</strong>整体模型 / 强度验收仍未通过</div></div></section>
<section id="tip-panel" class="card"><h2>ph10：理论单齿接触之外的齿端压力</h2><p>单元 7779 峰压 5283.265 MPa；理论在啮齿的局部峰压约 571.003 MPa。高压位于另一个齿端，后续须对这个实际接触位置做网格与接触收敛。</p>'''+h2+'''<div class="facts"><div>齿端初始局部最小间隙<strong>+0.001420295 mm</strong>41 个采样位置；尚非全域无穿透证明</div><div>轮心处接触 / 反力矩差<strong>0.001571%</strong>按同一坐标原点比较</div><div>接触矩 / 输入矩差<strong>0.003604%</strong>与原理想传动比偏差分别记录</div></div></section>
<div class="card"><h2>证据与限制</h2><p>原始输入与压力值均未改写。初态整体相交采用曲边离散多边形筛查，网格正 Jacobian 不代表齿端压力已收敛。刚度参考口径、实际接触区域的网格分辨率仍待闭合，M37 保持未验收。</p><p class="meta">输入 SHA256：<br>'''+ '<br>'.join(f'{k}: {g["input_sha256"]}' for k,g in geos.items())+'''</p></div></main>
<script>function showPanel(k){for(const n of ['compare','tip']){document.getElementById(n+'-panel').style.display=n===k?'block':'none';document.getElementById(n+'-tab').classList.toggle('active',n===k)}Plotly.Plots.resize(document.getElementById(k==='compare'?'comparison':'tip'))}</script></html>'''
    path=OUT/'M37-preprocessing-3D-review.html';path.write_text(html,encoding='utf8')
    manifest={'schema':'m37.geometry-viewer/v1','source_geometries':{k:hashlib.sha256((GEOM/f'{k}.json').read_bytes()).hexdigest() for k in geos},
        'output':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'external_network_required':False,
        'geometry':'2D exterior quadratic edges sampled at 5 points, extruded 1 mm; no 3D solve',
        'normal_arrow_length':'Graphical scale only; vector direction from original quadratic edge',
        'pressure':'Actual final DAT pressure attached to original, undeformed element edge; not a reconstructed 3D stress field'}
    (OUT/'viewer-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(path,path.stat().st_size)

if __name__=='__main__':main()
