"""Portable tree-first arena viewer. Standard library only."""
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def state_fingerprint(state):
    """Hash canonical state and contained source bytes, excluding viewer receipt.

    Missing/unsafe paths contribute a marker rather than reading outside the run.
    Arrival of a draft therefore invalidates an exported pending answer even if
    arena.json has not yet changed.
    """
    data = {key: value for key, value in state.items() if key != 'viewer'}
    sources = {}
    try:
        root = Path(state['dir']).resolve()
    except (KeyError, TypeError, ValueError, OSError):
        root = None
    def source(key, value):
        try:
            if root is None:
                raise ValueError('No run directory')
            sources[key] = _sha(_inside(root, value))
        except (OSError, ValueError, TypeError):
            sources[key] = 'missing-or-unavailable'
    for aid, agent in state.get('agents', {}).items():
        source('solution:' + str(aid), agent.get('solution'))
    for aid, package in state.get('finalist_packages', {}).items():
        if not isinstance(package, dict):
            continue
        for name in ('implementation.md', 'diagram.html', 'candidate.json', 'review/diagram.finalize-summary.json'):
            try:
                location = Path(package['directory']) / name
            except (KeyError, TypeError, ValueError):
                location = None
            source('package:' + str(aid) + ':' + name, location)
    if root is not None:
        for relative in ('visual/arena-tree.html', 'viewer/arena-tree.html', 'task.md', 'rubric.md', 'user-rubric.md'):
            source(relative, root/relative)
    payload = {'state': data, 'sources': sources}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _inline(text):
    # Escape all source HTML. Only this renderer creates executable markup.
    tokens = []
    def token(value):
        tokens.append(value)
        return '\x00%d\x00' % (len(tokens)-1)
    text = re.sub(r'`([^`]+)`', lambda m: token('<code>' + html.escape(m[1]) + '</code>'), text)
    def link(m):
        label, url = m.groups()
        try:
            scheme = urlsplit(url).scheme.lower()
        except ValueError:
            return label + ' (' + url + ')'
        if scheme not in ('http', 'https', 'mailto') and not url.startswith('#'):
            return label + ' (' + url + ')'
        return token('<a href="' + html.escape(url, quote=True) + '" rel="noopener noreferrer">' + html.escape(label) + '</a>')
    text = re.sub(r'\[([^\]\n]+)\]\(([^\s)]+)\)', link, text)
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*', r'<em>\1</em>', text)
    return re.sub(r'\x00(\d+)\x00', lambda m: tokens[int(m[1])], text)


