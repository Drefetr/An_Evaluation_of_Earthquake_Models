"""A staged companion can install only after canonical PDF and HTML identity."""
from pathlib import Path
import importlib.util,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]

class StagedCompanionPublication(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('staged_companion_builder',ROOT/'website/build_site.py')
        self.builder=importlib.util.module_from_spec(spec)
        import sys
        sys.path.insert(0,str(ROOT/'website'))
        try:spec.loader.exec_module(self.builder)
        finally:sys.path.pop(0)
        self.temp=tempfile.TemporaryDirectory(prefix='staged-guide-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.builder.ROOT=self.root
        self.canonical=self.root/'companion';self.staged=self.root/'build/guide'
        for directory in (self.canonical,self.staged):
            directory.mkdir(parents=True)
            (directory/'lay_guide_to_the_research.pdf').write_bytes(b'accepted PDF bytes')
            (directory/'lay_guide_to_the_research.html').write_bytes(b'accepted HTML bytes')

    def test_identical_staged_pair_binds_canonical_guide(self):
        source=self.builder.companion_repository_source(self.staged,True)
        self.assertEqual(source,self.canonical/'lay_guide_to_the_research.pdf')
        self.assertEqual((self.staged/source.name).read_bytes(),source.read_bytes())

    def test_changed_staged_pdf_or_html_is_rejected(self):
        for name in ('lay_guide_to_the_research.pdf','lay_guide_to_the_research.html'):
            with self.subTest(name=name):
                original=(self.staged/name).read_bytes();(self.staged/name).write_bytes(b'unreviewed candidate')
                with self.assertRaisesRegex(ValueError,'canonical PDF and HTML'):
                    self.builder.companion_repository_source(self.staged,True)
                self.assertNotEqual((self.staged/name).read_bytes(),(self.canonical/name).read_bytes())
                (self.staged/name).write_bytes(original)

    def test_noninstall_build_retains_actual_staged_source(self):
        self.assertEqual(self.builder.companion_repository_source(self.staged,False),self.staged/'lay_guide_to_the_research.pdf')

if __name__=='__main__':unittest.main()
