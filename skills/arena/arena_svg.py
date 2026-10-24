"""Extract inert native geometry for MCP clients that forbid nested frames."""
from html import escape
from html.parser import HTMLParser
import re

TAGS = frozenset(('svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline',
                  'polygon', 'text', 'tspan', 'title', 'desc', 'defs', 'marker',
                  'lineargradient', 'radialgradient', 'stop', 'clippath'))
ATTRS = frozenset(('id', 'class', 'viewbox', 'xmlns', 'width', 'height', 'x', 'y',
                   'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'd', 'points',
                   'transform', 'fill', 'stroke', 'stroke-width', 'stroke-dasharray',
                   'opacity', 'fill-opacity', 'stroke-opacity', 'text-anchor',
                   'dominant-baseline', 'font-size', 'font-weight', 'font-family',
                   'dx', 'dy', 'data-node-id', 'role', 'aria-label', 'tabindex',
                   'marker-end', 'marker-start', 'markerwidth', 'markerheight',
                   'refx', 'refy', 'orient', 'offset', 'stop-color', 'stop-opacity',
                   'gradientunits', 'gradienttransform', 'clip-path'))
CAMEL = {'viewbox': 'viewBox', 'markerwidth': 'markerWidth', 'markerheight': 'markerHeight',
         'refx': 'refX', 'refy': 'refY', 'gradientunits': 'gradientUnits',
         'gradienttransform': 'gradientTransform', 'lineargradient': 'linearGradient',
         'radialgradient': 'radialGradient', 'clippath': 'clipPath'}


class _Svg(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.drop = 0
        self.parts = []
        self.candidates = []
        self.main = False

    def handle_starttag(self, tag, attrs):
        if tag == 'svg':
            if not self.depth:
                self.parts = []
                self.main = dict(attrs).get('role') == 'img'
            self.depth += 1
        if not self.depth:
            return
        if tag in ('script', 'foreignobject', 'style'):
            self.drop += 1
        if self.drop or tag not in TAGS:
            return
        safe = []
        for key, value in attrs:
            if key not in ATTRS or value is None:
                continue
            if re.search(r'javascript:|data:|https?:|expression|@|[<>]', value, re.I):
                continue
            if 'url(' in value.lower() and not re.fullmatch(r'url\(#[A-Za-z0-9_-]+\)', value):
                continue
            safe.append(' %s="%s"' % (CAMEL.get(key, key), escape(value, quote=True)))
        self.parts.append('<' + CAMEL.get(tag, tag) + ''.join(safe) + '>')

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag in ('script', 'foreignobject', 'style'):
            self.drop = max(0, self.drop - 1)
        elif not self.drop and tag in TAGS:
            self.parts.append('</' + CAMEL.get(tag, tag) + '>')
        if tag == 'svg':
            self.depth -= 1
            if not self.depth:
                self.candidates.append((self.main, ''.join(self.parts)))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.depth and not self.drop:
            self.parts.append(escape(data))


def diagram_svg(document):
    parser = _Svg()
    parser.feed(document)
    if not parser.candidates:
        raise ValueError('Native diagram SVG is unavailable')
    return max(parser.candidates, key=lambda item: (item[0], len(item[1])))[1]
