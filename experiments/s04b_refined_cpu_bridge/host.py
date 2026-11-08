"""Reuse the frozen fixed-group orchestration with explicit public-entrypoint hooks."""
import argparse
import builtins
from pathlib import Path
import sys
import types
from . import contract
from experiments.s04b_exposure_refinement import host as frozen
from experiments.s04b_joint_remaining import host as generic


def reader_command(command, cap):
    require = contract.require
    require(command[:4] == [sys.executable,'-B','-m','experiments.s04b_exposure_refinement.case_driver'],
            'Unexpected scientific command')
    require(len(command) == 16 and command[4::2] == ['--mode','--case-id','--library','--build-receipt','--admission','--output'],
            'Unexpected scientific arguments')
    fields = dict(zip(command[4::2],command[5::2]))
    require(fields['--mode'] == 'untouched', 'Public command never resumes partial fits')
    return [sys.executable,'-B',str(contract.REPO/'scripts/fit_joint_refined_cpu.py'),'fit',
        '--case-id',fields['--case-id'],'--output',fields['--output'],
        '--wall-seconds',str(cap),'--rss-mib','6144','--headroom-mib','2048',
        '--execution-record',fields['--admission']]


def supervised(command, output, cap, admission, environment, spec_path):
    if command[:4] == [sys.executable,'-B','-m','experiments.s04b_exposure_refinement.case_driver']:
        command = reader_command(command,cap)
    elif command[:4] == [sys.executable,'-B','-m','experiments.s04b_exposure_refinement_audit.check']:
        command = command.copy(); command[3] = contract.CHECKER
    else:
        raise ValueError('Unrecognized dispatch in fixed public-reader host')
    return generic.supervised(command,output,cap,admission,environment,spec_path)


def facade():
    """No shared monkeypatching, bytecode rewriting or copied scheduler loop."""
    namespace = dict(frozen.__dict__)
    original_import = builtins.__import__
    def private_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'experiments.s04b_joint_remaining.host' and level == 0 and tuple(fromlist) == ('supervised','projection'):
            return types.SimpleNamespace(supervised=supervised,projection=generic.projection)
        return original_import(name,globals,locals,fromlist,level)
    namespace['__builtins__'] = dict(vars(builtins),__import__=private_import)
    for name in ('check_source_reviews','child_admission','append_candidate','check_receipt'):
        namespace[name] = getattr(contract,name)
    return types.FunctionType(frozen.run.__code__,namespace,'run_public_reader_group',frozen.run.__defaults__,frozen.run.__closure__)


def run(args):
    admission = contract.read(args.admission)
    # The first independently reviewed integration is the unchanged full third group.
    contract.require(admission['batch_id'] == 3, 'Public-reader bridge limited to reviewed fixed host three')
    code = facade()(args)
    result_path = Path(args.output)/'result.json'
    result = contract.read(result_path)
    result.update(schema='joint_refined_cpu_host_v1', execution_producer=admission['execution_producer'],
                  compatibility_source_scope='Frozen host/scientific maps denote reused core; per-case producer binds actual entrypoint')
    contract.write(result_path,result)
    return code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('admission','output','prior-index','prior-review','config','source-review','checker-review','library','build-receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--failed-prior',type=Path)
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
