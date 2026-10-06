import json
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.doctor import run_doctor
from aibenchmark_esw.models import CompilationResult
from aibenchmark_esw.reference_cache import ReferenceCache
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestDoctor(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.task = self.loader.get_task("tier1_crc16")
        self.executor = ExecutionSandbox()
        self.environment = patch.dict(os.environ, {"AIBENCHMARK_ESW_CPPCHECK": "off"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_trusted_fixture_and_explicit_builtin_mode_are_ready(self):
        with patch.object(self.loader, "get_reference_solution") as reference:
            report = run_doctor([self.task], self.loader, self.executor)
        self.assertTrue(report["passed"], report)
        reference.assert_not_called()
        checks = {check["name"]: check for check in report["checks"]}
        self.assertTrue(checks["compile_run:c99"]["passed"])
        self.assertTrue(checks["object_size:c99"]["passed"])
        self.assertEqual(checks["analyzer"]["status"], "builtin_disabled")
        json.dumps(report)  # CLI output is JSON serializable.

    def test_missing_compiler_fails_without_reference_execution(self):
        executor = ExecutionSandbox(compiler_path="missing-doctor-compiler-72605")
        with patch.object(executor, "compile_and_test") as compile_fixture:
            report = run_doctor([self.task], self.loader, executor, check_references=True)
        self.assertFalse(report["passed"])
        compile_fixture.assert_not_called()
        compiler = next(check for check in report["checks"] if check["name"] == "compiler")
        self.assertIn("Compiler not found", compiler["detail"])

    def test_optional_analyzer_absence_and_explicit_broken_analyzer_are_distinct(self):
        with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
            report = run_doctor([self.task], self.loader, self.executor)
        self.assertTrue(report["passed"], report)
        analyzer = next(check for check in report["checks"] if check["name"] == "analyzer")
        self.assertEqual(analyzer["status"], "builtin_unavailable")
        with patch.dict(os.environ, {"AIBENCHMARK_ESW_CPPCHECK": "missing-doctor-cppcheck-72605"}):
            report = run_doctor([self.task], self.loader, self.executor)
        self.assertFalse(report["passed"])
        analyzer = next(check for check in report["checks"] if check["name"] == "analyzer")
        self.assertEqual(analyzer["status"], "failed")
        self.assertTrue(analyzer["required"])

    def test_reference_validation_is_optional_and_cache_is_reused(self):
        cache = ReferenceCache()
        with patch.object(self.executor, "compile_and_test", wraps=self.executor.compile_and_test) as compile_test:
            first = run_doctor([self.task], self.loader, self.executor, True, cache)
            first_calls = compile_test.call_count
            second = run_doctor([self.task], self.loader, self.executor, True, cache)
        self.assertTrue(first["passed"], first)
        self.assertTrue(second["passed"], second)
        self.assertEqual(first_calls, 2)  # One trusted fixture and one reference.
        self.assertEqual(compile_test.call_count, 3)  # Only fixture compilation repeated.
        reference = next(check for check in second["checks"] if check["name"].startswith("reference:"))
        self.assertTrue(reference["cached"])

    def test_bad_reference_identifies_task_before_candidate_generation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(self.task.task_dir, root / "task")
            path = root / "task/reference/crc16.c"
            path.write_text(path.read_text(encoding="utf-8").replace("return 0;", "return 1;"), encoding="utf-8")
            loader = DatasetLoader(root)
            report = run_doctor(loader.list_tasks(), loader, self.executor, check_references=True)
        self.assertFalse(report["passed"])
        reference = next(check for check in report["checks"] if check["name"] == "reference:tier1_crc16")
        self.assertIn("Reference validation failed", reference["detail"])

    def test_missing_unity_and_unsupported_standard_are_diagnosed(self):
        with TemporaryDirectory() as directory:
            self.executor.unity_dir = Path(directory)
            report = run_doctor([self.task], self.loader, self.executor)
        self.assertFalse(report["passed"])
        unity = next(check for check in report["checks"] if check["name"] == "unity")
        self.assertIn("Unreadable Unity asset", unity["detail"])
        self.executor = ExecutionSandbox()
        with patch.object(self.executor, "_compile", return_value=CompilationResult(False, "Unsupported C standard")):
            report = run_doctor([self.task], self.loader, self.executor)
        self.assertFalse(report["passed"])
        fixture = next(check for check in report["checks"] if check["name"] == "compile_run:c99")
        self.assertIn("Unsupported C standard", fixture["detail"])
