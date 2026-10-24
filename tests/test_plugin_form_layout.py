"""The question and optional rubric stay visible above the Arena tree."""
from html.parser import HTMLParser
from pathlib import Path
import unittest


class FormLayoutTests(unittest.TestCase):
    def test_inputs_are_inline_above_tree(self):
        class Layout(HTMLParser):
            def __init__(self):
                super().__init__()
                self.elements = []

            def handle_starttag(self, tag, attrs):
                self.elements.append((tag, dict(attrs)))

        layout = Layout()
        layout.feed((Path(__file__).resolve().parents[1] / 'skills/arena/plugin/ui/index.html').read_text(encoding='utf-8'))
        indexed = {attrs['id']: (i, tag, attrs) for i, (tag, attrs) in enumerate(layout.elements) if 'id' in attrs}
        self.assertEqual(indexed['mode-arena'][1], 'button')
        self.assertEqual(indexed['mode-grudge'][1], 'button')
        self.assertLess(indexed['mode-grudge'][0], indexed['task'][0])
        self.assertEqual(indexed['form'][1], 'section')
        self.assertNotIn('hidden', indexed['form'][2])
        self.assertLess(indexed['task'][0], indexed['guidance'][0])
        self.assertLess(indexed['guidance'][0], indexed['tree'][0])
        self.assertLess(indexed['task'][0], indexed['attach-files'][0])
        self.assertLess(indexed['attach-files'][0], indexed['guidance'][0])
        self.assertEqual(indexed['file-picker'][2]['type'],'file')
        self.assertIn('multiple',indexed['file-picker'][2])
        self.assertEqual(indexed['job-count'][1],'p')
        self.assertNotIn('required', indexed['guidance'][2])
        self.assertIn('required', indexed['task'][2])


if __name__ == '__main__':
    unittest.main()
