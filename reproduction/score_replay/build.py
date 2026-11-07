"""Build pinned cached evaluators; this does not evaluate likelihoods."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from reproduction.score_replay.core import Inputs, digest, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=Path(__file__).with_name('cached_registry.json'))
    parser.add_argument('--adapter', action='append', help='Default: every declared adapter')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('build output must be a new directory')
    from engine.cpu_build import build_shared
    data = args.registry.read_bytes()
    registry = json.loads(data)
    inputs = Inputs(args.registry.parent)
    selected = args.adapter or list(registry['adapters'])
    if len(set(selected)) != len(selected):
        raise ValueError('duplicate adapter')
    args.output.mkdir(parents=True)
    libraries = {}
    for adapter_id in selected:
        adapter = registry['adapters'][adapter_id]
        if adapter['kind'] != 'original_cached_native':
            raise ValueError('unsupported build adapter')
        source_dir = args.output / adapter_id / 'source'
        source_dir.mkdir(parents=True)
        source = source_dir / 'objective.cpp'
        source.write_bytes(inputs.read(adapter['native']))
        receipt = build_shared(source, args.output / adapter_id / 'build', dependency_root=source_dir)
        library = Path(receipt['library'])
        receipt_path = library.parent / 'build_receipt.json'
        libraries[adapter_id] = {'path': str(library.resolve()), 'sha256': digest(library.read_bytes()),
                                'source_sha256': adapter['native']['sha256'],
                                'build_receipt_path': str(receipt_path.resolve()),
                                'build_receipt_sha256': digest(receipt_path.read_bytes()),
                                'build_receipt': receipt}
    value = {'registry_sha256': digest(data), 'libraries': libraries,
             'scope': 'Build only; no historical likelihood evaluated.'}
    write_new(args.output / 'libraries.json', value)
    print(json.dumps({'built_adapters': len(libraries)}))


if __name__ == '__main__':
    main()
