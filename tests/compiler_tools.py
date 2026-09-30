"""Optional compiler discovery for binary-format and target-width regressions."""

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


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
