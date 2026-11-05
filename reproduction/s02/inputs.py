"""Verify or extract the original completed S02 inputs, without model execution."""
import argparse,csv,hashlib,io,json,math,zipfile
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent
def need(value,message):
 if not value:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def safe_name(name):
 p=PurePosixPath(name)
 need(name==p.as_posix() and not p.is_absolute() and p.parts and all(v not in ('.','..') for v in p.parts) and ':' not in name and '\\' not in name,'Unsafe archive path')
 return p
def validate_fit(row,fit):
 need(all(fit[k]==row[k] for k in ('id','forest','h')) and fit['history_sha256']==row['history_sha256'],'Fit identity mismatch')
 methods=fit['methods'];need(fit['status']=='complete' and len(methods)==2 and {m['procedure'] for m in methods}=={'M1','M2'},'Method roster/status')
 for method in methods:
  need(method['status']=='complete','Incomplete method')
  for phase in ('null','alternative'):
   state=method[phase];need(len(state['pars'])==4 and all(math.isfinite(v) for v in state['pars']) and math.isfinite(state['nll']),'Invalid selected state')
 return sum(len(m['attempts']) for m in methods)
def verify(root=HERE):
 root=Path(root);manifest=json.loads((root/'manifest.json').read_text());archive=root/Path(*safe_name(manifest['archive']['path']).parts)
 need(sha(archive.read_bytes())==manifest['archive']['sha256'],'Archive hash mismatch')
 with zipfile.ZipFile(archive) as z:
  names=z.namelist();expected={m['path']:m for m in manifest['members']}
  need(len(names)==len(set(names))==len(expected) and set(names)==set(expected),'Archive inventory mismatch')
  for name in names:
   safe_name(name);raw=z.read(name);m=expected[name];need(len(raw)==m['bytes'] and sha(raw)==m['sha256'],'Member hash mismatch: '+name)
  rows=json.loads(z.read('index.json'))['cases'];need(len(rows)==300 and len({r['id'] for r in rows})==300 and {(r['forest'],r['h']) for r in rows}=={(i,h) for i in range(100) for h in (0.,.5,.9)},'S02 exact roster')
  attempts=0;events=0;skeletons={}
  for row in rows:
   need(row['time_seed']==2033000000+100*row['forest'] and row['mark_seed']==row['time_seed']+10000000,'Generation seed identity')
   raw=z.read(row['history']);need(sha(raw)==row['history_sha256'],'History pin mismatch')
   records=list(csv.DictReader(io.StringIO(raw.decode())));need(len(records)==row['generation']['events'] and row['generation']['status']=='ok','History count/status')
   need(all(math.isfinite(float(v)) for r in records for v in r.values()),'Nonfinite history')
   skeleton=[tuple(r[k] for k in ('time_hi','time_lo','event_gap','event_id','parent_id','generation')) for r in records]
   skeletons.setdefault(row['forest'],skeleton);need(skeletons[row['forest']]==skeleton,'Coupled skeleton mismatch')
   attempts+=validate_fit(row,json.loads(z.read(row['fit'])));events+=len(records)
   need(len(row['attempts'])==2 and all(name in expected for name in row['attempts']),'Missing attempt traces')
   need(row['generation_config'] in expected,'Missing generation configuration')
  need(attempts==9606,'Retained attempt count')
 return dict(passed=True,scope='Existing input/output verification only; no fitting, simulation or likelihood evaluation',histories=300,methods=600,retained_attempts=attempts,events=events,paired_forests=100,members=len(names),archive_sha256=manifest['archive']['sha256'])
def extract(output,root=HERE):
 result=verify(root);output=Path(output).resolve();need(not output.exists(),'Output must be a new directory');output.mkdir(parents=True)
 manifest=json.loads((Path(root)/'manifest.json').read_text())
 with zipfile.ZipFile(Path(root)/manifest['archive']['path']) as z:
  for name in z.namelist():
   target=output/Path(*safe_name(name).parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 (output/'input_verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True);s.add_parser('verify');e=s.add_parser('extract');e.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(verify() if a.command=='verify' else extract(a.output),indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
