"""Collect explicit, credential-free inputs needed to reproduce a benchmark."""

import hashlib
import json
import platform
import subprocess
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from aibenchmark_esw import __version__


def text_sha256(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _digest_records(records):
    digest = hashlib.sha256()
    for name, content in sorted(records):
        # Length-prefix names and data so distinct records cannot concatenate
        # into the same byte stream. Ignore checkout-specific line endings.
        name = name.encode("utf-8")
        content = content.replace(b"\r\n", b"\n")
        for part in (name, content):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()


def task_sha256(task, unity_dir):
    config = {key: getattr(task, key) for key in
              ("id", "tier", "target_standard", "entry_file", "reference_file", "prompt")}
    config.update(limits=asdict(task.limits), weights=asdict(task.weights))
    records = [("effective_config", json.dumps(config, sort_keys=True).encode("utf-8"))]
    for path in sorted(task.task_dir.rglob("*")):
        relative = path.relative_to(task.task_dir)
        if (path.is_file() and path.suffix in (".c", ".h", ".json", ".md", ".txt")
                and not any(part in ("build", "__pycache__", "CMakeFiles") for part in relative.parts)):
            records.append(("task/" + relative.as_posix(), path.read_bytes()))
    for path in sorted(Path(unity_dir).glob("*")):
        if path.is_file() and path.suffix in (".c", ".h"):
            records.append(("harness/" + path.name, path.read_bytes()))
    return _digest_records(records)


def _command_output(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                errors="backslashreplace", timeout=5)
        if result.returncode == 0:
            return (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def collect_run_metadata(tasks, executor, generation_settings=None):
    compiler = Path(executor.compiler_path).stem.lower()
    version = _command_output([executor.compiler_path, "/?" if compiler == "cl" else
                               "-v" if compiler == "tcc" else "--version"])
    fingerprints = {task.id: task_sha256(task, executor.unity_dir) for task in tasks}
    checkout = Path(__file__).resolve().parent.parent
    revision = dirty = None
    if (checkout / ".git").exists():
        revision = _command_output(["git", "-C", str(checkout), "rev-parse", "HEAD"])
        status = _command_output(["git", "-C", str(checkout), "status", "--porcelain"])
        dirty = bool(status) if status is not None else None
    return {
        "run_id": uuid.uuid4().hex,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": __version__,
        "evaluator_sha256": _digest_records([
            (path.relative_to(Path(__file__).parent).as_posix(), path.read_bytes())
            for path in Path(__file__).parent.rglob("*.py") if "_data" not in path.parts
        ]),
        "python_version": platform.python_version(),
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "compiler": {"name": compiler, "version": version.splitlines()[0] if version else None,
                     "optimization": "/O1" if compiler == "cl" else "native" if compiler == "tcc" else "-Os",
                     "allow_standard_fallback": executor.allow_standard_fallback},
        "source_revision": revision, "source_dirty": dirty,
        "selected_tasks": [task.id for task in tasks],
        "task_fingerprints": fingerprints,
        "dataset_sha256": _digest_records([(name, value.encode("ascii")) for name, value in fingerprints.items()]),
        "generation_settings": generation_settings,
    }
