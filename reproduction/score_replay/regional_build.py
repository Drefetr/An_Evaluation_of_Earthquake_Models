"""Build the exact portable S06 kernels declared by a raw-feature registry."""
import argparse
import json
from pathlib import Path
import shutil
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, digest, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('build output must be new')
    from engine.cpu_build import build_shared
    raw = args.registry.read_bytes()
    registry = json.loads(raw)
    inputs = Inputs(args.registry.parent)
    args.output.mkdir(parents=True)
    native_dir = args.output / 'native'
    native_dir.mkdir()
    libraries = {}
    for name in ('core', 'competitive'):
        spec = registry['engine_resources'][name + '.cpp']
        source_dir = args.output / 'source' / name
        source_dir.mkdir(parents=True)
        source = source_dir / (name + '.cpp')
        source.write_bytes(inputs.read(spec))
        receipt = build_shared(source, args.output / 'build' / name, dependency_root=source_dir)
        original_library = Path(receipt['library'])
        installed = native_dir / original_library.name
        shutil.copyfile(original_library, installed)
        receipt_path = original_library.parent / 'build_receipt.json'
        libraries[name] = {'path': str(installed.resolve()), 'sha256': digest(installed.read_bytes()),
                           'source_sha256': spec['sha256'], 'build_receipt': receipt,
                           'build_receipt_path': str(receipt_path.resolve()),
                           'build_receipt_sha256': digest(receipt_path.read_bytes())}
    write_new(args.output / 'libraries.json', {'registry_sha256': digest(raw),
              'native_directory': str(native_dir.resolve()), 'libraries': libraries,
              'scope': 'Compilation only, no model or feature evaluation.'})
    print(json.dumps({'built_libraries': len(libraries)}))


if __name__ == '__main__':
    main()