def render_markdown(text):
    """Readable Markdown subset; only attribute-free details/summary HTML is allowed."""
    lines = str(text).splitlines()
    result, paragraph = [], []
    scope_level = None
    def flush():
        if paragraph:
            result.append('<p>' + _inline('\n'.join(paragraph)) + '</p>')
            paragraph.clear()
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        detail = re.match(r'^\s*<details>\s*<summary>(.*?)</summary>(.*?)</details>', '\n'.join(lines[i:]), re.S) if re.match(r'^\s*<details>', line) else None
        if detail:
            flush()
            result.append('<details class="scope"><summary>' + _inline(detail[1]) + '</summary>' + render_markdown(detail[2]) + '</details>')
            i += detail[0].count('\n')
            suffix = '\n'.join(lines[i:])[len(detail[0].rsplit('\n', 1)[-1]):].split('\n', 1)[0]
            if suffix.strip():
                lines[i] = suffix
                i -= 1
        elif fence:
            flush()
            marker = fence[1][0]
            size = len(fence[1])
            block = []
            i += 1
            while i < len(lines) and not re.match(r'^\s*' + re.escape(marker) + '{' + str(size) + r',}\s*$', lines[i]):
                block.append(lines[i]); i += 1
            result.append('<pre><code>' + html.escape('\n'.join(block)) + '</code></pre>')
        elif re.match(r'^#{1,6}\s+', line):
            flush()
            match = re.match(r'^(#{1,6})\s+(.*?)\s*#*$', line)
            level, title = len(match[1]), match[2]
            if scope_level is not None and level <= scope_level:
                result.append('</details>'); scope_level = None
            plain = re.sub(r'[*_`]', '', title).strip()
            if scope_level is None and re.match(r'^(?:(?:technical|key|working)\s+)?(?:assumptions?\b|review\s+scope\b)', plain, re.I):
                result.append('<details class="scope"><summary>' + _inline(title) + '</summary>')
                scope_level = level
            else:
                result.append('<h%d>%s</h%d>' % (level, _inline(title), level))
        elif i+1 < len(lines) and '|' in line and re.match(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$', lines[i+1]):
            flush()
            cells = lambda value: [part.strip() for part in value.strip().strip('|').split('|')]
            result.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+_inline(c)+'</th>' for c in cells(line)) + '</tr></thead><tbody>')
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                result.append('<tr>'+''.join('<td>'+_inline(c)+'</td>' for c in cells(lines[i]))+'</tr>'); i += 1
            result.append('</tbody></table></div>'); i -= 1
        elif re.match(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', line):
            flush()
            ordered = bool(re.match(r'^\s*\d', line))
            tag = 'ol' if ordered else 'ul'
            result.append('<'+tag+'>')
            pattern = r'^\s*\d+[.)]\s+(.*)' if ordered else r'^\s*[-*+]\s+(.*)'
            while i < len(lines):
                match = re.match(pattern, lines[i])
                if not match: break
                result.append('<li>'+_inline(match[1])+'</li>'); i += 1
            result.append('</'+tag+'>'); i -= 1
        elif not line.strip():
            flush()
        else:
            paragraph.append(line)
        i += 1
    flush()
    if scope_level is not None: result.append('</details>')
    return '\n'.join(result)


def _inside(root, value):
    path = Path(value)
    if not path.is_absolute(): path = root / path
    path = path.resolve()
    path.relative_to(root)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finalists(state):
    for rd in reversed(state.get('rounds', [])):
        matches = rd.get('matches', [])
        if matches:
            return list(dict.fromkeys(aid for m in matches for aid in (m.get('a'), m.get('b')) if aid))
    return list(state.get('agents', {})) if len(state.get('agents', {})) == 1 else []


def _validate_export_paths(state, root, output, finalists):
    """Preflight every possible write before creating even a directory."""
    if output.suffix.lower() != '.html':
        raise ValueError('Viewer output must have an .html suffix')
    protected = {root/name for name in ('arena.json', 'task.md', 'rubric.md', 'baseline.md', 'final.verdict.json')}
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key != 'viewer':
                    collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)
        elif isinstance(value, str) and '\n' not in value:
            try:
                path = Path(value)
                if path.is_absolute() or path.suffix.lower() in ('.md', '.json', '.html', '.txt'):
                    protected.add((path if path.is_absolute() else root/path).resolve())
            except (ValueError, OSError):
                pass
    collect(state)
    protected.update((root/name).resolve() for name in ('visual/arena-tree.html', 'viewer/arena-tree.html', 'user-rubric.md'))
    for package in state.get('finalist_packages', {}).values():
        try:
            directory = _inside(root, package['directory'])
            for name in ('implementation.md', 'diagram.html', 'candidate.json', 'manifest.json', 'review/diagram.finalize-summary.json'):
                protected.add((directory/name).resolve())
        except (KeyError, TypeError, ValueError, OSError):
            pass
    writes = [output, output.with_suffix('.state.json')]
    for aid in finalists:
        if aid in state.get('finalist_packages', {}) and re.fullmatch(r'[A-Za-z0-9_-]+', aid):
            writes.append(output.parent/'finalists'/aid/'diagram.html')
    for target in writes:
        cursor = target
        while cursor != output.parent:
            if cursor.is_symlink():
                raise ValueError('Viewer destination must not follow a symlink: ' + str(cursor))
            cursor = cursor.parent
        target = target.resolve()
        try:
            target.relative_to(output.parent)
        except ValueError:
            raise ValueError('Viewer destination escapes its report directory: ' + str(target))
        try:
            relative = target.relative_to(root)
        except ValueError:
            relative = None
        if relative is not None and relative.parts:
            first = relative.parts[0].lower()
            if re.fullmatch(r'r\d+', first) or first in ('prompts', 'artifacts'):
                raise ValueError('Viewer output overlaps a protected run subtree: ' + str(target))
            if len(relative.parts) == 1 and (first == 'arena.json' or target.stem.lower() in ('task', 'rubric', 'baseline')):
                raise ValueError('Viewer output overlaps a protected run input: ' + str(target))
        for source in protected:
            collision = target == source
            if not collision:
                try:
                    collision = target.samefile(source)
                except OSError:
                    pass
            if collision:
                raise ValueError('Viewer output collides with a protected input: ' + str(target))


def _read_source(path):
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    return raw.decode('utf-8-sig')


