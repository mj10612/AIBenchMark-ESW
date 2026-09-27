import json
from typing import List, Dict, Any
from embeval.models import TaskEvaluationResult


class BenchmarkReporter:
    @staticmethod
    def generate_markdown(results: List[TaskEvaluationResult], model_name: str) -> str:
        if not results:
            return "No benchmark results available."

        total_tasks = len(results)
        compiled_tasks = sum(1 for r in results if r.compiled)
        all_passed_tasks = sum(1 for r in results if r.test_result.passed)

        avg_func = sum(r.scores.functional_score for r in results) / total_tasks
        avg_mem = sum(r.scores.memory_score for r in results) / total_tasks
        avg_safe = sum(r.scores.safety_score for r in results) / total_tasks
        avg_total = sum(r.scores.total_score for r in results) / total_tasks

        md = []
        md.append(f"# EmbEval Benchmark Report: `{model_name}`\n")
        md.append("### Summary Overview")
        md.append(f"- **Total Tasks**: {total_tasks}")
        md.append(f"- **Compilation Rate**: {compiled_tasks}/{total_tasks} ({compiled_tasks/total_tasks*100:.1f}%)")
        md.append(f"- **Pass@1 (All Tests Passed)**: {all_passed_tasks}/{total_tasks} ({all_passed_tasks/total_tasks*100:.1f}%)")
        md.append(f"- **Overall EmbEval Score**: **{avg_total:.2f} / 100.0**\n")

        md.append("### Dimensional Scores")
        md.append("| Dimension | Average Score | Weight |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| **Functional Correctness** | {avg_func:.2f} / 100 | 60% |")
        md.append(f"| **Memory Efficiency** | {avg_mem:.2f} / 100 | 20% |")
        md.append(f"| **Safety & Code Rules** | {avg_safe:.2f} / 100 | 20% |")
        md.append(f"| **Composite Score** | **{avg_total:.2f} / 100** | 100% |\n")

        md.append("### Detailed Task Breakdown")
        md.append("| Tier | Task ID | Compile | Tests Passed | Flash/RAM (B) | Safety | Score | Time |")
        md.append("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

        for r in results:
            status_comp = "✅" if r.compiled else "❌"
            test_str = f"{r.test_result.passed_tests}/{r.test_result.total_tests}"
            mem_str = f"{r.size_metrics.flash_bytes} / {r.size_metrics.ram_bytes}"
            safe_str = f"Err:{r.safety_metrics.error_count}, Warn:{r.safety_metrics.warning_count}"
            score_str = f"**{r.scores.total_score:.1f}**"
            time_str = f"{r.execution_time_sec:.2f}s"
            md.append(f"| {r.tier} | `{r.task_id}` | {status_comp} | {test_str} | {mem_str} | {safe_str} | {score_str} | {time_str} |")

        return "\n".join(md)

    @staticmethod
    def generate_cli_table(results: List[TaskEvaluationResult], model_name: str) -> str:
        lines = []
        lines.append("=" * 78)
        lines.append(f" EmbEval Benchmark Results - Model: {model_name}")
        lines.append("=" * 78)
        header = f"{'Tier':<5} {'Task ID':<22} {'Comp':<6} {'Tests':<8} {'Flash/RAM':<14} {'Score':<8}"
        lines.append(header)
        lines.append("-" * 78)

        for r in results:
            comp = "PASS" if r.compiled else "FAIL"
            tests = f"{r.test_result.passed_tests}/{r.test_result.total_tests}"
            mem = f"{r.size_metrics.flash_bytes}/{r.size_metrics.ram_bytes}B"
            score = f"{r.scores.total_score:.1f}"
            lines.append(f"{r.tier:<5} {r.task_id:<22} {comp:<6} {tests:<8} {mem:<14} {score:<8}")

        lines.append("-" * 78)
        avg_total = sum(r.scores.total_score for r in results) / max(1, len(results))
        pass_at_1 = sum(1 for r in results if r.test_result.passed) / max(1, len(results)) * 100.0
        lines.append(f"Final Score: {avg_total:.2f}/100.0 | Pass@1: {pass_at_1:.1f}%")
        lines.append("=" * 78)
        return "\n".join(lines)

    @staticmethod
    def to_json_dict(results: List[TaskEvaluationResult], model_name: str) -> Dict[str, Any]:
        return {
            "model_name": model_name,
            "overall_score": round(sum(r.scores.total_score for r in results) / max(1, len(results)), 2),
            "pass_at_1_pct": round(sum(1 for r in results if r.test_result.passed) / max(1, len(results)) * 100.0, 2),
            "tasks": [r.to_dict() for r in results],
        }
