"""Control-plane tests use fake workers, never model jobs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'arena'))
from arena_service import ArenaService


class FakeRunner:
    def __init__(self):
        self.current = {'status': 'idle', 'id': None}
        self.starts = []
        self.stops = 0

    def status(self):
        return dict(self.current)

    def start(self, task, rubric='', agents=16, wave=3, run_id=None):
        self.starts.append((task, rubric, run_id))
        self.current = {'status': 'running', 'id': run_id, 'completed': 0, 'total': 33}
        return self.status()

    def stop(self):
        self.stops += 1
        self.current['status'] = 'cancelled'
        return self.status()


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runner = FakeRunner()
        self.service = ArenaService(self.root, self.runner)

    def test_duplicate_start_is_durable_and_exact(self):
        one = self.service.start_run('  Question?  ', '', 'request-1')
        again = self.service.start_run('  Question?  ', '', 'request-1')
        self.assertEqual(one['id'], again['id'])
        self.assertEqual(self.runner.starts[0][:2], ('  Question?  ', ''))
        reopened = ArenaService(self.root, self.runner)
        self.assertEqual(reopened.start_run('  Question?  ', '', 'request-1')['id'], one['id'])
        self.assertEqual(len(self.runner.starts), 1)

    def test_changed_request_rejected(self):
        self.service.start_run('question', '', 'request-1')
        with self.assertRaises(ValueError):
            self.service.start_run('changed', '', 'request-1')
        self.assertEqual(len(self.runner.starts), 1)

    def test_concurrent_duplicate_starts_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.service.start_run('q', 'r', 'same'), range(4)))
        self.assertEqual(len({r['id'] for r in results}), 1)
        self.assertEqual(len(self.runner.starts), 1)

    def test_busy_and_stale_stop(self):
        run = self.service.start_run('q', '', 'first')
        with self.assertRaises(ValueError):
            self.service.start_run('q2', '', 'second')
        with self.assertRaises(ValueError):
            self.service.stop_run('stale')
        self.assertEqual(self.runner.stops, 0)
        self.assertEqual(self.service.stop_run(run['id'])['status'], 'cancelled')

    def test_failed_launch_reservation_never_retries(self):
        def crash(*args, **kwargs):
            raise RuntimeError('simulated crash after reservation')
        self.runner.start = crash
        with self.assertRaises(RuntimeError):
            self.service.start_run('q', '', 'crash')
        new_runner = FakeRunner()
        reopened = ArenaService(self.root, new_runner)
        self.assertEqual(reopened.start_run('q', '', 'crash')['status'], 'interrupted')
        self.assertEqual(new_runner.starts, [])
        with self.assertRaises(ValueError):
            reopened.start_run('new question', '', 'new')

    def test_invalid_inputs_and_traversal(self):
        for q, r, key in [('', '', 'x'), ('q', [], 'x'), ('q', '', '../x'), ('q', '', ''), ('q', '', True)]:
            with self.assertRaises(ValueError):
                self.service.start_run(q, r, key)
        for key in ('../x', 'a/b', '.', 'a\\b'):
            with self.assertRaises(ValueError):
                self.service.get_run_status(key)
        self.assertEqual(self.runner.starts, [])

    def test_historical_status_does_not_change_active_run(self):
        old = self.root / 'old'
        old.mkdir()
        (old / 'runner-status.json').write_text(json.dumps({'id': 'old', 'status': 'complete', 'completed': 33, 'total': 33, 'run_dir': 'private'}))
        active = self.service.start_run('q', '', 'active')
        result = self.service.get_run_status('old')
        self.assertEqual(result['status'], 'complete')
        self.assertNotIn('run_dir', result)
        self.assertEqual(self.runner.status()['id'], active['id'])

    def test_empty_view_never_starts_workers(self):
        result = self.service.open_arena()
        self.assertEqual(result['answers'], {})
        self.assertEqual(self.runner.starts, [])

    def test_redirected_database_rejected(self):
        link = self.root / 'linked.sqlite3'
        target = self.root / 'target'
        target.write_text('not a database')
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest('Symlink privilege unavailable')
        with self.assertRaises(ValueError):
            ArenaService(self.root, self.runner, database=link)


if __name__ == '__main__':
    unittest.main()
