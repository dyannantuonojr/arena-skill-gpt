"""New runs cannot finish without both Archify packages and an answer viewer."""
import hashlib
import json
import os
from pathlib import Path

from test_bracket import B, TempDir, cli, load, write


class RequiredOutputs(TempDir):
    def tournament(self, bad_loser=False):
        d = os.path.join(self.tmp, 'required')
        self.ok('init', '--agents', 2, '--task', 't', '--dir', d)
        self.ok('prompts', 'spawn', '--dir', d)
        for aid in load(d)['agents']:
            write(B.spawn_out(d, aid), '# Answer ' + aid + '\nUseful original recommendation.')
        if bad_loser:
            loser = load(d)['rounds'][0]['matches'][0]['b']
            Path(B.spawn_out(d, loser)).write_bytes(b'\x80\x81\x82')
        self.ok('prompts', 'judge', '--dir', d)
        job = B.phase_jobs(load(d), 'judge')[0]
        a, b = job['a'], job['b']
        verdict = {'match': job['match'], 'scores': {
            x: dict({k: 8 if x == a else 6 for k, _ in B.WEIGHTS}, fatal=False) for x in (a, b)},
            'winner': a, 'reason': 'Synthetic software fixture', 'standing': {a: [], b: []}}
        write(job['outputs'][0], json.dumps(verdict))
        self.ok('collect', '--dir', d)
        self.ok('advance', '--dir', d)
        return d

    def synthetic_package(self, d, aid):
        # This tests acceptance software, not that Archify actually rendered this fixture.
        p = Path(d) / 'artifacts' / 'finalists' / aid
        (p / 'review').mkdir(parents=True)
        (p / 'implementation.md').write_text('# Implementation\n1. Verify the proposed change.', encoding='utf-8')
        (p / 'candidate.json').write_text('{"fixture":true}', encoding='utf-8')
        (p / 'diagram.html').write_text('<html>Software test fixture</html>', encoding='utf-8')
        digest = lambda name: hashlib.sha256((p / name).read_bytes()).hexdigest()
        receipt = {'ok': True, 'command': 'finalize', 'status': 'pass', 'type': 'workflow',
                   'gates': {k: 'pass' for k in ('validate', 'deliver', 'check', 'browser-check')},
                   'specification': {'path': str(p / 'candidate.json'), 'sha256': digest('candidate.json')},
                   'artifact': {'path': str(p / 'diagram.html'), 'sha256': digest('diagram.html')}}
        (p / 'review' / 'diagram.finalize-summary.json').write_text(json.dumps(receipt), encoding='utf-8')

    def test_fresh_artifact_workers_receive_bundled_authoring_and_cli_paths(self):
        d = self.tournament()
        self.ok('prompts', 'artifacts', '--dir', d)
        for job in B.phase_jobs(load(d), 'artifacts'):
            brief = Path(job['prompt']).read_text(encoding='utf-8')
            for relative in ('SKILL.md', 'bin/archify.mjs'):
                bundled = Path(B.HERE)/'vendor'/'archify'/relative
                self.assertTrue(bundled.is_file())
                self.assertIn(str(bundled), brief)

    def test_default_budget_includes_two_required_packages(self):
        plan = json.loads(self.ok('plan', '--json'))
        self.assertEqual((plan['core_calls'], plan['artifact_calls'], plan['calls']), (31, 2, 33))

    def test_delivery_requires_accepted_packages_and_current_viewer(self):
        d = self.tournament()
        self.assertIn('NEXT: artifacts', self.ok('next', '--dir', d))
        self.assertEqual(cli('winner', '--dir', d).returncode, 2)
        for aid in load(d)['agents']:
            self.synthetic_package(d, aid)
            self.ok('accept-artifact', aid, '--dir', d)
        self.assertIn('NEXT: view', self.ok('next', '--dir', d))
        self.ok('view', '--dir', d)
        self.assertIn('DONE', self.ok('next', '--dir', d))
        self.ok('winner', '--json', '--dir', d)
        report = Path(load(d)['viewer']['path'])
        report.write_text('tampered view', encoding='utf-8')
        self.assertIn('NEXT: view', self.ok('next', '--dir', d))

    def test_stale_finalist_package_reopens_required_phase(self):
        d = self.tournament()
        for aid in load(d)['agents']:
            self.synthetic_package(d, aid)
            self.ok('accept-artifact', aid, '--dir', d)
        self.ok('view', '--dir', d)
        p = Path(d) / 'artifacts' / 'finalists' / 'a001' / 'diagram.html'
        p.write_text('changed after acceptance', encoding='utf-8')
        self.assertIn('NEXT: artifacts', self.ok('next', '--dir', d))
        self.assertEqual(cli('winner', '--dir', d).returncode, 2)

    def test_view_output_cannot_overwrite_original_answers_or_state(self):
        d = self.tournament()
        for target in (Path(d) / 'r0' / 'a001.md', Path(d) / 'arena.json'):
            before = target.read_bytes()
            result = cli('view', '--dir', d, '--output', str(target))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(target.read_bytes(), before)

    def test_deleted_copied_diagram_requires_view_rebuild(self):
        d = self.tournament()
        for aid in load(d)['agents']:
            self.synthetic_package(d, aid)
            self.ok('accept-artifact', aid, '--dir', d)
        self.ok('view', '--dir', d)
        asset = load(d)['viewer']['assets'][0]
        Path(asset['path']).unlink()
        self.assertIn('NEXT: view', self.ok('next', '--dir', d))

    def test_unreadable_eliminated_answer_blocks_complete_delivery(self):
        d = self.tournament(bad_loser=True)
        for aid in load(d)['agents']:
            self.synthetic_package(d, aid)
            self.ok('accept-artifact', aid, '--dir', d)
        result = cli('view', '--dir', d)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(load(d)['viewer']['answers_complete'])
        self.assertIn('NEXT: view', self.ok('next', '--dir', d))
