"""Install the checked-in dev graph into the active CI Python without re-resolution."""

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'uv==0.11.29'], check=True)
    subprocess.run([sys.executable, '-m', 'uv', 'lock', '--check'], check=True)
    with TemporaryDirectory(prefix='aibenchmark_locked_') as directory:
        requirements = Path(directory) / 'requirements.txt'
        subprocess.run([sys.executable, '-m', 'uv', 'export', '--locked', '--extra', 'dev', '--no-emit-project',
                        '--format', 'requirements-txt', '--output-file', str(requirements)], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--require-hashes', '-r', str(requirements)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', '.'], check=True)


if __name__ == '__main__':
    main()
