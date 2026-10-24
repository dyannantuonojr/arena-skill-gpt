"""Explicit browser fixture: no runner, Codex invocation, or real Arena jobs.

Run only for UI QA; the server binds to loopback and serves this fixture alone.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'arena'))
from arena_svg import diagram_svg
from arena_view import tree_document


def fixture():
    agents = {'a%03d' % i: {} for i in range(1, 17)}
    rounds = []
    current = list(agents)
    for n in range(1, 5):
        matches = [{'id': 'r%d-m%02d' % (n, i // 2 + 1), 'a': current[i], 'b': current[i+1],
                    'winner': current[i], 'scores': {current[i]: 8, current[i+1]: 7},
                    'reason': 'Software fixture judgment; not model evidence.'}
                   for i in range(0, len(current), 2)]
        rounds.append({'matches': matches})
        current = [m['winner'] for m in matches]
    state = {'dir': str(Path(__file__).parent.resolve()), 'agents': agents, 'rounds': rounds, 'champion': 'a001'}
    return {'id': 'fixture', 'status': {'status': 'complete', 'completed': 33, 'total': 33},
            'task': 'Software fixture: demonstrate the plugin interface', 'guidance': '',
            'tree_svg': diagram_svg(tree_document(state)), 'rounds': rounds, 'champion': 'a001',
            'answers': {a: {'ready': True, 'finalist': a in ('a001', 'a009'), 'champion': a == 'a001',
                            'package_ready': a in ('a001', 'a009')} for a in agents}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    data = json.dumps(fixture()).replace('<', '\\u003c')
    host = '''<!doctype html><title>Arena plugin software fixture</title><style>body{margin:0;background:#080e1d;color:white;font:14px system-ui}p{padding:10px;margin:0}iframe{width:100%;height:94vh;border:0}</style><p>SOFTWARE FIXTURE - no model jobs. <span id="calls">Starts: 0</span></p><button id="history" onclick="document.getElementById('app').src='/ui?historical=1'">Open historical fixture</button><button id="ready" onclick="state.answers.a016.ready=!state.answers.a016.ready">Toggle a016 readiness</button><span id="last">Last read: none</span><iframe id="app" src="/ui" sandbox="allow-scripts allow-same-origin"></iframe><script>
const state=__DATA__;let starts=0;window.addEventListener('message',e=>{if(e.source!==document.getElementById('app').contentWindow||!e.data)return;const m=e.data;if(m.method==='ui/notifications/initialized'){const run=document.getElementById('app').src.includes('historical=1')?'historical':null;const initial=run?{...state,id:run,task:'Historical fixture question'}:state;e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-input',params:{arguments:run?{run_id:run}:{}}},'*');e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:initial}},'*');return;}if(!m.id)return;let result={};if(m.method==='ui/initialize')result={protocolVersion:'2026-01-26',hostInfo:{name:'Fixture',version:'1'},hostCapabilities:{},hostContext:{}};else if(m.method==='tools/call'){const a=m.params.arguments||{},n=m.params.name;let value;if(n==='open_arena'){value=a.run_id==='historical'?{...state,id:'historical',task:'Historical fixture question'}:state;document.getElementById('last').textContent='Last read: '+value.id;}else if(n==='get_answer')value={id:a.answer_id,html:!state.answers[a.answer_id].ready?'Answer pending':'<h2>Software answer '+a.answer_id+'</h2><p>Fixture result for interface verification.</p><details><summary>Assumptions</summary><p>Fixture only.</p></details>'};else if(n==='get_finalist_package')value={guide:'<h2>Implementation '+a.answer_id+'</h2><p>Software guide.</p>',svg:'<svg viewBox="0 0 400 200" role="img"><rect x="20" y="40" width="350" height="100" rx="10"/><text x="40" y="100">Native diagram fixture '+a.answer_id+'</text></svg>'};else if(n==='start_run'){starts++;document.getElementById('calls').textContent='Starts: '+starts;state.status={status:'running',completed:0,total:33};state.task=a.question;state.guidance=a.guidance;value={id:'fixture',status:'running'};}else if(n==='stop_run'){state.status.status='cancelled';value=state.status;}else value=state.status;result={structuredContent:value,content:[{type:'text',text:JSON.stringify(value)}]};}else return;e.source.postMessage({jsonrpc:'2.0',id:m.id,result},'*');});</script>'''.replace('__DATA__', data)
    ui = Path(__file__).resolve().parents[1] / 'skills/arena/plugin/ui/index.html'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                content = host.encode()
            elif self.path.split('?')[0] == '/ui':
                content = ui.read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print('Software fixture http://127.0.0.1:%d/' % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
