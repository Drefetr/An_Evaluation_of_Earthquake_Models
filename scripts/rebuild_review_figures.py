"""Render saved aggregates and declared algebra only; never fit or simulate."""
from pathlib import Path
import argparse,fnmatch,hashlib,json,math,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'paper/figures';DATA=ROOT/'paper/data'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.5,'axes.titlesize':10,'axes.labelsize':9.5,'xtick.labelsize':9.5,'ytick.labelsize':9.5,'legend.fontsize':9.5,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
outputs=[]
def authority(pattern):
 rows=json.loads((ROOT/'validation/authority_manifest.json').read_text(encoding='utf-8'))
 found=[r for r in rows if fnmatch.fnmatch(Path(r.get('historical_bundled_path',r['bundled_path'])).name,pattern)]
 if len(found)!=1:raise ValueError('ambiguous or missing authority: '+pattern)
 row=found[0];path=ROOT/row['bundled_path']
 if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('public authority hash mismatch: '+str(path))
 return path
def save(fig,name):
 for ext in ('pdf','png'):
  p=FIG/(name+'.'+ext);fig.savefig(p,dpi=200,facecolor='white',metadata={'Creator':'Saved-evidence figure revision'});outputs.append({'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 plt.close(fig)
def exact():
 t=np.r_[0,np.geomspace(.001,100,600)];w=np.array([.5,.35,.15]);r=np.array([.05,1,20]);parts=np.exp(-t[:,None]*r)*w
 fig,axes=plt.subplots(2,1,figsize=(5.8,5.9),layout='constrained')
 for ax,v,title in [(axes[0],parts,'Relaxation'),(axes[1],parts*r,'Triggering (negative relaxation derivative)')]:
  for j in range(3):ax.plot(t,v[:,j],label=f'Mode {j+1}',lw=1.3)
  ax.plot(t,v.sum(1),color='black',label='Sum',lw=2);ax.set_xscale('symlog',linthresh=.01,linscale=.5)
  ax.set(xlabel='Dimensionless lag (symlog; linear below 0.01)',ylabel='Kernel value',title=title,xlim=(0,100));ax.set_xticks([0,.01,.1,1,10,100],['0','0.01','0.1','1','10','100']);ax.grid(alpha=.2)
 axes[0].set_title('Relaxation',pad=32);axes[0].legend(ncol=4,loc='lower center',bbox_to_anchor=(.5,1.01));save(fig,'finite_memory')
 g=math.log(2);states=np.array([[0,g],[g/2,g/2]])
 fig,axes=plt.subplots(2,1,figsize=(5.8,5.8),layout='constrained');x=np.arange(2)
 axes[0].bar(x-.16,states[:,0],.3,label='Region 1');axes[0].bar(x+.16,states[:,1],.3,label='Region 2');axes[0].set(xticks=x,xticklabels=['Concentrated','Evenly split'],ylabel='Local inhibition state',title='Same pooled state: G1 + G2 = log(2)');axes[0].legend(ncol=2,loc='upper right')
 local=np.exp(-states).sum(1);axes[1].bar(x,local,width=.5,color=['#246aa2','#d88932']);axes[1].axhline(1,color='#555555',ls='--');axes[1].text(.98,.94,'Dashed line: pooled rule = B',transform=axes[1].transAxes,ha='right',va='top',bbox={'facecolor':'white','edgecolor':'none'})
 for i,v in enumerate(local):axes[1].text(i,v+.04,f'{v:.4f}',ha='center')
 axes[1].set(xticks=x,xticklabels=['Concentrated','Evenly split'],ylabel='Total local intensity / B',ylim=(0,1.9),title='Local rule: exp(-G1) + exp(-G2)');save(fig,'pooling')
def geometry():
 s=json.loads((DATA/'geometry_summary.json').read_text(encoding='utf-8'));done=[c for c in s['cases'] if c['profiles']];assert len(done)==6
 fig,axes=plt.subplots(3,2,figsize=(5.8,7.8),layout='constrained')
 for ax,c in zip(axes.flat,done):
  rows=c['profiles'];d=sorted({r['d'] for r in rows});eta=sorted({r['eta'] for r in rows});best=min(r['fresh_ground_objective'] for r in rows);z=np.full((len(d),len(eta)),np.nan)
  for r in rows:z[d.index(r['d']),eta.index(r['eta'])]=r['fresh_ground_objective']-best
  im=ax.pcolormesh(eta,d,z,shading='nearest',vmin=0,vmax=20,cmap='viridis');ax.set(xlabel='Inhibition eta',ylabel='Trend d',title=c['id'].replace('_',' '),xlim=(0,3),ylim=(-2,2));ax.set_xticks([0,1,2,3])
 fig.colorbar(im,ax=list(axes.flat),location='bottom',shrink=.9,label='Profile NLL minus saved minimum (saturates at 20)');save(fig,'a1_profile_meshes')
 fig,(left,right)=plt.subplots(2,1,figsize=(5.8,7.8),layout='constrained');zeros=[]
 for i,c in enumerate(s['cases']):
  marker='x' if c['selection_class'].startswith('old_failure') else 'o';color='C'+str(i%10);label=c['id'].replace('_',' ')
  points=[p for p in c['points'] if p['realized_event_geometry']['eta_defined']]
  if points:left.scatter([p['pars'][3] for p in points],[p['realized_event_geometry']['eta_residual_fraction'] for p in points],color=color,marker=marker,label=label)
  p=next((p for p in c['points'] if p['pars'][3]==0),None)
  if p:
   rows=sorted((r for r in p['derivative_probe']['rows'] if r['coordinate']==3),key=lambda r:r['step']);errs=np.array([r['absolute_error'] for r in rows]);assert np.all(errs>=0)
   zeros.extend((label,r['step']) for r in rows if r['absolute_error']==0)
   if np.any(errs>0):right.plot([r['step'] for r in rows],np.ma.masked_equal(errs,0),marker=marker,color=color,label=label)
 left.set(xlabel='Fixed inhibition eta',ylabel='Residual fraction',title='Realized-event geometry after a,d projection');left.legend(ncol=2,loc='upper right')
 right.set(xlabel='One-sided eta=0 difference step',ylabel='Absolute derivative error',xscale='log',yscale='log',title='All saved derivative steps');right.tick_params(axis='both',which='major',labelsize=12);right.legend(ncol=2,loc='upper left');save(fig,'a1_geometry_and_derivative_steps')
 return {'planned_cases':len(s['cases']),'profile_cases':len(done),'missing_profile_cases':[{'id':c['id'],'status':c['status']} for c in s['cases'] if not c['profiles']],'zero_derivative_errors_omitted_from_log_axis':zeros}
PANELS=[('timing_OC_minus_fixedML','Timing: OC - FC','timing_logscore'),('location_OC_minus_OL','Location: OC - OL','conditional_location_logscore'),('joint_OC_minus_commonML','Joint: OC - MC','joint_logscore')]
def regional():
 datasets=[]
 for prefix,sens in [('bf4d50b9ecefc531',False),('e93db40b7871acc7',True)]:
  p=authority(prefix+'*.json');x=json.loads(p.read_text(encoding='utf-8'));data={}
  for cid,title,comp in PANELS:
   annual=sorted((r for r in (x['annual']['contrast_blocks'] if sens else x['annual_contrasts']) if r['contrast_id']==cid),key=lambda r:r['start_utc']);win=sorted((r for r in (x['contrasts'] if sens else x['fold_contrasts']) if r['contrast_id']==cid),key=lambda r:r['fold_id']);pool=next(r for r in x['pooled_contrasts'] if r['contrast_id']==cid)
   vals=[r['components'][comp] if sens else r['primary_value'] for r in annual];means=[r['nats_per_target'][comp] if sens else r['per_target_mean'] for r in win]+[pool['nats_per_target'][comp] if sens else pool['per_target_mean']];total=pool['components'][comp] if sens else pool['primary_value'];assert len(vals)==15 and math.isclose(sum(vals),total,abs_tol=1e-4)
   data[cid]={'values':vals,'means':means,'counts':[r['target_count'] for r in annual],'window_counts':[r['target_count'] for r in win],'total':total,'targets':pool['target_count']}
  datasets.append(data)
 for stem,annual,both in [('spatial_detail_annual_primary_contributions_v1',True,False),('spatial_detail_annual_primary_contributions_m4_m45_v1',True,True),('spatial_detail_window_primary_nats_per_target_m4_m45_v1',False,True)]:
  cols=2 if both else 1;fig,axes=plt.subplots(3,cols,figsize=(5.8,8.4 if annual else 7.3),squeeze=False,layout='constrained')
  for j in range(cols):
   for i,(cid,title,comp) in enumerate(PANELS):
    ax=axes[i,j];d=datasets[j][cid];vals=d['values'] if annual else d['means'];n=len(vals);colors=['#176F78' if v>=0 else '#B44B3D' for v in vals]
    if annual:
     ax.barh(range(n),vals,color=colors);ax.set_yticks(range(n),[str(y) for y in range(2011,2026)]);ax.invert_yaxis();ax.set_xlabel('Signed nats');ax.set_ylabel('UTC year')
     for k,c in enumerate(d['counts']):
      if c==0:ax.scatter(vals[k],k,marker='o',facecolor='white',edgecolor='#333333',zorder=3)
    else:
     ax.barh(range(3),vals[:3],color=colors[:3]);ax.scatter(vals[3],3,color=colors[3],marker='D');ax.set_yticks(range(4),['2011-16','2016-21','2021-26','Pooled']);ax.invert_yaxis();ax.set_xlabel('Nats / target')
    ax.axvline(0,color='#333333',lw=.7);ax.grid(axis='x',alpha=.2);ax.set_title(title+'\n'+('M >= 4.5' if j else 'M >= 4.0'),loc='left',pad=7)
  save(fig,stem)
def planned_bounds():
 p=authority('37a8da3e0df262d4*.json')
 rows=json.loads(p.read_text(encoding='utf-8'))['matrix_accounting']
 fig,axes=plt.subplots(2,1,figsize=(5.8,5.9),layout='constrained')
 for ax,role,title in zip(axes,['null_query','alternative_query'],['Null queries (planned N = 1000)','Alternative queries (planned N = 150)']):
  selected=[r for r in rows if r['role']==role];assert len(selected)==4
  for i,r in enumerate(selected):
   n=r['planned_queries'];lo=r['R']/n;hi=(r['R']+r['U'])/n
   assert r['R']+r['NR']+r['U']==n and math.isclose(lo,r['rejection_lower']) and math.isclose(hi,r['rejection_upper'])
   ax.plot([lo,hi],[i,i],color='#246aa2',lw=3);ax.scatter([lo,hi],[i,i],color='#246aa2',s=30,zorder=3)
   ax.text(.5,i-.24,f"R={r['R']}, NR={r['NR']}, U={r['U']}",ha='center',fontsize=9.5)
  ax.set(xlim=(-.04,1.04),ylim=(3.45,-.65),yticks=range(4),yticklabels=[r['cell'] for r in selected],xlabel='Rejection fraction: [R / N, (R + U) / N]',title=title)
  ax.set_xticks([0,.2,.4,.6,.8,1]);ax.grid(axis='x',alpha=.2)
 save(fig,'a1_planned_denominator_bounds')

def main():
 global FIG
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,default=ROOT/'build/review_figures',help='Fresh output directory (default: build/review_figures)')
 parser.add_argument('--install',action='store_true',help='Also install successful figures in paper/figures/. Requires visual review and manifest refresh.')
 args=parser.parse_args();FIG=args.output.resolve()
 protected=(ROOT/'paper').resolve()
 if FIG.is_relative_to(protected) or protected.is_relative_to(FIG):parser.error('output must be a fresh directory outside paper/')
 FIG.mkdir(parents=True,exist_ok=False)
 outputs.clear()
 exact();details=geometry();regional();planned_bounds()
 inputs=[DATA/'geometry_summary.json',authority('bf4d50b9ecefc531*.json'),authority('e93db40b7871acc7*.json'),authority('37a8da3e0df262d4*.json')]
 receipt={'scope':'Saved data and illustrative algebra only; no scientific fits or simulations','nominal_minimum_font_pt':8.4,'figure_width_inches':5.8,'final_pdf_font_sizes_require_check':True,'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],'outputs':outputs,'geometry':details,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (FIG/'figure_revision.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 if args.install:
  for row in outputs:shutil.copyfile(FIG/row['path'],ROOT/'paper/figures'/row['path'])
 print(json.dumps({'outputs':len(outputs),'geometry':details}))
if __name__=='__main__':main()
