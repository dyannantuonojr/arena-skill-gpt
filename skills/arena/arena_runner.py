"""Local Arena coordinator; each worker is an independent signed-in Codex CLI process.

Only the coordinator mutates arena.json. No API credentials or host agent tools
are required. The worker sandbox is workspace-write, with the run as its cwd.
"""
import concurrent.futures
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
import uuid

import bracket as B
import arena_setup
from arena_view import export_view, state_fingerprint


class RendererInfrastructureError(RuntimeError):
    """Retrying model authoring cannot repair the renderer environment."""


class Cancelled(Exception):
    pass


def child_environment():
    return {key: value for key, value in os.environ.items()
            if key.upper() not in ('CODEX_API_KEY', 'OPENAI_API_KEY', 'CONTROL_PLANE_API_KEY',
                                   'ARENA_OWNER_SUBJECT', 'ARENA_OAUTH_ISSUER',
                                   'ARENA_OAUTH_AUDIENCE', 'ARENA_OAUTH_JWKS_URL')}


def discover_program(name, explicit=None):
    value = explicit or os.environ.get('ARENA_' + name.upper())
    if value:
        resolved = shutil.which(str(value)) or str(Path(value).expanduser().resolve())
        if not Path(resolved).is_file():
            raise ValueError('%s executable not found: %s' % (name, value))
        return resolved
    if name == 'codex' and os.name == 'nt':
        # The desktop distribution has a native executable; avoid cmd wrappers.
        base = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI' / 'Codex' / 'bin'
        candidates = list(base.glob('*/codex.exe')) if base.is_dir() else []
        if candidates:
            return str(max(candidates, key=lambda path: path.stat().st_mtime))
    result = shutil.which(name + '.exe') if os.name == 'nt' else None
    result = result or shutil.which(name)
    if not result:
        raise ValueError('%s is not installed or available on PATH' % name)
    return result


def codex_prefix(executable, node=None):
    path = Path(executable)
    if path.suffix.lower() in ('.cmd', '.bat'):
        # Resolve the standard npm wrapper to its JavaScript entrypoint. Never
        # interpolate paths/prompts into cmd.exe or invoke a shell.
        script = path.parent / 'node_modules' / '@openai' / 'codex' / 'bin' / 'codex.js'
        if not script.is_file():
            raise ValueError('Use ARENA_CODEX with a native codex.exe; unsupported CLI wrapper: %s' % path)
        return [discover_program('node', node), str(script)]
    return [str(path)]


