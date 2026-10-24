from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'arena'))
from arena_svg import diagram_svg


class SvgTests(unittest.TestCase):
    def test_native_diagram_selected_and_active_content_removed(self):
        source = '''<svg><path d="toolbar"/></svg><svg viewBox="0 0 100 80" role="img"><script>evil()</script><foreignObject><div>no</div></foreignObject><g data-node-id="draft_a001" onclick="evil()"><rect width="10"/><text>Answer &amp; result</text><image href="https://evil/x"/></g></svg>'''
        svg = diagram_svg(source)
        self.assertIn('viewBox="0 0 100 80"', svg)
        self.assertIn('data-node-id="draft_a001"', svg)
        self.assertIn('Answer &amp; result', svg)
        for bad in ('script', 'foreignObject', 'onclick', 'https://evil', 'toolbar', 'evil()'):
            self.assertNotIn(bad, svg)

    def test_missing_diagram_rejected(self):
        with self.assertRaises(ValueError):
            diagram_svg('<html>No diagram</html>')
