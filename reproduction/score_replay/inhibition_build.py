"""Compile pinned original fixed-backbone replay kernels; no evaluation."""
from pathlib import Path
import argparse
import json
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, digest, write_new


def build(registry_path, output):
    from engine.cpu_build import build_shared
    if output.exists():
        raise FileExistsError('Build output must be new')
    raw = registry_path.read_bytes()
    registry = json.loads(raw)
    inputs = Inputs(registry_path.parent)
    output.mkdir(parents=True)
    source = output/'source'
    source.mkdir()
    for name in ('cpu_reference.cpp', 'architecture.hpp', 'radial.cpp'):
        (source/name).write_bytes(inputs.read(registry['source_resources'][name]))
    libraries = {}
    for name, filename in [('cpu', 'cpu_reference.cpp'), ('radial', 'radial.cpp')]:
        receipt = build_shared(source/filename, output/name, dependency_root=source)
        path = Path(receipt['library'])
        receipt_path = output/name/'build_receipt.json'
        libraries[name] = dict(path=str(path), sha256=digest(path.read_bytes()),
            source_sha256=registry['source_resources'][filename]['sha256'],
            build_receipt=receipt, build_receipt_path=str(receipt_path.resolve()),
            build_receipt_sha256=digest(receipt_path.read_bytes()))
    result = dict(registry_sha256=digest(raw), libraries=libraries)
    write_new(output/'libraries.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    build(args.registry, args.output.resolve())
