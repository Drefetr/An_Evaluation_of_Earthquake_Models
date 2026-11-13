"""Publication rejects unreviewed code and source-consistent false summaries."""
from pathlib import Path
import copy,hashlib,json,tempfile,unittest,zipfile
from website import current_joint_results as current

ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

class CompletedPublication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='completed-publication-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.base=self.root/current.DIRECTORY
        protocol=dict(roster=[f'S{r}_seed{i}' for r in range(4,8) for i in range(20)],
            coordinates=['a','d','n','log_c','p','eta','log_ell','log_psi'])
        write(self.root/current.PROTOCOL,protocol)
        reports=[];sources=[]
        for name in protocol['roster']:
            regime=int(name[1]);arm_names=['null','LI','LIplus_immigrant','LIplus_inclusive']
            case=dict(case_id=name,regime=regime,passed=True,training_selections_frozen=True,
                fits={a:dict(passed=True,resolved_starts=[True]*8,null_search_gaps=[],records=[dict(success=True)]) for a in arm_names},
                training_checks={a:dict(passed=True) for a in arm_names},
                n_train=100,n_test=100,thinning=dict(accepted_immigrants=10,rejected_immigrants=2,accepted_offspring=3,rejected_offspring=1),outcomes=[])
            for model,gate in [('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')]:
                gain=float(regime-5)
                case['outcomes'].append(dict(model=model,gate=gate,new_gain=gain,new_win=gain>0,
                    score=dict(joint=-100+gain),new_null_score=dict(joint=-100),
                    near_zero=gain==0,robust_positive=gain>0,robust_negative=gain<0,
                    off_floor=True,floor_return=False,coarse_fine_gate_disagreement=False,boundaries=[None]*8))
            path=self.base/'cases'/(name+'.json');write(path,case)
            source=self.root/'saved_sources'/(name+'.json');source.parent.mkdir(exist_ok=True);source.write_bytes(path.read_bytes())
            sources.append(dict(case_id=name,sha256=sha(path.read_bytes()),source=dict(path=source.relative_to(self.root).as_posix(),sha256=sha(source.read_bytes()))));reports.append(case)
        table=self.root/'paper/source/chapters/13_s04b_joint_dispositions.tex';table.parent.mkdir(parents=True);table.write_text('fixture table')
        self.summary=dict(schema='s04b_joint_complete_20261111',completed_histories=80,completed_outcomes=400,
            scientific_completion=True,summary=current.aggregate(reports,protocol),case_sources=sources)
        self.audit=dict(passed=True,missing_cells=0,table_sha256=sha(table.read_bytes()))
        self.review=dict(passed=True,review_kind='completed_joint_publication_source_and_saved_output_review',reviewed_files_sha256={})
        for name in current.REQUIRED_REVIEWED_SOURCES:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
            self.review['reviewed_files_sha256'][name]=sha(p.read_bytes())
        self.bind()

    def bind(self):
        write(self.base/'summary.json',self.summary)
        self.audit['summary_sha256']=sha((self.base/'summary.json').read_bytes());write(self.root/current.AUDIT,self.audit)
        self.review['summary_sha256']=self.audit['summary_sha256']
        self.review['independent_audit_sha256']=sha((self.root/current.AUDIT).read_bytes());write(self.root/current.REVIEW,self.review)

    def test_valid_complete_payload(self):
        summary,pins=current.validate(self.root)
        self.assertEqual((summary['completed_histories'],summary['completed_outcomes']),(80,400))
        self.assertIn(current.PROTOCOL,pins)

    def test_missing_reviewed_source_is_rejected(self):
        self.review['reviewed_files_sha256'].pop('website/current_joint_results.py');self.bind()
        with self.assertRaisesRegex(ValueError,'omits required sources'):current.validate(self.root)

    def test_hash_consistent_false_summary_is_rejected(self):
        self.summary['summary'][0]['mean_gain']+=1;self.bind()
        with self.assertRaisesRegex(ValueError,'arithmetic differs'):current.validate(self.root)

    def test_corrupt_case_bytes_are_rejected(self):
        case=self.base/'cases'/('S4_seed0.json');case.write_bytes(case.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'hash differs'):current.validate(self.root)

    def test_rebound_transformed_gain_is_rejected(self):
        item=self.summary['case_sources'][0];p=self.base/'cases'/(item['case_id']+'.json')
        case=json.loads(p.read_bytes());case['outcomes'][0]['new_gain']=999.;case['outcomes'][0]['new_win']=True
        write(p,case);source=self.root/item['source']['path'];source.write_bytes(p.read_bytes())
        item['sha256']=item['source']['sha256']=sha(p.read_bytes());self.bind()
        with self.assertRaisesRegex(ValueError,'score identity differs'):current.validate(self.root)

    def presentation(self):
        """A new table is additive: the former scientific audit stays byte-identical."""
        table=self.root/current.TABLE;old_table=table.read_bytes()
        self.old_audit=(self.root/current.AUDIT).read_bytes()
        previous=self.root/'previous_review.json';previous.write_bytes((self.root/current.REVIEW).read_bytes())
        archive=self.root/'previous_table.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr(current.TABLE,old_table)
        cases=[json.loads((self.base/'cases'/(i['case_id']+'.json')).read_bytes()) for i in self.summary['case_sources']]
        rows=[];regimes=[]
        for r in self.summary['summary']:
            rows.append(dict(regime=r['regime'],model=r['model'],gate=r['gate'],N=20,
                mean=r['mean_gain'],median=r['median_gain'],mcse=0.,sample_sd=0.,wins=r['wins'],
                values=[float(r['regime']-5)]*20,wilson95=r['wilson95'],primary=r['primary']))
        for regime in range(4,8):
            names=sorted(c['case_id'] for c in cases if c['regime']==regime)
            regimes.append(dict(regime=regime,N=20,case_ids=names,n_train=[100]*20,n_test=[100]*20,mean_n_train=100.,mean_n_test=100.))
        supplement=self.root/'mcse.json';write(supplement,dict(source_files=[],joint_rows=rows,regimes=regimes))
        numeric=self.root/'table_audit.json'
        label=lambda r:{'LI':'LI','LIplus_immigrant':'LI+ immigrant','LIplus_inclusive':'LI+ total'}[r['model']]+' ('+r['gate']+')'+('$^{\\dagger}$' if r['primary'] else '')
        text='\\label{tab:s04b-joint-disposition-scores}\n'
        for regime in range(4,8):
            text+=r'\multicolumn{8}{@{}l}{\textbf{S'+str(regime)+r'}: mean $N_{\mathrm{train}}=100.00$, $N_{\mathrm{test}}=100.00$} \\'+'\n'
            for r in [r for r in rows if r['regime']==regime]:
                cells=['S'+str(regime),label(r),'20/20',f"{r['mean']:.4f}",'0.0000',f"{r['median']:.4f}",str(r['wins'])+'/20','['+', '.join(f'{v:.4f}' for v in r['wilson95'])+']']
                text+=' & '.join(cells)+r' \\'+'\n'
        text+='\\end{table}\n\\label{tab:s04b-joint-disposition-diagnostics}\n'
        for r in self.summary['summary']:text+=' & '.join(['S'+str(r['regime']),label(r),'0','0/0','0/0','0','0','0'])+r' \\'+'\n'
        text+='\\end{table}\n\\label{tab:s04b-joint-disposition-floor-census}\n'
        for r in self.summary['summary']:text+=' & '.join(['S'+str(r['regime']),label(r)]+[str(r[k]) for k in ('off_floor','floor_returns','near_zero','positive_near_zero','robust_positive','robust_negative')])+r' \\'+'\n'
        text+='\\end{table}\n';table.write_text(text,encoding='utf-8')
        ref=lambda p:dict(path=p.relative_to(self.root).as_posix(),sha256=sha(p.read_bytes()))
        write(numeric,dict(passed=True,authority_path=ref(supplement)['path'],authority_sha256=sha(supplement.read_bytes()),
            manuscript_sha256={current.TABLE:sha(table.read_bytes())}))
        overlay=dict(schema='completed_joint_presentation_overlay_v1',summary=ref(self.base/'summary.json'),scientific_audit=ref(self.root/current.AUDIT),
            preceding_publication_review=ref(previous),archived_table=dict(**ref(archive),member=current.TABLE,member_sha256=sha(old_table)),
            current_table=ref(table),mcse_supplement=ref(supplement),table_audit=ref(numeric))
        path=self.root/'presentation.json';write(path,overlay)
        self.review['presentation']=ref(path);write(self.root/current.REVIEW,self.review)
        return path,overlay,supplement

    def test_additive_presentation_preserves_old_audit_and_science(self):
        self.presentation();report,_=current.validate(self.root)
        self.assertEqual((self.root/current.AUDIT).read_bytes(),self.old_audit)
        self.assertEqual(report['presentation']['scientific_rows_per_table'],20)
        self.assertEqual(report['presentation']['regime_subheaders'],4)

    def test_unreviewed_changed_table_has_no_fallback(self):
        table=self.root/current.TABLE;table.write_text('changed table')
        with self.assertRaisesRegex(ValueError,'table differs'):current.validate(self.root)

    def test_rebound_incorrect_mcse_is_rejected(self):
        path,overlay,supplement=self.presentation();data=json.loads(supplement.read_bytes());data['joint_rows'][0]['mcse']=99.;write(supplement,data)
        overlay['mcse_supplement']['sha256']=sha(supplement.read_bytes());write(path,overlay)
        audit=self.root/overlay['table_audit']['path'];data=json.loads(audit.read_bytes());data['authority_sha256']=sha(supplement.read_bytes());write(audit,data)
        overlay['table_audit']['sha256']=sha(audit.read_bytes());write(path,overlay)
        self.review['presentation']['sha256']=sha(path.read_bytes());write(self.root/current.REVIEW,self.review)
        with self.assertRaisesRegex(ValueError,'presentation/mcse'):current.validate(self.root)

    def test_rebound_changed_table_cell_is_rejected(self):
        path,overlay,_=self.presentation();table=self.root/current.TABLE
        table.write_text(table.read_text().replace(' & -1.0000 & 0.0000 &',' & 9.0000 & 0.0000 &',1))
        overlay['current_table']['sha256']=sha(table.read_bytes());write(path,overlay)
        audit=self.root/overlay['table_audit']['path'];data=json.loads(audit.read_bytes());data['manuscript_sha256'][current.TABLE]=sha(table.read_bytes());write(audit,data)
        overlay['table_audit']['sha256']=sha(audit.read_bytes());write(path,overlay)
        self.review['presentation']['sha256']=sha(path.read_bytes());write(self.root/current.REVIEW,self.review)
        with self.assertRaisesRegex(ValueError,'score-table cells differ'):current.validate(self.root)

    def test_rebound_primary_and_count_metadata_are_rejected(self):
        path,overlay,supplement=self.presentation();baseline=json.loads(supplement.read_bytes())
        for field,value in [('primary',True),('N',21)]:
            with self.subTest(field=field):
                data=copy.deepcopy(baseline);data['joint_rows'][0][field]=value;write(supplement,data)
                overlay['mcse_supplement']['sha256']=sha(supplement.read_bytes())
                audit=self.root/overlay['table_audit']['path'];check=json.loads(audit.read_bytes());check['authority_sha256']=sha(supplement.read_bytes());write(audit,check)
                overlay['table_audit']['sha256']=sha(audit.read_bytes());write(path,overlay)
                self.review['presentation']['sha256']=sha(path.read_bytes());write(self.root/current.REVIEW,self.review)
                with self.assertRaisesRegex(ValueError,'presentation/'+field):current.validate(self.root)

if __name__=='__main__':unittest.main()
