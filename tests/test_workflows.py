"""Bounded public-workflow checks; no catalogue downloads or scientific runs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublicWorkflows(unittest.TestCase):
    def command(self, *arguments, success=True):
        result = subprocess.run(
            [sys.executable, '-B', *map(str, arguments)], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_reader_documentation_local_links(self):
        # Bound historical authorities have original-workspace links; their source
        # locators must not be silently rewritten by a reader-documentation check.
        paths = [ROOT/'README.md', ROOT/'REVIEWER_START_HERE.md',
                 ROOT/'CONTRIBUTING.md', ROOT/'website/README.md',
                 ROOT/'engine/stage2_followup/README.md', ROOT/'validation/README.md']
        paths.extend(sorted((ROOT/'docs').rglob('*.md')))
        missing = []
        for path in paths:
            text = re.sub(r'(?ms)^```.*?^```[^\n]*', '', path.read_text(encoding='utf-8'))
            for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', text):
                target = urlsplit(link.strip('<>'))
                if target.scheme or target.netloc or not target.path:
                    continue
                local = unquote(target.path)
                destination = (ROOT/local.lstrip('/')) if local.startswith('/') else path.parent/local
                if not destination.exists():
                    missing.append(f'{path.relative_to(ROOT)} -> {local}')
        self.assertEqual(missing, [], '\n'.join(missing))

    def test_companion_build_isolated_and_complete(self):
        files = [ROOT/'companion'/name for name in
                 ['lay_guide_to_the_research.pdf', 'lay_guide_to_the_research.html']]
        before = [digest(path) for path in files]
        with tempfile.TemporaryDirectory(prefix='companion-workflow-') as temp:
            output = Path(temp)/'guide'
            self.command('companion/build_guide.py', '--output', output)
            data = json.loads((ROOT/'companion/guide_content.json').read_text(encoding='utf-8'))
            with pymupdf.open(output/files[0].name) as pdf:
                self.assertEqual(len(pdf), len(data['pages']))
                text = re.sub(r'\s+', ' ', '\n'.join(page.get_text() for page in pdf))
                self.assertIn(data['title'], text)
                for page in data['pages'][1:]:
                    self.assertIn(page['title'], text)
            html = (output/files[1].name).read_text(encoding='utf-8')
            self.assertEqual(html.count('<section id="page-'), len(data['pages']))
            self.command('companion/build_guide.py', '--output', output, success=False)
        self.assertEqual(before, [digest(path) for path in files])

    def test_site_build_keeps_source_documents_and_download_identities(self):
        documents = [ROOT/'paper/manuscript_unified.pdf',
                     ROOT/'companion/lay_guide_to_the_research.pdf']
        before = [digest(path) for path in documents]
        with tempfile.TemporaryDirectory(prefix='site-workflow-') as temp:
            output = Path(temp)/'site'
            self.command('website/build_site.py', '--output', output)
            metadata = json.loads((output/'documents.json').read_text(encoding='utf-8'))
            self.assertEqual(len(metadata['documents']), 2)
            downloads = {record['sha256'] for record in metadata['documents']}
            self.assertEqual(downloads, set(before))
            for record in metadata['documents']:
                self.assertEqual(digest(output/record['path']), record['sha256'])
            built = json.loads((output/'findings-data.json').read_text(encoding='utf-8'))
            published = json.loads((ROOT/'website/site/findings-data.json').read_text(encoding='utf-8'))
            self.assertEqual(built['studies'], published['studies'], 'committed findings need regeneration/review')
            node = shutil.which('node')
            self.assertIsNotNone(node, 'Node.js is required for website interaction checks')
            result = subprocess.run([node, 'website/check_interactions.cjs', str(output)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['passed'])
            self.command('website/build_site.py', '--output', output, success=False)
        self.assertEqual(before, [digest(path) for path in documents])

    def test_site_install_replaces_only_generated_bundle(self):
        spec = importlib.util.spec_from_file_location('site_builder_for_test', ROOT/'website/build_site.py')
        builder = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT/'website'))
        try:
            spec.loader.exec_module(builder)
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory(prefix='site-install-') as temp:
            isolated = Path(temp);builder.ROOT = isolated
            website = isolated/'website';website.mkdir()
            current = website/'site';current.mkdir();(current/'stale.pdf').write_bytes(b'old')
            source = isolated/'new-bundle';source.mkdir();(source/'index.html').write_text('accepted')
            document = isolated/'manuscript.pdf';document.write_bytes(b'untouched source')
            builder.install_bundle(source)
            self.assertEqual((current/'index.html').read_text(), 'accepted')
            self.assertFalse((current/'stale.pdf').exists())
            self.assertEqual(document.read_bytes(), b'untouched source')
            self.assertTrue((source/'index.html').exists())
            self.assertFalse((website/'site.previous-build').exists())

    def test_site_rejects_wrong_document_identity_before_output(self):
        metadata = json.loads((ROOT/'website/document_metadata.json').read_text(encoding='utf-8'))
        metadata['document']['sha256'] = '0'*64
        with tempfile.TemporaryDirectory(prefix='invalid-site-') as temp:
            path = Path(temp)/'metadata.json';path.write_text(json.dumps(metadata), encoding='utf-8')
            output = Path(temp)/'site'
            self.command('website/build_site.py', '--metadata', path, '--output', output, success=False)
            self.assertFalse(output.exists())

    def test_figure_generators_refuse_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='figure-workflow-') as temp:
            for script in ['scripts/make_figures.py', 'scripts/rebuild_review_figures.py']:
                with self.subTest(script=script):
                    self.command(script, '--output', temp, success=False)
                    self.assertEqual(list(Path(temp).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
