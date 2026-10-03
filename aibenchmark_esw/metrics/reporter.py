from typing import List, Dict, Any
from typing import Optional
from aibenchmark_esw.models import (
    TaskEvaluationResult, TestResult, SizeMetrics, StaticSafetyMetrics, DimensionScores, TaskWeights,
)


class BenchmarkReporter:
    @staticmethod
    def _all_tests_passed(result: TaskEvaluationResult) -> bool:
        return result.compiled and result.test_result.completed and result.test_result.passed

    @staticmethod
    def _weight_summary(results: List[TaskEvaluationResult], dimension: str) -> str:
        if any(result.weights is None for result in results):
            return "Unknown (legacy report)"
        values = {getattr(result.weights, dimension) for result in results}
        return f"{next(iter(values)) * 100:g}%" if len(values) == 1 else "Varies by task"

    @staticmethod
    def _task_weights(result: TaskEvaluationResult) -> str:
        if result.weights is None:
            return "Unknown"
        return "/".join(f"{getattr(result.weights, key) * 100:g}%"
                        for key in ("functional", "memory", "safety"))

    @staticmethod
    def _standard(result: TaskEvaluationResult) -> str:
        if result.target_standard is None:
            return "Unknown"
        if result.effective_standard is None:
            return f"{result.target_standard} (not run)"
        if result.target_standard != result.effective_standard:
            return f"{result.target_standard}->{result.effective_standard}"
        return result.effective_standard

    @staticmethod
    def from_json_dict(data: Dict[str, Any]) -> List[TaskEvaluationResult]:
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
            raise ValueError("Results must be an object containing a tasks array")
        if data.get("metadata") is not None and not isinstance(data["metadata"], dict):
            raise ValueError("Run metadata must be an object")
        results = []
        for item in data["tasks"]:
            tests = item["test_result"]
            size = item["size_metrics"]
            safety = item["safety_metrics"]
            scores = item["scores"]
            results.append(TaskEvaluationResult(
                task_id=item["task_id"], tier=item["tier"],
                model_name=item.get("model_name", data.get("model_name", "unknown")),
                compiled=item["compiled"],
                test_result=TestResult(
                    total_tests=tests["total"], passed_tests=tests["passed"],
                    failed_tests=tests["failed"], ignored_tests=tests.get("ignored", 0),
                    passed=tests["all_passed"], completed=tests.get("completed", tests["total"] > 0),
                    returncode=tests.get("returncode"),
                ),
                size_metrics=SizeMetrics(**size), safety_metrics=StaticSafetyMetrics(**safety),
                scores=DimensionScores(scores["functional"], scores["memory"],
                                       scores["safety"], scores["total"]),
                execution_time_sec=item["execution_time_sec"], error_log=item.get("error_log"),
                weights=TaskWeights(**item["weights"]) if item.get("weights") is not None else None,
                target_standard=item.get("target_standard"),
                effective_standard=item.get("effective_standard"),
                generation=item.get("generation"),
                provenance=item.get("provenance"),
            ))
        return results

    @staticmethod
    def generate_markdown(results: List[TaskEvaluationResult], model_name: str,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        if not results:
            return "No benchmark results available."

        total_tasks = len(results)
        compiled_tasks = sum(1 for r in results if r.compiled)
        all_passed_tasks = sum(1 for r in results if BenchmarkReporter._all_tests_passed(r))

        avg_func = sum(r.scores.functional_score for r in results) / total_tasks
        avg_mem = sum(r.scores.memory_score for r in results) / total_tasks
        avg_safe = sum(r.scores.safety_score for r in results) / total_tasks
        avg_total = sum(r.scores.total_score for r in results) / total_tasks

        md = []
        md.append(f"# AIBenchMark-ESW Benchmark Report: `{model_name}`\n")
        md.append("### Summary Overview")
        md.append(f"- **Total Tasks**: {total_tasks}")
        md.append(f"- **Compilation Rate**: {compiled_tasks}/{total_tasks} ({compiled_tasks/total_tasks*100:.1f}%)")
        md.append(f"- **Pass@1 (All Tests Passed)**: {all_passed_tasks}/{total_tasks} ({all_passed_tasks/total_tasks*100:.1f}%)")
        md.append(f"- **Overall AIBenchMark-ESW Score**: **{avg_total:.2f} / 100.0**\n")

        if metadata:
            compiler = metadata.get("compiler", {})
            md.append("### Reproducibility")
            md.append(f"- **Run (UTC)**: {metadata.get('created_at_utc', 'Unknown')}")
            md.append(f"- **Benchmark / Python**: {metadata.get('benchmark_version', 'Unknown')} / {metadata.get('python_version', 'Unknown')}")
            md.append(f"- **Compiler**: {compiler.get('name', 'Unknown')} / {compiler.get('version') or 'Unknown'} ({compiler.get('optimization', 'Unknown')})")
            md.append(f"- **Dataset SHA-256**: `{metadata.get('dataset_sha256', 'Unknown')}`")
            md.append(f"- **Source revision**: `{metadata.get('source_revision') or 'Unavailable in installed distribution'}`")
            md.append(f"- **Source had local changes**: {metadata.get('source_dirty', 'Unknown')}\n")

        md.append("### Dimensional Scores")
        md.append("| Dimension | Average Score | Weight |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| **Functional Correctness** | {avg_func:.2f} / 100 | {BenchmarkReporter._weight_summary(results, 'functional')} |")
        md.append(f"| **Memory Efficiency** | {avg_mem:.2f} / 100 | {BenchmarkReporter._weight_summary(results, 'memory')} |")
        md.append(f"| **Safety & Code Rules** | {avg_safe:.2f} / 100 | {BenchmarkReporter._weight_summary(results, 'safety')} |")
        md.append(f"| **Composite Score** | **{avg_total:.2f} / 100** | 100% |\n")

        md.append("### Detailed Task Breakdown")
        md.append("Weights below are functional/memory/safety. Memory and safety contributions are scaled by the functional pass fraction.\n")
        md.append("| Tier | Task ID | Standard | Weights | Compile | Tests Passed | Flash/RAM (B) | Safety | Score | Time |")
        md.append("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

        for r in results:
            status_comp = "PASS" if r.compiled else "FAIL"
            test_str = f"{r.test_result.passed_tests}/{r.test_result.total_tests}"
            if not r.test_result.completed:
                test_str += " (incomplete)"
            mem_str = (f"{r.size_metrics.flash_bytes} / {r.size_metrics.ram_bytes}"
                       if r.size_metrics.measured else "Unavailable")
            safe_str = f"Err:{r.safety_metrics.error_count}, Warn:{r.safety_metrics.warning_count}"
            score_str = f"**{r.scores.total_score:.1f}**"
            time_str = f"{r.execution_time_sec:.2f}s"
            md.append(f"| {r.tier} | `{r.task_id}` | {BenchmarkReporter._standard(r)} | {BenchmarkReporter._task_weights(r)} | {status_comp} | {test_str} | {mem_str} | {safe_str} | {score_str} | {time_str} |")

        return "\n".join(md)

    @staticmethod
    def generate_cli_table(results: List[TaskEvaluationResult], model_name: str) -> str:
        lines = []
        lines.append("=" * 110)
        lines.append(f" AIBenchMark-ESW Benchmark Results - Model: {model_name}")
        lines.append("=" * 110)
        header = f"{'Tier':<5} {'Task ID':<22} {'Standard':<14} {'Weights F/M/S':<16} {'Comp':<6} {'Tests':<8} {'Flash/RAM':<14} {'Score':<8}"
        lines.append(header)
        lines.append("-" * 110)

        for r in results:
            comp = "PASS" if r.compiled else "FAIL"
            tests = (f"{r.test_result.passed_tests}/{r.test_result.total_tests}"
                     if r.test_result.completed else "INCOMP")
            mem = (f"{r.size_metrics.flash_bytes}/{r.size_metrics.ram_bytes}B"
                   if r.size_metrics.measured else "Unavailable")
            score = f"{r.scores.total_score:.1f}"
            standard = BenchmarkReporter._standard(r)
            weights = BenchmarkReporter._task_weights(r)
            lines.append(f"{r.tier:<5} {r.task_id:<22} {standard:<14} {weights:<16} {comp:<6} {tests:<8} {mem:<14} {score:<8}")

        lines.append("-" * 110)
        avg_total = sum(r.scores.total_score for r in results) / max(1, len(results))
        pass_at_1 = sum(1 for r in results if BenchmarkReporter._all_tests_passed(r)) / max(1, len(results)) * 100.0
        lines.append(f"Final Score: {avg_total:.2f}/100.0 | Pass@1: {pass_at_1:.1f}%")
        lines.append("=" * 110)
        return "\n".join(lines)

    @staticmethod
    def to_json_dict(results: List[TaskEvaluationResult], model_name: str,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "schema_version": 2,
            "metadata": metadata,
            "model_name": model_name,
            "overall_score": round(sum(r.scores.total_score for r in results) / max(1, len(results)), 2),
            "pass_at_1_pct": round(sum(1 for r in results if BenchmarkReporter._all_tests_passed(r)) / max(1, len(results)) * 100.0, 2),
            "tasks": [r.to_dict() for r in results],
        }
