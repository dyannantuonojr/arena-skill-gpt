import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'skills' / 'arena' / 'arena_view.py'

class ViewerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('arena_view', PATH)
        self.view = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.view)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = {'dir': str(self.root), 'mode': 'select', 'agents': {}, 'rounds': [], 'champion': 'a014'}
        for i in range(1, 17):
            aid = 'a%03d' % i
            path = self.root / (aid + '.md')
            path.write_text('# Answer ' + aid + '\nOriginal recommendation', encoding='utf-8')
            self.state['agents'][aid] = {'solution': str(path)}
        self.state['rounds'] = [{'matches': [{'a': 'a014', 'b': 'a005', 'winner': 'a014', 'scores': {'a014': 94, 'a005': 90}, 'reason': 'More complete'}]}]

    def export(self):
        result = self.view.export_view(self.state, self.root / 'out' / 'index.html')
        html = Path(result['path']).read_text(encoding='utf-8')
        data = json.loads(re.search(r'<script id="arena-data" type="application/json">(.*?)</script>', html, re.S).group(1))
        return result, html, data

    def test_every_answer_has_sidebar_entry_original_text_and_bracket_selection(self):
        result, html, data = self.export()
        self.assertEqual(len(data['answers']), 16)
        for aid in self.state['agents']:
            self.assertIn('data-answer="' + aid + '"', html)
            self.assertIn('Original recommendation', data['answers'][aid]['text'])
        self.assertIn('data-answer="a014"', html)
        self.assertIn('More complete', html)
        self.assertIn('31', html)
        self.assertIn('2 required package jobs', html)
        self.assertEqual(result['sha256'], hashlib.sha256(Path(result['path']).read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.root/'out'/'index.state.json').read_text())['state_sha256'], result['state_sha256'])

    def test_tree_is_primary_and_answer_panel_opens_from_tree_messages(self):
        _, page, data = self.export()
        self.assertIn('id="arena-tree"', page)
        self.assertIn('id="results-panel" hidden', page)
        self.assertIn('event.source!==tree.contentWindow', page)
        self.assertIn('data-node-id="draft_a001"', data['tree_html'])
        self.assertIn('data-node-id="draft_a016"', data['tree_html'])
        self.assertIn('arena-node-selected', data['tree_html'])
        self.assertIn('aria-label="Close results"', page)

    def test_existing_archify_tree_is_preserved_and_embedded_with_selection_bridge(self):
        tree = self.root/'visual'/'arena-tree.html'
        tree.parent.mkdir()
        original = '<!doctype html><html><body><svg><g data-node-id="draft_a001" role="button"><text>Original native tree</text></g></svg></body></html>'
        tree.write_text(original, encoding='utf-8')
        fingerprint = self.view.state_fingerprint(self.state)
        _, page, data = self.export()
        self.assertIn('Original native tree', data['tree_html'])
        self.assertIn('parent.postMessage', data['tree_html'])
        self.assertEqual(tree.read_text(encoding='utf-8'), original)
        with self.assertRaises(ValueError):
            self.view.export_view(self.state, tree)
        tree.write_text(original.replace('Original native', 'Updated native'), encoding='utf-8')
        self.assertNotEqual(fingerprint, self.view.state_fingerprint(self.state))

    def test_live_updates_do_not_reload_the_page_or_discard_the_tree_camera(self):
        _, page, data = self.export()
        self.assertNotIn('location.reload()', page)
        self.assertIn('DOMParser', page)
        self.assertIn('arena-capture-view', page)
        self.assertIn('arena-restore-view', page)
        self.assertIn('arena-view-state', data['tree_html'])
        self.assertIn('arena-tree-ready', data['tree_html'])
        self.assertIn('window.arenaFallbackView', data['tree_html'])

    def test_task_prompt_precedes_rubric_and_start_submits_directly(self):
        task = 'Original question: compare the implementations.\nRespect the supplied constraints.'
        (self.root/'task.md').write_bytes(task.encode('utf-8'))
        (self.root/'rubric.md').write_text('# Actual grading rubric\nCheck reproducible evidence.', encoding='utf-8')
        _, page, data = self.export()
        self.assertEqual(data['task_text'], task)
        self.assertIn('Check reproducible evidence.', data['rubric_html'])
        self.assertLess(page.index('id="arena-task"'), page.index('id="user-rubric"'))
        self.assertIn('id="arena-task"', page)
        self.assertIn('Download rubric', page)
        self.assertIn('user-rubric.md', page)
        self.assertIn('id="start-arena"', page)
        self.assertIn("fetch('/api/run'", page)
        self.assertIn("'X-Arena-Token'", page)
        self.assertNotIn('Copy Arena start request', page)
        self.assertNotIn('navigator.clipboard.writeText', page)
        self.assertIn('taskInput.value=arena.task_text', page)
        self.assertIn('JSON.stringify({task,rubric:rubricInput.value,agents:16,wave:3})', page)
        self.assertIn('Enter the question or task first.', page)
        original = self.view.state_fingerprint(self.state)
        (self.root/'task.md').write_text(task+' Changed', encoding='utf-8')
        self.assertNotEqual(original, self.view.state_fingerprint(self.state))

    def test_renderer_escapes_active_markup_and_embedded_data_cannot_close_script(self):
        attack = '</script><script>alert(1)</script><img src=x onerror=alert(2)>\n[bad](javascript:alert(3))'
        Path(self.state['agents']['a001']['solution']).write_bytes(attack.encode('utf-8'))
        _, html, data = self.export()
        self.assertEqual(data['answers']['a001']['text'], attack)
        rendered = self.view.render_markdown(attack)
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('<img', rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertNotIn('</script><script>alert(1)', html)

    def test_malformed_links_remain_readable_without_breaking_export(self):
        rendered = self.view.render_markdown('[broken](http://[) and [good](https://example.com)')
        self.assertIn('broken', rendered)
        self.assertIn('href="https://example.com"', rendered)

    def test_scope_is_collapsed_but_following_recommendations_remain_visible(self):
        rendered = self.view.render_markdown('# Plan\n## Assumptions and review scope\nPrivate details\n### Boundary\nMore scope\n## Recommendations\nShip it\n')
        self.assertIn('<details', rendered)
        self.assertNotIn('<details open', rendered)
        self.assertLess(rendered.index('Private details'), rendered.index('</details>'))
        self.assertLess(rendered.index('</details>'), rendered.index('Ship it'))
        self.assertIn('<h2>Recommendations</h2>', rendered)
        self.assertIn('<details', self.view.render_markdown('<details><summary>Safe</summary>Text</details>'))

    def test_literal_details_are_closed_with_safe_summary_and_body(self):
        rendered = self.view.render_markdown('<details>\n<summary>Assumptions <img src=x onerror=alert(1)></summary>\nHidden marker\n<script>alert(2)</script>\n</details>\n\n## Recommendation\nVisible marker')
        self.assertIn('<details class="scope">', rendered)
        self.assertNotIn('<details open', rendered)
        self.assertLess(rendered.index('Hidden marker'), rendered.index('</details>'))
        self.assertLess(rendered.index('</details>'), rendered.index('Visible marker'))
        self.assertNotIn('<img', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;img', rendered)
        unsafe = self.view.render_markdown('<details open onclick="alert(1)"><summary>Bad</summary>Text</details>')
        self.assertNotIn('<details', unsafe)

    def test_package_hashes_and_paths_guard_copied_diagram(self):
        package = self.root/'package'
        package.mkdir()
        values = {'implementation.md': '# Guide\nUse this', 'diagram.html': '<html><h1>Architecture</h1></html>', 'candidate.json': '{}', 'review/diagram.finalize-summary.json': '{}'}
        for name, value in values.items():
            (package/name).parent.mkdir(parents=True, exist_ok=True)
            (package/name).write_text(value, encoding='utf-8')
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.state['finalist_packages'] = {'a014': {'directory': str(package), 'solution_sha256': digest(Path(self.state['agents']['a014']['solution'])), 'guide_sha256': digest(package/'implementation.md'), 'diagram_sha256': digest(package/'diagram.html'), 'candidate_sha256': digest(package/'candidate.json'), 'receipt_sha256': digest(package/'review'/'diagram.finalize-summary.json')}}
        result, html, data = self.export()
        copied = self.root/'out'/'finalists'/'a014'/'diagram.html'
        self.assertEqual(result['assets'], [{'path': str(copied.resolve()), 'sha256': digest(copied)}])
        self.assertEqual(copied.read_text(), values['diagram.html'])
        self.assertEqual(data['answers']['a014']['diagram'], 'finalists/a014/diagram.html')
        self.assertIn('sandbox="allow-scripts allow-downloads"', html)
        self.assertNotIn('allow-same-origin', html)
        (package/'diagram.html').write_text('tampered', encoding='utf-8')
        _, _, data = self.export()
        self.assertIsNone(data['answers']['a014']['diagram'])
        self.state['agents']['a001']['solution'] = str(self.root.parent/'outside.md')
        _, _, data = self.export()
        self.assertEqual(data['answers']['a001']['status'], 'pending')

    def test_export_rejects_input_collisions_and_protected_run_subtrees_before_writes(self):
        source = Path(self.state['agents']['a001']['solution'])
        before = source.read_bytes()
        arena = self.root/'arena.json'
        arena.write_text('{"original": true}', encoding='utf-8')
        for output in (source, arena, self.root/'r0'/'view.html', self.root/'r4'/'view.html', self.root/'prompts'/'view.html', self.root/'artifacts'/'view.html'):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    self.view.export_view(self.state, output)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(arena.read_text(), '{"original": true}')
        self.assertFalse((self.root/'r0').exists())
        # A .html source bypasses a mere extension guard; sidecars/assets must
        # also be checked against source paths before any output directory exists.
        html_source = self.root/'original.html'
        html_source.write_text('Frozen HTML answer', encoding='utf-8')
        self.state['agents']['a001']['solution'] = str(html_source)
        with self.assertRaises(ValueError):
            self.view.export_view(self.state, html_source)
        self.assertEqual(html_source.read_text(), 'Frozen HTML answer')
        pending_dir = self.root/'fresh'
        self.state['agents']['a001']['solution'] = str(pending_dir/'index.state.json')
        with self.assertRaises(ValueError):
            self.view.export_view(self.state, pending_dir/'index.html')
        self.assertFalse(pending_dir.exists())

    def test_evolve_and_legacy_counters_include_five_jobs_per_closed_match(self):
        self.state['mode'] = 'evolve'
        _, html, _ = self.export()
        self.assertIn('93 total jobs = 21/91 core jobs', html)
        del self.state['mode']
        _, html, _ = self.export()
        self.assertIn('93 total jobs = 21/91 core jobs', html)

    def test_bom_decoding_and_incomplete_answer_receipt_preserve_source_bytes(self):
        source = Path(self.state['agents']['a001']['solution'])
        invalid = b'\x80\x81\x82not-utf8'
        source.write_bytes(invalid)
        result, _, data = self.export()
        self.assertFalse(result['answers_complete'])
        self.assertEqual(data['answers']['a001']['status'], 'pending')
        self.assertIn('diagnostic', data['answers']['a001'])
        self.assertEqual(source.read_bytes(), invalid)
        original = '# UTF16 answer\nActual recommendation'
        encoded = original.encode('utf-16')
        source.write_bytes(encoded)
        result, _, data = self.export()
        self.assertTrue(result['answers_complete'])
        self.assertEqual(data['answers']['a001']['text'], original)
        self.assertEqual(source.read_bytes(), encoded)
        source.write_bytes(b'\xef\xbb\xbfUTF8 BOM answer')
        _, _, data = self.export()
        self.assertEqual(data['answers']['a001']['text'], 'UTF8 BOM answer')

    def test_fingerprint_tracks_safe_source_arrival_and_changes(self):
        source = Path(self.state['agents']['a001']['solution'])
        source.unlink()
        missing = self.view.state_fingerprint(self.state)
        source.write_text('Arrived', encoding='utf-8')
        arrived = self.view.state_fingerprint(self.state)
        self.assertNotEqual(missing, arrived)
        source.write_text('Changed', encoding='utf-8')
        self.assertNotEqual(arrived, self.view.state_fingerprint(self.state))
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)/'secret.md'
            outside.write_text('External original', encoding='utf-8')
            self.state['agents']['a001']['solution'] = str(outside)
            guarded = self.view.state_fingerprint(self.state)
            outside.write_text('External changed', encoding='utf-8')
            self.assertEqual(guarded, self.view.state_fingerprint(self.state))

    def test_fingerprint_ignores_receipt_and_export_does_not_mutate(self):
        before = copy.deepcopy(self.state)
        fingerprint = self.view.state_fingerprint(self.state)
        self.export()
        self.assertEqual(before, self.state)
        self.state['viewer'] = {'path': 'different', 'sha256': 'receipt'}
        self.assertEqual(fingerprint, self.view.state_fingerprint(self.state))
        self.state['champion'] = 'a005'
        self.assertNotEqual(fingerprint, self.view.state_fingerprint(self.state))

    def test_symlinked_sidecar_is_rejected_without_writing_external_file(self):
        directory = self.root/'out'
        directory.mkdir()
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)/'private.json'
            outside.write_text('Preserve this file', encoding='utf-8')
            try:
                (directory/'index.state.json').symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest('symlink creation is unavailable on this host')
            with self.assertRaises(ValueError):
                self.view.export_view(self.state, directory/'index.html')
            self.assertEqual(outside.read_text(encoding='utf-8'), 'Preserve this file')
            self.assertFalse((directory/'index.html').exists())

if __name__ == '__main__':
    unittest.main()
