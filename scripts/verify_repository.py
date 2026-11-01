"""Verify payload hashes, historical engine pins and public authority variants.

Normal execution is read-only. --write-manifest refreshes reviewed current
payload membership, never historical source pins.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', 'build', '__pycache__', '.venv', '.pytest_cache', 'external_data', 'node_modules'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_files(root):
    for directory, dirs, names in os.walk(root):
        base = Path(directory)
        rel = base.relative_to(root)
        dirs[:] = [n for n in dirs if n not in EXCLUDED and not
                   (rel.parts and rel.parts[0] == 'engine' and n in {'data', 'results', 'logs'})]
        for name in names:
            path = base / name
            if name in EXCLUDED or path.suffix in {'.pyc', '.pyo'} or path == root / 'MANIFEST.json':
                continue
            yield path


def relative_path(root, value):
    path = (root / value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(root):
        raise ValueError('path escapes repository: ' + value)
    return path


def source_errors(root):
    errors = []
    extraction = json.loads((root / 'provenance/extraction_manifest.json').read_text(encoding='utf-8'))
    variants = {v['path']: v for v in extraction.get('public_variants', [])}
    for row in extraction['files']:
        if not row['public_path'].startswith('engine/'):
            continue
        path = relative_path(root, row['public_path'])
        variant = variants.get(row['public_path'])
        if variant and variant['original_sha256'] != row['sha256']:
            errors.append('variant original pin: ' + row['public_path'])
        expected = variant['public_sha256'] if variant else row['sha256']
        if not path.is_file() or digest(path) != expected:
            errors.append('preserved source/public variant: ' + row['public_path'])
    for row in json.loads((root / 'validation/authority_manifest.json').read_text(encoding='utf-8')):
        path = relative_path(root, row['bundled_path'])
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            errors.append('public authority binding: ' + row['bundled_path'])
    recovery = root / 'provenance/stage2_source_recovery.json'
    if recovery.exists():
        for row in json.loads(recovery.read_text(encoding='utf-8'))['recovered']:
            path = relative_path(root, row['public_path'])
            if not path.is_file() or digest(path) != row['public_sha256']:
                errors.append('recovered Stage 2 source pin: ' + row['public_path'])
    if 'magnitudes' in json.loads((root / 'paper/data/catalogue.json').read_text(encoding='utf-8')):
        errors.append('event-level magnitude array')
    if list((root / 'paper').rglob('manuscript_v2.pdf')):
        errors.append('earlier third-party manuscript')
    return errors


def verify(root=ROOT, manifest=None, write_manifest=False):
    root = Path(root).resolve()
    manifest = Path(manifest) if manifest else root / 'MANIFEST.json'
    files = sorted(payload_files(root), key=lambda f: f.relative_to(root).as_posix())
    actual = {f.relative_to(root).as_posix(): f for f in files}
    errors = source_errors(root)
    if write_manifest and not errors:
        rows = [{'path': p, 'bytes': f.stat().st_size, 'sha256': digest(f)} for p, f in actual.items()]
        manifest.write_text(json.dumps({'schema': 'repository_payload_v2', 'files': rows}, indent=2) + '\n', encoding='utf-8')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    expected = {r['path']: r for r in data['files']}
    for p, row in expected.items():
        f = relative_path(root, p)
        if not f.is_file() or f.stat().st_size != row['bytes'] or digest(f) != row['sha256']:
            errors.append('payload hash: ' + p)
    if actual.keys() != expected.keys():
        errors.append({'coverage_missing': sorted(expected.keys() - actual.keys()),
                       'coverage_extra': sorted(actual.keys() - expected.keys())})
    return {'checked_files': len(expected), 'passed': not errors, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--write-manifest', action='store_true', help='Explicitly refresh reviewed current payload membership and hashes')
    args = parser.parse_args()
    result = verify(manifest=args.manifest, write_manifest=args.write_manifest)
    print(json.dumps(result, indent=2))
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
