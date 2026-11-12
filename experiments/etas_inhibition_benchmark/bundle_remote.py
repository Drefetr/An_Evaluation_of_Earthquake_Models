"""Create a hash-manifested portable input/source bundle; never execute models."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();files=set()
    def add(path):
        path=Path(path)
        if not path.is_file():raise FileNotFoundError(path)
        files.add(path.relative_to(ROOT).as_posix())
    for folder in ('experiments/etas_inhibition_benchmark','experiments/methodological_audit'):
        for path in (ROOT/folder).iterdir():
            if path.suffix in ('.py','.cpp','.cu','.md','.txt'):add(path)
    for rel in ['reproduction/score_replay/core.py','engine/stage2_followup/native_build.py','engine/iteration_27/code/adequacy.py','engine/iteration_5/code/kernels.py','reproduction/observed/historical_observed.json.gz','reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv']:
        add(ROOT/rel)
    for rel in ('reproduction/score_replay/california','reproduction/score_replay/california_benchmark','reproduction/score_replay/observed_fixedbackbone'):
        folder=ROOT/rel;add(folder/'registry.json');reg=json.loads((folder/'registry.json').read_bytes())
        for row in reg['rows']:
            if rel.endswith('/california'):
                eligible=row['study']=='primary_california' and row['procedure_key']=='Omori_smooth_cont'
            elif rel.endswith('california_benchmark'):
                eligible=row['procedure_key']=='EP' and row['phase']=='test'
            else:eligible=row['order']==16 and row['case'].startswith('california')
            if not eligible:continue
            for key in ('cache','state','selected_states','prepared','expected'):
                if key in row:add(folder/row[key]['archive'])
    for rel in ('validation/live_results/etas_inhibition_benchmark_20261111/california_fold_0/result.json','validation/live_results/etas_inhibition_benchmark_20261111/controls.json','validation/live_results/score_uncertainty_final_20261111/nz.json','validation/live_results/score_uncertainty_final_20261111/ca.json'):
        if (ROOT/rel).exists():add(ROOT/rel)
    for rel in list(files):
        for parent in (ROOT/rel).parents:
            if parent==ROOT:break
            init=parent/'__init__.py'
            if init.exists():add(init)
    manifest=dict(schema='remote_workstream3_source_input_bundle_v1',models_executed=False,members=[dict(path=r,bytes=(ROOT/r).stat().st_size,sha256=hashlib.sha256((ROOT/r).read_bytes()).hexdigest()) for r in sorted(files)])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for rel in sorted(files):z.write(ROOT/rel,rel)
        z.writestr('REMOTE_BUNDLE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    a.output.with_suffix(a.output.suffix+'.sha256').write_text(hashlib.sha256(a.output.read_bytes()).hexdigest()+'\n')
    print(json.dumps(dict(bundle=str(a.output),members=len(files),bytes=a.output.stat().st_size)))
if __name__=='__main__':main()
