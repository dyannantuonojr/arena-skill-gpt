"""Package validation tests. All receipts here are synthetic software fixtures.

They do not represent an Archify execution or evidence of renderer identity.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / 'skills' / 'arena' / 'arena_artifacts.py'


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.exists(), 'artifact validator has not been implemented')
        spec = importlib.util.spec_from_file_location('arena_artifacts', PATH)
        self.art = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.art)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = {'dir': str(self.root), 'agents': {}, 'champion': None,
                      'rounds': [{'matches': [{'a': 'a001', 'b': 'a002'}], 'bye': None}]}
        for aid in ('a001', 'a002', 'a003'):
            solution = self.root / (aid + '.md')
            solution.write_bytes(b'# Frozen answer\r\nOriginal bytes\n')
            self.state['agents'][aid] = {'solution': str(solution)}
        self.package = self.root / 'artifacts' / 'finalists' / 'a001'
        (self.package / 'review').mkdir(parents=True)
        (self.package / 'implementation.md').write_text('# Implementation\nBuild the proposed system.', encoding='utf-8')
        (self.package / 'candidate.json').write_text('{"type":"workflow"}', encoding='utf-8')
        (self.package / 'diagram.html').write_text('<!doctype html><html>Diagram</html>', encoding='utf-8')
        self.receipt_path = self.package / 'review' / 'diagram.finalize-summary.json'
        self.receipt = {'ok': True, 'command': 'finalize', 'status': 'pass', 'type': 'workflow',
                        'gates': {g: 'pass' for g in ('validate', 'deliver', 'check', 'browser-check')},
                        'specification': {'path': str(self.package / 'candidate.json'), 'sha256': self.digest(self.package / 'candidate.json')},
                        'artifact': {'path': str(self.package / 'diagram.html'), 'sha256': self.digest(self.package / 'diagram.html')}}
        self.write_receipt()

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt), encoding='utf-8')

    def accept(self):
        metadata = self.art.accept_package(self.state, 'a001')
        self.state['finalist_packages'] = {'a001': metadata}
        return metadata

    def test_accepted_packet_is_valid_without_state_or_solution_mutation(self):
        before = copy.deepcopy(self.state)
        metadata = self.art.accept_package(self.state, 'a001')
        self.assertEqual(self.state, before)
        self.assertEqual(set(metadata), {'directory', 'solution_sha256', 'guide_sha256', 'candidate_sha256', 'diagram_sha256', 'receipt_sha256', 'manifest_sha256'})
        self.assertEqual(metadata['directory'], str(self.package))
        self.assertEqual(metadata['solution_sha256'], self.digest(Path(self.state['agents']['a001']['solution'])))
        manifest = self.package / 'manifest.json'
        self.assertEqual(metadata['manifest_sha256'], self.digest(manifest))
        self.assertEqual(json.loads(manifest.read_text()), {k: v for k, v in metadata.items() if k != 'manifest_sha256'})
        self.state['finalist_packages'] = {'a001': metadata}
        self.assertTrue(self.art.package_valid(self.state, 'a001'))
        self.assertEqual(self.art.pending_finalists(self.state), ['a002'])

    def test_finalists_require_final_round_without_a_bye(self):
        self.assertEqual(self.art.finalists(self.state), ['a001', 'a002'])
        self.state['rounds'][0]['bye'] = 'a003'
        self.assertEqual(self.art.finalists(self.state), [])
        self.state['rounds'] = [{'matches': [{'a': 'a001', 'b': 'a002'}, {'a': 'a003', 'b': 'a004'}]}]
        self.assertEqual(self.art.finalists(self.state), [])
        self.state['rounds'] = []
        self.state['champion'] = 'a003'
        self.assertEqual(self.art.finalists(self.state), ['a003'])
        self.state['champion'] = None
        self.state['agents'] = {'a001': self.state['agents']['a001']}
        self.assertEqual(self.art.finalists(self.state), ['a001'])

    def test_stale_source_or_any_package_file_invalidates_acceptance(self):
        for name in ('solution', 'implementation.md', 'candidate.json', 'diagram.html', 'review/diagram.finalize-summary.json', 'manifest.json'):
            with self.subTest(name=name):
                self.accept()
                path = Path(self.state['agents']['a001']['solution']) if name == 'solution' else self.package / name
                original = path.read_bytes()
                path.write_bytes(original + b'\nchanged')
                self.assertFalse(self.art.package_valid(self.state, 'a001'))
                self.assertIn('a001', self.art.pending_finalists(self.state))
                path.write_bytes(original)

    def test_receipt_must_pass_all_native_finalize_gates(self):
        for field, bad in (('ok', False), ('ok', 1), ('command', 'render'), ('status', 'fail'), ('type', 'mermaid')):
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = bad
                self.write_receipt()
                with self.assertRaises(self.art.ArtifactError):
                    self.art.accept_package(self.state, 'a001')
                self.receipt[field] = original
        for gate in ('validate', 'deliver', 'check', 'browser-check'):
            self.receipt['gates'][gate] = 'fail'
            self.write_receipt()
            with self.assertRaises(self.art.ArtifactError):
                self.art.accept_package(self.state, 'a001')
            self.receipt['gates'][gate] = 'pass'

    def test_wrong_candidate_html_hash_or_path_is_rejected(self):
        for binding in ('specification', 'artifact'):
            for field, bad in (('sha256', '0' * 64), ('path', str(self.root / 'other'))):
                with self.subTest(binding=binding, field=field):
                    original = self.receipt[binding][field]
                    self.receipt[binding][field] = bad
                    self.write_receipt()
                    with self.assertRaises(self.art.ArtifactError):
                        self.art.accept_package(self.state, 'a001')
                    self.receipt[binding][field] = original

    def test_malformed_receipt_values_are_validation_errors(self):
        for field, bad in (('type', []), ('gates', None), ('specification', []), ('artifact', {'path': ''})):
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = bad
                self.write_receipt()
                with self.assertRaises(self.art.ArtifactError):
                    self.art.accept_package(self.state, 'a001')
                self.receipt[field] = original

    def test_missing_blank_or_malformed_inputs_rejected(self):
        for name in ('implementation.md', 'candidate.json', 'diagram.html', 'review/diagram.finalize-summary.json'):
            path = self.package / name
            original = path.read_bytes()
            path.unlink()
            with self.subTest(missing=name), self.assertRaises(self.art.ArtifactError):
                self.art.accept_package(self.state, 'a001')
            path.write_bytes(original)
        (self.package / 'implementation.md').write_bytes(b' \r\n\t')
        with self.assertRaises(self.art.ArtifactError):
            self.art.accept_package(self.state, 'a001')
        (self.package / 'implementation.md').write_bytes(b'# Guide')
        for malformed in ('{', '[]', 'null'):
            self.receipt_path.write_text(malformed, encoding='utf-8')
            with self.assertRaises(self.art.ArtifactError):
                self.art.accept_package(self.state, 'a001')

    def test_outsiders_and_path_escapes_rejected(self):
        for aid in ('a003', '../a001', 'unknown'):
            with self.subTest(aid=aid), self.assertRaises(self.art.ArtifactError):
                self.art.package_dir(self.state, aid)
            self.assertFalse(self.art.package_valid(self.state, aid))
        original = self.state['agents']['a001']['solution']
        self.state['agents']['a001']['solution'] = str(self.root.parent / 'outside.md')
        with self.assertRaises(self.art.ArtifactError):
            self.art.accept_package(self.state, 'a001')
        self.state['agents']['a001']['solution'] = original
        self.accept()
        self.state['finalist_packages']['a001']['directory'] = str(self.root)
        self.assertFalse(self.art.package_valid(self.state, 'a001'))

    def test_symlinked_canonical_file_rejected(self):
        path = self.package / 'implementation.md'
        target = self.root / 'guide.md'
        target.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(target)
        except OSError:
            self.skipTest('symlink creation is unavailable on this host')
        with self.assertRaises(self.art.ArtifactError):
            self.art.accept_package(self.state, 'a001')


if __name__ == '__main__':
    unittest.main()
