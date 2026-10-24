"""Runner tests use independent fake CLI outputs; no paid worker jobs are launched."""
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

SKILL = Path(__file__).resolve().parents[1] / 'skills' / 'arena'
sys.path.insert(0, str(SKILL))
import arena_runner as R
import bracket as B


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.runner = R.ArenaRunner(self.directory.name)
        self.runner.capabilities = lambda: {'ready': True}
        self.runner._prefix = ['codex.exe']
        self.runner._node = shutil.which('node')

    def tearDown(self):
        self.runner.stop()
        if self.runner._thread:
            self.runner._thread.join(8)
        self.directory.cleanup()

    def finish(self):
        self.runner._thread.join(12)
        self.assertFalse(self.runner._thread.is_alive(), self.runner.status())
        return self.runner.status()

    def fast_refresh(self, tree=False, force=False):
        state = self.runner._arena
        completed = sum(B._has_output(agent['solution']) for agent in state['agents'].values())
        completed += sum(bool(match.get('winner')) for rd in state['rounds'] for match in rd['matches'])
        completed += len(state.get('finalist_packages', {}))
        self.runner._update(completed=completed, viewer_ready=True)
        # A valid viewer receipt is irrelevant to fake worker execution tests.
        state['require_answer_view'] = False
        B.save_state(state)

    def fake_job(self, job, prompt, run, stop):
        self.assertTrue(Path(prompt).is_absolute())
        self.assertTrue(Path(prompt).is_file())
        if job['kind'] == 'competitor':
            Path(job['outputs'][0]).write_text('A real test answer for ' + job['agent'], encoding='utf-8')
        elif job['kind'] == 'judge':
            keys = ('correctness', 'completeness', 'specificity', 'robustness', 'clarity')
            score = dict.fromkeys(keys, 8)
            score['fatal'] = False
            lower = dict(score, correctness=5)
            value = {'match': job['match'], 'winner': job['a'],
                     'scores': {job['a']: score, job['b']: lower},
                     'standing': {job['a']: [], job['b']: []}, 'reason': 'Test evidence'}
            Path(job['outputs'][0]).write_text(json.dumps(value), encoding='utf-8')
        else:
            Path(job['outputs'][0]).write_text('{}', encoding='utf-8')
        return 0, 'fake worker process completed'

    def accepted(self, state, aid):
        return {'directory': str(Path(state['dir']) / 'artifacts' / aid)}

    def test_full_select_advances_and_requires_two_packages_with_bounded_waves(self):
        self.runner._refresh = self.fast_refresh
        lock = threading.Lock()
        active = [0, 0]
        jobs = []
        def launch(job, *args):
            with lock:
                active[0] += 1
                active[1] = max(active)
                jobs.append(job['id'])
            time.sleep(.015)
            try:
                return self.fake_job(job, *args)
            finally:
                with lock:
                    active[0] -= 1
        self.runner._launcher = launch
        with mock.patch.object(B.artifacts, 'accept_package', side_effect=self.accepted), \
             mock.patch.object(B.artifacts, 'package_valid', side_effect=lambda state, aid: aid in state.get('finalist_packages', {})):
            initial = self.runner.start('Solve this task', 'Exact custom criteria\r\n', agents=16, wave=3)
            self.assertEqual(initial['status'], 'running')
            final = self.finish()
        self.assertEqual(final['status'], 'complete', final)
        self.assertEqual(final['completed'], 33)
        self.assertEqual(final['total'], 33)
        self.assertEqual(len(jobs), 33)
        self.assertLessEqual(active[1], 3)
        state = self.runner._arena
        self.assertEqual(len(state['rounds']), 4)
        self.assertEqual(len(state['finalist_packages']), 2)
        self.assertEqual((Path(state['dir']) / 'user-rubric.md').read_bytes(), b'Exact custom criteria\r\n')
        B.verify_frozen_rubric(state)
        nodes = self.runner._tree_candidate()['nodes']
        ids = {node['id'] for node in nodes}
        self.assertEqual(len(nodes), 32)  # Root, 16 drafts and 15 actual matches.
        self.assertEqual(len(ids), len(nodes))
        self.assertTrue(all(node.get('parent') in ids for node in nodes if node['id'] != 'arena'))

    def test_missing_outputs_retry_twice_and_never_complete(self):
        self.runner._refresh = self.fast_refresh
        calls = []
        self.runner._launcher = lambda job, *args: (calls.append(job['id']) or 0, 'no output')
        self.runner.start('Task', agents=1)
        final = self.finish()
        self.assertEqual(final['status'], 'failed')
        self.assertEqual(len(calls), 2)
        self.assertIn('2 attempts', final['error'])
        ledger = json.loads((Path(final['run_dir']) / 'runner-attempts.json').read_text())
        self.assertEqual([row['status'] for row in ledger['a001.spawn']], ['failed', 'failed'])

    def test_invalid_judge_gets_three_attempts_and_failure_is_persisted(self):
        self.runner._refresh = self.fast_refresh
        judges = []
        def launch(job, *args):
            if job['kind'] == 'judge':
                judges.append(job['id'])
                Path(job['outputs'][0]).write_text('{"match":"wrong"}', encoding='utf-8')
                return 0, 'malformed judgment'
            return self.fake_job(job, *args)
        self.runner._launcher = launch
        self.runner.start('Task', agents=2)
        final = self.finish()
        self.assertEqual(final['status'], 'failed', final)
        self.assertEqual(len(judges), 3)
        self.assertIsNone(self.runner._arena['champion'])
        ledger = json.loads((Path(final['run_dir']) / 'runner-attempts.json').read_text())
        self.assertTrue(all(row['status'] == 'failed' for row in ledger[judges[0]]))

    def test_precreated_drafts_and_future_verdicts_cannot_skip_independent_jobs(self):
        self.runner._refresh = self.fast_refresh
        calls = []
        def launch(job, prompt, run, stop):
            calls.append(job['id'])
            if job['id'] == 'a001.spawn':
                for other in B.phase_jobs(self.runner._arena, 'spawn'):
                    Path(other['outputs'][0]).write_text('Unauthorized precreated answer', encoding='utf-8')
                for rnd in range(1, 5):
                    for index in range(1, 2 ** (4-rnd) + 1):
                        path = Path(B.verdict_out(run, rnd, 'r%d-m%02d' % (rnd, index)))
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text('Unauthorized precreated verdict', encoding='utf-8')
            return self.fake_job(job, prompt, run, stop)
        self.runner._launcher = launch
        with mock.patch.object(B.artifacts, 'accept_package', side_effect=self.accepted), \
             mock.patch.object(B.artifacts, 'package_valid', side_effect=lambda state, aid: aid in state.get('finalist_packages', {})):
            self.runner.start('Task', agents=16, wave=1)
            final = self.finish()
        self.assertEqual(final['status'], 'complete', final)
        self.assertEqual(len(calls), 33)
        self.assertEqual(len(set(calls)), 33)
        self.assertEqual(sum(value.endswith('.spawn') for value in calls), 16)
        self.assertTrue(any('Quarantined' in line for line in final['logs']))

    def test_cross_worker_change_to_accepted_draft_stops_integrity_failure(self):
        self.runner._refresh = self.fast_refresh
        calls = []
        def launch(job, prompt, run, stop):
            calls.append(job['id'])
            if job['id'] == 'a002.spawn':
                original = self.runner._arena['agents']['a001']['solution']
                Path(original).write_text('Another worker replaced the accepted answer', encoding='utf-8')
            return self.fake_job(job, prompt, run, stop)
        self.runner._launcher = launch
        self.runner.start('Task', agents=4, wave=1)
        final = self.finish()
        self.assertEqual(final['status'], 'failed', final)
        self.assertIn('Owned output integrity failure for a001.spawn', final['error'])
        self.assertEqual(calls, ['a001.spawn', 'a002.spawn'])

    def test_artifact_failure_cannot_be_reported_as_completion(self):
        self.runner._refresh = self.fast_refresh
        self.runner._launcher = self.fake_job
        with mock.patch.object(B.artifacts, 'accept_package', side_effect=ValueError('Missing real diagram receipt')):
            self.runner.start('Task', agents=1)
            final = self.finish()
        self.assertEqual(final['status'], 'failed')
        self.assertIn('2 attempts', final['error'])
        self.assertEqual(final['completed'], 1)
        self.assertEqual(self.runner._arena.get('finalist_packages', {}), {})

    def test_stop_prevents_next_wave(self):
        self.runner._refresh = self.fast_refresh
        entered = threading.Event()
        jobs = []
        def launch(job, prompt, run, stop):
            jobs.append(job['id'])
            entered.set()
            stop.wait(5)
            return 1, 'cancelled'
        self.runner._launcher = launch
        self.runner.start('Task', agents=16, wave=3)
        self.assertTrue(entered.wait(3))
        self.runner.stop()
        final = self.finish()
        self.assertEqual(final['status'], 'cancelled')
        self.assertLessEqual(len(jobs), 3)
        self.assertEqual(final['active'], [])

    @unittest.skipUnless(os.name in ('nt', 'posix'), 'Process tree cleanup requires Windows or POSIX')
    def test_stop_kills_real_grandchild_holding_worker_stdout(self):
        self.runner._refresh = self.fast_refresh
        marker = Path(self.directory.name) / 'grandchild.pid'
        script = (
            'import subprocess,sys,time,pathlib; '
            'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(120)"]); '
            'pathlib.Path(%r).write_text(str(child.pid)); '
            'print("grandchild started",flush=True); time.sleep(120)' % str(marker))
        self.runner._worker_command = lambda run: [sys.executable, '-c', script]
        self.runner.start('Task', agents=1, wave=1)
        deadline = time.monotonic() + 5
        while not marker.is_file() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(marker.is_file(), self.runner.status())
        grandchild = int(marker.read_text())
        def alive(pid):
            if os.name == 'nt':
                import ctypes
                api = ctypes.WinDLL('kernel32', use_last_error=True)
                api.OpenProcess.restype = ctypes.c_void_p
                api.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
                api.CloseHandle.argtypes = [ctypes.c_void_p]
                handle = api.OpenProcess(0x1000, False, pid)
                if not handle:
                    return False
                try:
                    code = ctypes.c_ulong()
                    return bool(api.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
                finally:
                    api.CloseHandle(handle)
            try:
                os.kill(pid, 0)
                status = Path('/proc/%d/status' % pid)
                return not status.exists() or '\nState:\tZ' not in status.read_text()
            except ProcessLookupError:
                return False
        self.assertTrue(alive(grandchild))
        started = time.monotonic()
        self.runner.stop()
        final = self.finish()
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(final['status'], 'cancelled', final)
        self.assertFalse(alive(grandchild), 'Owned grandchild survived cancellation')
        self.assertEqual(self.runner._processes, set())

    def test_command_uses_stdin_safe_args_account_auth_and_no_shell(self):
        command = self.runner._worker_command('C:/run with spaces')
        self.assertEqual(command, ['codex.exe', 'exec', '--json', '--ephemeral', '--skip-git-repo-check',
                                  '--sandbox', 'workspace-write', '--cd', 'C:/run with spaces',
                                  '-c', 'agents.enabled=false', '-'])
        with mock.patch.dict(R.os.environ, {'OPENAI_API_KEY': 'secret', 'CODEX_API_KEY': 'secret', 'PATH': 'kept'}):
            environment = R.child_environment()
        self.assertNotIn('OPENAI_API_KEY', environment)
        self.assertNotIn('CODEX_API_KEY', environment)
        self.assertEqual(environment['PATH'], 'kept')
        process = mock.Mock()
        process.stdin = io.BytesIO()
        process.stdout = io.BytesIO(b'{"type":"thread.started"}\n')
        process.wait.return_value = 0
        process.poll.return_value = 0
        self.runner._ledger = {'a001.spawn': [{}]}
        with mock.patch.object(R.subprocess, 'Popen', return_value=process) as popen:
            result = self.runner._execute_job({'id': 'a001.spawn'}, 'brief.md', self.directory.name, threading.Event())
        self.assertEqual(result[0], 0)
        self.assertIs(popen.call_args.kwargs['shell'], False)
        self.assertIs(popen.call_args.kwargs['stdin'], R.subprocess.PIPE)
        self.assertNotIn('OPENAI_API_KEY', popen.call_args.kwargs['env'])

    def test_real_native_tree_and_atomic_viewer_export_are_browsable(self):
        if not self.runner._node:
            self.skipTest('Node is needed for bundled tree renderer')
        entered = threading.Event()
        def launch(job, prompt, run, stop):
            entered.set()
            stop.wait(5)
            return 1, 'cancelled'
        self.runner._launcher = launch
        self.runner.start('Task', agents=2)
        self.assertTrue(entered.wait(8), self.runner.status())
        status = self.runner.status()
        self.assertTrue(status['viewer_ready'])
        run = Path(status['run_dir'])
        self.assertTrue((run / 'visual' / 'arena-tree.html').is_file())
        page = (run / 'viewer' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('a001', page)
        self.assertIn('a002', page)
        self.assertTrue(B.view_ready(self.runner._arena) is False)  # Missing answers remain incomplete.
        (run / 'viewer' / 'index.html').unlink()
        self.runner._refresh()
        self.assertTrue((run / 'viewer' / 'index.html').is_file())
        self.assertTrue(self.runner._published_intact())
        self.runner.stop()
        self.assertEqual(self.finish()['status'], 'cancelled')

    def test_input_validation_and_unique_run_directory(self):
        for values in ({'task': ''}, {'task': 'Task', 'agents': 17}, {'task': 'Task', 'wave': 4}):
            with self.assertRaises(ValueError):
                self.runner.start(**values)
        self.runner._refresh = self.fast_refresh
        self.runner._launcher = lambda *args: (1, 'expected test failure')
        first = self.runner.start('Task', agents=1)
        self.finish()
        second = self.runner.start('Task two', agents=1)
        self.finish()
        self.assertNotEqual(first['run_dir'], second['run_dir'])
        self.assertEqual((Path(first['run_dir']) / 'task.md').read_text().strip(), 'Task')

    def test_deleted_or_corrupt_copied_diagram_is_republished(self):
        run = Path(self.directory.name) / 'export-fixture'
        args = B.build_parser().parse_args(['init', '--dir', str(run), '--task', 'Task', '--agents', '1'])
        B.cmd_init(args)
        state = B.load_state(args)
        solution = Path(state['agents']['a001']['solution'])
        solution.parent.mkdir(parents=True, exist_ok=True)
        solution.write_text('Original answer', encoding='utf-8')
        package = run / 'package'
        # Exporter fixture only; this is never accepted as a real Arena package.
        values = {'implementation.md': '# Guide', 'diagram.html': '<html>Original diagram</html>',
                  'candidate.json': '{}', 'review/diagram.finalize-summary.json': '{}'}
        for name, value in values.items():
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding='utf-8')
        metadata = {'directory': str(package), 'solution_sha256': R.ArenaRunner._file_hash(solution)}
        for name, key in [('implementation.md', 'guide_sha256'), ('diagram.html', 'diagram_sha256'),
                          ('candidate.json', 'candidate_sha256'), ('review/diagram.finalize-summary.json', 'receipt_sha256')]:
            metadata[key] = R.ArenaRunner._file_hash(package / name)
        state['finalist_packages'] = {'a001': metadata}
        self.runner._arena = state
        self.runner._export_fingerprint = None
        self.runner._refresh()
        copied = run / 'viewer' / 'finalists' / 'a001' / 'diagram.html'
        self.assertEqual(copied.read_text(), values['diagram.html'])
        copied.unlink()
        self.runner._refresh()
        self.assertEqual(copied.read_text(), values['diagram.html'])
        copied.write_text('Corrupt exported copy', encoding='utf-8')
        self.runner._refresh()
        self.assertEqual(copied.read_text(), values['diagram.html'])
        self.assertTrue(self.runner._published_intact())

    def test_capabilities_use_chatgpt_login_status_and_remove_api_keys(self):
        runner = R.ArenaRunner(self.directory.name)
        version = mock.Mock(returncode=0, stdout='v22.1.0')
        logged_in = mock.Mock(returncode=0, stdout='Logged in using ChatGPT')
        with mock.patch.object(R, 'discover_program', side_effect=['codex.exe', 'node.exe']), \
             mock.patch.object(R.arena_setup, 'check_bundle', return_value={'status': 'pass'}), \
             mock.patch.object(R.arena_setup, 'probe_browser', return_value={'status': 'executable-found'}), \
             mock.patch.object(R.subprocess, 'run', side_effect=[version, logged_in]) as run, \
             mock.patch.dict(R.os.environ, {'OPENAI_API_KEY': 'excluded', 'CODEX_API_KEY': 'excluded'}):
            capabilities = runner.capabilities()
        self.assertTrue(capabilities['ready'], capabilities)
        self.assertEqual(run.call_args.args[0], ['codex.exe', 'login', 'status'])
        self.assertFalse(run.call_args.kwargs['shell'])
        self.assertNotIn('OPENAI_API_KEY', run.call_args.kwargs['env'])
        self.assertNotIn('CODEX_API_KEY', run.call_args.kwargs['env'])

    def test_cmd_wrapper_uses_node_entrypoint_without_shell(self):
        wrapper = Path(self.directory.name) / 'codex.cmd'
        entry = wrapper.parent / 'node_modules' / '@openai' / 'codex' / 'bin' / 'codex.js'
        entry.parent.mkdir(parents=True)
        entry.write_text('// test stub')
        with mock.patch.object(R, 'discover_program', return_value='node.exe'):
            self.assertEqual(R.codex_prefix(str(wrapper)), ['node.exe', str(entry)])


if __name__ == '__main__':
    unittest.main()
