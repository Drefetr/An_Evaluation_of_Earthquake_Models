"""Download exact provider snapshots to a new directory, rejecting changed bytes.

NZ's live service may revise records. A changed response fails and is retained as
a .rejected file; it is never installed as this historical snapshot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request

from replay import ReplayError, load_manifest, require, safe_path, sha256, write_json

ALLOWED_HOSTS = {"wfs.geonet.org.nz", "raw.githubusercontent.com"}


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS
            and parsed.username is None and parsed.password is None,
            "unapproved_provider_url")


def acquire_file(region, record, output, opener, timeout):
    validate_url(record["url"])
    destination = safe_path(output, region + "/" + record["filename"])
    require(destination.parent == (output / region).resolve(), "unsafe_raw_filename")
    require(not destination.exists(), "download_destination_exists")
    request = urllib.request.Request(record["url"], headers={
        "User-Agent":"Earthquake-models-exact-snapshot-replay/1.0", "Accept-Encoding":"identity"})
    with opener.open(request, timeout=timeout) as response:
        validate_url(response.geturl())
        require(response.status == 200, "provider_http_status")
        payload = response.read(record["bytes"] + 1)
    result = {"region":region,"file":record["filename"],"url":record["url"],
              "bytes":len(payload),"sha256":sha256(payload),"expected_sha256":record["sha256"]}
    matches = len(payload) == record["bytes"] and result["sha256"] == record["sha256"]
    if matches and "git_blob_sha1" in record:
        blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
        matches = blob == record["git_blob_sha1"]
        result["git_blob_sha1"] = blob
    if not matches:
        rejected = destination.with_name(destination.name + ".rejected")
        with rejected.open("xb") as stream:
            stream.write(payload)
        result["status"] = "rejected_changed_or_oversized_response"
        result["retained_response_prefix"] = len(payload) > record["bytes"]
        return result
    with destination.open("xb") as stream:
        stream.write(payload)
    result["status"] = "verified_historical_bytes"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region",choices=("nz","california","all"),default="all")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--timeout",type=float,default=60)
    args = parser.parse_args(argv)
    if args.output.exists():
        print(json.dumps({"status":"failed","passed":False,"error":"output_already_exists"}))
        return 2
    require(args.timeout > 0, "invalid_timeout")
    args.output.mkdir(parents=True,exist_ok=False)
    receipt = {"schema_version":1,"status":"running","passed":False,"files":[],"scope":"Provider input retrieval; no statistical or model validation."}
    return_code = 0
    try:
        manifest, manifest_sha = load_manifest()
        receipt["input_manifest_sha256"] = manifest_sha
        opener = urllib.request.build_opener(HTTPSOnlyRedirect())
        for region in (("nz","california") if args.region == "all" else (args.region,)):
            (args.output/region).mkdir()
            for record in manifest["datasets"][region]["raw_files"]:
                result = acquire_file(region,record,args.output,opener,args.timeout)
                receipt["files"].append(result)
                write_json(args.output/"result.json",receipt)
                require(result["status"] == "verified_historical_bytes", "historical_source_changed")
        receipt["status"] = "passed"
        receipt["passed"] = True
    except Exception as error:
        receipt.update(status="failed",passed=False,error_type=type(error).__name__,
                       error=str(error) if isinstance(error,ReplayError) else "provider_or_io_failure")
        return_code = 1
    write_json(args.output/"result.json",receipt)
    print(json.dumps({"status":receipt["status"],"files":len(receipt["files"]),"result":"result.json"}))
    return return_code


if __name__ == "__main__":
    sys.exit(main())
