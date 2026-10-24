"""Dependency-free plugin entry point, also usable with the core Python runtime."""
import os
from pathlib import Path
import sys


def runtime_python():
    configured = os.environ.get('ARENA_PLUGIN_PYTHON')
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path.home() / '.arena' / 'plugin-runtime'
    return root / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def main():
    executable = runtime_python()
    if not executable.is_file():
        raise SystemExit('Arena plugin runtime missing. Run Python 3.11+ on skills/arena/plugin/setup_runtime.py, or set ARENA_PLUGIN_PYTHON to the prepared runtime. No workers started.')
    os.execv(str(executable), [str(executable), str(Path(__file__).with_name('server.py'))] + sys.argv[1:])


if __name__ == '__main__':
    main()
