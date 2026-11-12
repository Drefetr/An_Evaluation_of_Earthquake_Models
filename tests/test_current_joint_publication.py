"""Publication rejects unreviewed code and source-consistent false summaries."""
from pathlib import Path
import copy,hashlib,json,tempfile,unittest
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

if __name__=='__main__':unittest.main()
