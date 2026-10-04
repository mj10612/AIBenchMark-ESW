import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from aibenchmark_esw import cli
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.metrics.comparison import compare_runs
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.provenance import text_sha256
from aibenchmark_esw.report_io import atomic_write_json


class TestCheckpoints(unittest.TestCase):
    def test_interruption_preserves_completed_work_usage_and_pending_denominator(self):
        reference = DatasetLoader().get_reference_solution("tier1_crc16")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            provider = MagicMock()
            observed = []

            def completion(**kwargs):
                checkpoint = json.loads(path.read_text(encoding="utf-8"))
                observed.append(checkpoint)
                if len(observed) == 2:
                    raise KeyboardInterrupt
                return Namespace(model="resolved-fixture", usage=Namespace(
                    prompt_tokens=20, completion_tokens=30, total_tokens=50), choices=[Namespace(
                    finish_reason="stop", message=Namespace(content=reference))])

            provider.completion.side_effect = completion
            args = cli.build_parser().parse_args(["run", "--model", "mock",
                "--tasks", "tier1_crc16,tier1_ring_buffer,tier2_debounce_fsm", "--output", str(path)])
            with patch.dict("sys.modules", {"litellm": provider}), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.cmd_run(args), 130)
            self.assertIn("Run status: interrupted", output.getvalue())
            self.assertEqual(provider.completion.call_count, 2)
            self.assertEqual(observed[0]["overall_score"], 0)
            self.assertEqual(observed[0]["metadata"]["run_status"], "running")
            self.assertEqual(observed[1]["tasks"][0]["scores"]["total"], 100)
            self.assertEqual(observed[1]["tasks"][0]["generation"]["usage"]["total_tokens"], 50)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["tasks"]), 3)
            self.assertEqual(data["overall_score"], 33.33)
            self.assertEqual(data["pass_at_1_pct"], 33.33)
            self.assertEqual(data["metadata"]["run_status"], "interrupted")
            self.assertEqual(data["metadata"]["pending_tasks"], ["tier1_ring_buffer", "tier2_debounce_fsm"])
            self.assertIn("interrupted", data["tasks"][1]["error_log"])
            self.assertIn("Not evaluated", data["tasks"][2]["error_log"])
            self.assertEqual(data["tasks"][0]["generation"]["usage"]["total_tokens"], 50)
            results = BenchmarkReporter.from_json_dict(data)
            self.assertIn("Run status: interrupted", BenchmarkReporter.generate_markdown(results, "mock", data["metadata"]))
            with self.assertRaisesRegex(ValueError, "unfinished"):
                compare_runs([data, data])

    def test_bad_output_path_fails_before_any_provider_request(self):
        with TemporaryDirectory() as directory:
            args = cli.build_parser().parse_args(["run", "--model", "mock", "--tasks", "tier1_crc16",
                                                 "--output", directory])
            with patch.object(cli.LLMClient, "generate_solution") as generate, redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):
                    cli.cmd_run(args)
                generate.assert_not_called()

    def test_atomic_write_preserves_previous_json_on_encoding_or_replace_failure(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            atomic_write_json(path, {"original": True})
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                atomic_write_json(path, {"partially_written": 1, "invalid": float("nan")})
            self.assertEqual(path.read_bytes(), original)
            with patch("aibenchmark_esw.report_io.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    atomic_write_json(path, {"replacement": True})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_local_reference_and_solution_exports_can_be_compared(self):
        reference = DatasetLoader().get_reference_solution("tier1_crc16")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "candidate.c"
            source.write_text(reference, encoding="utf-8")
            reports = []
            for name, selection in (("reference", ["--reference"]), ("candidate", ["--solution", str(source)])):
                report = Path(directory) / f"{name}.json"
                args = cli.build_parser().parse_args(["eval", "--task", "tier1_crc16", *selection, "--output", str(report)])
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_eval(args), 0)
                data = json.loads(report.read_text(encoding="utf-8"))
                self.assertEqual(data["metadata"]["run_status"], "completed")
                self.assertEqual(data["metadata"]["pending_tasks"], [])
                self.assertEqual(data["tasks"][0]["provenance"]["candidate_sha256"], text_sha256(reference))
                self.assertIsNone(data["tasks"][0]["provenance"]["prompt_sha256"])
                reports.append(data)
            comparison = compare_runs(reports)
            self.assertEqual([row["score"] for row in comparison["models"]], [100, 100])

    def test_local_compile_failure_and_interruption_still_export_results(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.c"
            source.write_text("this is invalid C", encoding="utf-8")
            path = Path(directory) / "report.json"
            args = cli.build_parser().parse_args(["eval", "--task", "tier1_crc16", "--solution", str(source), "--output", str(path)])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_eval(args), 1)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["metadata"]["run_status"], "completed")
            self.assertEqual(data["overall_score"], 0)
            BenchmarkReporter.from_json_dict(data)
            with patch.object(cli, "evaluate_task", side_effect=KeyboardInterrupt), redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_eval(args), 130)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["metadata"]["run_status"], "interrupted")
            self.assertEqual(data["metadata"]["pending_tasks"], ["tier1_crc16"])
            BenchmarkReporter.from_json_dict(data)

    def test_conflicting_local_inputs_are_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.build_parser().parse_args(["eval", "--task", "tier1_crc16", "--reference", "--solution", "file.c"])
        self.assertEqual(error.exception.code, 2)

    def test_run_state_must_match_tasks_and_pending_results(self):
        data = json.loads(Path("results/baseline.json").read_text(encoding="utf-8"))
        for status, pending in (("unknown", []), ("completed", ["tier1_crc16"]),
                                ("interrupted", ["unknown_task"]), ("running", ["tier1_crc16"])):
            data["metadata"].update(run_status=status, pending_tasks=pending)
            with self.subTest(status=status, pending=pending), self.assertRaises(ValueError):
                BenchmarkReporter.from_json_dict(data)
        data["metadata"].update(run_status="completed", pending_tasks=[], selected_tasks=[])
        with self.assertRaisesRegex(ValueError, "selected_tasks"):
            BenchmarkReporter.from_json_dict(data)


if __name__ == "__main__":
    unittest.main()
