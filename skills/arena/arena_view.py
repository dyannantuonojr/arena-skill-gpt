"""Portable, offline all-answer arena viewer. Standard library only."""
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
    data = {'answers': answers, 'rounds': state.get('rounds', []), 'champion': state.get('champion'), 'state_sha256': fingerprint}
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
    values = {'__HEADLINE__': html.escape(headline), '__SIDEBAR__': sidebar, '__BRACKET__': ''.join(rounds), '__COUNTER__': html.escape(counter), '__DATA__': encoded, '__STATE_FILE__': json.dumps(output.stem+'.state.json').replace('<', '\\u003c')}
    page = re.sub(r'__HEADLINE__|__SIDEBAR__|__BRACKET__|__COUNTER__|__DATA__|__STATE_FILE__', lambda m: values[m[0]], _PAGE)
    output.write_text(page, encoding='utf-8')
    output.with_suffix('.state.json').write_text(json.dumps({'state_sha256': fingerprint}), encoding='utf-8')
    return {'path': str(output), 'sha256': _sha(output), 'state_sha256': fingerprint, 'assets': assets, 'answers_complete': bool(answers) and all(item['status'] == 'ready' for item in answers.values())}


_PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Arena results</title>
<style>
:root{color-scheme:light;--ink:#17283b;--line:#d8e1e7;--accent:#007d79}*{box-sizing:border-box}body{margin:0;background:#f2f5f7;color:var(--ink);font:15px/1.6 system-ui,sans-serif}header{padding:20px 28px;background:#102e3c;color:white}h1{margin:0;font-size:24px}header p{margin:5px 0;color:#c0d9df}.layout{display:grid;grid-template-columns:245px minmax(0,1fr);max-width:1800px;margin:auto}aside{padding:20px 14px;border-right:1px solid var(--line)}aside nav{display:grid;gap:7px;position:sticky;top:12px}button{cursor:pointer;border:1px solid var(--line);border-radius:7px;padding:9px 12px;background:white;color:var(--ink);text-align:left;font:inherit}button:hover,button[aria-current=true]{border-color:var(--accent);background:#e2f4f1}main{min-width:0;padding:22px}.bracket{display:flex;gap:14px;overflow:auto;padding-bottom:14px}.round{min-width:235px;flex:1}.match{background:white;padding:12px;border:1px solid var(--line);border-radius:9px;margin-bottom:10px}.match button{width:100%}.match p{font-size:13px;margin-bottom:0}.score{font-size:12px;display:block;margin:3px 0 8px;color:#4a6070}article{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin-top:18px;min-height:450px}.tabs{display:flex;gap:8px;margin-bottom:20px}.tabs button[aria-selected=true]{background:var(--accent);color:white}h2{font-size:23px}h3{font-size:18px}pre{background:#102e3c;color:#ecf6f8;padding:16px;overflow:auto;border-radius:7px}code{font-family:Consolas,monospace}p{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#00766d}.scope{background:#f5f7f8;border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0}summary{cursor:pointer;font-weight:600}table{border-collapse:collapse;width:100%}th,td{padding:8px;border:1px solid var(--line);text-align:left}.table-wrap{overflow:auto}iframe{width:100%;height:75vh;border:1px solid var(--line);border-radius:8px}.pending{color:#765e2f}#badge{font-size:14px;color:#00766d}#content{max-width:1050px}#content h1{font-size:28px;margin:20px 0 12px}@media(max-width:750px){.layout{display:block}aside{border:0}aside nav{position:static;display:flex;overflow:auto}aside button{flex-shrink:0}main{padding:12px}article{padding:16px}.tabs{flex-wrap:wrap}}
</style></head><body><header><h1>Arena results</h1><p>__HEADLINE__</p><details><summary>Run details</summary><p>__COUNTER__</p><p>Judge scores compare the answers; they are not accuracy percentages.</p></details></header><div class="layout"><aside><h2>Browse all answers</h2><nav aria-label="All answers">__SIDEBAR__</nav></aside><main><details><summary>Tournament bracket | select any competitor</summary><div class="bracket">__BRACKET__</div></details><article><h2 id="selected"></h2><p id="badge"></p><div class="tabs" role="tablist"><button role="tab" data-tab="answer">Answer</button><button role="tab" data-tab="implementation">Implementation</button><button role="tab" data-tab="archify">Archify</button></div><p id="answer-note" class="score">Original answer, unchanged. Implementation guide reflects the required outputs.</p><div id="content"></div></article></main></div>
<template id="diagram-frame"><iframe sandbox=""></iframe></template>
<script id="arena-data" type="application/json">__DATA__</script>
<script>
'use strict';
const arena=JSON.parse(document.getElementById('arena-data').textContent);let selected=null,activeTab='answer';
function select(id,tab='answer'){
 if(!Object.prototype.hasOwnProperty.call(arena.answers,id)) id=Object.keys(arena.answers)[0];
 if(!id){document.getElementById('content').textContent='Answers pending';return;}
 selected=id;const a=arena.answers[id];activeTab=a.finalist?tab:'answer';
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
 if(location.hash.slice(1)!==id)history.replaceState(null,'','#'+encodeURIComponent(id));
}
document.querySelectorAll('[data-answer]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.answer)));
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>select(selected,b.dataset.tab)));
window.addEventListener('hashchange',()=>select(decodeURIComponent(location.hash.slice(1))));
select(decodeURIComponent(location.hash.slice(1))||arena.champion);
if(location.protocol!=='file:')setInterval(async()=>{try{const r=await fetch(__STATE_FILE__,{cache:'no-store'});if(r.ok&&(await r.json()).state_sha256!==arena.state_sha256)location.reload();}catch(error){}},5000);
</script></body></html>'''
