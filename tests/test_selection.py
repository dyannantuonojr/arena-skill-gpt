"""Fixed-answer selection through the real CLI."""
import json
import os
import random

from test_bracket import B, TempDir, cli, load, write


class FixedSelection(TempDir):
    def test_selection_is_default_and_evolve_is_explicit(self):
        default = json.loads(self.ok('plan', '--json'))
        self.assertEqual((default['agents'], default['rounds'], default['calls']), (16, 4, 31))
        legacy = json.loads(self.ok('plan', '--mode', 'evolve', '--json'))
        self.assertEqual(legacy['calls'], 91)

    def test_only_judges_follow_frozen_drafts_and_branches_stay_fixed(self):
        d = os.path.join(self.tmp, 'selection')
        self.ok('init', '--task', 'Choose the correct solution.', '--seed', 7, '--dir', d)
        self.ok('prompts', 'spawn', '--dir', d)
        initial = {}
        for aid in load(d)['agents']:
            path = B.spawn_out(d, aid)
            write(path, 'Frozen answer for ' + aid)
            initial[aid] = path
        jobs_run, prior_winners = 16, None
        rng = random.Random(7)
        while not load(d)['champion']:
            self.assertIn('NEXT: judge', self.ok('next', '--dir', d))
            self.ok('prompts', 'judge', '--dir', d)
            state = load(d)
            rd = state['rounds'][-1]
            if prior_winners is not None:
                actual = [set((m['a'], m['b'])) for m in rd['matches']]
                self.assertEqual(actual, [set(prior_winners[i:i+2]) for i in range(0, len(prior_winners), 2)])
            self.assertEqual(B.phase_jobs(state, 'attack'), [])
            self.assertEqual(B.phase_jobs(state, 'defend'), [])
            prior_winners = []
            for job in B.phase_jobs(state, 'judge'):
                a, b = job['a'], job['b']
                with open(job['prompt'], encoding='utf-8') as fh:
                    brief = fh.read()
                self.assertIn(initial[a], brief)
                self.assertIn(initial[b], brief)
                self.assertNotIn('.solution.md', brief)
                winner = rng.choice([a, b])
                scores = {x: dict({k: 8 if x == winner else 6 for k, _ in B.WEIGHTS}, fatal=False) for x in (a, b)}
                verdict = {'match': job['match'], 'scores': scores, 'winner': winner,
                           'reason': 'Synthetic scored comparison', 'standing': {a: [], b: []}}
                write(job['outputs'][0], json.dumps(verdict))
                prior_winners.append(winner)
                jobs_run += 1
            self.ok('collect', '--dir', d)
            self.ok('advance', '--dir', d)
            self.assertEqual({a: v['solution'] for a, v in load(d)['agents'].items()}, initial)
        self.assertEqual(jobs_run, 31)
        self.assertIn('DONE', self.ok('next', '--dir', d))
        self.assertEqual(len(load(d)['rounds']), 4)

    def test_changed_answer_is_rejected_after_judging_begins(self):
        d = os.path.join(self.tmp, 'changed')
        self.ok('init', '--agents', 2, '--task', 't', '--dir', d)
        self.ok('prompts', 'spawn', '--dir', d)
        for aid in load(d)['agents']:
            write(B.spawn_out(d, aid), 'original ' + aid)
        self.ok('prompts', 'judge', '--dir', d)
        write(B.spawn_out(d, 'a001'), 'revised answer')
        result = cli('next', '--dir', d)
        self.assertEqual(result.returncode, 2)
        self.assertIn('changed', result.stderr.lower())

    def test_saved_state_without_mode_retains_legacy_evolution(self):
        d = os.path.join(self.tmp, 'legacy')
        self.ok('init', '--agents', 2, '--task', 't', '--dir', d)
        self.ok('prompts', 'spawn', '--dir', d)
        state = load(d)
        state.pop('mode', None)
        write(os.path.join(d, 'arena.json'), json.dumps(state))
        for aid in state['agents']:
            write(B.spawn_out(d, aid), 'draft ' + aid)
        self.assertIn('NEXT: attack', self.ok('next', '--dir', d))

    def test_winner_rejects_a_changed_champion_after_done(self):
        d = os.path.join(self.tmp, 'winner-integrity')
        self.ok('init', '--agents', 2, '--task', 't', '--dir', d)
        self.ok('prompts', 'spawn', '--dir', d)
        for aid in load(d)['agents']:
            write(B.spawn_out(d, aid), 'original ' + aid)
        self.ok('prompts', 'judge', '--dir', d)
        state = load(d)
        job = B.phase_jobs(state, 'judge')[0]
        a, b = job['a'], job['b']
        verdict = {'match': job['match'], 'scores': {
            x: dict({k: 8 if x == a else 6 for k, _ in B.WEIGHTS}, fatal=False) for x in (a, b)},
            'winner': a, 'reason': 'Synthetic check', 'standing': {a: [], b: []}}
        write(job['outputs'][0], json.dumps(verdict))
        self.ok('collect', '--dir', d)
        self.ok('advance', '--dir', d)
        self.assertIn('DONE', self.ok('next', '--dir', d))
        write(load(d)['agents'][a]['solution'], 'changed after completion')
        result = cli('winner', '--dir', d)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('changed', result.stderr.lower())
