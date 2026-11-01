"""Local-only compiled original-OC adapter and private artifact writer.

Importing performs no loading, fitting, simulation or printing. Consumers must
not print state, event arrays, detailed scores, or private NPZ/JSON contents.
The conductor supplies already verified private state bytes and lease admission.
"""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import numpy as np

PARAM_KEYS = ('a','d','n','c','p','scale','bandwidth','beta','T0','start','end','spatial_q')
SCALAR_KEYS = ('count','exposure','immigrant_exposure','trigger_exposure',
    'count_minus_exposure','time_event_logsum','timing_logscore','location_logscore',
    'mark_logscore','joint_logscore','zone_logscore','cell_given_zone_logscore',
    'within_cell_density_logscore','subblock_balance_max','gap_ks','gap_serial',
    'censored_tail','spatial_rosenblatt_ks_max','spatial_rosenblatt_cross_abs',
    'cell_mass_residual_max','location_dimensionless_log_mean',
    'location_dimensionless_log_variance','within_cell_dimensionless_absmax',
    'within_cell_dimensionless_sum')
YEAR_KEYS = ('year_count','year_exposure','year_count_minus_exposure')
CELL_KEYS = ('cell_count','cell_conditional_expected','cell_exposure',
    'cell_count_minus_conditional_expected','cell_count_minus_exposure')
DETAIL_KEYS = ('gap','gap_uniform','rosenblatt_x','rosenblatt_y','log_ground',
    'log_point','log_cell','log_zone','log_mark','dimensionless_location',
    'dimensionless_within_cell')
SIM_META_KEYS = ('accepted_count','candidate_count','raw_engine_draws',
    'processed_parents','immigrants','preorigin_direct','future_direct',
    'spatial_proposals')
MASTER = 'Thread02|conditional_calibration_20261025T085151Z|EP|scientific-remediation-v1'
PURPOSES = ('immigrant','prehistory-offspring','descendants','marks')
D = C.POINTER(C.c_double)
U32 = C.POINTER(C.c_uint32)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def seeds(phase: str, case_id: str, index: int):
    if phase not in ('synthetic_control','engineering_pilot','production','audit') or index < 0:
        raise ValueError('SEED_NAMESPACE')
    records=[];words=[]
    for purpose in PURPOSES:
        text=f'{MASTER}|{phase}|{case_id}|{index}|{purpose}'
        digest=hashlib.sha256(text.encode('utf-8')).digest()
        part=[int.from_bytes(digest[i:i+4],'big') for i in range(0,16,4)]
        records.append(dict(purpose=purpose,sha256=digest.hex(),seed_words_uint32_be=part))
        words.extend(part)
    return np.asarray(words,dtype=np.uint32),records

def _array(x, shape=None):
    x=np.ascontiguousarray(x,dtype=np.float64)
    if shape is not None and x.shape != shape:
        raise ValueError('ARRAY_SHAPE')
    if not np.isfinite(x).all():
        raise ValueError('NONFINITE_ARRAY')
    return x

def _ptr(x): return x.ctypes.data_as(D)

def decode_stats(values):
    values=_array(values,(84,));out={k:float(values[i]) for i,k in enumerate(SCALAR_KEYS)}
    offset=24
    for keys,n in ((YEAR_KEYS,5),(CELL_KEYS,9)):
        for key in keys:
            out[key]=values[offset:offset+n].tolist();offset+=n
    return out

class Engine:
    def __init__(self,dll_path):
        self.path=Path(dll_path).resolve();self.dll=C.CDLL(str(self.path));d=self.dll
        d.cc_last_error.restype=C.c_char_p;d.cc_version.restype=C.c_char_p
        d.cc_create.argtypes=[C.c_int,D,C.c_int,D,D,D,D];d.cc_create.restype=C.c_void_p
        d.cc_destroy.argtypes=[C.c_void_p]
        d.cc_rectangle.argtypes=[D,C.c_double,C.c_double,C.c_double];d.cc_rectangle.restype=C.c_double
        d.cc_simulate.argtypes=[C.c_void_p,U32];d.cc_simulate.restype=C.c_void_p
        d.cc_path_size.argtypes=[C.c_void_p];d.cc_path_size.restype=C.c_uint64
        d.cc_path_copy.argtypes=[C.c_void_p,D,D];d.cc_path_copy.restype=C.c_int
        d.cc_path_destroy.argtypes=[C.c_void_p]
        d.cc_evaluate.argtypes=[C.c_void_p,C.c_int,D,D,D,D];d.cc_evaluate.restype=C.c_int
        d.cc_uniform_from_word.argtypes=[C.c_uint64];d.cc_uniform_from_word.restype=C.c_double

    def error(self):return self.dll.cc_last_error().decode('utf-8','replace')

    def rectangle(self,bounds,parent,scale):
        r=_array(bounds,(4,));v=self.dll.cc_rectangle(_ptr(r),float(parent[0]),float(parent[1]),float(scale))
        if not np.isfinite(v):raise RuntimeError(self.error())
        return float(v)

    def state(self,arrays):return State(self,arrays)

