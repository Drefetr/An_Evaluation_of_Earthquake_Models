"""Seal every training fit before any test-window score is read."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C
from experiments.pathway4_confirmatory_transfer.scoring import build_fit_seal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=C.PROTOCOL)
    args = parser.parse_args()
    seal = build_fit_seal(args.protocol)
    print(json.dumps({k: seal[k] for k in ("schema", "protocol_sha256",
                                           "manifest_sha256", "sealed_utc")},
                     indent=2))
    print("sealed files", len(seal["files"]))


if __name__ == "__main__":
    main()
