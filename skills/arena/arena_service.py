"""Owner-scoped control plane; no MCP dependency and no model calls on reads."""
import hashlib
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import threading
import uuid

import bracket as B
from arena_view import render_markdown

TERMINAL = ('complete', 'failed', 'cancelled')
MAX_TEXT = 60000


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Invalid identifier')
    return value


def public_status(value):
    return {k: value[k] for k in ('id', 'status', 'phase', 'completed', 'total',
                                'generation', 'updated_at', 'viewer_ready') if k in value}


class ArenaService:
    def __init__(self, data_root, runner, database=None):
        raw = Path(data_root).absolute()
        B.artifacts._reject_redirects(raw)
        self.root = raw.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.database = B.artifacts._contained(database or self.root / 'plugin-requests.sqlite3', self.root)
        for suffix in ('', '-wal', '-shm', '-journal'):
            B.artifacts._reject_redirects(Path(str(self.database) + suffix))
        self.lock = threading.RLock()
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (request TEXT PRIMARY KEY, digest TEXT NOT NULL, run TEXT UNIQUE NOT NULL, state TEXT NOT NULL)')

    @contextmanager
    def _db(self):
        B.artifacts._reject_redirects(self.database)
        connection = sqlite3.connect(str(self.database), timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _path(self, run_id, name):
        return B.artifacts._contained(self.root / identifier(run_id) / name, self.root / run_id)

    def _json(self, run_id, name):
        path = self._path(run_id, name)
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Saved data exceeds limit')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError('Invalid saved data')
        return value

    def start_run(self, question, guidance='', request_id=None):
        identifier(request_id)
        if not isinstance(question, str) or not question.strip() or len(question) > MAX_TEXT:
            raise ValueError('Enter a question of at most 60000 characters')
        if not isinstance(guidance, str) or len(guidance) > MAX_TEXT:
            raise ValueError('Guidance must be text of at most 60000 characters')
        digest = hashlib.sha256(json.dumps([question, guidance], ensure_ascii=True).encode()).hexdigest()
        with self.lock:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT digest,run FROM requests WHERE request=?', (request_id,)).fetchone()
                if existing:
                    if existing[0] != digest:
                        raise ValueError('Request ID already binds different inputs')
                    return self.get_run_status(existing[1])
                if self.runner.status().get('status') == 'running':
                    raise ValueError('An Arena run is already active')
                for run_id, in db.execute("SELECT run FROM requests WHERE state IN ('reserved','started')"):
                    if self.get_run_status(run_id).get('status') not in TERMINAL:
                        raise ValueError('An active or interrupted reservation requires operator recovery')
                    db.execute("UPDATE requests SET state='finished' WHERE run=?", (run_id,))
                run_id = 'arena-' + uuid.uuid4().hex
                db.execute('INSERT INTO requests VALUES (?,?,?,?)', (request_id, digest, run_id, 'reserved'))
            # Commit the stable identity BEFORE workers can start. A failed launch
            # keeps its reservation; retrying never launches it again.
            result = self.runner.start(question, rubric=guidance, agents=16, wave=3, run_id=run_id)
            with self._db() as db:
                db.execute("UPDATE requests SET state='started' WHERE run=?", (run_id,))
            return public_status(result)

    def get_run_status(self, run_id):
        identifier(run_id)
        current = self.runner.status()
        if current.get('id') == run_id:
            return public_status(current)
        try:
            saved = self._json(run_id, 'runner-status.json')
            if saved.get('id') != run_id:
                raise ValueError('Saved run identity mismatch')
            result = public_status(saved)
            if result.get('status') not in TERMINAL:
                result['status'] = 'interrupted'
            return result
        except FileNotFoundError:
            with self._db() as db:
                row = db.execute('SELECT run FROM requests WHERE run=?', (run_id,)).fetchone()
            if row:
                return {'id': run_id, 'status': 'interrupted', 'completed': 0, 'total': 33}
            raise ValueError('Unknown run')

    def _arena(self, run_id):
        value = self._json(run_id, 'arena.json')
        root = self._path(run_id, 'arena.json').parent
        if Path(value.get('dir', '')).resolve() != root.resolve():
            raise ValueError('Saved directory identity mismatch')
        for agent in value.get('agents', {}).values():
            B.artifacts._contained(agent['solution'], root)
        B.verify_frozen_rubric(value)
        B.verify_frozen_solutions(value)
        return value

    def _text(self, path):
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Artifact exceeds read limit')
        return path.read_text(encoding='utf-8-sig')

    def get_answer(self, run_id, answer_id):
        identifier(answer_id)
        arena = self._arena(run_id)
        if answer_id not in arena['agents']:
            raise ValueError('Unknown answer')
        path = B.artifacts._contained(arena['agents'][answer_id]['solution'], self.root / run_id)
        text = self._text(path)
        return {'id': answer_id, 'text': text, 'html': render_markdown(text),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def get_finalist_package(self, run_id, answer_id):
        from arena_svg import diagram_svg
        identifier(answer_id)
        arena = self._arena(run_id)
        if not B.artifacts.package_valid(arena, answer_id):
            raise ValueError('Finalist package is not ready or failed integrity checks')
        directory = Path(B.artifacts.package_dir(arena, answer_id))
        guide = self._text(directory / 'implementation.md')
        return {'id': answer_id, 'guide': render_markdown(guide),
                'svg': diagram_svg(self._text(directory / 'diagram.html')),
                'gates': {g: 'pass' for g in ('validate', 'deliver', 'check', 'browser-check')}}

    def open_arena(self, run_id=None):
        run_id = run_id or self.runner.status().get('id')
        if not run_id:
            return {'id': None, 'status': {'status': 'idle'}, 'answers': {}, 'rounds': [], 'task': '', 'guidance': '', 'tree_svg': ''}
        from arena_svg import diagram_svg
        from arena_view import tree_document
        status = self.get_run_status(run_id)
        try:
            arena = self._arena(run_id)
        except FileNotFoundError:
            return {'id': run_id, 'status': status, 'answers': {}, 'rounds': [], 'tree_svg': ''}
        answers = {}
        finalists = B.artifacts.finalists(arena)
        for aid, agent in arena['agents'].items():
            answers[aid] = {'ready': Path(agent['solution']).is_file(),
                            'finalist': aid in finalists, 'champion': aid == arena.get('champion'),
                            'package_ready': B.artifacts.package_valid(arena, aid) if aid in finalists else False}
        def input_text(name):
            try:
                return self._text(self._path(run_id, name))
            except FileNotFoundError:
                return ''
        return {'id': run_id, 'status': status, 'answers': answers, 'rounds': arena.get('rounds', []),
                'champion': arena.get('champion'), 'task': input_text('task.md'), 'guidance': input_text('user-rubric.md'),
                'tree_svg': diagram_svg(tree_document(arena))}

    def stop_run(self, run_id):
        identifier(run_id)
        with self.lock:
            current = self.runner.status()
            if current.get('id') != run_id:
                raise ValueError('Requested run is not the active owned run')
            return public_status(self.runner.stop())
