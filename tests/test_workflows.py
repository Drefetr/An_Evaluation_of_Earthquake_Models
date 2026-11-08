"""Bounded public-workflow checks; no catalogue downloads or scientific runs."""
import hashlib
import importlib.util
from html.parser import HTMLParser
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


class DocumentLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set()

    def handle_starttag(self, tag, attributes):
        attributes=dict(attributes)
        if 'id' in attributes:self.ids.add(attributes['id'])
        self.links.extend(attributes[key] for key in ('href','src') if attributes.get(key))


class PublicWorkflows(unittest.TestCase):
    def assert_site_links(self, site):
        for page in sorted(site.glob('*.html')):
            parser=DocumentLinks();parser.feed(page.read_text(encoding='utf-8'))
            for link in parser.links:
                target=urlsplit(link)
                if target.scheme or target.netloc:continue
                destination=(page.parent/unquote(target.path)).resolve() if target.path else page
                self.assertTrue(destination.is_file(), f'{page.name}: {link}')
                if target.fragment and destination.suffix=='.html':
                    linked=DocumentLinks();linked.feed(destination.read_text(encoding='utf-8'))
                    self.assertIn(unquote(target.fragment),linked.ids,f'{page.name}: {link}')

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
            # Match a clean reader/CI invocation: ignore PYTHONPATH and do not
            # rely on the repository being the subprocess working directory.
            result = subprocess.run(
                [sys.executable, '-E', '-B', str(ROOT/'website/build_site.py'),
                 '--output', str(output)], cwd=temp, capture_output=True,
                text=True, encoding='utf-8', errors='replace',
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            metadata = json.loads((output/'documents.json').read_text(encoding='utf-8'))
            self.assertEqual(len(metadata['documents']), 2)
            self.assertEqual(metadata['bundle_kind'],'self_contained_deployment')
            downloads = {record['sha256'] for record in metadata['documents']}
            self.assertEqual(downloads, set(before))
            for record in metadata['documents']:
                self.assertTrue(record['path'].startswith('downloads/'))
                self.assertEqual(digest(output/record['path']), record['sha256'])
            self.assert_site_links(output)
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
            source = isolated/'new-bundle';source.mkdir();(source/'downloads').mkdir()
            records=[]
            for path,name,content in [('paper/manuscript_unified.pdf','final-monograph.pdf',b'untouched monograph'),
                                      ('companion/lay_guide_to_the_research.pdf','research-guide.pdf',b'untouched guide')]:
                document=isolated/path;document.parent.mkdir(exist_ok=True);document.write_bytes(content)
                (source/'downloads'/name).write_bytes(content)
                records.append({'path':'downloads/'+name,'repository_source':path,'sha256':digest(document),'bytes':len(content)})
            (source/'index.html').write_text('<a href="downloads/final-monograph.pdf">Manuscript</a><a href="downloads/research-guide.pdf">Guide</a>')
            (source/'documents.json').write_text(json.dumps({'documents':records,'bundle_kind':'self_contained_deployment'}))
            builder.install_bundle(source)
            self.assertIn('href="../../paper/manuscript_unified.pdf"',(current/'index.html').read_text())
            self.assertFalse((current/'stale.pdf').exists())
            self.assertFalse((current/'downloads').exists())
            self.assertEqual((isolated/'paper/manuscript_unified.pdf').read_bytes(), b'untouched monograph')
            self.assertEqual((isolated/'companion/lay_guide_to_the_research.pdf').read_bytes(), b'untouched guide')
            self.assertTrue((source/'index.html').exists())
            self.assertTrue((source/'downloads/research-guide.pdf').exists())
            self.assertFalse((website/'site.previous-build').exists())
            metadata=json.loads((current/'documents.json').read_text())
            self.assertEqual(metadata['bundle_kind'],'repository_preview')
            for record in metadata['documents']:
                self.assertEqual(digest(current/record['path']),record['sha256'])
            # An ignored candidate cannot replace the installed preview, even
            # when its bytes happen to match the accepted canonical document.
            candidate=isolated/'build/unaccepted.pdf';candidate.parent.mkdir()
            candidate.write_bytes((isolated/'paper/manuscript_unified.pdf').read_bytes())
            records[0]['repository_source']='build/unaccepted.pdf'
            (source/'documents.json').write_text(json.dumps({'documents':records}))
            before=(current/'index.html').read_bytes()
            with self.assertRaisesRegex(ValueError,'canonical'):
                builder.install_bundle(source)
            self.assertEqual((current/'index.html').read_bytes(),before)
            self.assertFalse((website/'site.next-build').exists())

    def test_repository_preview_links_canonical_documents_without_copies(self):
        site=ROOT/'website/site';self.assert_site_links(site)
        self.assertEqual(list(site.rglob('*.pdf')),[])
        metadata=json.loads((site/'documents.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['bundle_kind'],'repository_preview')
        for record in metadata['documents']:
            document=(site/record['path']).resolve()
            self.assertEqual(document,ROOT/record['repository_source'])
            self.assertEqual(digest(document),record['sha256'])

    def test_canonical_figure_payload_has_only_source_referenced_formats(self):
        referenced=set()
        for source in (ROOT/'paper').rglob('*.tex'):
            tex=re.sub(r'(?m)(?<!\\)%.*$','',source.read_text(encoding='utf-8'))
            referenced.update(Path(name).name for name in re.findall(r'\\includegraphics\*?(?:\[[^\]]*\])?\{([^}]+)\}',tex))
        assets={p.name for p in (ROOT/'paper/figures').iterdir() if p.suffix in {'.pdf','.png','.svg'}}
        self.assertEqual(assets,referenced)

    def test_figure_install_omits_unreferenced_preview_formats(self):
        spec=importlib.util.spec_from_file_location('figure_builder_for_test',ROOT/'scripts/rebuild_review_figures.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='figure-install-') as temp:
            isolated=Path(temp);builder.ROOT=isolated;builder.FIG=isolated/'exports';builder.FIG.mkdir()
            figures=isolated/'paper/figures';figures.mkdir(parents=True)
            source=isolated/'paper/source';source.mkdir()
            (source/'main.tex').write_text(r'\includegraphics{used.pdf}')
            builder.outputs=[]
            for name in ['used.pdf','used.png','historical_profile.pdf','historical_profile.png']:
                (builder.FIG/name).write_bytes(name.encode())
                builder.outputs.append({'path':name})
            installed=builder.install_figures()
            self.assertEqual(installed,['used.pdf'])
            self.assertEqual({p.name for p in figures.iterdir()},{'used.pdf'})

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
