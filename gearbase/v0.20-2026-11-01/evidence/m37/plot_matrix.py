from pathlib import Path
import hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent
source=root/'ingest-matrix.json'; report=json.loads(source.read_text(encoding='utf8'))
rows=report['ladder']['L2']['rows']
fig,ax=plt.subplots(figsize=(10,4.6),layout='constrained')
ax.axhspan(.9,1.1,color='#dceee3',zorder=0,label='Original acceptance band [0.90, 1.10]')
x=list(range(len(rows)));values=[r['ratio'] for r in rows]
ax.bar(x,values,color=['#16816b' if r['pass'] else '#c34e44' for r in rows],width=.7,zorder=2)
for i,row in enumerate(rows):
 ax.text(i,row['ratio']+.007,f"{row['ratio']:.3f}",ha='center',fontsize=8)
ax.set_xticks(x,[r['point']+(' *' if not r['converged'] else '') for r in rows])
ax.set_ylim(.75,1.14);ax.set_ylabel('Richardson YFS_FE / YFS_ISO')
ax.set_title('Actual canonical L2 matrix: 9/14 pass; overall qualification FAILED')
ax.grid(axis='y',alpha=.2,zorder=0);ax.legend(loc='upper left',fontsize=8)
fig.text(.02,.005,'* Convergence requirement also failed. Assumed-order fallbacks remain reported; no threshold or reference changes.',fontsize=8)
for suffix in ('png','svg'):fig.savefig(root/f'matrix-summary.{suffix}',dpi=180)
(root/'matrix-plot-provenance.json').write_text(json.dumps({'receipt_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'plot_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'rows':rows,'limits':'All fixed 14 points; no omitted failures; validation ladder remains blocked.'},indent=2)+'\n',encoding='utf8')
