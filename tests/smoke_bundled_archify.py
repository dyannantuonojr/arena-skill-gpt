"""Exercise an installed copy, including bundled native rendering/browser gates."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node', default=shutil.which('node'))
    args = parser.parse_args()
    if not args.node:
        parser.error('Node 18+ must be available on PATH or passed with --node')
    source = Path(__file__).resolve().parents[1] / 'skills' / 'arena'
    with tempfile.TemporaryDirectory(prefix='arena-install-smoke-') as directory:
        root = Path(directory)
        installed = root / 'installed' / 'arena'
        shutil.copytree(str(source), str(installed), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        check = subprocess.run([sys.executable, str(installed/'arena_setup.py'), '--check', '--probe-browser', '--json'], capture_output=True, text=True)
        if check.returncode:
            print(check.stdout, check.stderr)
            return check.returncode
        candidate = root / 'tree.json'
        candidate.write_text(json.dumps({'schema_version':1,'diagram_type':'tree',
            'meta':{'title':'Arena bundled renderer check','quality_profile':'showcase','output':'tree.html'},
            'layout':{'direction':'right'},'nodes':[
                {'id':'arena','label':'Arena','sublabel':'Installed bundle'},
                {'id':'a001','parent':'arena','label':'Answer 1','sublabel':'Separate worker'},
                {'id':'a002','parent':'arena','label':'Answer 2','sublabel':'Separate worker'}]}),encoding='utf-8')
        output = root / 'tree.html'
        result = subprocess.run([args.node,str(installed/'vendor'/'archify'/'bin'/'archify.mjs'),
            'finalize','tree',str(candidate),str(output),'--quality','showcase','--json'],
            capture_output=True,text=True,encoding='utf-8',timeout=180)
        if result.returncode:
            print(result.stdout[-9000:], result.stderr[-3000:])
            return result.returncode
        receipt = json.loads((root/'tree.finalize-summary.json').read_text(encoding='utf-8'))
        gates = receipt.get('gates',{})
        if not receipt.get('ok') or any(gates.get(key)!='pass' for key in ('validate','deliver','check','browser-check')):
            print(json.dumps(receipt))
            return 1
        print(json.dumps({'installed_copy':True,'bundled_renderer':True,'gates':gates,'status':'pass'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
