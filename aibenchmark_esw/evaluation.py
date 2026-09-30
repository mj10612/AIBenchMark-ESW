"""Shared local and model evaluation pipeline."""

import tempfile
import time
from pathlib import Path
from typing import Optional

from aibenchmark_esw.models import (
    TaskConfig, TaskEvaluationResult, TestResult, SizeMetrics,
    StaticSafetyMetrics, DimensionScores,
)
from aibenchmark_esw.metrics.scorer import BenchmarkScorer
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


def failed_evaluation(task: TaskConfig, model_name: str, error: str) -> TaskEvaluationResult:
    return TaskEvaluationResult(
        task.id, task.tier, model_name, False,
        TestResult(output=error, completed=False), SizeMetrics(measured=False),
        StaticSafetyMetrics(), DimensionScores(), 0.0, error_log=error,
        weights=task.weights, target_standard=task.target_standard,
    )


def evaluate_task(task: TaskConfig, solution_code: str, reference_code: Optional[str],
                  model_name: str, executor: ExecutionSandbox) -> TaskEvaluationResult:
    start = time.perf_counter()
    errors = []
    size = SizeMetrics(measured=False)
    with tempfile.TemporaryDirectory(prefix="aibenchmark_eval_") as directory:
        work_dir = Path(directory)
        test_dir = work_dir / "tests"
        comp, tests = executor.compile_and_test(task, solution_code, test_dir)
        if not comp.success:
            errors.append(comp.output or comp.error_message or "Compilation failed")
        elif not tests.passed:
            errors.append(tests.output or "Tests did not complete successfully")

        if comp.success:
            try:
                if not reference_code:
                    raise ValueError("Reference implementation is required for memory measurement")
                candidate = executor.compile_object(task, solution_code, work_dir / "candidate", "candidate")
                reference = executor.compile_object(task, reference_code, work_dir / "reference", "reference")
                if not candidate.success or not reference.success:
                    raise ValueError(candidate.output + reference.output)
                size = SizeAnalyzer().analyze(candidate.binary_path, reference.binary_path)
            except (OSError, ValueError) as error:
                errors.append(f"Memory analysis failed: {error}")

        source = test_dir / Path(task.entry_file).name
        safety = StaticAnalyzer().analyze(source, [task.task_dir / "include"],
                                           comp.effective_standard or task.target_standard)
        scores = BenchmarkScorer.calculate_scores(task, comp, tests, size, safety)

    return TaskEvaluationResult(
        task.id, task.tier, model_name, comp.success, tests, size, safety, scores,
        time.perf_counter() - start, error_log="\n".join(errors) if errors else None,
        weights=task.weights, target_standard=task.target_standard,
        effective_standard=comp.effective_standard,
    )