class State:
    def __init__(self,engine,arrays):
        self.engine=engine
        keys=set(arrays.keys());required={'params','rectangles','pi','training_xy','prehistory','subblocks'}
        if not required<=keys or keys-required-{'observed'}:raise ValueError('STATE_KEY_SCHEMA')
        self.has_observed='observed' in keys
        self.params=_array(arrays['params'],(12,));self.rect=_array(arrays['rectangles'],(9,4));self.pi=_array(arrays['pi'],(9,))
        self.train=_array(arrays['training_xy']);self.history=_array(arrays['prehistory']);self.blocks=_array(arrays['subblocks'],(6,))
        if self.train.ndim!=2 or self.train.shape[1]!=2 or self.history.ndim!=2 or self.history.shape[1]!=4:
            raise ValueError('STATE_ROW_SCHEMA')
        self.handle=engine.dll.cc_create(len(self.history),_ptr(self.history),len(self.train),_ptr(self.train),_ptr(self.rect),_ptr(self.pi),_ptr(self.params))
        if not self.handle:raise RuntimeError(engine.error())

    def close(self):
        if self.handle:self.engine.dll.cc_destroy(self.handle);self.handle=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def simulate(self,words):
        if self.has_observed:raise ValueError('SIMULATION_STATE_CONTAINS_OBSERVED')
        words=np.ascontiguousarray(words,dtype=np.uint32)
        if words.shape!=(16,):raise ValueError('SEED_WORD_SHAPE')
        h=self.engine.dll.cc_simulate(self.handle,words.ctypes.data_as(U32))
        if not h:raise RuntimeError(self.engine.error())
        try:
            n=self.engine.dll.cc_path_size(h);events=np.empty((n,4));meta=np.empty(8)
            status=self.engine.dll.cc_path_copy(h,_ptr(events),_ptr(meta));message=self.engine.error()
            return events,dict(status=int(status),message=message,**dict(zip(SIM_META_KEYS,map(float,meta))))
        finally:self.engine.dll.cc_path_destroy(h)

    def evaluate(self,events):
        events=_array(events)
        if events.ndim!=2 or events.shape[1]!=4:raise ValueError('EVENT_ROW_SCHEMA')
        stats=np.empty(84);detail=np.empty((len(events),11))
        status=self.engine.dll.cc_evaluate(self.handle,len(events),_ptr(events),_ptr(self.blocks),_ptr(stats),_ptr(detail))
        if status:raise RuntimeError(self.engine.error())
        return decode_stats(stats),detail

