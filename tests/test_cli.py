import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw import cli
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.metrics.reporter import BenchmarkReporter


class TestCLI(unittest.TestCase):
    def test_generation_failure_is_saved_and_included_in_denominator(self):
        loader = DatasetLoader()
        with TemporaryDirectory() as directory:
            report = Path(directory) / "results.json"
            args = Namespace(tier=None, tasks="tier1_crc16,tier1_ring_buffer", model="mock",
                             compiler=None, output=str(report))
            with patch.object(cli.LLMClient, "generate_solution", side_effect=[
                RuntimeError("API failed"), loader.get_reference_solution("tier1_ring_buffer")
            ]), redirect_stdout(io.StringIO()):
                exit_code = cli.cmd_run(args)
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(data["tasks"]), 2)
        self.assertEqual(data["pass_at_1_pct"], 50)
        self.assertEqual(data["tasks"][0]["scores"]["total"], 0)
        self.assertIn("API failed", data["tasks"][0]["error_log"])

    def test_all_generation_failures_are_saved(self):
        with TemporaryDirectory() as directory:
            report = Path(directory) / "results.json"
            args = Namespace(tier=1, tasks=None, model="mock", compiler=None, output=str(report))
            with patch.object(cli.LLMClient, "generate_solution", side_effect=RuntimeError("API failed")), redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_run(args), 1)
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(len(data["tasks"]), 2)
        self.assertEqual(data["pass_at_1_pct"], 0)
        self.assertEqual(data["overall_score"], 0)

    def test_missing_baseline_reference_is_saved(self):
        with TemporaryDirectory() as directory:
            report = Path(directory) / "results.json"
            args = Namespace(tier=None, tasks="tier1_crc16", model="baseline", compiler=None, output=str(report))
            with patch.object(cli.DatasetLoader, "get_reference_solution", return_value=None), redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_run(args), 1)
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(len(data["tasks"]), 1)
        self.assertIn("Missing reference", data["tasks"][0]["error_log"])

    def test_unknown_task_is_rejected_before_running(self):
        args = Namespace(tier=None, tasks="tier1_crc16,typo", model="baseline", compiler=None, output=None)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(cli.cmd_run(args), 1)

    def test_report_formats_and_legacy_json(self):
        data = json.loads(Path("results/baseline.json").read_text(encoding="utf-8"))
        # Exercise the pre-change schema even after refreshing the stored baseline.
        for task in data["tasks"]:
            task["test_result"].pop("completed", None)
            task["test_result"].pop("returncode", None)
            task["size_metrics"].pop("measured", None)
            task["safety_metrics"].pop("violations", None)
        with TemporaryDirectory() as directory:
            report = Path(directory) / "legacy.json"
            report.write_text(json.dumps(data), encoding="utf-8")
            for format_name, expected in [("markdown", "# AIBenchMark-ESW Benchmark Report"),
                                          ("cli", "AIBenchMark-ESW Benchmark Results")]:
                with self.subTest(format=format_name), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(cli.cmd_report(Namespace(results=str(report), format=format_name)), 0)
                    self.assertIn(expected, output.getvalue())
                    output.getvalue().encode("cp949")
        restored = BenchmarkReporter.from_json_dict(data)
        self.assertEqual(len(restored), 5)


if __name__ == "__main__":
    unittest.main()
