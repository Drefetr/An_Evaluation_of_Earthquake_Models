"""Publication controls against disposable local bare Git remotes only."""
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages_publisher', ROOT/'scripts/publish_pages.py')
pages = importlib.util.module_from_spec(spec);spec.loader.exec_module(pages)


class PagesPublish(unittest.TestCase):
    def git(self, *arguments, repository=None, data=None):
        result = subprocess.run(['git', '-C', str(repository or self.repo), *map(str, arguments)],
                                input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        return result.stdout.decode('utf-8').strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pages-publish-')
        self.addCleanup(self.temp.cleanup);base = Path(self.temp.name)
        self.remote = base/'remote.git';self.remote.mkdir()
        self.repo = base/'source';self.repo.mkdir()
        self.git('init', '--bare', repository=self.remote)
        self.git('init');self.git('checkout', '-b', 'main')
        self.git('config', 'user.name', 'Local publication test')
        self.git('config', 'user.email', 'pages-test@example.invalid')
        (self.repo/'README.md').write_text('Research source stays on main.\n')
        (self.repo/'index.html').write_text('Existing source index stays unchanged.\n')
        (self.repo/'.gitignore').write_text('build/\n')
        self.git('add', '.');self.git('commit', '-m', 'Source baseline')
        self.git('remote', 'add', 'origin', self.remote)
        self.git('push', 'origin', 'HEAD:refs/heads/main')
        self.source = self.git('rev-parse', 'HEAD')
        self.bundle = self.repo/'build/site';self.bundle.mkdir(parents=True)
        (self.bundle/'index.html').write_text('<h1>Generated research site</h1>')
        (self.bundle/'.nojekyll').write_text('')
        (self.bundle/'a note.txt').write_text('Static filenames with spaces survive publication.\n')
        (self.bundle/'downloads').mkdir();records = []
        for name, raw in [('monograph.pdf', b'fixed document fixture'), ('guide.pdf', b'fixed guide fixture')]:
            (self.bundle/'downloads'/name).write_bytes(raw)
            records.append({'path':'downloads/'+name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
        (self.bundle/'documents.json').write_text(json.dumps({'bundle_kind':'self_contained_deployment','documents':records}))
        self.snapshot_source()

    def snapshot_source(self):
        self.before_head = self.git('rev-parse', 'HEAD')
        self.before_index = (self.repo/'.git/index').read_bytes()
        self.before_files = {p.name:p.read_bytes() for p in self.repo.iterdir() if p.is_file()}

    def assert_source_unchanged(self):
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.before_head)
        self.assertEqual(self.git('rev-parse', 'refs/heads/main'), self.before_head)
        self.assertEqual((self.repo/'.git/index').read_bytes(), self.before_index)
        self.assertEqual({p.name:p.read_bytes() for p in self.repo.iterdir() if p.is_file()}, self.before_files)

    def publish(self, name='published'):
        return pages.publish(self.bundle, self.source, self.repo/'build'/name, repository=self.repo)

    def publication_tip(self):
        return self.git('rev-parse', pages.PUBLISH_REF, repository=self.remote)

    def test_publishes_site_at_branch_root_and_exports_exact_same_tree(self):
        result = self.publish();self.assertTrue(result['changed'])
        tip = self.publication_tip();self.assertEqual(tip,result['published_sha'])
        self.assertEqual(self.git('rev-parse', tip+'^{tree}', repository=self.remote),result['published_tree'])
        names = self.git('ls-tree','-r','--name-only',tip,repository=self.remote).splitlines()
        self.assertIn('index.html',names);self.assertIn('.nojekyll',names)
        self.assertNotIn('README.md',names);self.assertNotIn('build/site/index.html',names)
        exported = self.repo/'build/published'
        self.assertEqual(set(names), {p.relative_to(exported).as_posix() for p in exported.rglob('*') if p.is_file()})
        for name in names:
            remote = subprocess.check_output(['git','-C',str(self.remote),'show',tip+':'+name])
            self.assertEqual(remote,(exported/name).read_bytes())
        receipt=json.loads((exported/pages.RECEIPT).read_text())
        self.assertEqual(receipt['source_sha'],self.source)
        self.assertEqual(receipt['source_ref'],'refs/heads/main')
        self.assertEqual(receipt['content_tree'],result['content_tree'])
        self.assert_source_unchanged()

    def test_identical_source_and_bundle_are_idempotent(self):
        first=self.publish();second=self.publish('published-again')
        self.assertFalse(second['changed']);self.assertEqual(first['published_sha'],second['published_sha'])
        self.assertEqual(self.publication_tip(),first['published_sha'])
        self.assert_source_unchanged()

    def test_pages_tar_preserves_dotfiles_and_exact_published_file_bytes(self):
        artifact=Path(self.temp.name)/'artifact.tar';output=self.repo/'build/tar-export'
        result=pages.publish(self.bundle,self.source,output,repository=self.repo,artifact=artifact)
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),result['artifact_sha256'])
        names=self.git('ls-tree','-r','--name-only',result['published_sha'],repository=self.remote).splitlines()
        with tarfile.open(artifact,'r:') as archive:
            self.assertEqual(set(archive.getnames()),set(names))
            self.assertIn('.nojekyll',archive.getnames());self.assertIn('publication.json',archive.getnames())
            for member in archive.getmembers():
                self.assertTrue(member.isfile());self.assertFalse(member.issym() or member.islnk())
                raw=archive.extractfile(member).read()
                published=subprocess.check_output(['git','-C',str(self.remote),'show',result['published_sha']+':'+member.name])
                self.assertEqual(raw,published);self.assertEqual(raw,(output/member.name).read_bytes())
        again=Path(self.temp.name)/'artifact-again.tar'
        repeated=pages.publish(self.bundle,self.source,self.repo/'build/tar-export-again',
                               repository=self.repo,artifact=again)
        self.assertFalse(repeated['changed'])
        self.assertEqual(artifact.read_bytes(),again.read_bytes())
        self.assert_source_unchanged()

    def test_existing_or_unsafe_tar_paths_are_rejected_before_publication(self):
        existing=self.repo/'build/existing.tar';existing.write_bytes(b'prior artifact')
        output=self.repo/'build/tar-export'
        for path in [existing,self.bundle/'artifact.tar',output/'artifact.tar',output,self.repo/'artifact.tar']:
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'artifact'):
                pages.publish(self.bundle,self.source,output,repository=self.repo,artifact=path)
            self.assertNotIn(pages.PUBLISH_REF,pages.remote_refs(self.repo,'origin'))
            self.assertFalse(output.exists())
        self.assertEqual(existing.read_bytes(),b'prior artifact')
        self.assert_source_unchanged()

    def test_official_artifact_allows_only_empty_branch_marker_omission(self):
        self.publish();output=self.repo/'build/published'
        artifact=Path(self.temp.name)/'official.tar'
        with tarfile.open(artifact,'w') as archive:
            for name in ['.', 'downloads']:
                entry=tarfile.TarInfo('./'+name);entry.type=tarfile.DIRTYPE
                archive.addfile(entry)
            for path in output.rglob('*'):
                if path.is_file() and path.name!='.nojekyll':
                    archive.add(path,arcname='./'+path.relative_to(output).as_posix(),recursive=False)
        result=pages.verify_artifact(artifact,output)
        self.assertEqual(result['omitted_branch_markers'],['.nojekyll'])
        self.assertEqual(result['verified_public_files'],len([p for p in output.rglob('*') if p.is_file()])-1)
        self.assert_source_unchanged()

    def test_official_artifact_rejects_missing_changed_extra_and_link_members(self):
        self.publish();output=self.repo/'build/published'
        files={p.relative_to(output).as_posix():p.read_bytes() for p in output.rglob('*') if p.is_file()}
        artifact=Path(self.temp.name)/'invalid.tar'
        for variant in ['missing_pdf','changed_pdf','extra','duplicate','symlink','traversal']:
            with self.subTest(variant=variant):
                changed=dict(files)
                if variant=='missing_pdf':changed.pop('downloads/guide.pdf')
                if variant=='changed_pdf':changed['downloads/guide.pdf']=b'changed content'
                if variant=='extra':changed['unexpected.txt']=b'extra'
                with tarfile.open(artifact,'w') as archive:
                    for name,raw in changed.items():
                        entry=tarfile.TarInfo('./'+name);entry.size=len(raw)
                        archive.addfile(entry,io.BytesIO(raw))
                    if variant in ['duplicate','symlink','traversal']:
                        name={'duplicate':'./index.html','symlink':'./link','traversal':'../escape'}[variant]
                        entry=tarfile.TarInfo(name)
                        if variant=='symlink':entry.type=tarfile.SYMTYPE;entry.linkname='index.html'
                        archive.addfile(entry)
                with self.assertRaises(ValueError):pages.verify_artifact(artifact,output)
        (output/'.nojekyll').write_bytes(b'nonempty marker')
        with self.assertRaisesRegex(ValueError,'complete exported publication'):
            pages.verify_artifact(artifact,output)
        self.assert_source_unchanged()

    def test_updates_are_children_of_previous_publication_without_source_mutation(self):
        first=self.publish()
        (self.repo/'notes.md').write_text('Accepted source revision.\n')
        self.git('add','notes.md');self.git('commit','-m','Source revision')
        self.git('push','origin','HEAD:refs/heads/main');self.source=self.git('rev-parse','HEAD')
        (self.bundle/'index.html').write_text('<h1>Updated generated site</h1>')
        self.snapshot_source();second=self.publish('published-update')
        self.assertTrue(second['changed'])
        self.assertEqual(self.git('rev-parse',second['published_sha']+'^',repository=self.remote),first['published_sha'])
        self.assert_source_unchanged()

    def test_stale_source_main_is_rejected(self):
        tree=self.git('rev-parse',self.source+'^{tree}')
        newer=self.git('commit-tree',tree,'-p',self.source,data=b'A concurrent main revision\n')
        self.git('push','origin',newer+':refs/heads/main')
        with self.assertRaisesRegex(RuntimeError,'current remote main'):
            self.publish()
        self.assertNotIn(pages.PUBLISH_REF,pages.remote_refs(self.repo,'origin'))
        self.assert_source_unchanged()

    def test_main_cannot_be_selected_as_publication_target(self):
        with patch.object(pages,'PUBLISH_REF',pages.SOURCE_REF):
            with self.assertRaisesRegex(ValueError,'cannot be the source branch'):
                self.publish()
        self.assert_source_unchanged()
        self.assertNotIn(pages.PUBLISH_REF,pages.remote_refs(self.repo,'origin'))

    def race_before_push(self, initial):
        original=pages.git;racer={}
        def intervening(repository,*arguments,**kwargs):
            if arguments[0]=='push' and not racer:
                old=self.source if initial else self.publication_tip()
                tree=self.git('rev-parse',old+'^{tree}')
                racer['commit']=self.git('commit-tree',tree,'-p',old,data=b'Concurrent publication\n')
                self.git('push','origin',racer['commit']+':'+pages.PUBLISH_REF)
            return original(repository,*arguments,**kwargs)
        with patch.object(pages,'git',side_effect=intervening):
            with self.assertRaisesRegex(RuntimeError,'git push failed'):
                self.publish('racing')
        self.assertEqual(self.publication_tip(),racer['commit'])
        self.assertFalse((self.repo/'build/racing').exists())
        self.assert_source_unchanged()

    def test_expected_tip_lease_rejects_concurrent_publication(self):
        (self.bundle/'index.html').write_text('<h1>First version</h1>')
        self.publish('first')
        # Change the bundle so this attempt requires a real branch update.
        (self.bundle/'index.html').write_text('<h1>Second version</h1>')
        self.race_before_push(initial=False)

    def test_empty_tip_lease_rejects_concurrent_branch_creation(self):
        self.race_before_push(initial=True)

    def test_repository_preview_and_tampered_download_are_rejected(self):
        metadata=self.bundle/'documents.json';original=json.loads(metadata.read_text())
        for variant in ['repository_preview','wrong_hash']:
            changed=json.loads(json.dumps(original))
            if variant=='wrong_hash':changed['documents'][0]['sha256']='0'*64
            else:changed['bundle_kind']=variant
            metadata.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):self.publish(variant)
            self.assertNotIn(pages.PUBLISH_REF,pages.remote_refs(self.repo,'origin'))
        self.assert_source_unchanged()

    def test_cli_rejects_pr_and_nonmain_workflow_contexts(self):
        for event,ref in [('pull_request','refs/heads/main'),('workflow_dispatch','refs/heads/feature')]:
            with self.subTest(event=event,ref=ref), patch.dict(os.environ, GITHUB_ACTIONS='true',
                    GITHUB_EVENT_NAME=event,GITHUB_REF=ref,GITHUB_SHA=self.source),redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    pages.main(['--bundle',str(self.bundle),'--source-sha',self.source,
                                '--output',str(self.repo/'build/blocked')])
                self.assertEqual(caught.exception.code,2)
        self.assert_source_unchanged()


if __name__=='__main__':unittest.main()
