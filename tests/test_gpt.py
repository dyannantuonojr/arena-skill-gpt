"""Regression tests for the GPT fork's CLI and judging contracts."""
import json
import math
import os
import sys
import subprocess
import shlex
import unittest

from test_bracket import B, BRACKET, TempDir, cli, load, write


class GPTDefaults(TempDir):
    def test_default_run_deals_16_and_plans_31_jobs(self):
        plan = json.loads(self.ok('plan', '--json'))
        self.assertEqual((plan['agents'], plan['rounds'], plan['calls']), (16, 4, 31))
        d = os.path.join(self.tmp, 'default')
        self.ok('init', '--task', 'Find the simplest correct solution.', '--dir', d)
        self.assertEqual(len(load(d)['agents']), 16)
        self.assertEqual(load(d)['wave'], 1)

    def test_cli_rejects_counts_over_16_without_creating_state(self):
        for command in ('plan', 'init'):
            args = [command, '--agents', '17']
            d = os.path.join(self.tmp, command)
            if command == 'init':
                args += ['--task', 't', '--dir', d]
            result = cli(*args)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(os.path.exists(d))

    def test_plan_rejects_nonpositive_wave_without_traceback(self):
        for wave in ('0', '-1'):
            result = cli('plan', '--wave', wave)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_suggested_resume_command_preserves_explicit_run(self):
        d = os.path.join(self.tmp, 'run with spaces')
        self.ok('init', '--mode', 'evolve', '--agents', '2', '--task', 't', '--dir', d)
        output = self.ok('next', '--dir', d)
        command = next(line.split('1. ', 1)[1] for line in output.splitlines() if '1. ' in line)
        if os.name == 'nt':
            invocation = ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command]
        else:
            invocation = shlex.split(command)
        result = subprocess.run(invocation, cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(d, result.stdout)


class StrictJudging(TempDir):
    def verdict(self):
        return {'scores': {a: dict({key: 7 for key, _ in B.WEIGHTS}, fatal=False)
                           for a in ('a001', 'a002')}, 'winner': 'a001'}

    def test_incomplete_scores_cannot_advance_a_pick(self):
        with self.assertRaises(B.ArenaError):
            B.decide({'winner': 'a001'}, 'a001', 'a002')

    def test_invalid_numeric_scores_are_rejected(self):
        for value in (float('nan'), float('inf'), -1, 11, True, '7', None):
            with self.subTest(value=value):
                verdict = self.verdict()
                verdict['scores']['a001']['correctness'] = value
                with self.assertRaises(B.ArenaError):
                    B.decide(verdict, 'a001', 'a002')

    def test_missing_or_nonboolean_fatal_is_rejected(self):
        for value in (None, 'false', 'true', 0, 1):
            verdict = self.verdict()
            verdict['scores']['a001']['fatal'] = value
            with self.assertRaises(B.ArenaError):
                B.decide(verdict, 'a001', 'a002')

    def test_wrong_match_verdict_is_quarantined_and_job_remains(self):
        d = os.path.join(self.tmp, 'wrong-match')
        self.ok('init', '--mode', 'evolve', '--agents', '2', '--task', 't', '--dir', d)
        state = load(d)
        match = state['rounds'][0]['matches'][0]
        verdict = self.verdict()
        verdict['match'] = 'r999-m99'
        path = B.verdict_out(d, 1, match['id'])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, json.dumps(verdict))
        result = cli('collect', '--dir', d)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIsNone(load(d)['rounds'][0]['matches'][0]['winner'])
        self.assertTrue(os.path.exists(path + '.unreadable'))
        self.assertTrue(B.missing_jobs(B.phase_jobs(load(d), 'judge')))

    def test_malformed_standing_attacks_cannot_decide_a_tie(self):
        verdict = self.verdict()
        verdict['standing'] = {'a001': 'STANDING ATTACK', 'a002': []}
        with self.assertRaises(B.ArenaError):
            B.decide(verdict, 'a001', 'a002')

    def test_match_verdict_requires_standing_lists_for_both_sides(self):
        d = os.path.join(self.tmp, 'missing-standing')
        self.ok('init', '--mode', 'evolve', '--agents', '2', '--task', 't', '--dir', d)
        state = load(d)
        match = state['rounds'][0]['matches'][0]
        verdict = self.verdict()
        verdict['match'] = match['id']
        path = B.verdict_out(d, 1, match['id'])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, json.dumps(verdict))
        self.assertEqual(cli('collect', '--dir', d).returncode, 1)
        self.assertIsNone(load(d)['rounds'][0]['matches'][0]['winner'])


class OutputIntegrity(TempDir):
    def test_failure_placeholders_do_not_complete_spawn_jobs(self):
        d = os.path.join(self.tmp, 'placeholder')
        self.ok('init', '--mode', 'evolve', '--agents', '2', '--task', 't', '--dir', d)
        state = load(d)
        self.ok('prompts', 'spawn', '--dir', d)
        for value in ('NO OUTPUT', '  \n\t'):
            for job in B.phase_jobs(state, 'spawn'):
                write(job['outputs'][0], value)
            self.assertEqual(B.next_action(state)[0], 'spawn')
            self.assertEqual(len(B.missing_jobs(B.phase_jobs(state, 'spawn'))), 2)

    def test_zero_attacks_marker_is_a_completed_attack(self):
        d = os.path.join(self.tmp, 'no-attacks')
        self.ok('init', '--mode', 'evolve', '--agents', '2', '--task', 't', '--dir', d)
        state = load(d)
        for phase, text in (('spawn', 'A solution.'), ('attack', 'NO ATTACKS FOUND')):
            self.ok('prompts', phase, '--dir', d)
            for job in B.phase_jobs(state, phase):
                write(job['outputs'][0], text)
        self.assertEqual(B.next_action(state)[0], 'defend')


if __name__ == '__main__':
    unittest.main()
