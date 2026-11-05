"""Verify/extract recovered inputs; never evaluate, fit or simulate a model."""
import argparse,hashlib,io,json,math,re,zipfile
from pathlib import Path,PurePosixPath
import numpy as np
HERE=Path(__file__).resolve().parent
ORIGINS=tuple('california_fold_'+str(i) for i in range(3))
def need(test,message):
 if not test:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def encode(x):return (json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def numeric(x,path=''):
 if isinstance(x,bool) or x is None:return []
 if isinstance(x,(int,float)):return [(path,x)]
 if isinstance(x,list):return [v for i,a in enumerate(x) for v in numeric(a,path+'/'+str(i))]
 if isinstance(x,dict):return [v for k in sorted(x) for v in numeric(x[k],path+'/'+k.replace('~','~0').replace('/','~1'))]
 return []
def safe_name(name):
 p=PurePosixPath(name)
 need(name==p.as_posix() and not p.is_absolute() and all(x not in ('..','.') for x in p.parts) and ':' not in name and '\\' not in name,'Unsafe archive member: '+name)
 return p
def seed_records(model,origin,index):
 master='Thread02|conditional_calibration_20261025T085151Z|'+('OC|v1' if model=='OC' else 'EP|scientific-remediation-v1')
 result=[]
 for purpose in ('immigrant','prehistory-offspring','descendants','marks'):
  digest=hashlib.sha256(f'{master}|production|{origin}|{index}|{purpose}'.encode()).digest()
  result.append(dict(purpose=purpose,sha256=digest.hex(),seed_words_uint32_be=[int.from_bytes(digest[i:i+4],'big') for i in range(0,16,4)]))
 return result
def npz(data):
 with np.load(io.BytesIO(data),allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
def validate_state(state,model):
 need(set(state)=={'params','rectangles','pi','training_xy','prehistory','subblocks'},'Unexpected state arrays / observed-future leakage')
 need(all(np.isfinite(v).all() for v in state.values()),'Nonfinite state')
 need(state['params'].shape==((11,) if model=='OC' else (12,)),'Parameter schema')
 need(state['rectangles'].shape==(9,4) and state['pi'].shape==(9,) and np.all(state['pi']>0) and abs(state['pi'].sum()-1)<1e-12,'Region/cell state schema')
 need(state['training_xy'].ndim==2 and state['training_xy'].shape[1]==2 and state['prehistory'].ndim==2 and state['prehistory'].shape[1]==4,'Training/prehistory schema')
 need(np.all(state['prehistory'][:,0]<state['params'][9]),'Future event in prehistory')
def validate_future(row,state,events):
 need(events.ndim==2 and events.shape[1]==4 and np.isfinite(events).all(),'Event schema/nonfinite')
 need(np.all(np.diff(events[:,0])>=0) and np.all(events[:,1]>=0),'Event order/marks')
 start,end=state['params'][9:11]
 need(np.all((events[:,0]>=start)&(events[:,0]<end)),'Events outside frozen forecast interval')
 need(int(row['scalars']['stats']['count'])==len(events),'Expected count does not equal raw path count')
 receipt=row['receipt'];need(receipt['status']=='complete' and receipt['case_id']==row['origin'],'Receipt identity/status')
 if row['index']>=0:
  need(receipt['mode']=='simulate' and receipt['phase']=='production' and receipt['index']==row['index'],'Simulation role/index')
  need(receipt['seed_records']==seed_records(row['model'],row['origin'],row['index']),'Seed identity')
 else:need(receipt['mode']=='observed','Observed role')
 count=sum(1 if isinstance(v,(int,float)) else len(v) for v in row['scalars']['stats'].values())
 need(count==84,'Expected diagnostic vector is not 84 coordinates')
def verify(root=HERE):
 root=Path(root);manifest=json.loads((root/'manifest.json').read_text());payload=root/manifest['payload']
 need(sha(payload.read_bytes())==manifest['payload_sha256'],'Payload hash mismatch')
 checked=0
 with zipfile.ZipFile(payload) as z:
  names=z.namelist();need(len(names)==len(set(names)),'Duplicate archive members');expected={x['path']:x for x in manifest['members']}
  need(set(names)==set(expected),'Archive member inventory mismatch')
  for name in names:
   safe_name(name);b=z.read(name);v=expected[name];need(len(b)==v['bytes'] and sha(b)==v['sha256'],'Member hash/size mismatch: '+name)
   if name.endswith(('.json','.jsonl','.py','.md')):need(not re.search(rb'[Cc]:[/\\]+Users[/\\]+',b),'Private account path remains: '+name)
  rows=[json.loads(x) for x in z.read('S05/records.jsonl').splitlines()];identities={(r['model'],r['origin'],r['index']) for r in rows}
  roster={(m,o,i) for m in ('OC','EP') for o in ORIGINS for i in (-1,*range(999))}
  need(len(rows)==6000 and identities==roster,'S05 exact 6000-identity roster')
  states={}
  for r in rows:
   if r['state'] not in states:
    state=npz(z.read(r['state']));validate_state(state,r['model']);states[r['state']]=state
   validate_future(r,states[r['state']],npz(z.read(r['path']))['events'])
  crosswalk=[json.loads(x) for x in z.read('source_crosswalk.jsonl').splitlines()]
  for entry in crosswalk:
   if 'numeric_leaf_sha256' not in entry:continue
   if entry['member']=='S05/records.jsonl':value=rows[entry['record_index']][entry['output_pointer'].lstrip('/')]
   else:value=json.loads(z.read(entry['member']))
   need(sha(encode(numeric(value)))==entry['numeric_leaf_sha256'],'Numerical leaf crosswalk mismatch')
   need(sha(encode([v for _,v in numeric(value)]))==entry['source_numeric_values_sha256']==entry['output_numeric_values_sha256'],'Source/output numerical value mismatch')
   checked+=1
  s03=[json.loads(z.read(f'S03/{o}/fits.json')) for o in ORIGINS]
  need(all({v['arm'] for v in d['results']}=={1,2,3,4} and all(v['fit']['status']=='complete' and len(v['fit']['selected']['pars'])==3 for v in d['results']) for d in s03),'S03 selected roster')
  fitnames=[n for n in names if n.startswith('S06/s06_results/CA_') and '/fits/' in n and n.endswith('.json')]
  need(len(fitnames)==55,'S06 fit roster')
  for n in fitnames:
   d=json.loads(z.read(n));need(d['status']=='complete' and d['selected'] and np.isfinite(d['selected']['x']).all(),'S06 incomplete/nonfinite fit')
 for s in manifest['scoring_sources']:need(sha((root/s['path']).read_bytes())==s['sha256'],'Scoring source hash mismatch')
 return dict(passed=True,scope='Input verification only; no scientific likelihood/replay',S05_simulated_paths=5994,S05_observed_paths=6,S05_states=6,S03_selected_arms=12,S06_fit_records=55,numerical_crosswalk_records=checked,members=len(names),payload_sha256=manifest['payload_sha256'])
def extract(output,root=HERE):
 result=verify(root);output=Path(output).resolve();need(not output.exists(),'Output must be a new directory');output.mkdir(parents=True)
 with zipfile.ZipFile(Path(root)/'payload.zip') as z:
  for name in z.namelist():
   target=output/Path(*safe_name(name).parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 (output/'input_verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
def full84_inputs(root=HERE):
 """Load exact original inputs for the fifteen completed checks; no scoring."""
 root=Path(root);manifest=json.loads((root/'original_completion_20261101.manifest.json').read_text())
 archive=root/Path(*safe_name(manifest['archive']['path']).parts)
 need(sha(archive.read_bytes())==manifest['archive']['sha256'],'Original-completion archive hash mismatch')
 with zipfile.ZipFile(archive) as z:
  names=z.namelist();expected={m['path']:m for m in manifest['members']}
  need(len(names)==len(set(names))==len(expected) and set(names)==set(expected),'Original-completion member roster')
  for name in names:
   safe_name(name);data=z.read(name);record=expected[name]
   need(len(data)==record['bytes'] and sha(data)==record['sha256'],'Original-completion member mismatch: '+name)
  rows=json.loads(z.read('full84_inputs/index.json'))['rows'];roster={('EP',origin,i) for origin in ORIGINS for i in (0,249,499,749,998)}
  need(len(rows)==15 and {(r['model'],r['origin'],r['index']) for r in rows}==roster,'Original full84 input roster')
  result={}
  for row in rows:
   need(set(row['artifact_members'])=={'receipt.json','scalars.json','private_path.npz','private_detail.npz'},'Full84 input artifact coverage')
   result[(row['model'],row['origin'],row['index'])]=dict(state=z.read(row['state_member']),artifacts={name:z.read(member) for name,member in row['artifact_members'].items()},source=dict(archive_sha256=manifest['archive']['sha256'],detail_member=row['artifact_members']['private_detail.npz'],historical_receipt_sha256=row['historical_receipt_sha256']))
 return result

def checked_full84_detail(row,state_bytes,path_bytes,restored):
 """Cross-check recovered detail against exact original state/path/receipt."""
 a=restored['artifacts'];receipt=json.loads(a['receipt.json']);scalars=json.loads(a['scalars.json'])
 need(restored['state']==state_bytes and a['private_path.npz']==path_bytes,'Full84 state/path does not match base package')
 need(receipt==row['receipt'] and scalars==row['scalars'],'Full84 original receipt/scalars differ from base package')
 need(sha(a['receipt.json'])==restored['source']['historical_receipt_sha256'],'Full84 historical receipt hash')
 need(sha(a['private_detail.npz'])==receipt['detail_sha256'],'Full84 original detail hash')
 detail=npz(a['private_detail.npz']);need(set(detail)=={'detail'},'Full84 detail array schema')
 need(detail['detail'].shape==(int(row['scalars']['stats']['count']),11) and np.isfinite(detail['detail']).all(),'Full84 detail count/eleven-column/finite schema')
 return a['private_detail.npz']

def materialized_receipt(original,state_sha256,path_sha256,scalars_sha256,job_sha256=None,detail_sha256=None):
 result=dict(original);fields=('input_state_sha256','path_sha256','scalars_sha256','detail_sha256','job_sha256')
 result['materialization_provenance']=dict(scope='Current extracted inputs; original receipt retained in S05/records.jsonl',historical_hash_fields={k:result.pop(k) for k in fields if k in result})
 result.update(input_state_sha256=state_sha256,path_sha256=path_sha256,scalars_sha256=scalars_sha256)
 if job_sha256 is not None:result['job_sha256']=job_sha256
 if detail_sha256 is not None:result['detail_sha256']=detail_sha256
 return result
def materialize(output,root=HERE,full84=False,completion_root=None):
 details=full84_inputs(completion_root or root) if full84 else {}
 output=Path(output).resolve();result=extract(output,root);rows=[json.loads(x) for x in (output/'S05/records.jsonl').read_text().splitlines()];terminal=json.loads((output/'S05/contracts/saved_manifest.json').read_text());roster=[]
 for row in rows:
  folder=output/'S05/replay'/row['model']/row['origin']/str(row['index']);folder.mkdir(parents=True)
  paths={};state=output/row['state'];state_sha256=sha(state.read_bytes())
  p=folder/'scalars.json';p.write_bytes(encode(row['scalars']));scalars_sha256=sha(p.read_bytes());paths[str(p)]=scalars_sha256
  p=folder/'private_path.npz';p.write_bytes((output/row['path']).read_bytes());path_sha256=sha(p.read_bytes());paths[str(p)]=path_sha256
  job_sha256=None
  if 'job' in row:
   p=folder/'historical_job.json';p.write_bytes(encode(row['job']));job_sha256=sha(p.read_bytes());paths[str(p)]=job_sha256
  detail_sha256=None;identity=(row['model'],row['origin'],row['index'])
  if identity in details:
   data=checked_full84_detail(row,state.read_bytes(),(output/row['path']).read_bytes(),details[identity]);p=folder/'private_detail.npz';p.write_bytes(data);detail_sha256=sha(data);paths[str(p)]=detail_sha256
  receipt=materialized_receipt(row['receipt'],state_sha256,path_sha256,scalars_sha256,job_sha256,detail_sha256)
  if identity in details:receipt['materialization_provenance']['full84_detail_source']=details[identity]['source']
  p=folder/'receipt.json';p.write_bytes(encode(receipt));paths[str(p)]=sha(p.read_bytes())
  roster.append(dict(model=row['model'],origin=row['origin'],index=row['index'],state=str(state),state_sha256=sha(state.read_bytes()),scalars=str(folder/'scalars.json'),artifacts=paths))
 adapted=dict(passed=True,simulated_paths=5994,observed_vectors=6,vectors=6000,schema84=terminal['schema84'],rows=roster,full84_detail_paths=len(details),scope='Portable input materialization only; passed refers to input checks, not a new likelihood replay. Original detail files installed for the fifteen predeclared EP full-vector checks.' if full84 else 'Portable input materialization only; passed refers to input checks, not likelihood replay; per-event detail files intentionally excluded')
 (output/'S05/replay_manifest.json').write_text(json.dumps(adapted,indent=2)+'\n');return dict(**result,replay_manifest=str(output/'S05/replay_manifest.json'),full84_detail_paths=len(details))
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True);s.add_parser('verify')
 for mode in ('extract','materialize-s05'):
  command=s.add_parser(mode);command.add_argument('--output',type=Path,required=True)
  if mode=='materialize-s05':command.add_argument('--full84',action='store_true',help='Install the exact fifteen original EP event-detail inputs from the recovered completion archive')
 a=p.parse_args();result=verify() if a.command=='verify' else extract(a.output) if a.command=='extract' else materialize(a.output,full84=a.full84);print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
