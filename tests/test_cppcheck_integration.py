"""Opt-in real-tool checks, required in the dedicated cppcheck CI job."""

import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.provenance import collect_run_metadata
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


@unittest.skipUnless(os.environ.get("AIBENCHMARK_ESW_TEST_CPPCHECK"),
                     "Set AIBENCHMARK_ESW_TEST_CPPCHECK to run real cppcheck integration")
class TestCppcheckIntegration(unittest.TestCase):
    def setUp(self):
        executable = os.environ["AIBENCHMARK_ESW_TEST_CPPCHECK"]
        self.assertIsNotNone(shutil.which(executable), f"Required cppcheck executable missing: {executable}")
        self.analyzer = StaticAnalyzer(executable)

    def test_real_analyzer_loads_standard_library_and_records_version(self):
        loader = DatasetLoader()
        task = loader.get_task("tier1_crc16")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "crc16.c"
            source.write_text(loader.get_reference_solution(task.id), encoding="utf-8")
            result = self.analyzer.analyze(source, [task.task_dir / "include"], task.target_standard)
        self.assertEqual(result.cppcheck_status, "completed", result.cppcheck_diagnostic)
        metadata = collect_run_metadata([task], ExecutionSandbox(), static_analyzer=self.analyzer)
        self.assertEqual(metadata["static_analysis"]["engine"], "builtin+cppcheck")
        self.assertIn("Cppcheck", metadata["static_analysis"]["cppcheck_version"] or "")

    def test_real_analyzer_reports_out_of_bounds_write(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "bounds.c"
            source.write_text("int check_bounds(void) { int samples[2] = {0, 0}; "
                              "samples[2] = 17; return samples[0]; }\n", encoding="utf-8")
            result = self.analyzer.analyze(source)
        self.assertEqual(result.cppcheck_status, "completed", result.cppcheck_diagnostic)
        self.assertGreater(result.error_count, 0)
        finding = next(item for item in result.findings if item["engine"] == "cppcheck" and item["rule_id"] == "arrayIndexOutOfBounds")
        self.assertEqual(finding["file"], "bounds.c")
        self.assertEqual(finding["line"], 1)
        self.assertTrue(any("arrayIndexOutOfBounds" in violation for violation in result.violations), result.violations)


if __name__ == "__main__":
    unittest.main()