def build(output,compiler='auto'):
    """Only conductor under its serial machine lease may call this function."""
    src=Path(__file__).with_name('engine.cpp').resolve();output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    artifacts=[output,output.with_suffix(output.suffix+'.build.json'),output.with_suffix(output.suffix+'.failed-build.txt')]
    artifacts += [output.with_suffix(ext) for ext in ('.obj','.lib','.exp','.pdb')]
    if any(path.exists() for path in artifacts):raise FileExistsError('BUILD_ARTIFACT_ALREADY_EXISTS_USE_NEW_PATH')
    if compiler=='auto':compiler=shutil.which('g++') or ('msvc' if os.name=='nt' else 'g++')
    if compiler=='msvc':
        vcvars=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
        if not vcvars.is_file():raise FileNotFoundError('PINNED_MSVC_VCVARS_MISSING')
        # cmd receives trusted absolute local paths only, without metacharacters.
        for path in (src,output):
            if any(c in str(path) for c in '\r\n"&|<>^%'):raise ValueError('BUILD_PATH_METACHARACTER')
        options=['cl.exe','/nologo','/std:c++17','/O2','/DNDEBUG','/EHsc','/fp:strict','/LD',str(src),'/Fo'+str(output.with_suffix('.obj')),'/link','/OUT:'+str(output),'/IMPLIB:'+str(output.with_suffix('.lib'))]
        command='call "'+str(vcvars)+'" >nul && '+subprocess.list2cmdline(options)
        cmd=['cmd.exe','/d','/s','/c',command]
        result=subprocess.run(cmd,capture_output=True,text=True,cwd=output.parent)
        version_command='call "'+str(vcvars)+'" >nul && cl.exe /Bv'
        probe=subprocess.run(['cmd.exe','/d','/s','/c',version_command],capture_output=True,text=True,cwd=output.parent)
        version=probe.stdout+probe.stderr
    else:
        cmd=[compiler,'-std=c++17','-O3','-DNDEBUG','-fno-fast-math','-ffp-contract=off','-shared',str(src),'-o',str(output)]
        if os.name!='nt':cmd.insert(1,'-fPIC')
        result=subprocess.run(cmd,capture_output=True,text=True,cwd=output.parent)
        version=subprocess.run([compiler,'--version'],capture_output=True,text=True,check=True).stdout
    if result.returncode:
        output.with_suffix(output.suffix+'.failed-build.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
        raise RuntimeError('BUILD_FAILED: see exclusive failed-build.txt')
    manifest=dict(schema='thread02_engine_build_v1',command=cmd,source_sha256=sha(src),adapter_sha256=sha(__file__),binary_sha256=sha(output),compiler_version=version,compiled_engine_version=Engine(output).dll.cc_version().decode('ascii'),platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,threads=1,fast_math=False)
    output.with_suffix(output.suffix+'.build.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest

def run_job(job_path):
    """Consumed job is pinned by conductor; writes local private artifacts only.

    Fields: state_npz,state_sha256,binary,binary_sha256,output_dir,case_id,
    phase,index,mode ('simulate' or 'observed'), optional frozen seed_words16.
    Caller pins this job JSON, source, adapter, binary and state before run.
    """
    job=json.loads(Path(job_path).read_text(encoding='utf-8'))
    if sha(job['state_npz'])!=job['state_sha256'] or sha(job['binary'])!=job['binary_sha256']:
        raise ValueError('JOB_INPUT_HASH')
    out=Path(job['output_dir']);out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();cpu=time.process_time();receipt=dict(schema='thread02_path_receipt_v1',case_id=job['case_id'],phase=job['phase'],index=int(job['index']),mode=job['mode'],status='running',input_state_sha256=job['state_sha256'],binary_sha256=job['binary_sha256'],adapter_sha256=sha(__file__),job_sha256=sha(job_path))
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    try:
        engine=Engine(job['binary'])
        with np.load(job['state_npz'],allow_pickle=False) as arrays, engine.state(arrays) as state:
            if job['mode']=='simulate':
                words,records=seeds(job['phase'],job['case_id'],job['index'])
                if 'seed_words16' in job and words.tolist()!=job['seed_words16']:raise ValueError('JOB_SEED_MISMATCH')
                receipt['seed_records']=records;events,status=state.simulate(words);receipt['generator']=status
            elif job['mode']=='observed':events=_array(arrays['observed']);status={'status':0}
            else:raise ValueError('JOB_MODE')
            np.savez_compressed(out/'private_path.npz',events=events)
            receipt['path_sha256']=sha(out/'private_path.npz')
            if status['status']:
                receipt['status']='generator_failed';receipt['reason']=status.get('message','')
            else:
                stats,detail=state.evaluate(events)
                np.savez_compressed(out/'private_detail.npz',detail=detail)
                (out/'scalars.json').write_text(json.dumps(dict(schema='thread02_scalar_vector_v1',case_id=job['case_id'],stats=stats),indent=2,allow_nan=False)+'\n',encoding='utf-8')
                receipt.update(status='complete',scalars_sha256=sha(out/'scalars.json'),detail_sha256=sha(out/'private_detail.npz'))
    except Exception as exc:
        receipt.update(status='failed',reason=type(exc).__name__+':'+str(exc))
    receipt.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return receipt

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('build');p.add_argument('--output',required=True);p.add_argument('--compiler',default='auto')
    p=sub.add_parser('job');p.add_argument('--job',required=True)
    args=parser.parse_args()
    if args.action=='build':build(args.output,args.compiler)
    else:
        receipt=run_job(args.job)
        raise SystemExit(0 if receipt['status']=='complete' else 1)
    # Deliberately no stdout: manager summaries are conductor-allowlisted.

if __name__=='__main__':main()
