"""Use the original bounded host launcher with an explicit public-reader producer."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('frozen_refinement_launcher',ROOT/'scripts/run_joint_exposure_refinement.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

PUBLIC_REQUIRED = {
    'scripts/fit_joint_refined_cpu.py','scripts/run_joint_refined_cpu_host.py',
    '.github/workflows/joint-refined-cpu.yml',
    'experiments/s04b_refined_cpu_reader/__init__.py',
    'experiments/s04b_refined_cpu_reader/profile.json',
    'experiments/s04b_refined_cpu_reader/reader.py',
    'experiments/s04b_refined_cpu_bridge/__init__.py',
    'experiments/s04b_refined_cpu_bridge/contract.py',
    'experiments/s04b_refined_cpu_bridge/host.py',
    'experiments/s04b_refined_cpu_reader_audit/__init__.py',
    'experiments/s04b_refined_cpu_reader_audit/check.py',
    'tests/test_joint_refined_cpu_reader.py',
    'tests/test_joint_refined_cpu_bridge.py',
    'tests/test_joint_refined_cpu_reader_audit.py',
}


def check_public_sources(review):
    """Check the new executable graph before importing its metadata helpers."""
    pins=review['reviewed_files_sha256']
    old.require(PUBLIC_REQUIRED.issubset(pins),'Incomplete public reader source coverage')
    for name in PUBLIC_REQUIRED:
        old.require(old.sha(old.inside(ROOT,name))==pins[name],'Changed public source: '+name)
    profile=old.read(ROOT/'experiments/s04b_refined_cpu_reader/profile.json')
    names=profile['producer_source_paths']
    old.require(isinstance(names,list) and len(names)==len(set(names)) and PUBLIC_REQUIRED.issubset(names),
                'Reader profile omits required executable source')
    for name in names:
        old.require(name in pins and old.sha(old.inside(ROOT,name))==pins[name],'Unreviewed producer dependency: '+name)


def validate(review):
    group,host,driver=old.validate(review)
    old.require(review.get('public_reader_profile') == 'joint_refined_cpu_producer_v1'
                and review['batch_id'] == 3,'Only the reviewed full third group is admitted')
    check_public_sources(review)
    from experiments.s04b_refined_cpu_reader import verify_profile,source_identity,producer
    verify_profile()
    for name,pin in source_identity().items():
        old.require(review['reviewed_files_sha256'].get(name)==pin,'Unreviewed public producer: '+name)
    reference=dict(path=review['source_review'],sha256=review['source_review_sha256'])
    old.require(review['execution_producer']==producer(reference),'Wrong explicit public producer')
    return group,host,driver


def prepare(review,output,started):
    # Reuse original native extraction, prior binding, caps and outer command spec.
    namespace=dict(old.__dict__,validate=validate)
    function=types.FunctionType(old.prepare.__code__,namespace,'prepare_public_reader_host',old.prepare.__defaults__)
    result=function(review,output,started)
    from experiments.s04b_exposure_refinement.case_driver import write
    admission=old.read(output/'admission.json')
    admission.update(reader_source_review=dict(path=review['source_review'],sha256=review['source_review_sha256']),
                     execution_producer=review['execution_producer'])
    write(output/'admission.json',admission)
    old.require(result['command'][:4]==[sys.executable,'-B','-m','experiments.s04b_exposure_refinement.host'],
                'Unexpected original outer command')
    result['command'][3]='experiments.s04b_refined_cpu_bridge.host'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    old.require(sys.platform.startswith('linux'),'Declared Linux CPU host required')
    started=os.environ['CONTINUATION_HOST_STARTED_UTC']
    output=args.output.resolve()
    old.require(not output.is_relative_to(ROOT),'Fresh external output required')
    output.mkdir(parents=True,exist_ok=False)
    review=old.read(args.admission);old.write(output/'conductor_review.json',review)
    request=prepare(review,output,started)
    group,_,_=validate(review)
    request['wall_cap_seconds']=old.remaining_window(review,group,started)
    old.write(output/'supervisor_spec.json',request)
    return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/supervise_research.py'),
                           str(output/'supervisor_spec.json')],cwd=ROOT).returncode


if __name__=='__main__':
    raise SystemExit(main())
