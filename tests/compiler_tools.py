"""Optional compiler discovery for binary-format and target-width regressions."""

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


def find_msvc():
    compiler = shutil.which('cl')
    if compiler or os.name != 'nt':
        return compiler
    vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if not vswhere.is_file():
        return None
    for attempt in range(2):
        try:
            result = subprocess.run([str(vswhere), '-latest', '-products', '*', '-requires',
                                     'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                     '-property', 'installationPath'], capture_output=True, text=True,
                                    errors='backslashreplace', timeout=10)
            break
        except subprocess.TimeoutExpired:
            if attempt:
                raise
    if result.returncode or not result.stdout.strip():
        return None
    vc = Path(result.stdout.strip()) / 'VC'
    try:
        version = (vc / 'Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text(encoding='utf-8-sig').strip()
    except (OSError, UnicodeError):
        return None
    compiler = vc / 'Tools/MSVC' / version / 'bin/Hostx64/x64/cl.exe'
    return str(compiler) if compiler.is_file() else None


@lru_cache(maxsize=1)
def find_clang():
    compiler = shutil.which("clang")
    if compiler or os.name != "nt":
        return compiler
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.is_file():
        return None
    result = subprocess.run([str(vswhere), "-latest", "-products", "*", "-find",
                             "VC/Tools/Llvm/**/clang.exe"], capture_output=True, text=True,
                            errors="backslashreplace", timeout=10)
    candidates = result.stdout.splitlines()
    return candidates[-1] if result.returncode == 0 and candidates else None
