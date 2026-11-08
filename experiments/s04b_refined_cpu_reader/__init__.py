"""Metadata-only contract for the public amended Linux CPU reader."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
PROFILE = 'experiments/s04b_refined_cpu_reader/profile.json'
ENTRYPOINT = 'scripts/fit_joint_refined_cpu.py'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(root, relative):
    parts = PurePosixPath(relative)
    require(isinstance(relative, str) and relative and '\\' not in relative and ':' not in relative
            and not parts.is_absolute() and '..' not in parts.parts, 'Unsafe relative path')
    path = (Path(root)/relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), 'Path escapes root')
    return path


def verify_profile():
    p = read(REPO/PROFILE)
    require(p['schema'] == 'joint_refined_cpu_reader_profile_v1'
            and p['entrypoint'] == ENTRYPOINT and p['operation'] == 'fit', 'Wrong reader profile')
    require(p['numerical_version'] == 'joint_exposure_refinement_v1', 'Unknown numerical amendment')
    paths = p['producer_source_paths']
    require(paths == sorted(set(paths)) and PROFILE in paths and ENTRYPOINT in paths, 'Producer source roster differs')
    for relative, pin in p['core_source_sha256'].items():
        require(sha(safe(REPO, relative)) == pin, 'Frozen core source changed: '+relative)
    amendment = read(safe(REPO, p['amendment_protocol']['path']))
    require(sha(safe(REPO, p['amendment_protocol']['path'])) == p['amendment_protocol']['sha256'], 'Amendment protocol changed')
    require(sha(safe(REPO, p['scientific_protocol']['path'])) == p['scientific_protocol']['sha256']
            == amendment['original_scientific_protocol_sha256'], 'Original scientific protocol differs')
    core = dict(amendment['source_sha256'])
    base = REPO/'experiments/s04b_exposure_refinement'
    core.update({q.relative_to(REPO).as_posix(): sha(q) for q in base.iterdir()
                 if q.is_file() and q.suffix in ('.py', '.json')})
    require(core == p['core_source_sha256'], 'Frozen core compatibility map differs')
    require(p['case_ids'] == amendment['full_sequence'] and len(set(p['case_ids'])) == 80, 'Original history roster differs')
    native = p['bundled_native']; old = amendment['permanent_unknown']
    require(native['archive_reference'] == {'path': old['archive'], 'sha256': old['archive_sha256']}
            and native['review_reference'] == {'path': old['review'], 'sha256': old['review_sha256']}
            and native['library_member'] == old['library_member']
            and native['build_receipt_member'] == old['build_receipt_member'], 'Native artifact source changed')
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(native[key] == amendment['original_native'][key], 'Native identity differs')
    require(sha(safe(REPO, native['review_reference']['path'])) == native['review_reference']['sha256'], 'Bundled native audit changed')
    return p


def source_identity():
    p = verify_profile()
    full = dict(p['core_source_sha256'])
    for path in p['producer_source_paths']:
        value = sha(safe(REPO, path))
        require(path not in full or full[path] == value, 'Conflicting source identity')
        full[path] = value
    return dict(sorted(full.items()))


def producer(source_review=None):
    p = verify_profile(); full = source_identity()
    if source_review is not None:
        require(set(source_review) == {'path', 'sha256'}, 'Invalid source-review reference')
        review_path = safe(REPO, source_review['path'])
        require(sha(review_path) == source_review['sha256'], 'Source review changed')
        review = read(review_path)
        require(review.get('passed') is True and review.get('live_agent_review') is True
                and review.get('live_agent_review_performed') is not False
                and review.get('final_batch_agent_review_required') is not True, 'Source review not accepted')
        require(all(review['reviewed_files_sha256'].get(k) == v for k, v in full.items()), 'Source review misses actual producer')
    return dict(schema='joint_refined_cpu_producer_v1', kind='public_refined_cpu', entrypoint=ENTRYPOINT,
                operation='fit', profile_reference={'path': PROFILE, 'sha256': sha(REPO/PROFILE)},
                core_source_sha256=p['core_source_sha256'],
                producer_source_sha256={k: full[k] for k in p['producer_source_paths']},
                execution_source_sha256=full, source_review=source_review)
