import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw import cli
from aibenchmark_esw.metrics.reporter import BenchmarkReporter


class TestReportValidation(unittest.TestCase):
    def report(self):
        return json.loads(Path("results/baseline.json").read_text(encoding="utf-8"))

    def test_invalid_flags_counts_measurements_and_scores_are_rejected(self):
        mutations = [
            lambda task: task.update(compiled="false"),
            lambda task: task["test_result"].update(completed="false"),
            lambda task: task["test_result"].update(all_passed=1),
            lambda task: task["test_result"].update(total=True),
            lambda task: task["test_result"].update(passed=-1),
            lambda task: task["test_result"].update(passed=999),
            lambda task: task["test_result"].update(all_passed=False),
            lambda task: task["test_result"].update(returncode=7),
            lambda task: task["size_metrics"].update(flash_bytes=-1),
            lambda task: task["size_metrics"].update(measured="false"),
            lambda task: task["size_metrics"].update(measured=False),
            lambda task: task["safety_metrics"].update(error_count=-1),
            lambda task: task["safety_metrics"].update(violations="diagnostic"),
            lambda task: task.update(execution_time_sec=float("nan")),
            lambda task: task.update(execution_time_sec=-1),
            lambda task: task.update(tier=True),
            lambda task: task.update(task_id=[]),
            lambda task: task["scores"].update(functional=50),
            lambda task: task["scores"].update(total=50),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data = self.report()
                mutate(data["tasks"][0])
                with self.assertRaises(ValueError):
                    BenchmarkReporter.from_json_dict(data)

    def test_incomplete_diagnostics_are_kept_but_cannot_earn_points(self):
        data = self.report()
        task = data["tasks"][0]
        task["test_result"].update(completed=False, all_passed=False, total=1, passed=0,
                                    failed=2, ignored=3, returncode=7)
        task["scores"] = dict.fromkeys(("functional", "memory", "safety", "total"), 0)
        result = BenchmarkReporter.from_json_dict(data)[0]
        self.assertEqual(result.test_result.failed_tests, 2)
        self.assertEqual(BenchmarkReporter.to_json_dict([result], "baseline")["pass_at_1_pct"], 0)
        task["scores"]["total"] = 10
        with self.assertRaisesRegex(ValueError, "zero scores"):
            BenchmarkReporter.from_json_dict(data)

    def test_rounded_partial_scores_and_valid_legacy_reports_still_load(self):
        data = self.report()
        task = data["tasks"][0]
        task["test_result"].update(total=3, passed=1, failed=2, ignored=0, all_passed=False, returncode=2)
        task["scores"].update(functional=33.33, memory=17.21, safety=94, total=27.41)
        self.assertEqual(BenchmarkReporter.from_json_dict(data)[0].scores.total_score, 27.41)
        legacy = self.report()
        legacy.pop("schema_version")
        for task in legacy["tasks"]:
            task.pop("weights", None)
            task["test_result"].pop("completed", None)
            task["test_result"].pop("returncode", None)
        self.assertEqual(len(BenchmarkReporter.from_json_dict(legacy)), len(legacy["tasks"]))

    def test_unsupported_schema_and_duplicate_tasks_are_rejected(self):
        for version in (True, "2", 0, 3, None):
            data = self.report()
            data["schema_version"] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "schema version"):
                BenchmarkReporter.from_json_dict(data)
        data = self.report()
        data["tasks"].append(copy.deepcopy(data["tasks"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate task"):
            BenchmarkReporter.from_json_dict(data)

    def test_pass_at_1_does_not_trust_in_memory_success_flags_alone(self):
        result = BenchmarkReporter.from_json_dict(self.report())[0]
        result.compiled = "false"
        self.assertEqual(BenchmarkReporter.to_json_dict([result], "test")["pass_at_1_pct"], 0)
        result.compiled = True
        result.test_result.passed_tests = 0
        self.assertEqual(BenchmarkReporter.to_json_dict([result], "test")["pass_at_1_pct"], 0)

    def test_report_and_compare_return_clean_errors_for_invalid_boolean(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            data = self.report()
            data["tasks"][0]["compiled"] = "false"
            path.write_text(json.dumps(data), encoding="utf-8")
            for argv in (["report", "--results", str(path)],
                         ["compare", "--results", str(path), "results/baseline.json"]):
                args = cli.build_parser().parse_args(argv)
                command = cli.cmd_report if args.command == "report" else cli.cmd_compare
                with self.subTest(command=args.command), redirect_stderr(io.StringIO()) as errors, redirect_stdout(io.StringIO()):
                    self.assertEqual(command(args), 1)
                    self.assertIn("compiled must be a boolean", errors.getvalue())
                    self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
