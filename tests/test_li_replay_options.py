"""Constructor/custody fixtures only; no original engine, DLL or model calls."""
import ast,copy,json,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from reproduction.score_replay import li_replay
from reproduction.score_replay.core import digest

ROOT=Path(__file__).resolve().parents[1]/'reproduction/score_replay/original_li'
SCIENTIFIC=dict(order=8,fine_order=16,space_scheme='adaptive',spatial_tol=1e-8,near_width=20.,tile_width=40.)
RESOURCE=dict(tile_nodes=2048,interval_chunk=16,parent_chunk=128)


class ConstructorOptions(unittest.TestCase):
    def test_cpu_scientific_options_are_preserved_exactly(self):
        original=copy.deepcopy(SCIENTIFIC);value=li_replay.objective_options(original)
        self.assertEqual(value['cpu_constructor'],original);self.assertEqual(value['original'],original)
        self.assertEqual(value['original_gpu_resource_controls'],{});self.assertEqual(value['excluded_from_cpu_constructor'],[])
        value['cpu_constructor']['order']=99;self.assertEqual(original,SCIENTIFIC)

    def test_only_three_known_gpu_resource_fields_are_excluded_and_retained(self):
        original={**SCIENTIFIC,**RESOURCE};unchanged=copy.deepcopy(original)
        value=li_replay.objective_options(original)
        self.assertEqual(value['original'],unchanged);self.assertEqual(value['cpu_constructor'],SCIENTIFIC)
        self.assertEqual(value['original_gpu_resource_controls'],RESOURCE)
        self.assertEqual(value['excluded_from_cpu_constructor'],sorted(RESOURCE));self.assertEqual(original,unchanged)

    def test_unknown_options_and_bad_resource_domains_are_rejected(self):
        for extra in ({'tile_node':2048},{'dll_path':'other.dll'},{'tolerance':1e-2},{'invented':None}):
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'Unexpected'):li_replay.objective_options({**SCIENTIFIC,**extra})
        for key,maximum in [('tile_nodes',4096),('interval_chunk',64),('parent_chunk',4096)]:
            for value in (0,-1,True,1.5,'128',maximum+1):
                with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'resource'):li_replay.objective_options({**SCIENTIFIC,key:value})
        for bad in (None,[],[('order',8)]):
            with self.assertRaises(ValueError):li_replay.objective_options(bad)

    def test_pinned_cpu_signature_and_all38_original_state_mappings(self):
        registry=json.loads((ROOT/'registry.json').read_bytes());affected=[]
        with zipfile.ZipFile(ROOT/'inputs/cached_01.zip')as z:
            spec=registry['source_resources']['local_inhibition_experiment/engine.py'];raw=z.read(spec['member'])
            self.assertEqual(digest(raw),spec['sha256'])
            tree=ast.parse(raw);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='Objective')
            init=next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='__init__')
            self.assertEqual({n.arg for n in init.args.kwonlyargs},set(SCIENTIFIC)|{'dll_path'})
            self.assertIsNone(init.args.kwarg)
            for row in registry['rows']:
                state_raw=z.read(row['state']['member']);self.assertEqual(digest(state_raw),row['state']['sha256'])
                state=json.loads(state_raw);original=state['objective_kwargs'];mapping=li_replay.objective_options(original)
                self.assertEqual(mapping['cpu_constructor'],{k:v for k,v in original.items()if k in SCIENTIFIC})
                self.assertEqual(mapping['original'],original)
                if mapping['original_gpu_resource_controls']:
                    affected.append(row['id']);self.assertEqual(mapping['original_gpu_resource_controls'],RESOURCE)
        self.assertEqual(len(registry['rows']),38);self.assertEqual(len(affected),4)
        self.assertEqual(set(affected),{'original_li/LI_CA_M4_F'+str(fold)+'/LI/'+phase for fold in (1,2)for phase in ('train','test')})

    def test_constructor_receives_exact_scientific_values_and_records_original_options(self):
        for eta in (0.,.4):
            with self.subTest(eta=eta),tempfile.TemporaryDirectory()as temp:
                root=Path(temp);state=dict(model='LI',parameters=[-2.,0.,.3,-3.,1.2,eta,2.,1.],objective_kwargs={**SCIENTIFIC,**RESOURCE})
                original=copy.deepcopy(state);calls=[]
                class InventedObjective:
                    def __init__(self,path,*,order,fine_order,dll_path,space_scheme,tile_width,spatial_tol,near_width):
                        calls.append(dict(order=order,fine_order=fine_order,space_scheme=space_scheme,tile_width=tile_width,spatial_tol=spatial_tol,near_width=near_width))
                        self.metadata={'ne':1};self.a={'invented':np.array([1.])}
                    def __enter__(self):return self
                    def __exit__(self,*_):return False
                    def evaluate(self,model,parameters,**kwargs):
                        calls.append((model,list(parameters),kwargs))
                        return dict(P=-2.,E=1.,M=-.3,timing=-3.,event_logs=np.array([-2.]))
                class InventedInputs:
                    def json(self,spec):
                        if spec!='state':raise AssertionError('Expected reference must not be read')
                        return state
                    def materialize(self,*_):return root/'opaque-unused-raw'
                row=dict(state='state',raw={'sha256':'raw-pin'},n_events_expected=1)
                # State is ordinarily a resource mapping; this fake supplies its pin as well.
                row['state']={'sha256':'state-pin'}
                inputs=InventedInputs();inputs.json=lambda spec:state if spec==row['state']else (_ for _ in ()).throw(AssertionError('Unexpected resource'))
                actual,arrays=li_replay.evaluate(inputs,row,SimpleNamespace(Objective=InventedObjective),root/'opaque-unused-dll',root)
                self.assertEqual(calls[0],SCIENTIFIC);self.assertEqual(actual['parameters'],original['parameters'])
                self.assertEqual(actual['objective_options']['original'],original['objective_kwargs'])
                self.assertEqual(actual['objective_options']['original_gpu_resource_controls'],RESOURCE)
                self.assertEqual(state,original);self.assertEqual(len(calls),3)
                self.assertEqual(actual['evaluated_model'],'OC'if eta==0. else'LI')
                self.assertEqual(calls[1][1],original['parameters'][:5]if eta==0. else original['parameters'])
                self.assertEqual(set(arrays),{'coarse__event_logs','fine__event_logs'})

    def test_repair_keeps_three_pilot_identities_and_only_failed_retry(self):
        proposal=json.loads((ROOT/'pilot_proposal.json').read_bytes());repair=proposal['constructor_repair']
        retained=[r['id']for r in repair['retained_passed_rows']];retry=repair['retry_row_ids']
        self.assertEqual(len(retained),2);self.assertEqual(len(retry),1);self.assertFalse(set(retained)&set(retry))
        self.assertEqual(set(retained+retry),set(proposal['row_ids']))
        registry=json.loads((ROOT/'registry.json').read_bytes())
        self.assertEqual(len([r for r in registry['rows']if r['id']not in proposal['row_ids']]),35)
        self.assertEqual(proposal['source_sha256'],li_replay.source_pins())


if __name__=='__main__':unittest.main()