class ArenaRunner:
    planned_jobs = None

    def __init__(self, data_root, codex=None, node=None, repo_root=None):
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.codex = codex
        self.node = node
        self.repo_root = None
        if repo_root is not None:
            repository = Path(repo_root).expanduser().resolve()
            if not repository.is_dir():
                raise ValueError('Configured --repo-root must be an existing local Git working-tree root')
            try:
                result = subprocess.run(['git', '-C', str(repository), 'rev-parse', '--show-toplevel'],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        env=child_environment(), shell=False, timeout=10,
                                        encoding='utf-8', errors='replace')
                if result.returncode or Path(result.stdout.strip()).resolve() != repository:
                    raise ValueError('Configured --repo-root must be the local Git working-tree root')
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError('Cannot validate configured Git --repo-root: ' + str(error)) from error
            self.repo_root = str(repository)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._processes = set()
        self._cleanup_lock = threading.Lock()
        self._thread = None
        self._capabilities = None
        self._cap_checked = 0
        self._launcher = self._execute_job  # Tests can inject a worker, never used in production.
        self._state = {'status': 'idle', 'id': None, 'phase': None, 'completed': 0,
                       'total': 0, 'active': [], 'error': None, 'generation': 0,
                       'updated_at': time.time(), 'viewer_url': None, 'logs': []}
        self._arena = None
        self._ledger = {}

    def _update(self, **values):
        with self._lock:
            self._state.update(values)
            self._state['generation'] += 1
            self._state['updated_at'] = time.time()

    def _log(self, message):
        with self._lock:
            logs = (self._state['logs'] + [str(message)[-2000:]])[-40:]
            self._update(logs=logs)

    def capabilities(self):
        with self._lock:
            if self._capabilities is not None and time.monotonic() - self._cap_checked < 5:
                return copy.deepcopy(self._capabilities)
        result = {'ready': False, 'codex': None, 'node': None, 'auth': None,
                  'backend': 'codex-exec', 'max_workers': 3}
        try:
            executable = discover_program('codex', self.codex)
            node = discover_program('node', self.node)
            version = subprocess.run([node, '--version'], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, shell=False, timeout=10,
                                     encoding='utf-8', errors='replace')
            if version.returncode or int(version.stdout.strip().lstrip('v').split('.')[0]) < 18:
                raise ValueError('Arena requires Node.js 18 or newer')
            bundle = arena_setup.check_bundle()
            if bundle['status'] != 'pass':
                raise ValueError('Bundled Archify integrity check failed: ' + json.dumps(bundle))
            browser = arena_setup.probe_browser(node)
            result['browser'] = browser
            if browser['status'] != 'executable-found':
                raise ValueError('Chrome, Chromium or Edge is required for finalist diagrams. ' +
                                 str(browser.get('error', 'Set ARCHIFY_CHROME to your browser executable.')))
            prefix = codex_prefix(executable, node)
            login = subprocess.run(prefix + ['login', 'status'], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   env=child_environment(), shell=False, timeout=12,
                                   encoding='utf-8', errors='replace')
            text = login.stdout.strip()
            result.update(codex=executable, node=node, auth=text[-2000:])
            if login.returncode != 0 or 'logged in using chatgpt' not in text.lower():
                raise ValueError('Codex must be signed in using ChatGPT. Run codex login. ' + text[-600:])
            self._prefix = prefix
            self._node = node
            result['ready'] = True
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result['error'] = str(error)
        with self._lock:
            self._capabilities = result
            self._cap_checked = time.monotonic()
        return copy.deepcopy(result)

    def status(self):
        with self._lock:
            return copy.deepcopy(self._state)

    snapshot = status

    def restore(self, run_id):
        """Select a saved run for inspection without starting workers or writing files."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ValueError('An Arena run is already active. Stop it before selecting another.')
            if (not isinstance(run_id, str) or not run_id or run_id in ('.', '..')
                    or any(char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for char in run_id)):
                raise ValueError('Invalid saved Arena run ID')
            run = B.artifacts._contained(self.data_root / run_id, self.data_root)
            if not run.is_dir():
                raise ValueError('Saved Arena run directory does not exist: ' + run_id)
            def read_json(name, optional=False):
                path = B.artifacts._contained(run / name, run)
                if optional and not path.exists():
                    return {}
                value = json.loads(path.read_text(encoding='utf-8-sig'))
                if not isinstance(value, dict):
                    raise ValueError('Saved ' + name + ' must contain a JSON object')
                return value
            arena = read_json('arena.json')
            if Path(arena.get('dir', '')).resolve() != run.resolve():
                raise ValueError('Saved Arena directory does not match selected run directory')
            B.artifacts._contained(arena['dir'], run)
            for name in ('task.md', 'rubric.md', 'user-rubric.md'):
                path = B.artifacts._contained(run / name, run)
                if name == 'task.md' and not B._has_output(path):
                    raise ValueError('Saved Arena task input is missing or empty')
            for agent in arena['agents'].values():
                B.artifacts._contained(agent['solution'], run)
            viewer = arena.get('viewer') or {}
            for item in [viewer] + viewer.get('assets', []):
                if item.get('path'):
                    B.artifacts._contained(item['path'], run)
            if arena.get('supporting_documents_sha256'):
                from supporting_documents import verify_run_documents
                verify_run_documents(run,arena['supporting_documents_sha256'])
            B.verify_frozen_rubric(arena)
            B.verify_frozen_solutions(arena)
            ledger = read_json('runner-attempts.json', optional=True)
            for history in ledger.values():
                if not isinstance(history, list) or any(not isinstance(entry, dict) for entry in history):
                    raise ValueError('Saved runner attempts are invalid')
                if history and history[-1].get('accepted'):
                    for name, digest in history[-1].get('output_sha256', {}).items():
                        path = B.artifacts._contained(name, run)
                        if not path.is_file() or self._file_hash(path) != digest:
                            raise ValueError('Saved owned output integrity failure: ' + str(path))
            saved = read_json('runner-status.json', optional=True)
            phase, unused_left, unused_jobs = B.next_action(arena)
            complete = phase == 'done'
            if complete:
                B.verify_frozen_solutions(arena, required=True)
            status = 'complete' if complete else saved.get('status')
            if status not in ('complete', 'failed', 'cancelled') or (not complete and status == 'complete'):
                status = 'failed'
            error = None if complete else saved.get('error')
            if status == 'failed' and not error:
                error = 'Saved run is incomplete; passive restore does not resume workers.'
            total = B.plan_totals(arena['agents_n'], arena.get('wave', 1), arena.get('mode', 'select'),
                                  arena.get('require_finalist_artifacts', True))['calls']
            if arena.get('has_baseline'):
                total += 1
            completed = sum(B._has_output(agent['solution']) and bool(ledger.get(aid + '.spawn'))
                            and ledger[aid + '.spawn'][-1].get('accepted', False)
                            for aid, agent in arena['agents'].items())
            completed += sum(bool(match.get('winner')) for rd in arena['rounds'] for match in rd['matches'])
            completed += sum(B.artifacts.package_valid(arena, aid) for aid in B.artifacts.finalists(arena))
            if (arena.get('final') or {}).get('result'):
                completed += 1
            self._arena = arena
            self._ledger = ledger
            self._input_hashes = {}
            self._tree_source = None
            self._export_fingerprint = None
            self._stop = threading.Event()
            self._update(status=status, id=run_id, run_dir=str(run), phase='done' if complete else saved.get('phase', phase),
                         completed=total if complete else completed, total=total, active=[], error=error,
                         agents=arena['agents_n'], wave=arena.get('wave', 1),
                         viewer_ready=B.view_ready(arena), viewer_url='/runs/' + run_id + '/viewer/index.html',
                         logs=saved.get('logs', [])[-40:])
            return self.status()

    def start(self, task, rubric='', agents=16, wave=3, run_id=None, documents=None):
        if not isinstance(task, str) or not task.strip():
            raise ValueError('Enter a question or task before starting Arena.')
        if not isinstance(rubric, str):
            raise ValueError('Grading criteria must be text.')
        if isinstance(agents, bool) or not isinstance(agents, int) or not 1 <= agents <= 16:
            raise ValueError('agents must be an integer from 1 to 16')
        if isinstance(wave, bool) or not isinstance(wave, int) or not 1 <= wave <= 3:
            raise ValueError('wave must be an integer from 1 to 3')
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ValueError('An Arena run is already active. Stop it before starting another.')
            if run_id is not None and (not isinstance(run_id, str) or not run_id
                    or len(run_id) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id)):
                raise ValueError('Invalid reserved run ID')
            run_id = run_id or (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:10])
            run = self.data_root / run_id
            run.mkdir()  # Never reuse or overwrite an existing run.
            if documents:
                from supporting_documents import snapshot_documents
                snapshot_documents(run,documents)
            self._stop = threading.Event()
            self._ledger = {}
            self._input_hashes = {}
            self._arena = None
            self._tree_source = None
            self._export_fingerprint = None
            self._update(status='running', id=run_id, run_dir=str(run),
                         phase='initializing', completed=0,
                         total=self.planned_jobs or B.plan_totals(agents, wave, 'select')['calls'],
                         active=[], error=None, logs=[], agents=agents, wave=wave,
                         viewer_ready=False,
                         viewer_url='/runs/' + run_id + '/viewer/index.html')
            self._thread = threading.Thread(target=self._coordinate,
                                            args=(run, task, rubric, agents, wave), daemon=True)
            self._thread.start()
            return self.status()

    def stop(self):
        with self._lock:
            if self._state['status'] != 'running':
                return self.status()
            self._stop.set()
            self._update(phase='stopping')
            result = self.status()
            threading.Thread(target=self._reap_stopped, daemon=True).start()
        return result

    def _reap_stopped(self):
        with self._lock:
            processes = list(self._processes)
        for process in processes:
            self._terminate_owned(process)

    def _terminate_owned(self, process):
        # Serialize cleanup: a worker's finally block and the stop reaper must
        # never race to target a PID. Only a registered, still-live child is
        # eligible. Kill the tree before its root exits and loses ancestry.
        with self._cleanup_lock:
            with self._lock:
                if process not in self._processes or process.poll() is not None:
                    return
                try:
                    if os.name == 'nt':
                        result = subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL, shell=False, timeout=8,
                                                creationflags=subprocess.CREATE_NO_WINDOW)
                        if result.returncode and process.poll() is None:
                            process.kill()
                    else:
                        # Every worker has its own session/process group. Force
                        # the entire owned group down, including inherited pipes.
                        os.killpg(process.pid, signal.SIGKILL)
                except (OSError, subprocess.TimeoutExpired):
                    if process.poll() is None:
                        process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def _check_stop(self):
        if self._stop.is_set():
            raise Cancelled()

    def _persist_ledger(self):
        path = Path(self._arena['dir']) / 'runner-attempts.json'
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(self._ledger, indent=2), encoding='utf-8')
        os.replace(str(temporary), str(path))

    @staticmethod
    def _file_hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _owned_success(self, job):
        history = self._ledger.get(job['id'], [])
        return bool(history and history[-1].get('accepted') and
                    history[-1]['status'] in ('produced', 'complete'))

    def _assert_integrity(self):
        for path, digest in self._input_hashes.items():
            if not os.path.isfile(path) or self._file_hash(path) != digest:
                raise RuntimeError('Frozen Arena input changed: ' + path)
        for job_id, history in self._ledger.items():
            entry = history[-1]
            if not entry.get('accepted'):
                continue
            for path, digest in entry.get('output_sha256', {}).items():
                if not os.path.isfile(path) or self._file_hash(path) != digest:
                    raise RuntimeError('Owned output integrity failure for %s: %s changed' % (job_id, path))

    def _quarantine_unowned(self, jobs):
        for job in jobs:
            if self._owned_success(job):
                continue
            for path in job['outputs']:
                if os.path.isfile(path):
                    destination = path + '.unowned-' + uuid.uuid4().hex[:10]
                    os.replace(path, destination)
                    self._log('Quarantined output without an accepted owned attempt: ' + job['id'])

    def _next_owned_action(self):
        self._assert_integrity()
        # Files alone cannot skip a worker invocation, including whole phases
        # prewritten by a different worker. Inspect every currently possible phase
        # before consulting the bracket's file-based transition engine.
        for phase in ('spawn', 'judge', 'final', 'artifacts'):
            jobs = B.phase_jobs(self._arena, phase)
            self._quarantine_unowned(jobs)
        return B.next_action(self._arena)

    def _coordinate(self, run, task, rubric, agents, wave):
        try:
            capabilities = self.capabilities()
            if not capabilities['ready']:
                raise RuntimeError(capabilities.get('error', 'Codex CLI is unavailable'))
            self._check_stop()
            # Init is the authority for task validation and frozen rubric bytes.
            rubric_file = run / 'input-rubric.md'
            arguments = ['init', '--dir', str(run), '--agents', str(agents),
                         '--mode', 'select', '--wave', str(wave), '--task', task]
            if rubric.strip():
                with rubric_file.open('w', encoding='utf-8', newline='') as source:
                    source.write(rubric)
                arguments += ['--rubric-file', str(rubric_file)]
            args = B.build_parser().parse_args(arguments)
            args.preserve_task = True
            B.cmd_init(args)
            self._arena = B.load_state(args)
            self._input_hashes = {str(run / name): self._file_hash(run / name)
                                  for name in ('task.md', 'rubric.md', 'user-rubric.md')
                                  if (run / name).is_file()}
            from supporting_documents import register_documents
            self._input_hashes.update(register_documents(run,self._arena))
            B.save_state(self._arena)
            self._refresh(tree=True)
            while True:
                self._check_stop()
                B.verify_frozen_rubric(self._arena)
                phase, left, jobs = self._next_owned_action()
                self._update(phase=phase)
                if phase == 'done':
                    self._update(status='complete', active=[])
                    return
                if phase in B.PHASES:
                    B.write_prompts(self._arena, phase, artifact_renderer="runner", evidence_root=self.repo_root)
                    self._run_phase(phase, wave)
                elif phase == 'collect':
                    for mid, outcome, note in B.collect(self._arena):
                        self._log('%s: %s %s' % (mid, outcome, note))
                        key = mid + '.judge'
                        if self._ledger.get(key):
                            self._ledger[key][-1].update(status='complete' if outcome == 'recorded' else 'failed',
                                                        accepted=outcome == 'recorded',
                                                        validation=note or outcome)
                    self._persist_ledger()
                    B.save_state(self._arena)
                elif phase == 'advance':
                    B.advance(self._arena)
                    B.save_state(self._arena)
                elif phase != 'view':
                    raise RuntimeError('Unsupported bracket phase: ' + phase)
                self._refresh(tree=True, force=phase == 'view')
                if phase == 'view' and not B.view_ready(self._arena):
                    raise RuntimeError('Viewer delivery failed integrity validation after export')
        except Cancelled:
            self._update(status='cancelled', phase='cancelled', active=[])
        except Exception as error:
            self._stop.set()
            self._log(str(error))
            self._update(status='failed', error=str(error), active=[])
        finally:
            # The only processes in this set were created by this runner.
            self._reap_stopped()
            terminal = run / 'runner-status.json'
            temporary = terminal.with_suffix('.json.tmp')
            try:
                temporary.write_text(json.dumps(self.status(), indent=2), encoding='utf-8')
                os.replace(str(temporary), str(terminal))
            except OSError:
                pass

    def _run_phase(self, phase, wave):
        while True:
            self._check_stop()
            self._assert_integrity()
            phase_jobs = B.phase_jobs(self._arena, phase)
            jobs = [job for job in phase_jobs if not self._owned_success(job)]
            if not jobs:
                return
            batch = jobs[:wave]
            self._quarantine_unowned(batch)
            for job in batch:
                history = self._ledger.setdefault(job['id'], [])
                limit = 3 if job['kind'] in ('judge', 'final') else 2
                if len(history) >= limit:
                    raise RuntimeError('%s failed after %d attempts. Saved incomplete run: %s' %
                                       (job['id'], limit, self._arena['dir']))
                history.append({'attempt': len(history) + 1, 'phase': phase,
                                'started_at': time.time(), 'status': 'running'})
            self._persist_ledger()
            self._update(active=[{'job': job['id'], 'phase': phase,
                                  'attempt': len(self._ledger[job['id']])} for job in batch])
            # A bounded wave finishes before any following wave is admitted.
            with concurrent.futures.ThreadPoolExecutor(max_workers=wave) as pool:
                futures = {pool.submit(self._launcher, job, job['prompt'], self._arena['dir'], self._stop): job
                           for job in batch}
                while futures:
                    done, unused = concurrent.futures.wait(futures, timeout=2,
                                                          return_when=concurrent.futures.FIRST_COMPLETED)
                    for future in done:
                        job = futures.pop(future)
                        entry = self._ledger[job['id']][-1]
                        try:
                            code, detail = future.result()
                            if self._stop.is_set():
                                raise Cancelled()
                            if code:
                                raise RuntimeError('Codex exited %s: %s' % (code, detail[-1800:]))
                            if phase == 'artifacts':
                                self._render_artifact(job)
                                metadata = B.artifacts.accept_package(self._arena, job['agent'])
                                self._arena.setdefault('finalist_packages', {})[job['agent']] = metadata
                                B.save_state(self._arena)
                            elif not all(B._has_output(path) for path in job['outputs']):
                                raise RuntimeError('Worker exited without required nonempty output')
                            entry.update(status='produced', accepted=True, finished_at=time.time(),
                                         output_sha256={path: self._file_hash(path) for path in job['outputs']},
                                         detail=detail[-2000:])
                        except Cancelled:
                            entry.update(status='cancelled', finished_at=time.time())
                        except RendererInfrastructureError as error:
                            entry.update(status='failed', finished_at=time.time(), error=str(error),
                                         infrastructure_failure=True)
                            self._persist_ledger()
                            self._stop.set()
                            self._reap_stopped()
                            raise
                        except Exception as error:
                            entry.update(status='failed', finished_at=time.time(), error=str(error)[-2000:])
                            self._log(job['id'] + ': ' + str(error))
                            if phase == 'artifacts':
                                with Path(job['prompt']).open('a', encoding='utf-8') as brief:
                                    brief.write('\n\nFOCUSED CANDIDATE REPAIR: The runner rejected the previous attempt. '
                                                'Repair the candidate/guide using these actual diagnostics; '
                                                'do not generate HTML or receipts.\n' + str(error)[-12000:] + '\n')
                                    if 'repository-evidence/repository-required' in str(error):
                                        brief.write('node.sources is reserved for real committed repository evidence with '
                                                    'truthful pinned meta.repository. For nonrepository recommendations, '
                                                    'cite frozen answer sections in plain diagram cards and implementation.md; '
                                                    'do not represent the unversioned answer file as Git evidence. '
                                                    'Keep real repository provenance when it is valid.\n')
                            # A nonzero exit cannot become success merely because
                            # the process left a partial output on disk.
                            if phase != 'artifacts':
                                for output in job['outputs']:
                                    if os.path.isfile(output):
                                        os.replace(output, output + '.failed-attempt-%d' % entry['attempt'])
                        self._persist_ledger()
                    self._update(active=[{'job': job['id'], 'phase': phase,
                                          'attempt': len(self._ledger[job['id']])}
                                         for job in futures.values()])
                    if self._stop.is_set():
                        self._reap_stopped()
                    self._refresh(tree=bool(done))
            self._check_stop()

    def _render_artifact(self, job):
        """Finalize model-authored data in an owned trusted process, never in its sandbox."""
        try:
            self._finalize_artifact(job)
        except PermissionError as error:
            raise RendererInfrastructureError('Archify filesystem access failed: ' + str(error)) from error
        except B.artifacts.ArtifactError as error:
            if isinstance(error.__cause__, PermissionError):
                raise RendererInfrastructureError('Archify filesystem access failed: ' + str(error)) from error
            raise

    def _finalize_artifact(self, job):
        self._check_stop()
        artifacts = B.artifacts
        directory = Path(artifacts.package_dir(self._arena, job['agent']))
        candidate = artifacts._contained(directory / 'candidate.json', directory)
        guide = artifacts._contained(directory / 'implementation.md', directory)
        diagram = artifacts._contained(directory / 'diagram.html', directory)
        receipt = artifacts._contained(directory / 'review' / 'diagram.finalize-summary.json', directory)
        value = artifacts._object(artifacts._read(candidate), 'candidate specification')
        diagram_type = value.get('diagram_type')
        if diagram_type not in artifacts.NATIVE_TYPES:
            raise ValueError('candidate.diagram_type must be a supported native Archify type: ' +
                             ', '.join(sorted(artifacts.NATIVE_TYPES)))
        def has_repository_evidence(item):
            if isinstance(item, dict):
                if item.get('repository') or item.get('sources'):
                    return True
                return any(has_repository_evidence(child) for child in item.values())
            if isinstance(item, list):
                return any(has_repository_evidence(child) for child in item)
            return False
        if has_repository_evidence(value) and not self.repo_root:
            raise RendererInfrastructureError('Candidate contains repository evidence but no trusted repository root is configured. '
                                              'Restart the Arena server with operator --repo-root PATH pointing to the real local Git root; '
                                              'preserve valid pinned repository provenance. For a nonrepository task, repair the candidate '
                                              'to cite answer sections in plain cards/guide instead of node.sources.')
        if not artifacts._read(guide).decode('utf-8-sig').strip():
            raise ValueError('implementation.md must be nonempty UTF-8')
        # The CLI validates the schema. Containment and redirects are checked before
        # invoking trusted code; worker-produced receipts never establish acceptance.
        receipt.parent.mkdir(parents=True, exist_ok=True)
        if receipt.exists():
            os.replace(receipt, receipt.with_name(receipt.name + '.unowned-' + uuid.uuid4().hex[:10]))
        review = artifacts._contained(receipt.parent / ('attempt-' + uuid.uuid4().hex), directory)
        review.mkdir()
        source_hash = self._file_hash(candidate)
        cli = Path(__file__).resolve().parent / 'vendor' / 'archify' / 'bin' / 'archify.mjs'
        command = [self._node, str(cli), 'finalize', diagram_type, str(candidate), str(diagram),
                   '--quality', 'showcase', '--out-dir', str(review), '--json']
        if self.repo_root:
            command += ['--repo-root', self.repo_root]
        entry = self._ledger[job['id']][-1]
        record = {'command': command, 'review_dir': str(review), 'started_at': time.time()}
        entry['renderer'] = record
        log_path = review / 'runner-finalize.log'
        try:
            code, output = self._execute_renderer(command, directory, log_path)
            record.update(exit_code=code, finished_at=time.time(), log=str(log_path))
            try:
                summary = json.loads(output)
                if not isinstance(summary, dict):
                    raise ValueError('expected an object')
            except (ValueError, TypeError) as error:
                raise RendererInfrastructureError('Archify returned no valid JSON summary: ' + output[-3000:]) from error
            if code != 0:
                diagnostics = json.dumps(summary.get('diagnostics', summary), ensure_ascii=False)
                codes = [str(row.get('code', '')) for row in summary.get('diagnostics', []) if isinstance(row, dict)]
                if (any('path-identity' in item or item in ('finalize/runtime', 'browser-check/runtime', 'viewer/browser-check-runtime') for item in codes)
                        or any(token in diagnostics for token in ('EPERM', 'EACCES', 'ENOENT', 'browser-not-found'))):
                    raise RendererInfrastructureError('Archify infrastructure failure: ' + diagnostics)
                raise ValueError('Archify finalize rejected candidate: ' + diagnostics)
            if (summary.get('ok') is not True or summary.get('status') != 'pass'
                    or summary.get('command') != 'finalize' or summary.get('type') != diagram_type
                    or any(summary.get('gates', {}).get(gate) != 'pass'
                           for gate in ('validate', 'deliver', 'check', 'browser-check'))):
                raise RendererInfrastructureError('Archify exited without all passing native/browser gates: ' + output[-4000:])
            actual = summary.get('evidence', {}).get('summaryReceipt')
            if not isinstance(actual, str) or not Path(actual).is_absolute():
                raise RendererInfrastructureError('Archify did not identify its actual summary receipt')
            try:
                actual = artifacts._contained(actual, review)
            except artifacts.ArtifactError as error:
                raise RendererInfrastructureError('Archify summary receipt escaped owned review directory: ' + str(error)) from error
            if not actual.is_file():
                raise RendererInfrastructureError('Archify passing summary receipt is missing: ' + str(actual))
            data = actual.read_bytes()
            if artifacts._object(data, 'renderer summary receipt') != summary:
                raise RendererInfrastructureError('Archify output and saved summary receipt disagree')
            if self._file_hash(candidate) != source_hash:
                raise RendererInfrastructureError('Candidate changed during trusted finalization')
            # Preserve actual upstream receipt bytes; accept_package binds all hashes.
            receipt.write_bytes(data)
            record['summary_receipt'] = str(actual)
            self._check_stop()
        except (OSError, subprocess.SubprocessError) as error:
            raise RendererInfrastructureError('Archify infrastructure failure: ' + str(error)) from error
        finally:
            record['finished_at'] = time.time()

    def _execute_renderer(self, command, directory, log_path, timeout=180):
        # Register Node before Stop can inspect ownership. Its browser and renderer
        # subprocesses inherit the owned process tree/session, just like workers.
        with log_path.open('w+b') as log:
            with self._lock:
                self._check_stop()
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, cwd=str(directory),
                                           env=child_environment(), shell=False,
                                           **({'creationflags': subprocess.CREATE_NO_WINDOW}
                                              if os.name == 'nt' else {'start_new_session': True}))
                self._processes.add(process)
            started = time.monotonic()
            try:
                while True:
                    self._check_stop()
                    if time.monotonic() - started > timeout:
                        raise RendererInfrastructureError('Archify finalize timed out after %s seconds' % timeout)
                    try:
                        code = process.wait(timeout=.25)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                self._check_stop()
                log.seek(0)
                return code, log.read().decode('utf-8', errors='replace').strip()
            finally:
                self._terminate_owned(process)
                with self._lock:
                    self._processes.discard(process)

    def _worker_command(self, run):
        return self._prefix + ['exec', '--json', '--ephemeral', '--skip-git-repo-check',
                               '--sandbox', 'workspace-write', '--cd', str(run),
                               '-c', 'agents.enabled=false', '-']

    def _worker_input(self,prompt,run):
        from supporting_documents import documents_brief
        context=documents_brief(run) if self._arena and self._arena.get('supporting_documents_sha256') else ''
        return context+'Read and follow exactly this generated Arena worker brief: '+str(Path(prompt).resolve())+'\nWrite only the outputs and scratch files permitted by the brief.\n'

    def _execute_job(self, job, prompt, run, stop):
        attempt = len(self._ledger[job['id']])
        log_path = Path(run) / 'worker-logs' / (job['id'] + '-%d.jsonl' % attempt)
        log_path.parent.mkdir(exist_ok=True)
        # Write JSON events straight to disk. A descendant inheriting stdout
        # cannot hold a pipe read open after its owned root exits or is stopped.
        with log_path.open('w+b') as log:
            with self._lock:
                if stop.is_set():
                    raise Cancelled()
                environment = child_environment()
                environment['PATH'] = str(Path(self._node).parent) + os.pathsep + environment.get('PATH', '')
                process = subprocess.Popen(self._worker_command(run), stdin=subprocess.PIPE,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           cwd=run, env=environment, shell=False,
                                           **({'creationflags': subprocess.CREATE_NO_WINDOW}
                                              if os.name == 'nt' else {'start_new_session': True}))
                self._processes.add(process)
            try:
                process.stdin.write(self._worker_input(prompt,run).encode('utf-8'))
                process.stdin.close()
                while True:
                    try:
                        code = process.wait(timeout=.5)
                        break
                    except subprocess.TimeoutExpired:
                        if stop.is_set():
                            self._terminate_owned(process)
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 12000))
                return code, log.read().decode('utf-8', errors='replace')
            finally:
                self._terminate_owned(process)
                with self._lock:
                    self._processes.discard(process)
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()

    def _tree_candidate(self):
        state = self._arena
        nodes = {'arena': {'id': 'arena', 'label': 'Arena %d' % state['agents_n'],
                           'sublabel': 'Selected ' + state['champion'] if state.get('champion') else 'Independent answers'}}
        frontier = {}
        for aid in sorted(state['agents']):
            nid = 'draft_' + aid
            nodes[nid] = {'id': nid, 'label': aid, 'parent': 'arena', 'sublabel': 'Original answer'}
            frontier[aid] = nid
        for rd in state.get('rounds', []):
            previous = dict(frontier)
            for match in rd['matches']:
                mid = match['id']
                nodes[mid] = {'id': mid, 'label': 'R%d %s / %s' % (rd['n'], match['a'], match['b']),
                              'parent': 'arena', 'sublabel': 'Winner ' + match['winner'] if match.get('winner') else 'Judgment pending'}
                for aid in (match['a'], match['b']):
                    if aid in previous:
                        nodes[previous[aid]]['parent'] = mid
                if match.get('winner'):
                    frontier[match['winner']] = mid
        return {'schema_version': 1, 'diagram_type': 'tree',
                'meta': {'title': 'Arena tournament', 'quality_profile': 'standard'},
                'layout': {'direction': 'right'}, 'nodes': list(nodes.values())}

    def _published_intact(self):
        receipt = self._arena.get('viewer') or {}
        try:
            if self._file_hash(receipt['path']) != receipt['sha256']:
                return False
            return all(self._file_hash(asset['path']) == asset['sha256']
                       for asset in receipt.get('assets', []))
        except (OSError, KeyError, TypeError):
            return False

    def _refresh(self, tree=False, force=False):
        state = self._arena
        root = Path(state['dir'])
        if tree:
            visual = root / 'visual'
            visual.mkdir(exist_ok=True)
            candidate = visual / 'arena-tree.json'
            serialized = json.dumps(self._tree_candidate(), sort_keys=True)
            if serialized != self._tree_source:
                self._render_tree(visual, candidate, serialized)
                self._tree_source = serialized
        fingerprint = state_fingerprint(state)
        if not force and fingerprint == self._export_fingerprint and self._published_intact():
            return
        self._export_view(state, root)

    def _render_tree(self, visual, candidate, serialized):
        candidate.write_text(serialized, encoding='utf-8')
        temporary = visual / 'arena-tree.next.html'
        renderer = Path(__file__).resolve().parent / 'vendor' / 'archify' / 'renderers' / 'tree' / 'render-tree.mjs'
        result = subprocess.run([self._node, str(renderer), str(candidate), str(temporary)],
                                cwd=self._arena['dir'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                shell=False, timeout=45, encoding='utf-8', errors='replace')
        if result.returncode:
            raise RuntimeError('Arena native tree rendering failed: ' + result.stdout[-2000:])
        os.replace(str(temporary), str(visual / 'arena-tree.html'))

    def _export_view(self, state, root):
        # Export receipts use canonical paths; normalize Windows 8.3 aliases
        # before computing asset-relative paths during atomic publication.
        root = Path(root).resolve()
        viewer = root / 'viewer'
        staging = viewer / '.refresh'
        staging.mkdir(parents=True, exist_ok=True)
        receipt = export_view(state, str(staging / 'index.html'))
        # Publish complete files with atomic replacement so polling never sees a
        # half-written HTML/JSON file. Preserve exporter-generated relative URLs.
        assets = []
        for asset in receipt['assets']:
            source = Path(asset['path'])
            destination = viewer / source.relative_to(staging)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix('.html.tmp')
            shutil.copyfile(str(source), str(temporary))
            os.replace(str(temporary), str(destination))
            assets.append(dict(asset, path=str(destination)))
        for name in ('index.html', 'index.state.json'):
            os.replace(str(staging / name), str(viewer / name))
        receipt.update(path=str(viewer / 'index.html'), assets=assets)
        state['viewer'] = receipt
        self._export_fingerprint = receipt['state_sha256']
        B.save_state(state)
        completed = sum(B._has_output(agent['solution']) and
                        bool(self._ledger.get(aid + '.spawn')) and
                        self._ledger[aid + '.spawn'][-1]['status'] in ('produced', 'complete')
                        for aid, agent in state['agents'].items())
        completed += sum(bool(match.get('winner')) for rd in state['rounds'] for match in rd['matches'])
        completed += len(state.get('finalist_packages', {}))
        self._update(completed=completed, viewer_ready=True)
