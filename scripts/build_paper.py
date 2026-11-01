"""Build the unified monograph with Tectonic 0.17.0; no scientific execution."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,shutil,subprocess,platform,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
 if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--engine',help='Path to Tectonic 0.17.0; alternatively set TECTONIC')
 p.add_argument('--output',type=Path,help='Fresh build directory (default build/<UTC timestamp>)')
 p.add_argument('--install',action='store_true',help='Explicitly install this successful build as paper/manuscript_unified.pdf. Omit for isolated verification.')
 a=p.parse_args()
 engine=a.engine or os.environ.get('TECTONIC') or shutil.which('tectonic')
 if not engine:raise SystemExit('Tectonic 0.17.0 is required. Set TECTONIC or pass --engine PATH.')
 engine=Path(engine).resolve()
 version=subprocess.check_output([str(engine),'--version'],text=True).strip()
 if version!='Tectonic 0.17.0':raise SystemExit('Expected Tectonic 0.17.0; got '+version)
 out=(a.output or ROOT/'build'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
 out.mkdir(parents=True,exist_ok=False)
 source=ROOT/'paper/source/main.tex'
 command=[str(engine),source.name,'--outdir',str(out),'--keep-logs','--keep-intermediates','--makefile-rules',str(out/'dependencies.mk')]
 result=subprocess.run(command,cwd=source.parent,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 (out/'console.log').write_text(result.stdout,encoding='utf-8')
 receipt={'engine':str(engine),'engine_version':version,'engine_sha256':hashlib.sha256(engine.read_bytes()).hexdigest(),'platform':platform.platform(),'command':command,'cwd':str(source.parent),'exit_code':result.returncode,'scope':'LaTeX compilation only; no scientific execution','tex_resources':'Tectonic resolves TeX resources through its installed cache/bundle; exact historical cache not claimed.'}
 if result.returncode==0:
  built=out/'main.pdf'
  receipt['built_pdf_sha256']=hashlib.sha256(built.read_bytes()).hexdigest();receipt['built_pdf']=str(built)
  receipt['installed']=bool(a.install)
  if a.install:
   target=ROOT/'paper/manuscript_unified.pdf';shutil.copy2(built,target)
   receipt['delivered_pdf_sha256']=hashlib.sha256(target.read_bytes()).hexdigest();receipt['delivered_pdf']=str(target)
 (out/'build_record.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 lines=result.stdout.splitlines()
 print('\n'.join(lines[-25:]));print('Build record:',out/'build_record.json')
 return result.returncode
if __name__=='__main__':raise SystemExit(main())
