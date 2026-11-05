"""Verify recovered original fit/document archives; no numerical model calls."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parent
ARCHIVES={
 "historical_fit_package.zip":"79ae909337b5fa7ac0e2fa13dfecf5a0c3e4c071be387a84b67bd6655aa30c22",
 "historical_diagnostic_package.zip":"18e4e2e1b341b0b050246b1ddf6c0160891c4d67117caa5bc0199e15caa32558",
}
def verify():
 records=[]
 for name,expected in ARCHIVES.items():
  p=ROOT/name
  actual=hashlib.sha256(p.read_bytes()).hexdigest()
  if actual!=expected:raise ValueError("archive_hash_mismatch:"+name)
  with zipfile.ZipFile(p) as z:
   if len(z.namelist())!=len(set(z.namelist())):raise ValueError("duplicate_member")
   if z.testzip() is not None:raise ValueError("archive_crc_error")
   manifest=json.loads(z.read("manifest.json"))
   if manifest.get("errors"):raise ValueError("historical_source_pin_errors")
   for row in manifest.get("exact_sources",[]):
    if hashlib.sha256(z.read(row["output"])).hexdigest()!=row["source_sha256"]:
     raise ValueError("exact_member_hash_mismatch:"+row["output"])
   for row in manifest.get("projected_files",[]):
    raw=z.read(row["path"])
    if hashlib.sha256(raw).hexdigest()!=row["sha256"]:raise ValueError("projection_hash_mismatch")
    parsed=[json.loads(line) for line in raw.splitlines()]
    if len(parsed)!=row["records"]:raise ValueError("projection_record_count")
    if any(not x.get("selected_subtrees") for x in parsed):raise ValueError("empty_selected_fit")
   records.append({"archive":name,"sha256":actual,"members":len(z.namelist())})
 return {"passed":True,"scope":"Archive identity, exact members and projection rosters; no likelihood or optimizer execution.","archives":records}
if __name__=="__main__":print(json.dumps(verify(),indent=2))
