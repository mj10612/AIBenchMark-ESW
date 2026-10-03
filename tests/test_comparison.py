import copy
import csv
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw import cli
from aibenchmark_esw.metrics.comparison import compare_runs, render_comparison


class TestComparison(unittest.TestCase):
    def report(self, name):
        data = json.loads(Path("results/baseline.json").read_text(encoding="utf-8"))
        data["model_name"] = name
        for task in data["tasks"]:
            task["model_name"] = name
        data["metadata"] = {
            "dataset_sha256": "same-dataset", "compiler": {"name": "tcc", "version": "0.9.27"},
            "platform": {"system": "Windows", "machine": "AMD64"},
            "generation_settings": {"temperature": None, "max_tokens": 4096},
        }
        return data

    def test_comparison_keeps_failed_tasks_in_denominator_and_recomputes_summaries(self):
        first, second = self.report("openai/mock"), self.report("anthropic/mock")
        second["tasks"][0]["compiled"] = False
        second["tasks"][0]["test_result"].update(all_passed=False, completed=False)
        second["tasks"][0]["scores"] = dict.fromkeys(("functional", "memory", "safety", "total"), 0)
        second["overall_score"] = 100  # Ignore stale or misleading stored summaries.
        comparison = compare_runs([first, second])
        self.assertEqual(comparison["models"][0]["model"], "openai/mock")
        self.assertEqual(comparison["models"][1]["score"], 80)
        self.assertEqual(comparison["models"][1]["pass_at_1_pct"], 80)
        self.assertEqual(len(comparison["task_ids"]), 5)

    def test_incompatible_inputs_are_rejected(self):
        mutations = [
            lambda data: data["tasks"].pop(),
            lambda data: data["tasks"].append(copy.deepcopy(data["tasks"][0])),
            lambda data: data["metadata"].update(dataset_sha256="other-dataset"),
            lambda data: data["metadata"]["compiler"].update(version="other-version"),
            lambda data: data["metadata"]["platform"].update(machine="other-architecture"),
            lambda data: data["metadata"]["generation_settings"].update(max_tokens=1),
            lambda data: data["tasks"][0].update(weights={"functional": 0.8, "memory": 0.1, "safety": 0.1}),
            lambda data: data["tasks"][0].update(effective_standard="c11"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                first, second = self.report("one"), self.report("two")
                mutate(second)
                with self.assertRaises(ValueError):
                    compare_runs([first, second])
        with self.assertRaises(ValueError):
            compare_runs([self.report("same"), self.report("same")])

    def test_task_fingerprint_mismatch_is_rejected_even_without_run_provenance(self):
        first, second = self.report("one"), self.report("two")
        first["tasks"][0]["provenance"] = {"task_sha256": "one"}
        second["tasks"][0]["provenance"] = {"task_sha256": "two"}
        first.pop("metadata")
        second.pop("metadata")
        with self.assertRaisesRegex(ValueError, "fingerprints"):
            compare_runs([first, second])

    def test_legacy_missing_provenance_and_partial_usage_are_visible(self):
        first, second = self.report("one"), self.report("two")
        first.pop("metadata")
        first["tasks"][0]["generation"] = {"usage": {"total_tokens": 50}, "latency_seconds": 1.25}
        comparison = compare_runs([first, second])
        markdown = render_comparison(comparison)
        self.assertIn("compatibility cannot be fully checked", markdown)
        self.assertIn("50 (1/5 tasks)", markdown)
        self.assertIn("1.25 (1/5 tasks)", markdown)
        self.assertIn("Unknown", markdown)

    def test_csv_round_trip_and_cli_output(self):
        first, second = self.report("one"), self.report("two")
        comparison = compare_runs([first, second])
        rows = list(csv.DictReader(io.StringIO(render_comparison(comparison, "csv"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["score"], "100.0")
        self.assertIn("Pass@1", render_comparison(comparison, "cli"))
        with TemporaryDirectory() as directory:
            files = [Path(directory) / f"{index}.json" for index in range(2)]
            for path, report in zip(files, (first, second)):
                path.write_text(json.dumps(report), encoding="utf-8")
            output = Path(directory) / "comparison.csv"
            args = cli.build_parser().parse_args(["compare", "--results", *map(str, files),
                                                 "--format", "csv", "--output", str(output)])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_compare(args), 0)
            self.assertEqual(len(list(csv.DictReader(io.StringIO(output.read_text(encoding="utf-8"))))), 2)
            files[1].write_text("{}", encoding="utf-8")
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(cli.cmd_compare(args), 1)
            self.assertIn("Cannot compare reports", errors.getvalue())
