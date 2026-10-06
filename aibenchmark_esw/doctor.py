"""Offline readiness checks using a trusted fixture and optional references."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import validate_task_assets
from aibenchmark_esw.models import TaskConfig
from aibenchmark_esw.reference_cache import ReferenceCache
from aibenchmark_esw.sandbox.process_runner import run_bounded
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


_FIXTURE_SOURCE = '''#include "doctor.h"
int32_t doctor_add(int32_t left, int32_t right) { return left + right; }
'''
_FIXTURE_TEST = '''#include "unity.h"
#include "doctor.h"
void setUp(void) {}
void tearDown(void) {}
void test_trusted_arithmetic(void) { TEST_ASSERT_EQUAL_INT(42, doctor_add(20, 22)); }
int main(void) { UNITY_BEGIN(); RUN_TEST(test_trusted_arithmetic); return UNITY_END(); }
'''


def run_doctor(tasks, loader, executor, check_references=False, reference_cache=None):
    """Check offline evaluation readiness without generation or persistent writes.

    Compiler/Unity/selected assets and fixture execution are required. A missing
    optional cppcheck installation is valid builtin-only mode; an explicitly
    configured but broken analyzer is a required failure. Reference checks share
    the supplied cache with the following evaluation when requested.
    """
    tasks = list(tasks)
    report: Dict[str, Any] = {"passed": True, "checks": [], "selected_tasks": [task.id for task in tasks],
              "check_references": bool(check_references), "effective_standards": {}}

    def record(name, passed, detail, required=True, **extra):
        report["checks"].append({"name": name, "passed": bool(passed), "detail": str(detail),
                                 "required": required, **extra})
        if required and not passed:
            report["passed"] = False

    record("selection", bool(tasks), f"{len(tasks)} selected task(s)")
    compiler = str(executor.compiler_path)
    resolved = shutil.which(compiler) or (str(Path(compiler).resolve()) if Path(compiler).is_file() else None)
    record("compiler", bool(resolved), resolved or f"Compiler not found: {compiler}")
    if resolved:
        name = Path(compiler).stem.lower()
        try:
            version = run_bounded([compiler, "/?" if name == "cl" else "-v" if name == "tcc" else "--version"],
                                  timeout=5, max_output_bytes=65536)
            text = version.stdout.decode("utf-8", errors="replace").strip()
            record("compiler_version", version.returncode == 0 and bool(text),
                   text.splitlines()[0] if text else "Compiler did not report a version", required=False)
        except (OSError, subprocess.SubprocessError) as error:
            record("compiler_version", False, error, required=False)

    unity_errors = []
    for name in ("unity.c", "unity.h", "unity_internals.h"):
        path = executor.unity_dir / name
        try:
            if not path.read_text(encoding="utf-8").strip():
                unity_errors.append(f"Empty Unity asset: {path}")
        except (OSError, UnicodeError) as error:
            unity_errors.append(f"Unreadable Unity asset {path}: {error}")
    record("unity", not unity_errors, "; ".join(unity_errors) or "Unity sources and headers are readable")

    valid_assets = {}
    for task in tasks:
        errors = validate_task_assets(task)
        valid_assets[task.id] = not errors
        record(f"assets:{task.id}", not errors, "; ".join(errors) or "Required task assets are readable")

    analyzer = StaticAnalyzer()
    configured = os.environ.get("AIBENCHMARK_ESW_CPPCHECK")
    with TemporaryDirectory(prefix="aibenchmark_doctor_") as directory:
        root = Path(directory)
        include = root / "include"
        include.mkdir()
        (root / "tests").mkdir()
        (include / "doctor.h").write_text(
            "#include <stdint.h>\nint32_t doctor_add(int32_t left, int32_t right);\n", encoding="utf-8")
        (root / "tests/test_doctor.c").write_text(_FIXTURE_TEST, encoding="utf-8")
        source = root / "doctor.c"
        source.write_text(_FIXTURE_SOURCE, encoding="utf-8")
        if analyzer.cppcheck_cmd:
            metrics = analyzer.analyze(source, [include], "c99")
            success = metrics.cppcheck_status == "completed"
            record("analyzer", success,
                   "Configured cppcheck successfully analyzed the trusted fixture" if success else
                   metrics.cppcheck_diagnostic or "cppcheck failed on the trusted fixture",
                   required=bool(configured and configured != "off"),
                   status=metrics.cppcheck_status)
        else:
            status = "builtin_disabled" if configured == "off" else "builtin_unavailable"
            record("analyzer", True,
                   "Builtin-only analysis explicitly selected" if configured == "off" else
                   "Optional cppcheck not found; builtin-only analysis is available", status=status)

        ready_standards = set()
        if resolved and not unity_errors:
            for standard in sorted({task.target_standard for task in tasks}):
                fixture = TaskConfig.from_dict({"id": f"doctor_{standard}", "target_standard": standard,
                                               "limits": {"timeout_seconds": 3}}, root)
                code = _FIXTURE_SOURCE
                if standard in ("c11", "c17"):
                    code += '_Static_assert(sizeof(int32_t) == 4, "32-bit fixture type");\n'
                compiled, tested = executor.compile_and_test(fixture, code, root / standard / "tests")
                try:
                    success = compiled.success and tested.completed and tested.passed
                    effective = compiled.effective_standard
                    report["effective_standards"][standard] = effective
                    record(f"compile_run:{standard}", success,
                           f"Trusted fixture compiled and passed using {effective}" if success else
                           compiled.output if not compiled.success else tested.output)
                finally:
                    compiled.cleanup()
                if not success:
                    continue
                try:
                    obj = executor.compile_object(fixture, code, root / standard / "object", "fixture")
                    if not obj.success:
                        raise ValueError(obj.output or "Trusted object compilation failed")
                    assert obj.binary_path is not None
                    size_metrics = SizeAnalyzer().analyze(obj.binary_path)
                    if size_metrics.flash_bytes <= 0 or size_metrics.ram_bytes < 0:
                        raise ValueError("Trusted object footprint was not measurable")
                    record(f"object_size:{standard}", True,
                           f"Flash={size_metrics.flash_bytes} bytes, RAM={size_metrics.ram_bytes} bytes")
                    ready_standards.add(standard)
                except (OSError, ValueError) as error:
                    record(f"object_size:{standard}", False, error)

        if check_references:
            cache = reference_cache if reference_cache is not None else ReferenceCache()
            for task in tasks:
                if not valid_assets[task.id] or task.target_standard not in ready_standards:
                    record(f"reference:{task.id}", False,
                           "Reference check requires valid task assets and a working compiler/Unity/size environment")
                    continue
                try:
                    code = loader.get_reference_solution(task.id)
                    validation, hit = cache.validate(task, code, executor)
                    record(f"reference:{task.id}", validation.error is None,
                           validation.error or f"Reference passes; Flash={validation.flash_bytes}, RAM={validation.ram_bytes}",
                           cached=hit)
                except (OSError, ValueError) as error:
                    record(f"reference:{task.id}", False, error)
    return report
