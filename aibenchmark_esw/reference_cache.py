"""In-process reference validation keyed by the actual evaluation inputs."""

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from tempfile import TemporaryDirectory

from aibenchmark_esw.provenance import task_sha256, text_sha256
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer


@dataclass(frozen=True)
class ReferenceValidation:
    flash_bytes: int = 0
    ram_bytes: int = 0
    error: Optional[str] = None


class ReferenceCache:
    def __init__(self):
        self._records = {}
        self._locks = {}
        self._guard = threading.Lock()

    def validate(self, task, code, executor, existing=None):
        if not code:
            return ReferenceValidation(error="Reference implementation is required for memory measurement"), False
        settings = executor.execution_settings() if hasattr(executor, "execution_settings") else {}
        compiler = Path(executor.compiler_path)
        stamp = (compiler.stat().st_mtime_ns, compiler.stat().st_size) if compiler.is_file() else None
        key = (task_sha256(task, executor.unity_dir), text_sha256(code), str(compiler), stamp,
               executor.allow_standard_fallback, json.dumps(settings, sort_keys=True))
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            if key in self._records:
                return self._records[key], True
            try:
                with TemporaryDirectory(prefix="aibenchmark_reference_") as directory:
                    root = Path(directory)
                    if existing is None:
                        comp, tests = executor.compile_and_test(task, code, root / "tests")
                        obj = None
                    else:
                        comp, tests, obj = existing
                    if not comp.success or not tests.completed or not tests.passed:
                        detail = comp.output if not comp.success else tests.output
                        raise ValueError("Reference validation failed: reference must complete and pass all tests\n" + detail)
                    if obj is None:
                        obj = executor.compile_object(task, code, root / "object", "reference")
                    if not obj.success:
                        raise ValueError("Reference validation failed: " + (obj.output or "object compilation failed"))
                    size = SizeAnalyzer().analyze(obj.binary_path)
                    if size.flash_bytes > task.limits.max_flash_bytes:
                        raise ValueError(f"Reference validation failed: Flash footprint {size.flash_bytes} exceeds budget {task.limits.max_flash_bytes}")
                    if size.ram_bytes > task.limits.max_ram_bytes:
                        raise ValueError(f"Reference validation failed: RAM footprint {size.ram_bytes} exceeds budget {task.limits.max_ram_bytes}")
                    record = ReferenceValidation(size.flash_bytes, size.ram_bytes)
            except (OSError, ValueError) as error:
                record = ReferenceValidation(error=str(error))
            self._records[key] = record
            return record, False


_creation_lock = threading.Lock()


def executor_reference_cache(executor):
    with _creation_lock:
        if not hasattr(executor, "_reference_validation_cache"):
            executor._reference_validation_cache = ReferenceCache()
        return executor._reference_validation_cache
