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
from aibenchmark_esw.reference_cache import executor_reference_cache


def failed_evaluation(task: TaskConfig, model_name: str, error: str) -> TaskEvaluationResult:
    return TaskEvaluationResult(
        task.id, task.tier, model_name, False,
        TestResult(output=error, completed=False), SizeMetrics(measured=False),
        StaticSafetyMetrics(cppcheck_status="not_run"), DimensionScores(), 0.0, error_log=error,
        weights=task.weights, target_standard=task.target_standard, limits=task.limits,
        candidate_time_sec=0.0, reference_validation_time_sec=0.0,
    )


def evaluate_task(task: TaskConfig, solution_code: str, reference_code: Optional[str],
                  model_name: str, executor: ExecutionSandbox,
                  analyzer: Optional[StaticAnalyzer] = None, reference_cache=None) -> TaskEvaluationResult:
    start = time.perf_counter()
    errors = []
    size = SizeMetrics(measured=False)
    reference_elapsed = 0.0
    cache_hit = False
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
                candidate = executor.compile_object(task, solution_code, work_dir / "candidate", "candidate")
                if not candidate.success:
                    raise ValueError(candidate.output or "Candidate object compilation failed")
                assert candidate.binary_path is not None
                size = SizeAnalyzer().analyze(candidate.binary_path)
                reference_start = time.perf_counter()
                try:
                    cache = reference_cache if reference_cache is not None else executor_reference_cache(executor)
                    existing = (comp, tests, candidate) if reference_code == solution_code else None
                    reference, cache_hit = cache.validate(task, reference_code, executor, existing)
                finally:
                    reference_elapsed = time.perf_counter() - reference_start
                if reference.error:
                    raise ValueError(reference.error)
                size.ref_flash_bytes, size.ref_ram_bytes = reference.flash_bytes, reference.ram_bytes
                size.measured = True
            except (OSError, ValueError) as error:
                size.measured = False
                errors.append(f"Memory analysis failed: {error}")

        source = test_dir / Path(task.entry_file).name
        safety = (analyzer or StaticAnalyzer()).analyze(source, [task.task_dir / "include"],
                                                       comp.effective_standard or task.target_standard)
        scores = BenchmarkScorer.calculate_scores(task, comp, tests, size, safety)

    candidate_elapsed = max(0.0, time.perf_counter() - start - reference_elapsed)
    return TaskEvaluationResult(
        task.id, task.tier, model_name, comp.success, tests, size, safety, scores,
        candidate_elapsed, error_log="\n".join(errors) if errors else None,
        weights=task.weights, target_standard=task.target_standard,
        effective_standard=comp.effective_standard,
        limits=task.limits, candidate_time_sec=candidate_elapsed,
        reference_validation_time_sec=reference_elapsed,
        provenance={"reference_cache_hit": cache_hit},
        footprint_target=executor.cross.target if executor.cross is not None else "host",
    )
