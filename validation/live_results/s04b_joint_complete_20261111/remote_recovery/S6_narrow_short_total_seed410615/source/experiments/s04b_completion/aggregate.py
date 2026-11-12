"""Aggregate all 80 source-bound histories and generate complete joint tables."""
import hashlib,json,math,zipfile
from pathlib import Path
from experiments.s04b_completion.recover import REPO,OUT,read
from experiments.s04b_joint_nuisance.run import aggregate
from experiments.s04b_joint_nuisance.checkpoint import write

def main():
    old=read(REPO/'validation/live_results/joint_nuisance_dispositions_20261107/report.json')
    reports=[];pins=[];archives={};dest=OUT/'cases';dest.mkdir(exist_ok=True)
    for c in old['case_dispositions']:
        case_id=c['case_id']
        if c['scientific_passed']:
            e=c['evidence']['case'];path=REPO/e['path']
            if e['path'] not in archives:
                assert hashlib.file_digest(path.open('rb'),'sha256').hexdigest()==e['sha256']
                archives[e['path']]=zipfile.ZipFile(path)
            data=archives[e['path']].read(e['member']);assert hashlib.sha256(data).hexdigest()==e['member_sha256']
            r=json.loads(data);source=e
        else:
            path=OUT/'recovery'/case_id/'cases'/(case_id+'.json')
            r=read(path);source=dict(path=path.relative_to(REPO).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        assert r['passed'] and len(r['outcomes'])==5 and all(v['passed'] for v in r['fits'].values())
        assert all(v['passed'] for v in r['training_checks'].values())
        write(dest/(case_id+'.json'),r);reports.append(r);pins.append(dict(case_id=case_id,source=source,sha256=hashlib.sha256((dest/(case_id+'.json')).read_bytes()).hexdigest()))
    for z in archives.values():z.close()
    protocol=read(REPO/'experiments/s04b_joint_nuisance/protocol.json');summary=aggregate(reports,protocol)
    # Preserve the explicitly requested seven-start selection, excluding capped5.
    r=next(r for r in reports if r['seed']==410518);arm=r['fits']['LIplus_immigrant']
    seven=min([v for v in arm['candidates'] if v['start_index']!=5],key=lambda v:(v['score']['nll'],v['kind']=='optimizer',v['start_index']))
    payload=dict(schema='s04b_joint_complete_20261111',completed_histories=80,completed_outcomes=400,scientific_completion=True,summary=summary,
        case_sources=pins,seven_start_s5_immigrant_selection=seven,s5_all_start_selection=arm['selected'])
    write(OUT/'summary.json',payload)
    path=REPO/'paper/source/chapters/13_s04b_joint_dispositions.tex'
    label=lambda v: {'LI':'LI','LIplus_immigrant':'LI+ immigrant','LIplus_inclusive':'LI+ total'}[v['model']]+' ('+v['gate']+')'+(r'$^{\dagger}$' if v['primary'] else '')
    def row(v,cells):return f"S{v['regime']} & {label(v)} & "+' & '.join(map(str,cells))+r' \\'
    def table(caption,label_,fmt,head,rows):
        return '\n'.join([r'\begin{table}[htbp]',r'\centering\small',r'\setlength{\tabcolsep}{2.5pt}',r'\caption{'+caption+'}',r'\label{'+label_+'}',r'\begin{tabular}{@{}'+fmt+r'@{}}',r'\toprule',head+r' \\',r'\midrule',*rows,r'\bottomrule',r'\end{tabular}',r'\end{table}'])
    text='''All 80 histories have completed training selections and held-out scores, giving 400 procedure outcomes.\\footnote{The two recovery histories are S5 seed 410518 and S6 seed 410615; all other histories retain their saved completed fits.} Both arms jointly fit the temporal backbone $(a,d,n,c,p)$; the common spatial and mark laws remain fixed. Eight starts are resolved in every arm. The exact fitted null is an eligible state in each inhibited search. Table rows report all twenty histories in each regime; positive near-zero gains remain strict wins.\n\n'''
    text+=table('Held-out joint-score gains against the jointly training-refitted uninhibited comparator, in nats. Wins are strictly positive gains; Wilson intervals quantify the win probability, not uncertainty in the mean gain. Marked rows are the matched broad/long contrasts.', 'tab:s04b-joint-disposition-scores','llrrrrr','Regime & Procedure & Computed & Mean & Median & Wins & Wilson interval',[
        row(v,['20/20',f"{v['mean_gain']:.4f}",f"{v['median_gain']:.4f}",f"{v['wins']}/20",f"[{v['wilson95'][0]:.4f}, {v['wilson95'][1]:.4f}]"]) for v in summary])+'\n\n'
    text+=table('Search and numerical census for all twenty histories per regime. Boundary counts are lower/upper. Failed attempts count unsuccessful attempts for the shared null and named alternative; raw/BIC rows reuse searches and must not be added. Near-zero is numerical, not statistical significance.', 'tab:s04b-joint-disposition-diagnostics','llrrrrrr',r'Regime & Procedure & Unavailable & $a$ bounds & $\eta$ bounds & Failed attempts & Null gaps & Gate differences',[
        row(v,[0,f"{v['coordinate_boundaries']['a']['lower']}/{v['coordinate_boundaries']['a']['upper']}",f"{v['eta_lower']}/{v['eta_upper']}",v['optimizer_failed_attempts'],v['null_search_gap_cases'],v['coarse_fine_gate_disagreements']]) for v in summary])+'\n\n'
    text+=table('Floor and near-zero census for all twenty histories per regime. An alternative with zero inhibition and a better nuisance solution is a procedure and optimizer contrast, not evidence of inhibition.', 'tab:s04b-joint-disposition-floor-census','llrrrrrr','Regime & Procedure & Off-floor & Floor returns & Near zero & Positive near zero & Robust positive & Robust negative',[
        row(v,[v['off_floor'],v['floor_returns'],v['near_zero'],v['positive_near_zero'],v['robust_positive'],v['robust_negative']]) for v in summary])+'\n'
    path.write_text(text,encoding='utf-8')
    print(json.dumps(dict(completed_histories=80,completed_outcomes=400,summary=summary),indent=2))

if __name__=='__main__':main()
