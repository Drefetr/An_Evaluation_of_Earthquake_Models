"""Publish a verified standalone bundle to gh-pages and export its exact tree.

The source checkout, its index and main history are never switched or rewritten.
Only an explicit child of the observed publication tip may be pushed. A remote
lease rejects concurrent publication; stale source-main builds are rejected.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

SOURCE_REF = 'refs/heads/main'
PUBLISH_REF = 'refs/heads/gh-pages'
RECEIPT = 'publication.json'
ROOT = Path(__file__).resolve().parents[1]


def git(repository, *arguments, data=None, environment=None, check=True):
    environment = dict(os.environ if environment is None else environment, GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run(
        ['git', '-C', str(repository), *map(str, arguments)], input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
    )
    if check and result.returncode:
        raise RuntimeError('git ' + str(arguments[0]) + ' failed: ' +
                           result.stderr.decode('utf-8', 'replace').strip())
    return result


def text(repository, *arguments, **kwargs):
    return git(repository, *arguments, **kwargs).stdout.decode('utf-8').strip()


def remote_refs(repository, remote):
    if not remote or remote.startswith('-') or any(c in remote for c in '\r\n\0'):
        raise ValueError('remote must be an explicit remote name or location')
    raw = text(repository, 'ls-remote', '--heads', remote, SOURCE_REF, PUBLISH_REF)
    return {line.split()[1]: line.split()[0] for line in raw.splitlines()}


def verified_files(bundle):
    """Require the document contract and regular, self-contained static files."""
    if not bundle.is_dir() or not (bundle/'index.html').is_file() or not (bundle/'.nojekyll').is_file():
        raise ValueError('bundle must be a generated static site root with index.html and .nojekyll')
    files = []
    for path in sorted(bundle.rglob('*')):
        if path.is_symlink():
            raise ValueError('Pages bundles must not contain symbolic links')
        if path.is_file():
            relative = path.relative_to(bundle)
            if '.git' in relative.parts or relative.as_posix() == RECEIPT:
                raise ValueError('bundle contains reserved Git/publication metadata')
            files.append((relative.as_posix(), path.read_bytes()))
        elif not path.is_dir():
            raise ValueError('Pages bundles must contain only regular files/directories')
    by_name = dict(files)
    metadata = json.loads(by_name['documents.json'])
    if metadata.get('bundle_kind') != 'self_contained_deployment':
        raise ValueError('publish a generated self-contained deployment, not the repository preview')
    records = metadata.get('documents')
    if not isinstance(records, list) or not records:
        raise ValueError('deployment must declare its PDF downloads')
    for record in records:
        name = record['path']
        if not isinstance(name, str) or not name.startswith('downloads/') or '..' in Path(name).parts:
            raise ValueError('deployment PDFs must remain inside downloads/')
        raw = by_name.get(name)
        if raw is None or hashlib.sha256(raw).hexdigest() != record['sha256'] or len(raw) != record['bytes']:
            raise ValueError('deployment PDF identity differs from documents.json')
    return files


def write_tree(repository, files, environment):
    git(repository, 'read-tree', '--empty', environment=environment)
    for name, raw in files:
        blob = text(repository, 'hash-object', '-w', '--stdin', data=raw, environment=environment)
        git(repository, 'update-index', '--add', '--cacheinfo', '100644', blob, name,
            environment=environment)
    return text(repository, 'write-tree', environment=environment)


def assert_refs(repository, remote, source_sha, expected_tip):
    refs = remote_refs(repository, remote)
    if refs.get(SOURCE_REF) != source_sha:
        raise RuntimeError('source main changed; publish the current main build instead')
    if refs.get(PUBLISH_REF) != expected_tip:
        raise RuntimeError('gh-pages changed concurrently; rebuild/retry against its current tip')


def publish(bundle, source_sha, output, *, repository=ROOT, remote='origin', artifact=None):
    repository = Path(repository).resolve();bundle = Path(bundle).resolve();output = Path(output).resolve()
    artifact = Path(artifact).resolve() if artifact is not None else None
    if PUBLISH_REF == SOURCE_REF:
        raise ValueError('publication target cannot be the source branch')
    if not isinstance(source_sha, str) or not re.fullmatch(r'[0-9a-f]{40}(?:[0-9a-f]{24})?', source_sha):
        raise ValueError('source_sha must be a complete Git commit identity')
    if output.exists() or output == repository or output in repository.parents:
        raise ValueError('export output must be a fresh directory outside source ancestors')
    if output.is_relative_to(bundle) or bundle.is_relative_to(output):
        raise ValueError('export output and input bundle must be separate directories')
    if output.is_relative_to(repository) and not output.is_relative_to(repository/'build'):
        raise ValueError('exports inside the source checkout must stay under ignored build/')
    if artifact is not None:
        if artifact.exists():
            raise ValueError('artifact output must be a fresh file')
        if artifact.is_relative_to(bundle) or artifact.is_relative_to(output) or artifact in output.parents:
            raise ValueError('artifact output must be separate from the bundle and exported tree')
        if artifact.is_relative_to(repository) and not artifact.is_relative_to(repository/'build'):
            raise ValueError('artifact outputs inside the source checkout must stay under ignored build/')
    if text(repository, 'rev-parse', 'HEAD') != source_sha:
        raise RuntimeError('source_sha must match the current source checkout')
    git(repository, 'diff', '--quiet', source_sha, '--')
    refs = remote_refs(repository, remote)
    if refs.get(SOURCE_REF) != source_sha:
        raise RuntimeError('only the current remote main commit may be published')
    previous = refs.get(PUBLISH_REF)
    files = verified_files(bundle)
    if previous:
        # Fetch objects without switching branches or touching the source index.
        git(repository, 'fetch', '--no-tags', remote, PUBLISH_REF)
        if text(repository, 'cat-file', '-t', previous) != 'commit':
            raise RuntimeError('publication tip must be a commit')
    with tempfile.TemporaryDirectory(prefix='pages-index-') as temporary:
        environment = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary)/'index'))
        content_tree = write_tree(repository, files, environment)
        receipt = {'schema':'pages_publication_v1', 'source_ref':SOURCE_REF,
                   'source_sha':source_sha, 'content_tree':content_tree}
        files.append((RECEIPT, (json.dumps(receipt, indent=2)+'\n').encode('utf-8')))
        tree = write_tree(repository, files, environment)
        unchanged = previous and text(repository, 'rev-parse', previous+'^{tree}') == tree
        assert_refs(repository, remote, source_sha, previous)
        if unchanged:
            commit = previous
        else:
            identity = dict(environment, GIT_AUTHOR_NAME='github-actions[bot]',
                            GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
                            GIT_COMMITTER_NAME='github-actions[bot]',
                            GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
            parent = ['-p', previous] if previous else []
            commit = text(repository, 'commit-tree', tree, *parent,
                          data=('Publish Pages from '+source_sha+'\n').encode(), environment=identity)
            if previous:
                git(repository, 'merge-base', '--is-ancestor', previous, commit)
            # The commit is a normal child of previous. This exact-tip lease
            # adds compare-and-swap protection, including initial branch creation.
            lease = '--force-with-lease='+PUBLISH_REF+':'+(previous or '')
            git(repository, 'push', '--porcelain', lease, remote, commit+':'+PUBLISH_REF)
        assert_refs(repository, remote, source_sha, commit)
        if text(repository, 'rev-parse', commit+'^{tree}') != tree:
            raise RuntimeError('published branch tree differs from the verified artifact')
        output.mkdir(parents=True, exist_ok=False)
        for name, raw in files:
            destination = output/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        if artifact is not None:
            artifact.parent.mkdir(parents=True, exist_ok=True)
            # Build from the same frozen bytes as the Git tree, with no dotfile
            # filter, links, filesystem timestamps or other directory contents.
            with tarfile.open(artifact, 'x', format=tarfile.PAX_FORMAT) as archive:
                for name, raw in files:
                    info = tarfile.TarInfo(name);info.size = len(raw);info.mode = 0o644;info.mtime = 0
                    archive.addfile(info, io.BytesIO(raw))
    result = {'source_sha':source_sha, 'published_sha':commit, 'published_tree':tree,
              'content_tree':content_tree, 'changed':not bool(unchanged), 'files':len(files)}
    if artifact is not None:
        result['artifact_sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True, help='Fresh export of the exact published root')
    parser.add_argument('--artifact', type=Path, help='Optional fresh uncompressed Pages artifact.tar containing the exact published files')
    parser.add_argument('--remote', default='origin')
    args = parser.parse_args(argv)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        if os.environ.get('GITHUB_EVENT_NAME') not in {'push','workflow_dispatch'} or os.environ.get('GITHUB_REF') != SOURCE_REF:
            parser.error('Pages publication is restricted to push/manual runs of main')
        if os.environ.get('GITHUB_SHA') != args.source_sha:
            parser.error('source-sha must match the main workflow commit')
    result = publish(args.bundle, args.source_sha, args.output, remote=args.remote, artifact=args.artifact)
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
            output.write('published_sha='+result['published_sha']+'\n')
            output.write('published_tree='+result['published_tree']+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
