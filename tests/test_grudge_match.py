"""Grudge Match software fixtures. No model workers are invoked."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/arena'))
import bracket as B
from grudge_match import GrudgeRunner, GrudgeService


class GrudgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runner = GrudgeRunner(self.root)
        self.runner.capabilities = lambda: {'ready': True}
        self.service = GrudgeService(self.root, self.runner)
        self.jobs = []
        self.original_wins = False
        self.invalid = False
        self.tamper = False
        self.evidence_invalid = False
        self.runner._launcher = self.launch
        self.runner._render_artifact = lambda job: None

    def launch(self, job, prompt, run, stop):
        self.jobs.append(job['kind'])
        text = Path(prompt).read_text(encoding='utf-8')
        if job['kind'] != 'artifact':
            self.assertIn(str(Path(run) / 'rubric.md'), text)
        if job['kind'] == 'review':
            self.assertTrue(Path(self.runner._arena['agents']['a001']['solution']).is_file())
        if job['kind'] == 'synthesis':
            self.assertTrue((Path(run)/'review.md').is_file())
            if self.tamper:
                Path(self.runner._arena['agents']['a001']['solution']).write_text('changed')
        if job['kind'] == 'evidence':
            self.assertTrue(Path(self.runner._arena['agents']['a002']['solution']).is_file())
            self.assertIn('original answer:', text)
            self.assertIn('peer review:', text)
            self.assertIn('synthesis:', text)
            from test_grudge_evidence import evidence_fixture
            report = evidence_fixture()
            if self.evidence_invalid: report['claims'][0]['sources'][0]['url']='javascript:bad()'
            Path(job['outputs'][0]).write_text(json.dumps(report), encoding='utf-8')
        if job['kind'] == 'judge':
            self.assertNotIn('review.md', text)
            scores = {label: dict.fromkeys([k for k, _ in B.WEIGHTS], 5) for label in ('x','y')}
            best = self.runner._arena['judge_labels']['a001' if self.original_wins else 'a002']
            scores[best] = dict.fromkeys([k for k, _ in B.WEIGHTS], 9)
            for value in scores.values():
                value['fatal'] = False
            result = {'winner': best, 'scores': scores, 'standing': {'x': [], 'y': []}, 'reason': 'Fixture evidence'}
            if self.invalid:
                result['scores']['x']['correctness'] = 'invalid'
            Path(job['outputs'][0]).write_text(json.dumps(result))
        elif job['kind'] not in ('artifact','evidence'):
            Path(job['outputs'][0]).write_text('# Fixture '+job['kind'])
        return 0, 'software fixture'

    def run_match(self,document_ids=None):
        def accept(state, aid):
            directory = Path(B.artifacts.package_dir(state, aid))
            directory.mkdir(parents=True, exist_ok=True)
            (directory/'manifest.json').write_text('{}')
            return {'directory': str(directory)}
        with mock.patch.object(B.artifacts, 'accept_package', side_effect=accept), mock.patch.object(B.artifacts, 'package_valid', side_effect=lambda s,a: a in s.get('finalist_packages',{})):
            first = self.service.start_run('  Exact task\r\n ', ' Optional rubric\r\n', 'fixture',document_ids=document_ids)
            again = self.service.start_run('  Exact task\r\n ', ' Optional rubric\r\n', 'fixture',document_ids=document_ids)
            self.assertEqual(first['id'], again['id'])
            self.runner._thread.join(12)
            self.assertFalse(self.runner._thread.is_alive())
            return first, self.runner.status(), self.service.open_arena(first['id'])

    def test_six_stages_and_synthesis_winner_only(self):
        first, status, view = self.run_match()
        self.assertEqual(status['status'], 'complete', status)
        self.assertEqual(self.jobs, ['original','review','synthesis','evidence','judge','artifact'])
        self.assertEqual(status['completed'], 6)
        self.assertEqual(status['total'], 6)
        self.assertEqual(view['champion'], 'a002')
        self.assertEqual(B.artifacts.finalists(self.runner._arena), ['a002'])
        self.assertEqual(set(view['answers']), {'a001','review','a002','evidence','judgment'})
        self.assertEqual((self.root/first['id']/'task.md').read_bytes(), b'  Exact task\r\n ')
        self.assertIn('https://example.com/reference', self.service.get_answer(first['id'], 'evidence')['html'])
        self.assertIn('Fixture review', self.service.get_answer(first['id'], 'review')['text'])
        self.assertIn('Fixture evidence', self.service.get_answer(first['id'], 'judgment')['text'])
        self.assertFalse(view['answers']['a001']['package_ready'])

    def test_original_can_win_and_gets_only_package(self):
        self.original_wins = True
        _, status, view = self.run_match()
        self.assertEqual(status['status'], 'complete', status)
        self.assertEqual(view['champion'], 'a001')
        self.assertEqual(B.artifacts.finalists(self.runner._arena), ['a001'])

    def test_invalid_judge_cannot_launch_archify(self):
        self.invalid = True
        _, status, _ = self.run_match()
        self.assertEqual(status['status'], 'failed')
        self.assertNotIn('artifact', self.jobs)

    def test_tampering_stops_before_judge(self):
        self.tamper = True
        with self.assertRaises(ValueError):
            self.run_match()
        self.assertNotIn('judge', self.jobs)

    def test_saved_task_tampering_is_rejected(self):
        first, _, _ = self.run_match()
        (self.root/first['id']/'task.md').write_text('different question', encoding='utf-8')
        with self.assertRaises(ValueError):
            GrudgeService(self.root, GrudgeRunner(self.root)).open_arena(first['id'])

    def test_supporting_snapshots_are_available_and_frozen(self):
        import base64,hashlib
        from supporting_documents import DocumentStore
        store=DocumentStore(self.root/'uploads')
        data=b'Item,Amount\nWidgets,42\n'
        store.upload('a'*32,'budget.csv',len(data),hashlib.sha256(data).hexdigest(),0,base64.b64encode(data).decode())
        self.service.document_store=store
        original_launch=self.runner._launcher
        observed=[]
        def launch(job,prompt,run,stop):
            self.assertTrue((Path(run)/'supporting'/'index.md').is_file())
            self.assertIn('supporting',self.runner._worker_input(prompt,run))
            observed.append(job['kind'])
            return original_launch(job,prompt,run,stop)
        self.runner._launcher=launch
        first,status,view=self.run_match(['a'*32])
        self.assertEqual(status['status'],'complete',status)
        self.assertEqual(len(observed),6)
        self.assertEqual(view['documents'][0]['name'],'budget.csv')
        text=self.service.read_document(first['id'],'a'*32,'CSV!B2')['text']
        self.assertIn('42',text)
        (self.root/first['id']/'supporting'/('a'*32)/'source.csv').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.service.open_arena(first['id'])

    def test_sources_are_alongside_answers_without_rewriting_them(self):
        first, _, _ = self.run_match()
        original = self.service.get_answer(first['id'], 'a001')
        self.assertIn('https://example.com/reference', original['html'])
        self.assertIn('evidence_sha256', original)
        self.assertEqual(original['text'], '# Fixture original')
        review = self.service.get_answer(first['id'], 'review')
        self.assertIn('unverified', review['html'])
        synthesis = self.service.get_answer(first['id'], 'a002')
        self.assertIn('https://example.com/reference', synthesis['html'])
        self.assertEqual(synthesis['text'], '# Fixture synthesis')

    def test_old_five_job_matches_remain_readable(self):
        first, _, _ = self.run_match()
        directory = self.root/first['id']
        state = json.loads((directory/'arena.json').read_text(encoding='utf-8'))
        del state['evidence_version']
        (directory/'arena.json').write_text(json.dumps(state), encoding='utf-8')
        saved = json.loads((directory/'runner-status.json').read_text(encoding='utf-8'))
        saved.update(total=5, completed=5)
        (directory/'runner-status.json').write_text(json.dumps(saved), encoding='utf-8')
        fresh = GrudgeService(self.root, GrudgeRunner(self.root))
        with mock.patch.object(B.artifacts,'package_valid',return_value=False):
            view = fresh.open_arena(first['id'])
        self.assertEqual(view['status']['total'], 5)
        self.assertNotIn('evidence', view['answers'])
        self.assertNotIn('Evidence check', view['tree_svg'])

    def test_bad_evidence_blocks_judge(self):
        self.evidence_invalid = True
        _, status, _ = self.run_match()
        self.assertEqual(status['status'], 'failed')
        self.assertNotIn('judge', self.jobs)
        self.assertNotIn('artifact', self.jobs)

    def test_live_search_does_not_change_arena(self):
        from arena_runner import ArenaRunner
        self.runner._prefix = ['codex.exe']
        plain = ArenaRunner(self.root/'plain')
        plain._prefix = ['codex.exe']
        command = self.runner._worker_command(self.root)
        self.assertIn('--search', command)
        self.assertIn('workspace-write', command)
        self.assertNotIn('--search', plain._worker_command(self.root))

    def test_initial_job_total_is_six(self):
        with mock.patch('threading.Thread.start'):
            status = self.runner.start('Question', run_id='initial')
        self.assertEqual(status['total'], 6)

    def test_idle_open_starts_nothing(self):
        result = self.service.open_arena()
        self.assertEqual(result['status']['status'], 'idle')
        self.assertEqual(self.jobs, [])
        self.assertIn('Original answer', result['tree_svg'])


if __name__ == '__main__':
    unittest.main()
