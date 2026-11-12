"""Build the unchanged attenuation source on Windows or Linux."""
from pathlib import Path
import argparse,hashlib,json,os,platform,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2]
def build(output=None):
    out=Path(output).resolve() if output else ROOT/'validation/live_results/s04b_joint_complete_20261111/native';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'experiments/s04b_joint_nuisance/attenuation.cpp'
    if os.name=='nt':
        from reproduction.synthetic.native import _vcvars,_quote
        library=out/'joint.dll'
        command='cl.exe /nologo /std:c++17 /O2 /DNDEBUG /EHsc /fp:strict /LD '+_quote(source)+' /Fo'+_quote(out/'joint.obj')+' /link /OUT:'+_quote(library)+' /IMPLIB:'+_quote(out/'joint.lib')
        batch=out/'build.cmd';batch.write_text('\n'.join(['@echo off','call '+_quote(_vcvars()),command]))
        invocation=['cmd.exe','/d','/c',str(batch)]
    else:
        compiler=os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++')
        if not compiler:raise FileNotFoundError('A C++17 compiler is required')
        library=out/'attenuation.so'
        command=[compiler,'-std=c++17','-O2','-fPIC','-shared','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(library)]
        invocation=command
    with (out/'build.log').open('w') as log:subprocess.run(invocation,stdout=log,stderr=subprocess.STDOUT,check=True)
    receipt=dict(platform=platform.platform(),command=command,library=library.name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),compiler_log_sha256=hashlib.sha256((out/'build.log').read_bytes()).hexdigest())
    (out/'build_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);args=p.parse_args();print(build(args.output))
