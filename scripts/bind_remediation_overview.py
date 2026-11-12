"""Bind overview displays to the completed joint-control authority; no fitting."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
SOURCE='validation/live_results/s04b_joint_complete_20261111/summary.json'
OUT='validation/live_results/remediation_overview_claims_20261111.json'

def main():
    raw=(ROOT/SOURCE).read_bytes();data=json.loads(raw)
    assert data['completed_histories']==80 and data['completed_outcomes']==400
    digest=hashlib.sha256(raw).hexdigest();claims=[]
    locations=['chapters/01_introduction.tex','chapters/13_continuous_local_inhibition.tex','chapters/14_discussion_conclusion.tex']
    def add(name,pointer,value,display,files):
        claims.append(dict(id='remediation-overview-'+name,bundled_source=SOURCE,
            source_path=SOURCE,source_sha256=digest,json_pointer=pointer,value=value,
            display=str(display),transformation='decimal rounding to displayed precision',
            json_value_kind='numeric_scalar',ledger_role='manuscript_binding',
            final_display_locations=files,component='Completed joint-control overview',
            qualification='Training-only selections and completed held-out scores; no fixed-null or partial-history substitution.'))
    for regime,model in [(5,'LIplus_immigrant'),(7,'LIplus_inclusive')]:
        index=next(i for i,r in enumerate(data['summary']) if r['regime']==regime and r['model']==model and r['gate']=='raw')
        row=data['summary'][index];base=f'/summary/{index}/';tag='s'+str(regime)
        add(tag+'-mean4',base+'mean_gain',row['mean_gain'],f"{row['mean_gain']:.4f}",locations)
        add(tag+'-mean2',base+'mean_gain',row['mean_gain'],f"{row['mean_gain']:.2f}",['abstract.tex'])
        for key in ['wins','N']:add(tag+'-'+key,base+key,row[key],row[key],['abstract.tex',*locations])
        if regime==5:add(tag+'-median',base+'median_gain',row['median_gain'],f"{row['median_gain']:.4f}",['chapters/14_discussion_conclusion.tex'])
        else:
            for j,value in enumerate(row['wilson95']):
                add(tag+'-wilson4-'+str(j),base+'wilson95/'+str(j),value,f'{value:.4f}',['chapters/14_discussion_conclusion.tex'])
                add(tag+'-wilson2-'+str(j),base+'wilson95/'+str(j),value,f'{value:.2f}',['abstract.tex'])
    for key in ['completed_histories','completed_outcomes']:
        add(key,'/'+key,data[key],data[key],['chapters/13_continuous_local_inhibition.tex'])
    (ROOT/OUT).write_bytes((json.dumps({'claims':claims},indent=2)+'\n').encode('utf8'))
    print(json.dumps({'claims':len(claims),'output':OUT}))

if __name__=='__main__':main()