def export_view(state, output_path):
    """Export a viewer and source fingerprint; never modify input state."""
    root = Path(state['dir']).resolve()
    output = Path(output_path).resolve()
    finalists = _finalists(state)
    _validate_export_paths(state, root, output, finalists)
    output.parent.mkdir(parents=True, exist_ok=True)
    answers = {}
    valid_packages = 0
    assets = []
    for aid, agent in state.get('agents', {}).items():
        solution = None
        entry = {'text': '', 'html': '', 'status': 'pending', 'finalist': aid in finalists, 'champion': aid == state.get('champion'), 'guide': None, 'diagram': None, 'package_status': 'pending'}
        try:
            solution = _inside(root, agent['solution'])
            entry['text'] = _read_source(solution)
            entry['html'] = render_markdown(entry['text'])
            entry['status'] = 'ready'
        except (OSError, ValueError, KeyError, TypeError) as error:
            entry['diagnostic'] = 'Answer unavailable: ' + str(error)
        package = state.get('finalist_packages', {}).get(aid)
        if package and aid in finalists and entry['status'] == 'ready':
            try:
                directory = _inside(root, package['directory'])
                guide = _inside(root, directory / 'implementation.md')
                diagram = _inside(root, directory / 'diagram.html')
                candidate = _inside(root, directory / 'candidate.json')
                receipt = _inside(root, directory / 'review' / 'diagram.finalize-summary.json')
                for path, key in ((solution, 'solution_sha256'), (guide, 'guide_sha256'), (diagram, 'diagram_sha256'), (candidate, 'candidate_sha256'), (receipt, 'receipt_sha256')):
                    if _sha(path) != package[key]: raise ValueError('Package hash mismatch')
                if not re.fullmatch(r'[A-Za-z0-9_-]+', aid): raise ValueError('Unsafe candidate ID')
                target = output.parent/'finalists'/aid/'diagram.html'
                target.resolve().relative_to(output.parent)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(diagram.read_bytes())
                assets.append({'path': str(target.resolve()), 'sha256': _sha(target)})
                entry.update(guide=render_markdown(_read_source(guide)), diagram='finalists/'+aid+'/diagram.html', package_status='ready')
                valid_packages += 1
            except (OSError, ValueError, KeyError, TypeError, UnboundLocalError):
                entry['package_status'] = 'pending (missing or unvalidated artifacts)'
        answers[aid] = entry
    fingerprint = state_fingerprint(state)
    data = {'answers': answers, 'rounds': state.get('rounds', []), 'champion': state.get('champion'), 'state_sha256': fingerprint, 'tree_html': tree_document(state), 'rubric_html': '', 'task_text': ''}
    try:
        data['rubric_html'] = render_markdown(_read_source(_inside(root, root/'rubric.md')))
    except (OSError, ValueError):
        data['rubric_html'] = '<p>Grading rubric unavailable in this saved run.</p>'
    try:
        data['task_text'] = _read_source(_inside(root, root/'task.md'))
    except (OSError, ValueError):
        pass
    encoded = json.dumps(data, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    def button(aid):
        item = answers.get(aid, {})
        badge = ' | Champion' if item.get('champion') else (' | Finalist' if item.get('finalist') else '')
        return '<button data-answer="'+html.escape(aid, quote=True)+'">'+html.escape(aid+badge)+'</button>'
    sidebar = ''.join(button(aid) for aid in answers)
    rounds = []
    for number, rd in enumerate(state.get('rounds', []), 1):
        matches = []
        for match in rd.get('matches', []):
            scores = match.get('scores') or {}
            competitors = ''.join(button(aid)+'<span class="score">Rubric score: '+html.escape(str(scores.get(aid, 'pending')))+'</span>' for aid in (match.get('a'), match.get('b')) if aid in answers)
            matches.append('<section class="match">'+competitors+'<p>'+html.escape(str(match.get('reason') or 'Judgment pending'))+'</p></section>')
        rounds.append('<section class="round"><h3>Round '+str(number)+'</h3>'+''.join(matches)+'</section>')
    count = len(answers)
    jobs_per_match = 1 if state.get('mode', 'evolve') == 'select' else 5
    core = count + jobs_per_match * max(0, count-1)
    done = sum(item['status']=='ready' for item in answers.values()) + jobs_per_match * sum(bool(m.get('winner')) for rd in state.get('rounds', []) for m in rd.get('matches', []))
    counter = '%d total jobs = %d/%d core jobs | %d/%d required package jobs | artifacts %s' % (core + min(2, count), done, core, valid_packages, min(2, count), 'ready' if valid_packages == min(2, count) and count else 'pending')
    headline = '%d answers | %d finalist guides | %s' % (count, valid_packages, 'Complete' if valid_packages == min(2, count) and all(a['status'] == 'ready' for a in answers.values()) and state.get('champion') else 'Preparing guides')
    if not count:
        headline = 'Ready for your question'
        counter = 'No run started'
    values = {'__HEADLINE__': html.escape(headline), '__SIDEBAR__': sidebar, '__BRACKET__': ''.join(rounds), '__COUNTER__': html.escape(counter), '__DATA__': encoded, '__STATE_FILE__': json.dumps(output.stem+'.state.json').replace('<', '\\u003c')}
    page = re.sub(r'__HEADLINE__|__SIDEBAR__|__BRACKET__|__COUNTER__|__DATA__|__STATE_FILE__', lambda m: values[m[0]], _PAGE)
    output.write_text(page, encoding='utf-8')
    output.with_suffix('.state.json').write_text(json.dumps({'state_sha256': fingerprint}), encoding='utf-8')
    return {'path': str(output), 'sha256': _sha(output), 'state_sha256': fingerprint, 'assets': assets, 'answers_complete': bool(answers) and all(item['status'] == 'ready' for item in answers.values())}



_TREE_BRIDGE = '''<style>#focus-chip{display:none!important}[data-arena-selected] rect{stroke:#65dfc2!important;stroke-width:3px!important}</style><script>
(function(){
 function selected(event){
  if(event.type==='keydown'&&event.key!=='Enter'&&event.key!==' ')return;
  const node=event.target.closest&&event.target.closest('[data-node-id]');
  if(node){event.preventDefault();event.stopImmediatePropagation();document.querySelectorAll('[data-arena-selected]').forEach(n=>n.removeAttribute('data-arena-selected'));node.setAttribute('data-arena-selected','true');parent.postMessage({type:'arena-node-selected',id:node.getAttribute('data-node-id')},'*');}
 }
 document.addEventListener('click',selected,true);
 document.addEventListener('keydown',selected,true);
})();
</script>'''


def tree_document(state):
    """Reuse the run's native Archify reader, retaining its canvas and controls.

    The selection bridge runs inside an opaque sandbox. The parent validates the
    sending window and handles only known answer/match IDs, never supplied HTML.
    A native SVG tree keeps fresh/pending runs navigable before Archify delivery.
    """
    root = Path(state['dir']).resolve()
    for name in ('visual/arena-tree.html', 'viewer/arena-tree.html'):
        try:
            native = _read_source(_inside(root, root/name))
            if '</body>' in native.lower():
                return re.sub(r'</body>', lambda m: _TREE_BRIDGE + m[0], native, count=1, flags=re.I)
        except (OSError, ValueError):
            pass
    agents = list(state.get('agents', {}))
    rounds = state.get('rounds', [])
    first = rounds[0].get('matches', []) if rounds else []
    order = []
    for match in first:
        for aid in (match.get('a'), match.get('b')):
            if aid in agents and aid not in order:
                order.append(aid)
    order += [aid for aid in agents if aid not in order]
    depth = max(1, len(rounds))
    positions, nodes, edges, winner_nodes = {}, [], [], {}
    for index, aid in enumerate(order):
        node = 'draft_' + aid
        positions[node] = ((depth+1)*245, 48+index*80)
        nodes.append((node, aid, 'Original answer'))
        winner_nodes[aid] = node
    for number, rd in enumerate(rounds, 1):
        previous = dict(winner_nodes)
        for index, match in enumerate(rd.get('matches', []), 1):
            mid = str(match.get('id') or 'r%d-m%02d' % (number,index))
            children = [previous[a] for a in (match.get('a'),match.get('b')) if a in previous]
            y = sum(positions[c][1] for c in children)/len(children) if children else 48+index*80
            positions[mid] = ((depth-number+1)*245, y)
            winner = match.get('winner')
            nodes.append((mid, 'R%d %s / %s' % (number,match.get('a','?'),match.get('b','?')), 'Winner '+winner if winner else 'Judgment pending'))
            edges += [(mid,child) for child in children]
            if winner:
                winner_nodes[winner] = mid
    positions['arena'] = (0, sum(p[1] for p in positions.values())/max(1,len(positions)))
    nodes.append(('arena','Arena '+str(len(agents)) if agents else 'New Arena run', 'Selected '+state['champion'] if state.get('champion') else ('Answers in progress' if agents else 'Enter your question to begin')))
    if rounds:
        last = rounds[-1].get('matches', [])
        edges += [('arena',str(m.get('id') or 'r%d-m%02d' % (len(rounds),i))) for i,m in enumerate(last,1)]
    else:
        edges += [('arena','draft_'+aid) for aid in agents]
    shapes = []
    for source,target in edges:
        if source not in positions or target not in positions: continue
        x,y=positions[source];xx,yy=positions[target]
        shapes.append('<path d="M %s %s C %s %s, %s %s, %s %s"/>' % (x+205,y+25,x+225,y+25,xx-20,yy+25,xx,yy+25))
    for nid,label,detail in nodes:
        x,y=positions[nid]
        shapes.append('<g data-node-id="%s" tabindex="0" role="button" aria-label="%s" transform="translate(%s %s)"><rect width="205" height="54" rx="10"/><text x="14" y="23">%s</text><text class="detail" x="14" y="43">%s</text></g>' % (html.escape(nid,quote=True),html.escape(label,quote=True),x,y,html.escape(label),html.escape(detail)))
    width=(depth+1)*245+235;height=max(180,len(agents)*80+60)
    return '''<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;background:#0b1120;color:#dce8fa;font:14px system-ui;height:100vh;overflow:hidden}svg{width:100%%;height:100%%;touch-action:none}path{fill:none;stroke:#386b86;stroke-width:2}rect{fill:#152336;stroke:#497d98}g{cursor:pointer}g:hover rect,g:focus rect{stroke:#65e1c5;stroke-width:3}text{fill:#edf7ff;font:13px system-ui}.detail{fill:#9fb3c9;font-size:11px}.controls{position:absolute;top:14px;left:14px;display:flex;gap:8px}button{background:#152336;color:#edf7ff;border:1px solid #497d98;border-radius:6px;padding:7px 12px;cursor:pointer}.hint{position:absolute;bottom:12px;left:14px;color:#9fb3c9}
    </style></head><body><div class="controls"><button id="in" aria-label="Zoom in">+</button><button id="out" aria-label="Zoom out">-</button><button id="fit">Fit tree</button></div><svg viewBox="-25 -10 %d %d" aria-label="Arena tournament tree">%s</svg><div class="hint">Click an answer to read results. Scroll to zoom. Drag to pan.</div><script>
    const svg=document.querySelector('svg'),initial=svg.getAttribute('viewBox').split(' ').map(Number);let v=initial.slice(),drag=null;
    function draw(){svg.setAttribute('viewBox',v.join(' '));}function zoom(scale){v[0]+=v[2]*(1-scale)/2;v[1]+=v[3]*(1-scale)/2;v[2]*=scale;v[3]*=scale;draw();}
    document.getElementById('in').onclick=()=>zoom(.8);document.getElementById('out').onclick=()=>zoom(1.25);document.getElementById('fit').onclick=()=>{v=initial.slice();draw();};
    svg.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.12:.89);},{passive:false});
    svg.addEventListener('pointerdown',e=>{if(e.target.closest('[data-node-id]'))return;drag=[e.clientX,e.clientY,v.slice()];svg.setPointerCapture(e.pointerId);});svg.addEventListener('pointermove',e=>{if(!drag)return;const b=svg.getBoundingClientRect();v[0]=drag[2][0]-(e.clientX-drag[0])*v[2]/b.width;v[1]=drag[2][1]-(e.clientY-drag[1])*v[3]/b.height;draw();});svg.addEventListener('pointerup',()=>drag=null);
    </script>%s</body></html>''' % (width,height,''.join(shapes),_TREE_BRIDGE)


_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Arena tree</title>
<style>
:root{color-scheme:dark;--ink:#e3edf8;--line:#30445c;--accent:#65dfc2}*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0;background:#0b1120;color:var(--ink);font:14px/1.6 system-ui,sans-serif;height:100dvh;overflow:hidden}header{height:58px;display:flex;align-items:center;gap:16px;padding:8px 18px;border-bottom:1px solid var(--line)}header h1{font-size:17px;white-space:nowrap;margin:0}header p{font-size:12px;color:#a9bfd3;margin:0;max-width:40vw}button:disabled{opacity:.5;cursor:wait}.tools{margin-left:auto;display:flex;gap:8px;align-items:center}button,summary{cursor:pointer}button{border:1px solid var(--line);border-radius:7px;padding:7px 11px;background:#142338;color:var(--ink);font:inherit;text-align:left}button:hover,button[aria-current=true]{border-color:var(--accent);background:#203f45}summary{list-style:none;font-weight:600}.popover{position:relative}.popover>div{position:absolute;right:0;top:36px;z-index:9;background:#132137;padding:16px;border:1px solid var(--line);border-radius:9px;width:min(450px,90vw);box-shadow:0 15px 50px #0009;max-height:75vh;overflow:auto}nav{display:grid;grid-template-columns:1fr 1fr;gap:7px}.workspace{height:calc(100dvh - 58px);display:flex}#tree-region{flex:1;min-width:0}#arena-tree{width:100%;height:100%;border:0}#results-panel{width:clamp(430px,43vw,760px);flex-shrink:0;border-left:1px solid var(--line);background:#101c2e;overflow:auto;padding:22px}#results-panel h2{margin:0;font-size:23px}.panel-head{display:flex;justify-content:space-between;align-items:center;gap:10px;position:sticky;top:-22px;background:#101c2e;z-index:2;padding:8px 0}#badge{font-size:13px;color:var(--accent)}.tabs{display:flex;gap:8px;margin:12px 0 18px}.tabs button[aria-selected=true]{background:#246756;border-color:var(--accent)}#content h1{font-size:25px}#content h2{font-size:21px;margin:25px 0 12px}#content h3{font-size:17px}p{white-space:pre-wrap;overflow-wrap:anywhere}a{color:var(--accent)}.scope{border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0;background:#142338}pre{background:#08111e;padding:14px;overflow:auto;border-radius:7px}code{font-family:Consolas,monospace}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid var(--line);text-align:left}.table-wrap{overflow:auto}#content iframe{width:100%;height:68vh;border:1px solid var(--line);border-radius:8px;background:#fff}.score{font-size:12px;color:#99aec3}.match button{margin-right:7px}.round{margin-top:16px}#rubric-dialog{position:fixed;z-index:20;inset:70px max(20px,calc((100vw - 850px)/2));overflow:auto;background:#132137;border:1px solid var(--line);border-radius:12px;padding:24px;box-shadow:0 0 0 100vmax #0009}textarea{width:100%;min-height:180px;background:#0a1525;color:var(--ink);padding:12px;border:1px solid #4a6888;border-radius:7px;font:inherit;resize:vertical}label{display:block;font-weight:600;margin:14px 0 6px}.rubric-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}#rubric-status{color:var(--accent)}.pending{color:#e6c887}@media(max-width:850px){header{gap:8px;padding:8px}header>p{display:none}.tools{gap:8px}button{padding:7px 9px}.workspace:has(#results-panel:not([hidden])){flex-direction:column}#results-panel{width:100%;height:58%;border-left:0;border-top:1px solid var(--line);padding:16px}#tree-region{min-height:35%}.panel-head{top:-16px}#rubric-dialog{inset:65px 10px 10px}}
@media(max-width:850px){header{height:88px;flex-wrap:wrap;align-content:center;row-gap:3px}header #run-status{display:block;order:2;flex:0 0 100%;max-width:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.workspace{height:calc(100dvh - 88px)}#rubric-dialog{inset:98px 10px 10px}}
</style></head><body>
<header><h1>Arena tree</h1><p id="run-status" role="status">__HEADLINE__</p><div class="tools"><details class="popover" id="answer-picker"><summary>Find answer</summary><div><nav aria-label="All answers">__SIDEBAR__</nav></div></details><button id="rubric-button">Task &amp; rubric</button><button id="stop-arena" hidden>Stop run</button><details class="popover"><summary>Run details</summary><div><p>__COUNTER__</p><p>Judge scores compare the answers; they are not accuracy percentages.</p><details><summary>Match results</summary>__BRACKET__</details></div></details></div></header>
<div class="workspace"><section id="tree-region" aria-label="Arena tree"><iframe id="arena-tree" title="Arena tournament tree" sandbox="allow-scripts allow-downloads"></iframe></section><article id="results-panel" hidden aria-label="Selected answer results"><div class="panel-head"><h2 id="selected"></h2><button id="close-results" aria-label="Close results">Close</button></div><p id="badge"></p><div class="tabs" role="tablist"><button role="tab" data-tab="answer">Answer</button><button role="tab" data-tab="implementation">Implementation</button><button role="tab" data-tab="archify">Archify</button></div><p id="answer-note" class="score">Original answer, unchanged. Implementation guide reflects the required outputs.</p><div id="content"></div></article></div>
<section id="rubric-dialog" role="dialog" aria-modal="true" aria-labelledby="rubric-title" hidden><div class="panel-head"><h2 id="rubric-title">Prepare an Arena run</h2><button id="close-rubric" aria-label="Close rubric">Close</button></div><label for="arena-task">Question / task</label><p class="score">Enter the question you want the answers to solve. Saved runs show their original task here.</p><textarea id="arena-task" placeholder="What should the 16 independent answers solve?"></textarea><details><summary>Rubric used for this run</summary><div id="current-rubric"></div></details><label for="user-rubric">Grading guidance (optional)</label><p>Describe what a strong answer must achieve, what evidence to check, and what should fail. These criteria accompany the standard scoring rubric. Leave blank to use the standard rubric.</p><textarea id="user-rubric" placeholder="Example: Require reproducible evidence, cite the exact source, and prioritize a working implementation."></textarea><p class="score">Start creates 16 fixed answers, 15 judgments, and 2 finalist guides: 33 worker jobs. It uses your signed-in Codex account. Your task and rubric are saved before work begins.</p><div class="rubric-actions"><button id="start-arena" disabled>Start Arena</button><button id="download-rubric">Download rubric</button></div><p id="rubric-status" role="status"></p></section>
<template id="diagram-frame"><iframe sandbox="allow-scripts allow-downloads"></iframe></template>
<script id="arena-data" type="application/json">__DATA__</script>
<script>
'use strict';
const arena=JSON.parse(document.getElementById('arena-data').textContent),tree=document.getElementById('arena-tree'),panel=document.getElementById('results-panel');let selected=null,activeTab='answer';
tree.srcdoc=arena.tree_html;
function openPanel(){panel.hidden=false;document.getElementById('answer-picker').open=false;}
function select(id,tab='answer'){
 if(!Object.prototype.hasOwnProperty.call(arena.answers,id))return;
 selected=id;const a=arena.answers[id];activeTab=a.finalist?tab:'answer';openPanel();
 document.getElementById('selected').textContent=id;
 document.getElementById('answer-note').hidden=activeTab!=='answer';
 document.getElementById('badge').textContent=(a.champion?'Champion | ':'')+(a.finalist?'Finalist | Artifacts '+a.package_status:'Original answer');
 document.querySelectorAll('[data-answer]').forEach(b=>b.setAttribute('aria-current',String(b.dataset.answer===id)));
 document.querySelectorAll('[data-tab]').forEach(b=>{b.hidden=b.dataset.tab!=='answer'&&!a.finalist;b.setAttribute('aria-selected',String(b.dataset.tab===activeTab));});
 const body=document.getElementById('content');body.replaceChildren();
 if(activeTab==='archify'&&a.diagram){const frame=document.getElementById('diagram-frame').content.firstElementChild.cloneNode(true);frame.title=id+' architecture';frame.src=a.diagram;body.appendChild(frame);}
 else if(activeTab==='implementation'&&a.guide){body.innerHTML=a.guide;}
 else if(activeTab==='answer'&&a.status==='ready'){body.innerHTML=a.html;}
 else{body.textContent=activeTab==='answer'?(a.diagnostic||'Answer pending'):'Required finalist artifacts pending validation';body.className='pending';}
 if(body.childElementCount)body.className='';
 history.replaceState(null,'','#'+encodeURIComponent(id));
}
function matchResult(id){
 let match=null;arena.rounds.forEach((r,n)=>r.matches.forEach((m,i)=>{if((m.id||'r'+(n+1)+'-m'+String(i+1).padStart(2,'0'))===id)match=m;}));
 if(!match)return;openPanel();selected=null;
 document.getElementById('selected').textContent='Match '+id;
 document.getElementById('badge').textContent=match.winner?'Winner: '+match.winner:'Judgment pending';
 document.querySelectorAll('[data-tab]').forEach(b=>b.hidden=true);document.getElementById('answer-note').hidden=true;
 const body=document.getElementById('content');body.replaceChildren();
 const reason=document.createElement('p');reason.textContent=match.reason||'Judgment pending';body.appendChild(reason);
 [match.a,match.b].forEach(aid=>{if(!arena.answers[aid])return;const b=document.createElement('button');b.textContent='Read '+aid+(match.scores&&match.scores[aid]!==undefined?' | Score '+match.scores[aid]:'');b.onclick=()=>select(aid);body.appendChild(b);});
 history.replaceState(null,'','#match='+encodeURIComponent(id));
}
window.addEventListener('message',event=>{
 if(event.source!==tree.contentWindow||!event.data||event.data.type!=='arena-node-selected'||typeof event.data.id!=='string')return;
 const id=event.data.id;if(id.startsWith('draft_'))select(id.slice(6));else if(arena.answers[id])select(id);else if(id==='arena'&&arena.champion)select(arena.champion);else matchResult(id.replace('_','-'));
});
document.querySelectorAll('[data-answer]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.answer)));
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>select(selected,b.dataset.tab)));
function closeResults(){panel.hidden=true;history.replaceState(null,'',location.pathname+location.search);}
document.getElementById('close-results').onclick=closeResults;
function restoreHash(){let hash;try{hash=decodeURIComponent(location.hash.slice(1));}catch(e){return;}if(hash.startsWith('match='))matchResult(hash.slice(6));else if(hash.startsWith('focus=')){const node=hash.slice(6);if(node.startsWith('draft_'))select(node.slice(6));else matchResult(node.replace('_','-'));}else if(hash)select(hash);}
window.addEventListener('hashchange',restoreHash);restoreHash();
const taskInput=document.getElementById('arena-task');taskInput.value=arena.task_text;
const rubricDialog=document.getElementById('rubric-dialog'),rubricInput=document.getElementById('user-rubric'),rubricStatus=document.getElementById('rubric-status');
document.getElementById('current-rubric').innerHTML=arena.rubric_html;
try{rubricInput.value=localStorage.getItem('arena-user-rubric-draft')||'';}catch(e){}
rubricInput.addEventListener('input',()=>{try{localStorage.setItem('arena-user-rubric-draft',rubricInput.value);}catch(e){}});
document.getElementById('rubric-button').onclick=()=>{rubricDialog.hidden=false;taskInput.focus();};document.getElementById('close-rubric').onclick=()=>{rubricDialog.hidden=true;document.getElementById('rubric-button').focus();};
function rubricText(){const text=rubricInput.value;if(!text.trim()){rubricStatus.textContent='Enter your grading criteria first.';rubricInput.focus();return null;}return text;}
document.getElementById('download-rubric').onclick=()=>{const text=rubricText();if(text===null)return;const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download='user-rubric.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);rubricStatus.textContent='Rubric downloaded. Your grading criteria have been saved to a file.';};
const startButton=document.getElementById('start-arena'),stopButton=document.getElementById('stop-arena'),runStatus=document.getElementById('run-status');
let appConfig=null,currentStatus=null,pendingRun=null,starting=false,pollBusy=false;
function statusText(s){
 const phases={spawn:'Writing answers',judge:'Judging matches',artifacts:'Preparing finalist guides',initializing:'Preparing the tree',collect:'Recording judgments',advance:'Advancing winners',view:'Updating results'};
 if(s.status==='running')return (phases[s.phase]||'Arena running')+' | '+(s.completed||0)+'/'+(s.total||33)+' jobs | '+(s.active||[]).length+' active';
 if(s.status==='complete')return 'Complete | '+(s.completed||33)+' jobs';
 if(s.status==='failed')return 'Run stopped: '+(s.error||'A worker failed.');
 if(s.status==='cancelled')return 'Run cancelled';
 return 'Ready for your question';
}
function applyStatus(s){
 currentStatus=s;const caps=s.capabilities||(appConfig&&appConfig.capabilities)||{};
 startButton.disabled=starting||s.status==='running'||!caps.ready;stopButton.hidden=s.status!=='running';
 runStatus.textContent=statusText(s);
 if(!caps.ready)rubricStatus.textContent=caps.error||'Codex needs setup. Sign in to Codex and check the required local tools.';
 else if(s.status==='failed')rubricStatus.textContent=s.error||'The run could not finish. You can start a new run.';
 else if(s.status==='idle'&&!starting)rubricStatus.textContent='Codex is ready. Enter your question and start Arena here.';
 if(s.viewer_ready&&typeof s.viewer_url==='string'&&/^\/runs\/[A-Za-z0-9_-]+\/viewer\/index\.html$/.test(s.viewer_url)){
  if((pendingRun&&pendingRun===s.id)||(!Object.keys(arena.answers).length&&s.status==='running'))location.assign(s.viewer_url);
 }
 if(pendingRun&&(s.status==='failed'||s.status==='cancelled')){pendingRun=null;starting=false;startButton.textContent='Start Arena';startButton.disabled=!caps.ready;}
}
async function pollStatus(){
 if(pollBusy||!appConfig)return;pollBusy=true;
 try{const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw new Error('Arena server is unavailable.');applyStatus(await response.json());}
 catch(error){runStatus.textContent='Connection lost | Reconnecting';}
 finally{pollBusy=false;}
}
async function connectApp(){
 try{const response=await fetch('/api/config',{cache:'no-store'});if(!response.ok)throw new Error();appConfig=await response.json();if(typeof appConfig.token!=='string')throw new Error();await pollStatus();if(!Object.keys(arena.answers).length){rubricDialog.hidden=false;taskInput.focus();}}
 catch(error){startButton.disabled=true;rubricStatus.textContent='This is a saved report. Open the Arena app to start a run.';}
}
startButton.onclick=async()=>{
 const task=taskInput.value;if(!task.trim()){rubricStatus.textContent='Enter the question or task first.';taskInput.focus();return;}
 if(!appConfig||starting)return;starting=true;startButton.disabled=true;startButton.textContent='Starting...';rubricStatus.textContent='Saving the task and rubric. Preparing your Arena run...';
 try{const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json','X-Arena-Token':appConfig.token},body:JSON.stringify({task,rubric:rubricInput.value,agents:16,wave:3})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Unable to start Arena.');pendingRun=result.id;rubricDialog.hidden=true;runStatus.textContent='Preparing the tree...';await pollStatus();}
 catch(error){rubricStatus.textContent=error.message;starting=false;startButton.textContent='Start Arena';startButton.disabled=!(currentStatus&&currentStatus.capabilities&&currentStatus.capabilities.ready);}
};
stopButton.onclick=async()=>{if(!appConfig)return;stopButton.disabled=true;try{const response=await fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json','X-Arena-Token':appConfig.token},body:'{}'});if(!response.ok)throw new Error();await pollStatus();}catch(error){runStatus.textContent='Could not stop the run. Retry when the connection returns.';}finally{stopButton.disabled=false;}};
if(location.protocol!=='file:'){connectApp();setInterval(pollStatus,1500);}

document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!rubricDialog.hidden)document.getElementById('close-rubric').click();else closeResults();}});
if(location.protocol!=='file:')setInterval(async()=>{try{const r=await fetch(__STATE_FILE__,{cache:'no-store'});if(r.ok&&(await r.json()).state_sha256!==arena.state_sha256)location.reload();}catch(error){}},5000);
</script></body></html>'''
