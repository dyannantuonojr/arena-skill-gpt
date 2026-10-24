"""Explicitly prepare the optional runtime. Does not connect or start Arena."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, default=Path.home() / '.arena' / 'plugin-runtime')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('The plugin runtime needs Python 3.11+; the standalone Arena app still supports Python 3.8+.')
    root = args.runtime.expanduser().absolute()
    if any(p.is_symlink() for p in (root,) + tuple(root.parents)):
        parser.error('Runtime directory must not be redirected')
    venv.EnvBuilder(with_pip=True).create(root)
    executable = root / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(Path(__file__).with_name('requirements.lock'))], check=True)
    print('Plugin runtime ready at ' + str(root) + '. No server or workers started.')


if __name__ == '__main__':
    main()
