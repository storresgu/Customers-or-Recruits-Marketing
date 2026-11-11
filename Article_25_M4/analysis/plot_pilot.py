"""Descriptive time courses: bands are interquartile simulation ranges, not CIs."""
import csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
src=Path(sys.argv[1]); dest=Path(sys.argv[2]);dest.mkdir(parents=True,exist_ok=True)
with (src/'monthly_metrics.csv').open() as f: rows=list(csv.DictReader(f))
scenarios=sorted({r['scenario_id'] for r in rows})
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey=False,layout='constrained')
for ax,sid in zip(axes.flat,scenarios):
 for condition,color,label in [('control','#2467A6','Control'),('shock','#CB632C','Recruitment stopped')]:
  matrix=np.array([[float(next(r['external_units'] for r in rows if r['scenario_id']==sid and r['condition']==condition and int(r['replicate_id'])==rep and int(r['month'])==month)) for month in range(1,121)] for rep in range(1,11)])
  ax.plot(range(1,121),matrix.mean(axis=0),color=color,lw=1.8,label=label)
  lo,hi=np.quantile(matrix,[.25,.75],axis=0)
  ax.fill_between(range(1,121),lo,hi,color=color,alpha=.13,linewidth=0)
 ax.axvline(61,color='#555555',ls='--',lw=1)
 retail=int(sid.split('_')[0][6:])/100; repeat=int(sid.split('_')[1][6:])/100
 ax.set_title(f'Retail conversion {retail:.2f} · Repurchase {repeat:.2f}',loc='left',fontweight='bold')
 ax.grid(axis='y',alpha=.16);ax.set_xlim(1,120);ax.set_ylim(bottom=0)
 ax.set_xlabel('Month');ax.set_ylabel('External units / month')
axes[0,0].legend(frameon=False)
fig.suptitle('Article 25 · Pilot demand trajectories\n10 pairs per scenario · Means and interquartile ranges · Panel-specific y scales',fontsize=12,fontweight='bold')
fig.savefig(dest/'Article_25_M4_Trayectorias_v0.1.png',dpi=180)
fig.savefig(dest/'Article_25_M4_Trayectorias_v0.1.svg')
(dest/'plot_environment.json').write_text(json.dumps({'matplotlib':matplotlib.__version__,'numpy':np.__version__},indent=2)+'\n')
