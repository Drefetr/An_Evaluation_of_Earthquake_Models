"""Enumerate every source table in the declared replay scope, without scoring."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

FILES = (
    '09_temporal_mark_extensions.tex', '09_s02_completed.tex',
    '10_nz_spatial_background.tex', '11_external_transfer_benchmarks.tex',
    '11_s03_completed.tex', '11_s06_completed.tex',
    '12_conditional_calibration.tex', '12_s05_completed.tex',
    '13_continuous_local_inhibition.tex', '13_s04_observed_completed.tex',
    '13_s04_expanded.tex',
)
APPENDIX_FILES = ('ch09_audit.tex', 'ch10_audit.tex', 'ch11_backup.tex', 'ch12_audit.tex')
EXCLUDED = ('07_synthetic.tex', '08_observed_baseline.tex',
            '13_s04_diagnostics.tex', '13_s04_refitted_floor.tex')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def group(text: str, start: int) -> str:
    """Read a balanced TeX group. This is an inventory parser, not a renderer."""
    if text[start] != '{':
        raise ValueError('group must start with brace')
    depth = 1
    for i in range(start + 1, len(text)):
        if i and text[i - 1] == '\\':
            continue
        depth += (text[i] == '{') - (text[i] == '}')
        if depth == 0:
            return text[start + 1:i]
    raise ValueError('unclosed TeX group')


def commands(text: str, name: str) -> list[str]:
    return [group(text, m.end() - 1)
            for m in re.finditer(r'\\' + name + r'(?:\[[^\]]*\])?\{', text)]


def tables(text: str) -> list[dict]:
    """Top-level table containers, including uncaptained tabular/longtable."""
    pattern = re.compile(r'\\(begin|end)\{(table\*?|longtable|tabular\*?)\}')
    stack, result, beginning = [], [], None
    for match in pattern.finditer(text):
        kind, env = match.groups()
        if kind == 'begin':
            if not stack:
                beginning = match.start()
            stack.append(env)
        else:
            if not stack or stack.pop() != env:
                raise ValueError('unbalanced table environment')
            if not stack:
                body = text[beginning:match.end()]
                result.append({
                    'begin_line': text.count('\n', 0, beginning) + 1,
                    'end_line': text.count('\n', 0, match.end()) + 1,
                    'body_sha256': sha(body.encode('utf-8')),
                    'caption': commands(body, 'caption'),
                    'labels': commands(body, 'label'),
                    'source_rows': [s.strip() for s in body.splitlines()
                                    if '&' in s and not s.lstrip().startswith('%')],
                })
    if stack:
        raise ValueError('unclosed table environment')
    return result


def build(repo: Path) -> dict:
    ledger = json.loads((repo / 'validation/MASTER_CLAIM_LEDGER.json').read_text(encoding='utf-8'))
    records = []
    sources = {}
    for name in FILES + APPENDIX_FILES:
        directory = 'chapters/' if name in FILES else 'appendix_tables/'
        relative = 'paper/source/' + directory + name
        data = (repo / relative).read_bytes()
        sources[relative] = sha(data)
        text = data.decode('utf-8')
        headings = [(m.start(), m.group(1), group(text, m.end() - 1)) for m in
                    re.finditer(r'\\(section|subsection|subsubsection)\{', text)]
        fileclaims = [r for r in ledger['claims'] if
                      r.get('tex_file') == directory + name or
                      directory + name in r.get('final_display_locations', [])]
        for index, table in enumerate(tables(text), 1):
            offset = sum(len(s) for s in text.splitlines(keepends=True)[:table['begin_line'] - 1])
            hierarchy = {}
            for position, level, heading in headings:
                if position > offset:
                    break
                hierarchy[level] = heading
                if level == 'section':
                    hierarchy.pop('subsection', None)
                    hierarchy.pop('subsubsection', None)
                elif level == 'subsection':
                    hierarchy.pop('subsubsection', None)
            table.update(id=name.removesuffix('.tex') + ':table:' + str(index),
                         source_file=relative, headings=hierarchy,
                         execution_status='not_run', replay_rows=[],
                         source_authorities=sorted({r['bundled_source'] for r in fileclaims
                                                    if r.get('bundled_source')}),
                         coverage_note='Complete source-table census. Per-table replay-row mapping is explicit; an empty mapping never means reproduced.')
            records.append(table)
    return {'schema': 'score_replay_table_inventory_v1',
            'baseline': '5374140404130421d878152a952024b43c1fbcc4',
            'execution_status': 'inventory_only_no_scoring',
            'source_sha256': sources, 'tables': records,
            'counts': {'tables': len(records), 'source_files': len(FILES + APPENDIX_FILES)},
            'excluded_completed_source_files': list(EXCLUDED),
            'scope': 'Every table container in the requested chapters, including parameter/design/diagnostic tables. A table census is not a likelihood replay. Already-replayed S04B and S05 scope is mapped separately; historical F/S01 remains withdrawn.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    value = build(repo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps(value['counts']))


if __name__ == '__main__':
    main()
