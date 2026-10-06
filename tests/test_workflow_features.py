"""Regression evidence for the integrated offline and provider workflows."""

import copy
import io
import json
import threading
import time
import unittest
from argparse import Namespace
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from compiler_tools import find_clang
from aibenchmark_esw import cli
from aibenchmark_esw.baseline_check import verify_baseline, current_fingerprints
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.llm.client import LLMClient
from aibenchmark_esw.metrics.comparison import compare_runs, render_comparison
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.models import TaskConfig
from aibenchmark_esw.provenance import collect_run_metadata
from aibenchmark_esw.reference_cache import ReferenceCache
from aibenchmark_esw.report_schema import report_schema, validate_report_structure
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


def response(code, finish="stop"):
    return Namespace(model="resolved-fixture", usage=Namespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
                     choices=[Namespace(finish_reason=finish, message=Namespace(content=code))])


class TestWorkflowFeatures(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.task = self.loader.get_task("tier1_crc16")
        self.code = self.loader.get_reference_solution(self.task.id)

    def run_cli(self, args):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return cli.cmd_run(cli.build_parser().parse_args(args))

    def test_retry_transient_only_and_record_all_attempts(self):
        provider = MagicMock()
        provider.completion.side_effect = [TimeoutError("temporary"), response(self.code)]
        client = LLMClient("mock", max_retries=2, retry_backoff_seconds=0)
        with patch.dict("sys.modules", {"litellm": provider}):
            self.assertEqual(client.generate_solution([{"role": "user", "content": "implement"}]), self.code.strip())
        self.assertEqual(provider.completion.call_count, 2)
        self.assertEqual([attempt["error"] for attempt in client.last_generation["attempts"]], ["TimeoutError", None])
        self.assertEqual(client.last_generation["usage"]["total_tokens"], 5)
        error = RuntimeError("invalid credentials")
        error.status_code = 401
        provider.completion.side_effect = error
        with patch.dict("sys.modules", {"litellm": provider}), self.assertRaises(RuntimeError):
            client.generate_solution([{"role": "user", "content": "implement"}])
        self.assertEqual(len(client.last_generation["attempts"]), 1)

    def test_plan_review_public_transcripts_and_task_overrides(self):
        client = LLMClient("mock", prompt_strategy="plan", review_turn=True)
        prompt = client.build_prompt("task", "uint16_t crc16_compute(const uint8_t *data, size_t len);", "", prompt_overrides={
            "allow_dynamic_memory": True, "extra_rules": ["Use bounded loops."]})
        self.assertNotIn("Do NOT use dynamic", prompt[0]["content"])
        self.assertIn("Use bounded loops", prompt[0]["content"])
        provider = MagicMock()
        provider.completion.side_effect = [response("Check boundaries and polynomial."), response(self.code), response(self.code)]
        with patch.dict("sys.modules", {"litellm": provider}):
            self.assertEqual(client.generate_solution(prompt), self.code.strip())
        self.assertEqual(len(client.last_generation["turns"]), 3)
        self.assertEqual(client.last_generation["usage"]["total_tokens"], 15)
        self.assertEqual(len(client.last_generation["request_messages"]), 3)

    def test_api_implementation_fence_wins_over_long_header(self):
        client = LLMClient("mock")
        client.build_prompt("task", "uint16_t crc16_compute(const uint8_t *data, size_t len);", "")
        header = "#ifndef HEADER\n#define HEADER\n" + "uint16_t unused(void);\n" * 100 + "#endif\n"
        output = f"```c\n{self.code}\n```\n```c\n{header}\n```"
        self.assertEqual(client.extract_c_code(output), self.code.strip())

    def test_fatal_provider_aborts_without_spending_on_remaining_tasks(self):
        provider = MagicMock()
        failure = RuntimeError("authentication failed")
        failure.status_code = 401
        provider.completion.side_effect = failure
        with TemporaryDirectory() as directory, patch.dict("sys.modules", {"litellm": provider}):
            path = Path(directory) / "run.json"
            self.assertEqual(self.run_cli(["run", "--model", "mock", "--tier", "1", "--output", str(path)]), 1)
            report = json.loads(path.read_text())
            self.assertEqual(report["metadata"]["run_status"], "aborted")
            self.assertEqual(len(report["metadata"]["pending_tasks"]), 3)
            self.assertEqual(provider.completion.call_count, 1)
            BenchmarkReporter.from_json_dict(report)

    def test_truncated_response_preserved_and_never_scored(self):
        provider = MagicMock()
        provider.completion.return_value = response("int incomplete;", "length")
        with TemporaryDirectory() as directory, patch.dict("sys.modules", {"litellm": provider}):
            self.assertEqual(self.run_cli(["run", "--model", "mock", "--tasks", self.task.id,
                "--output", str(Path(directory) / "run.json"), "--save-solutions", directory]), 1)
            self.assertEqual((Path(directory) / (self.task.id + ".truncated.c")).read_text(), "int incomplete;")
            report = json.loads((Path(directory) / "run.json").read_text())
            self.assertEqual(report["overall_score"], 0)
            self.assertEqual(report["tasks"][0]["generation"]["partial_response"], "int incomplete;")
            self.assertFalse((Path(directory) / (self.task.id + ".c")).exists())

    def test_resume_preserves_completed_task_run_id_and_denominator(self):
        provider = MagicMock()
        provider.completion.side_effect = [response(self.code), KeyboardInterrupt()]
        with TemporaryDirectory() as directory, patch.dict("sys.modules", {"litellm": provider}):
            path = Path(directory) / "run.json"
            self.assertEqual(self.run_cli(["run", "--model", "mock", "--tasks", "tier1_crc16,tier1_ring_buffer", "--output", str(path)]), 130)
            before = json.loads(path.read_text())
            provider.completion.side_effect = None
            provider.completion.return_value = response(self.loader.get_reference_solution("tier1_ring_buffer"))
            self.assertEqual(self.run_cli(["run", "--resume", str(path)]), 0)
            after = json.loads(path.read_text())
            self.assertEqual(provider.completion.call_count, 3)
            self.assertEqual(after["tasks"][0], before["tasks"][0])
            self.assertEqual(after["metadata"]["run_id"], before["metadata"]["run_id"])
            self.assertEqual(after["metadata"]["pending_tasks"], [])
            self.assertEqual(after["overall_score"], 100)

    def test_parallel_tasks_overlap_preserve_order_and_checkpoint(self):
        original = cli.evaluate_task
        lock = threading.Lock()
        active = peak = 0
        def evaluate(*args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.05)
                return original(*args, **kwargs)
            finally:
                with lock:
                    active -= 1
        with TemporaryDirectory() as directory, patch.object(cli, "evaluate_task", side_effect=evaluate):
            path = Path(directory) / "run.json"
            self.assertEqual(self.run_cli(["run", "--tier", "1", "--jobs", "2", "--output", str(path)]), 0)
            report = json.loads(path.read_text())
        self.assertEqual(peak, 2)
        self.assertEqual([task["task_id"] for task in report["tasks"]], report["metadata"]["selected_tasks"])
        self.assertEqual(report["overall_score"], 100)

    def test_reference_cache_avoids_repeated_validation_and_excludes_time(self):
        executor, cache = ExecutionSandbox(), ReferenceCache()
        candidate = self.code + "\n/* independently generated */\n"
        with patch.object(executor, "compile_and_test", wraps=executor.compile_and_test) as compile_test:
            first = evaluate_task(self.task, candidate, self.code, "m", executor, reference_cache=cache)
            second = evaluate_task(self.task, candidate, self.code, "m", executor, reference_cache=cache)
            self.assertEqual(compile_test.call_count, 3)
        self.assertFalse(first.provenance["reference_cache_hit"])
        self.assertTrue(second.provenance["reference_cache_hit"])
        self.assertEqual(first.execution_time_sec, first.candidate_time_sec)
        self.assertGreater(first.reference_validation_time_sec, 0)
        self.assertLess(second.reference_validation_time_sec, first.reference_validation_time_sec)

    def test_policy_deletion_and_weight_tampering_are_rejected(self):
        executor = ExecutionSandbox()
        result = evaluate_task(self.task, self.code, self.code, "m", executor)
        metadata = collect_run_metadata([self.task], executor)
        result.provenance["task_sha256"] = metadata["task_fingerprints"][self.task.id]
        report = BenchmarkReporter.to_json_dict([result], "m", metadata)
        BenchmarkReporter.from_json_dict(report)
        for change in (lambda task: task.pop("limits"), lambda task: task.update(weights={"functional":1,"memory":0,"safety":0})):
            bad = copy.deepcopy(report)
            change(bad["tasks"][0])
            with self.assertRaisesRegex(ValueError, "scoring_policy"):
                BenchmarkReporter.from_json_dict(bad)
        bad = copy.deepcopy(report)
        bad["metadata"]["scoring_policy"]["tasks"][self.task.id]["weights"] = {"functional":1,"memory":0,"safety":0}
        bad["tasks"][0]["weights"] = {"functional":1,"memory":0,"safety":0}
        with self.assertRaisesRegex(ValueError, "referenced task"):
            BenchmarkReporter.from_json_dict(bad)

    def test_structured_findings_type_coverage_and_roundtrip(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.c"
            for basic in ("long", "long long", "unsigned long", "unsigned char", "short", "signed char", "unsigned int"):
                path.write_text(basic + " value;\n")
                metrics = StaticAnalyzer("off").analyze(path)
                self.assertEqual(metrics.warning_count, 1, basic)
                self.assertEqual(metrics.findings[0]["rule_id"], "builtin.misra.4.6")
                self.assertEqual(metrics.findings[0]["line"], 1)
            for fixed in ("uint32_t", "int16_t", "uint8_t", "int", "char"):
                path.write_text(fixed + " value;\n")
                self.assertEqual(StaticAnalyzer("off").analyze(path).warning_count, 0, fixed)
            path.write_text("// ignored\nvoid f(void){malloc(1);}\n")
            metrics = StaticAnalyzer("off").analyze(path)
            self.assertEqual(metrics.findings[0]["line"], 2)
        result = evaluate_task(self.task, self.code, self.code, "m", ExecutionSandbox())
        result.safety_metrics.findings = metrics.findings
        report = BenchmarkReporter.to_json_dict([result], "m")
        self.assertEqual(BenchmarkReporter.from_json_dict(report)[0].safety_metrics.findings, metrics.findings)
        report["tasks"][0]["safety_metrics"]["findings"][0]["severity"] = "unknown"
        with self.assertRaises(ValueError):
            BenchmarkReporter.from_json_dict(report)

    def test_schema_and_python_reject_structural_corruption(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("schema extra required")
        schema = report_schema()
        Draft202012Validator.check_schema(schema)
        report = json.loads(Path("results/baseline.json").read_text())
        validate_report_structure(report)
        for key, bad in (("compiled", "yes"), ("tier", True), ("task_id", ""), ("execution_time_sec", -1), ("scores", {})):
            data = copy.deepcopy(report)
            data["tasks"][0][key] = bad
            with self.assertRaises(ValueError):
                validate_report_structure(data)
            with self.assertRaises(ValueError):
                BenchmarkReporter.from_json_dict(data)

    def test_published_fingerprint_gate_matching_and_drift(self):
        fresh = current_fingerprints()
        verify_baseline({"metadata": fresh}, fresh)
        bad = {**fresh, "evaluator_sha256": "stale"}
        with self.assertRaisesRegex(ValueError, "stale evaluator"):
            verify_baseline({"metadata": bad}, fresh)

    @unittest.skipUnless(find_clang(), "Cross-object integration requires Clang")
    def test_real_arm_object_target_budgets_and_comparison_rejection(self):
        executor = ExecutionSandbox(target="arm:cortex-m0", cross_compiler=find_clang())
        result = evaluate_task(self.task, self.code, self.code, "target", executor)
        self.assertTrue(result.test_result.passed, result.error_log)
        self.assertTrue(result.size_metrics.measured, result.error_log)
        self.assertGreater(result.size_metrics.flash_bytes, 0)
        self.assertEqual(result.footprint_target, "arm:cortex-m0")
        config = TaskConfig.from_dict({"id":"custom","limits":{"default":{"max_flash_bytes":1024},
            "targets":{"cortex-m0":{"max_flash_bytes":64}}}}, self.task.task_dir)
        selected = cli._target_task(config, Namespace(target="arm:cortex-m0"))
        self.assertEqual(selected.limits.max_flash_bytes, 64)
        constrained = replace(self.task, limits=replace(self.task.limits, max_flash_bytes=1))
        low = evaluate_task(constrained, self.code, self.code, "low", executor)
        self.assertEqual(low.scores.memory_score, 0)
        self.assertLess(low.scores.total_score, result.scores.total_score)
        host = evaluate_task(self.task, self.code, self.code, "host", ExecutionSandbox())
        with self.assertRaisesRegex(ValueError, "targets"):
            compare_runs([BenchmarkReporter.to_json_dict([host], "host"), BenchmarkReporter.to_json_dict([result], "target")])
        self.assertIn("arm:cortex-m0", BenchmarkReporter.generate_markdown([result], "target"))
        self.assertIn("1024/128", BenchmarkReporter.generate_cli_table([result], "target"))

    def test_comparison_matrix_largest_gap_and_long_csv(self):
        import csv
        reference = evaluate_task(self.task, self.code, self.code, "one", ExecutionSandbox())
        other = copy.deepcopy(reference)
        other.model_name = "two"
        other.size_metrics.measured = False
        other.scores.memory_score = 0
        other.scores.total_score = 80
        comparison = compare_runs([BenchmarkReporter.to_json_dict([reference], "one"), BenchmarkReporter.to_json_dict([other], "two")])
        self.assertEqual(comparison["largest_gap"]["gap"], 20)
        for format_name in ("cli", "markdown"):
            rendered = render_comparison(comparison, format_name)
            self.assertIn("Per-task totals", rendered)
            self.assertIn("Largest gap: tier1_crc16", rendered)
            self.assertIn("Memory unavailable", rendered)
        rows = list(csv.DictReader(io.StringIO(render_comparison(comparison, "csv-long"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0]), {"model","task_id","total","functional","memory","safety","measured","pass_at_1"})
        self.assertEqual(rows[1]["memory"], "")


if __name__ == "__main__":
    unittest.main()
