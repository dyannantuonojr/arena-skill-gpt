"""Explicit browser fixture: no runner, Codex invocation, or real Arena jobs.

Run only for UI QA; the server binds to loopback and serves this fixture alone.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile

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
    return {'id': 'fixture', 'status': {'status': 'complete', 'completed': 33, 'total': 33}, 'uploads_available':True,
            'task': 'Software fixture: demonstrate the plugin interface', 'guidance': '',
            'tree_svg': diagram_svg(tree_document(state)), 'rounds': rounds, 'champion': 'a001',
            'answers': {a: {'ready': True, 'finalist': a in ('a001', 'a009'), 'champion': a == 'a001',
                            'package_ready': a in ('a001', 'a009')} for a in agents}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grudge', action='store_true')
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    from supporting_documents import DocumentStore
    document_tmp=tempfile.TemporaryDirectory()
    document_store=DocumentStore(Path(document_tmp.name)/'uploads')
    state = fixture()
    from grudge_match import LABELS, tree_svg
    state.update(id='grudge-fixture', champion='a002', task='Software fixture: Grudge Match', status={'status':'complete','completed':6,'total':6})
    state['answers'] = {key: {'ready':True, 'label':label, 'finalist':key=='a002', 'champion':key=='a002', 'package_ready':key=='a002', 'evidence_ready':key in ('a001','review','a002')} for key,label in LABELS.items()}
    state['tree_svg'] = tree_svg(state['answers'], 'a002')
    grudge_state = state
    state = grudge_state if args.grudge else fixture()
    from test_grudge_evidence import evidence_fixture
    from grudge_evidence import report_html
    data = json.dumps({'initial': state, 'arena': fixture(), 'grudge': grudge_state, 'evidence_html': report_html(evidence_fixture()), 'per_answer_evidence': {aid: report_html(evidence_fixture(),origin=origin) for aid,origin in {'a001':'original','review':'review','a002':'synthesis'}.items()}}).replace('<', '\\u003c')
    host = '''<!doctype html><title>Arena plugin software fixture</title><style>body{margin:0;background:#080e1d;color:white;font:14px system-ui}p{padding:10px;margin:0}iframe{width:100%;height:94vh;border:0}</style><p>SOFTWARE FIXTURE - no model jobs. <span id="calls">Starts: 0</span></p><button id="history" onclick="document.getElementById('app').src='/ui?historical=1'">Open historical fixture</button><button id="ready" onclick="state.answers.a016.ready=!state.answers.a016.ready">Toggle a016 readiness</button><button id="fail" onclick="failNextRead=true">Fail next mode read</button><span id="last">Last read: none</span><span id="source"></span><button id="evidence-ready" onclick="state.answers.evidence.ready=!state.answers.evidence.ready;for(const id of ['a001','review','a002'])state.answers[id].evidence_ready=state.answers.evidence.ready">Toggle evidence readiness</button><iframe id="app" src="/ui" sandbox="allow-scripts allow-same-origin"></iframe><script>
const views=__DATA__;let state=views.initial,starts=0,failNextRead=false;window.addEventListener('message',e=>{if(e.source!==document.getElementById('app').contentWindow||!e.data)return;const m=e.data;if(m.method==='ui/notifications/initialized'){const run=document.getElementById('app').src.includes('historical=1')?'historical':null;const initial=run?{...state,id:run,task:'Historical fixture question'}:state;e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-input',params:{arguments:run?{run_id:run}:{}}},'*');e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:initial}},'*');return;}if(!m.id)return;let result={};if(m.method==='ui/initialize')result={protocolVersion:'2026-01-26',hostInfo:{name:'Fixture',version:'1'},hostCapabilities:{},hostContext:{}};else if(m.method==='ui/open-link'){document.getElementById('source').textContent='Opened source: '+m.params.url;result={};}else if(m.method==='tools/call'){const a=m.params.arguments||{};let n=m.params.name;if(n==='upload_supporting_document'||n==='read_supporting_document'){fetch('/documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,arguments:a})}).then(r=>r.json()).then(r=>e.source.postMessage(r.error?{jsonrpc:'2.0',id:m.id,error:{code:-32000,message:r.error}}:{jsonrpc:'2.0',id:m.id,result:{structuredContent:r,content:[{type:'text',text:JSON.stringify(r)}]}},'*')).catch(error=>e.source.postMessage({jsonrpc:'2.0',id:m.id,error:{code:-32000,message:String(error)}},'*'));return;}if(failNextRead&&n.startsWith('open_')){failNextRead=false;e.source.postMessage({jsonrpc:'2.0',id:m.id,error:{code:-32000,message:'Software fixture read failure'}},'*');return;}state=views[n.includes('grudge')?'grudge':'arena'];n=({open_grudge_match:'open_arena',get_grudge_answer:'get_answer',get_grudge_winner_package:'get_finalist_package',start_grudge_match:'start_run',stop_grudge_match:'stop_run'})[n]||n;let value;if(n==='open_arena'){value=a.run_id==='historical'?{...state,id:'historical',task:'Historical fixture question'}:state;document.getElementById('last').textContent='Last read: '+value.id;}else if(n==='get_answer')value={id:a.answer_id,html:a.answer_id==='evidence'?views.evidence_html:!state.answers[a.answer_id].ready?'Answer pending':'<h2>Software answer '+a.answer_id+'</h2><p>Fixture result for interface verification.</p><details><summary>Assumptions</summary><p>Fixture only.</p></details>'+((state.id==='grudge-fixture'&&state.answers[a.answer_id].evidence_ready)?views.per_answer_evidence[a.answer_id]:'' )};else if(n==='get_finalist_package')value={guide:'<h2>Implementation '+a.answer_id+'</h2><p>Software guide.</p>',svg:'<svg viewBox="0 0 400 200" role="img"><rect x="20" y="40" width="350" height="100" rx="10"/><text x="40" y="100">Native diagram fixture '+a.answer_id+'</text></svg>'};else if(n==='start_run'){starts++;document.getElementById('calls').textContent='Starts: '+starts;state.status={status:'running',completed:0,total:33};state.task=a.question;state.guidance=a.guidance;value={id:'fixture',status:'running'};}else if(n==='stop_run'){state.status.status='cancelled';value=state.status;}else value=state.status;result={structuredContent:value,content:[{type:'text',text:JSON.stringify(value)}]};}else return;e.source.postMessage({jsonrpc:'2.0',id:m.id,result},'*');});</script>'''.replace('__DATA__', data)
    ui = Path(__file__).resolve().parents[1] / 'skills/arena/plugin/ui/index.html'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/', '/?narrow=1'):
                content = host.encode()
                if self.path == '/?narrow=1':
                    content = content.replace(b'iframe{width:100%;', b'iframe{width:700px;max-width:100%;')
            elif self.path.split('?')[0] == '/ui':
                content = ui.read_bytes()
                if args.grudge:
                    content = content.replace(b'<body>', b'<body data-workflow="grudge">')
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
        def do_POST(self):
            if self.path!='/documents':self.send_error(404);return
            size=int(self.headers.get('Content-Length','0'))
            if size>128*1024:self.send_error(413);return
            try:
                request=json.loads(self.rfile.read(size));args=request['arguments']
                if request['name']=='upload_supporting_document':result=document_store.upload(**args)
                elif request['name']=='read_supporting_document':result=document_store.preview(args['document_id'],args.get('locator',''))
                else:raise ValueError('Unknown fixture tool')
            except Exception as error:result={'error':str(error)}
            data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
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
        document_tmp.cleanup()


if __name__ == '__main__':
    main()
