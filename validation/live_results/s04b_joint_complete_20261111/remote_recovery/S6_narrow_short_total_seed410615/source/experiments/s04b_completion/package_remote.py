"""Stage a source/input bundle without running any numerical fit."""
import ast,hashlib,json,zipfile
from pathlib import Path
from experiments.s04b_completion.recover import REPO,evidence

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    out=REPO/'validation/live_results/s04b_remote_transfer_20261111';out.mkdir(exist_ok=True)
    refs=json.loads((REPO/'validation/live_results/joint_nuisance_dispositions_20261107/report.json').read_text())
    extracted=out/'saved_evidence';extracted.mkdir(exist_ok=True);index={}
    for case in refs['case_dispositions']:
        if case['seed'] not in (410518,410615):continue
        for kind in ('case','trace'):
            ref=case['evidence'][kind];data=evidence(ref)
            key=hashlib.sha256((ref['path']+'::'+ref['member']).encode()).hexdigest();name=key+('.json' if kind=='case' else '.jsonl')
            (extracted/name).write_bytes(data);index[key]=dict(file=name,original_reference=ref)
    (extracted/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    files=set(json.loads((REPO/'experiments/s04b_joint_nuisance/input_pins.json').read_text()))
    for base in ('s04b_completion','s04b_joint_nuisance','s04b_joint_execution','s04b_exposure_refinement'):
        files.update(p.relative_to(REPO).as_posix() for p in (REPO/'experiments'/base).iterdir() if p.is_file() and p.suffix in ('.py','.json','.cpp'))
    files.update(p.relative_to(REPO).as_posix() for p in (REPO/'reproduction/synthetic/source').iterdir() if p.is_file() and p.suffix in ('.py','.cpp','.hpp'))
    files.update(['reproduction/synthetic/native.py','reproduction/synthetic/replay.py','reproduction/synthetic/s8_moderate.py','scripts/fit_joint_refined_cpu.py','validation/live_results/joint_nuisance_dispositions_20261107/report.json'])
    for folder in (REPO/'reproduction/synthetic/s8_moderate_total',REPO/'validation/live_results/s8_moderate_20261111',REPO/'validation/live_results/s04b_joint_complete_20261111/recovery',REPO/'validation/live_results/s04b_joint_complete_20261111/source',extracted):
        files.update(p.relative_to(REPO).as_posix() for p in folder.rglob('*') if p.is_file() and p.suffix in ('.py','.npz','.json','.jsonl','.log'))
    entries=[]
    for relative in sorted(files):
        path=REPO/relative
        if path.suffix=='.py':ast.parse(path.read_text(encoding='utf-8-sig'),filename=relative)
        entries.append(dict(path=relative,sha256=sha(path),bytes=path.stat().st_size))
    manifest=dict(schema='s04b_remote_transfer_v1',numerical_execution=False,files=entries,total_bytes=sum(v['bytes'] for v in entries),
                  prior_status='S04B78 complete; S8four complete. No full aggregate exists.',runtime_requirements=['Python>=3.11','numpy','scipy','threadpoolctl','C++17 compiler'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    bundle=out/'sources_inputs.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_STORED) as z:
        for row in entries:z.write(REPO/row['path'],row['path'])
        z.write(out/'manifest.json','REMOTE_TRANSFER_MANIFEST.json')
    receipt=dict(bundle=str(bundle),sha256=sha(bundle),bytes=bundle.stat().st_size,file_count=len(entries),manifest_sha256=sha(out/'manifest.json'))
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
if __name__=='__main__':main()
