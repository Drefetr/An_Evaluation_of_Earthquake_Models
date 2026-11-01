"""Compile sources only; never loads or runs resulting binaries."""
import hashlib,json,subprocess,argparse
from pathlib import Path
VCVARS=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
def q(path):
    path=Path(path).resolve()
    if any(c in str(path) for c in '\r\n"&|<>^%!'):raise ValueError('M02_BUILD_PATH')
    return '"'+str(path)+'"'
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent
    commands=['@echo off','setlocal DisableDelayedExpansion','call '+q(VCVARS),'if errorlevel 1 exit /b %errorlevel%',
      'cl /nologo /std:c++17 /W4 /EHsc /fp:strict '+q(here/'fixture.cpp')+' /Fo'+q(out/'fixture.obj')+' /Fe:'+q(out/'fixture.exe'),
      'if errorlevel 1 exit /b %errorlevel%',
      'cl /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict /LD '+q(here/'engine.cpp')+' /Fo'+q(out/'engine.obj')+' /link /OUT:'+q(out/'engine.dll'),
      'if errorlevel 1 exit /b %errorlevel%',
      'cl /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict /LD '+q(here/'radial.cpp')+' /Fo'+q(out/'radial.obj')+' /link /OUT:'+q(out/'radial.dll'),
      'if errorlevel 1 exit /b %errorlevel%',
      'cl /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict /LD '+q(here/'integrated.cpp')+' /Fo'+q(out/'integrated.obj')+' /link /OUT:'+q(out/'integrated.dll'),
      'exit /b %errorlevel%','']
    batch=out/'build.cmd';batch.write_text('\n'.join(commands),encoding='utf-8')
    result=subprocess.run(['cmd.exe','/d','/c',str(batch)],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (out/'build.log').write_text(result.stdout,encoding='utf-8')
    pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [VCVARS,*here.glob('*.hpp'),*here.glob('*.cpp'),Path(__file__),batch]}
    receipt=dict(schema='m02_build_only_v1',returncode=result.returncode,pins=pins,binaries_executed=False)
    for name in ('fixture.exe','engine.dll'):
        binary=out/name
        if binary.is_file():receipt[name]=hashlib.sha256(binary.read_bytes()).hexdigest()
    (out/'build_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    raise SystemExit(result.returncode)
if __name__=='__main__':main()
