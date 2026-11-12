"""Protocol controls only: no fitting, catalogues, integration or native library."""
from pathlib import Path
import hashlib,json,tempfile,unittest
import numpy as np
from experiments.etas_inhibition_benchmark.acceptance_protocol import construct_starts,EvaluationTrace

class AcceptanceStartProtocol(unittest.TestCase):
    def test_fresh_positive_starts_survive_zero_terminal_warm_states(self):
        null=np.array([-3.,.1,.7,-5.,1.2,np.log(2),.6,2.,0.,np.log(20),np.log(5),1.7]);warm=[null.copy(),null.copy()]
        specs=construct_starts(null,warm);positive=[s for s in specs if s['role']=='prescribed_positive']
        self.assertEqual(len(specs),6);self.assertEqual(len(positive),3)
        for spec,(eta,ell,psi) in zip(positive,[(.05,10,2),(.2,20,5),(.5,50,30)]):
            x=np.asarray(spec['initial_parameters']);np.testing.assert_array_equal(x[:8],null[:8]);self.assertEqual(x[8],eta);self.assertAlmostEqual(np.exp(x[9]),ell);self.assertAlmostEqual(np.exp(x[10]),psi)
        specs[0]['initial_parameters'][0]=0
        self.assertEqual(null[0],-3.);self.assertEqual(warm[0][8],0.)

    def test_trace_counts_only_completed_interior_optimizer_evaluations(self):
        calls=[]
        def target(x,inhibit=False,details=False):
            calls.append(x.copy());value=float(np.dot(x,x));return {'nll':value} if details else (value,2*x)
        start=np.zeros(12);start[8]=.2;spec=dict(initial_parameters=start.tolist())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl';trace=EvaluationTrace(target,spec,17,path)
            actual=trace(start,True);np.testing.assert_array_equal(actual[1],2*start)
            floor=start.copy();floor[8]=0;trace(floor,True);trace(start,True,True)
            summary=trace.close();rows=[json.loads(v) for v in path.read_text().splitlines()]
            self.assertEqual(len(calls),3);self.assertEqual(summary['completed_objective_evaluations'],3);self.assertEqual(summary['interior_objective_evaluations'],1)
            self.assertTrue(summary['first_evaluation_matches_initial']);self.assertEqual(summary['trace_sha256'],hashlib.sha256(path.read_bytes()).hexdigest());self.assertTrue(all(r['training_power']==17 for r in rows));self.assertEqual(rows[0]['parameters'][8],.2)

if __name__=='__main__':unittest.main()
