"""Required finalist implementation packages and local integrity checks.

An unsigned finalize receipt records reported Archify gates; these checks do not
cryptographically attest renderer identity or the semantic truth of a diagram.
Only accept_package writes files, and none of these functions mutate arena state.
"""
import hashlib
import json
import os
from pathlib import Path


class ArtifactError(ValueError):
    """A required finalist package is missing, stale, or invalid."""


NATIVE_TYPES = frozenset(('workflow', 'architecture', 'sequence', 'dataflow',
                          'lifecycle', 'tree', 'erd', 'class', 'timeline', 'waterfall'))


def finalists(state):
    """Return both final-round entrants, a singleton, or no entrants yet."""
    agents = state.get('agents', {})
    if len(agents) == 1:
        return list(agents)
    rounds = state.get('rounds', [])
    if rounds:
        last = rounds[-1]
        matches = last.get('matches', [])
        if len(matches) == 1 and not last.get('bye'):
            match = matches[0]
            pair = [match.get('a'), match.get('b')]
            if pair[0] != pair[1] and all(a in agents for a in pair):
                return pair
    champion = state.get('champion')
    return [champion] if champion in agents else []


def _reject_redirects(path):
    """Reject links/junctions while allowing Windows 8.3 path spellings."""
    for current in (path,) + tuple(path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ArtifactError('symlink or redirected path: %s' % current)


def _root(state):
    try:
        root = Path(os.path.abspath(state['dir']))
        _reject_redirects(root)
        return root
    except (KeyError, TypeError, OSError, RuntimeError) as exc:
        raise ArtifactError('invalid RUN directory: %s' % exc)


def _contained(path, boundary):
    """Check canonical containment without mistaking 8.3 aliases for links."""
    path = Path(os.path.abspath(str(path)))
    try:
        _reject_redirects(path)
        path.resolve().relative_to(boundary.resolve())
    except (ValueError, OSError, RuntimeError) as exc:
        raise ArtifactError('path escapes its canonical directory: %s (%s)' % (path, exc))
    return path


def package_dir(state, aid):
    """Return the absolute canonical package directory for a finalist."""
    if not isinstance(aid, str) or not aid or aid in ('.', '..') or '/' in aid or '\\' in aid or ':' in aid:
        raise ArtifactError('invalid finalist ID')
    if aid not in finalists(state):
        raise ArtifactError('agent is not a finalist: %s' % aid)
    root = _root(state)
    return str(_contained(root / 'artifacts' / 'finalists' / aid, root))


def _read(path):
    try:
        if not path.is_file():
            raise ArtifactError('required file is missing: %s' % path)
        return path.read_bytes()
    except OSError as exc:
        raise ArtifactError('cannot read %s: %s' % (path, exc))


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _object(data, label):
    try:
        value = json.loads(data.decode('utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError('expected a JSON object')
        return value
    except (ValueError, UnicodeError) as exc:
        raise ArtifactError('invalid %s: %s' % (label, exc))


def _inspect(state, aid):
    directory = Path(package_dir(state, aid))
    root = _root(state)
    try:
        solution = _contained(state['agents'][aid]['solution'], root)
    except (KeyError, TypeError) as exc:
        raise ArtifactError('missing finalist solution: %s' % exc)
    files = {
        'guide': 'implementation.md', 'candidate': 'candidate.json',
        'diagram': 'diagram.html', 'receipt': 'review/diagram.finalize-summary.json',
    }
    paths = {key: _contained(directory / name, directory) for key, name in files.items()}
    data = {key: _read(path) for key, path in paths.items()}
    try:
        if not data['guide'].decode('utf-8-sig').strip():
            raise ArtifactError('implementation guide must not be blank')
    except UnicodeError as exc:
        raise ArtifactError('implementation guide must be UTF-8: %s' % exc)
    _object(data['candidate'], 'candidate specification')
    if not data['diagram'].strip():
        raise ArtifactError('diagram must not be blank')
    receipt = _object(data['receipt'], 'finalize receipt')
    if (receipt.get('ok') is not True or receipt.get('command') != 'finalize'
            or receipt.get('status') != 'pass' or not isinstance(receipt.get('type'), str)
            or receipt.get('type') not in NATIVE_TYPES):
        raise ArtifactError('receipt must report successful native Archify finalize')
    gates = receipt.get('gates')
    if not isinstance(gates, dict) or any(gates.get(g) != 'pass' for g in ('validate', 'deliver', 'check', 'browser-check')):
        raise ArtifactError('all finalize gates, including browser-check, must pass')
    for binding, key in (('specification', 'candidate'), ('artifact', 'diagram')):
        entry = receipt.get(binding)
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            raise ArtifactError('receipt is missing %s binding' % binding)
        bound = Path(entry['path'])
        if not bound.is_absolute() or _contained(bound, directory) != paths[key]:
            raise ArtifactError('receipt %s path does not bind canonical file' % binding)
        if entry.get('sha256') != _digest(data[key]):
            raise ArtifactError('receipt %s hash does not match file' % binding)
    metadata = {'directory': str(directory), 'solution_sha256': _digest(_read(solution))}
    metadata.update({key + '_sha256': _digest(value) for key, value in data.items()})
    return metadata


def accept_package(state, aid):
    """Validate files, write manifest.json, and return metadata for the caller to save."""
    metadata = _inspect(state, aid)
    directory = Path(metadata['directory'])
    manifest = _contained(directory / 'manifest.json', directory)
    payload = (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode('utf-8')
    try:
        manifest.write_bytes(payload)
    except OSError as exc:
        raise ArtifactError('cannot write package manifest: %s' % exc)
    return dict(metadata, manifest_sha256=_digest(payload))


def package_valid(state, aid):
    """Check current files against both previously accepted metadata and manifest."""
    try:
        accepted = state.get('finalist_packages', {}).get(aid)
        if not isinstance(accepted, dict):
            return False
        metadata = _inspect(state, aid)
        directory = Path(metadata['directory'])
        manifest = _contained(directory / 'manifest.json', directory)
        payload = _read(manifest)
        if _object(payload, 'manifest') != metadata:
            return False
        return accepted == dict(metadata, manifest_sha256=_digest(payload))
    except (ArtifactError, OSError, TypeError, ValueError):
        return False


def pending_finalists(state):
    """Return finalists whose required implementation package is missing or stale."""
    return [aid for aid in finalists(state) if not package_valid(state, aid)]
