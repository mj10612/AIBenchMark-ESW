from aibenchmark_esw.models import (
    TaskConfig,
    CompilationResult,
    TestResult,
    SizeMetrics,
    StaticSafetyMetrics,
    DimensionScores,
)


SCORING_FORMULA_VERSION = "functional-gated-v1"
SAFETY_ERROR_PENALTY = 15
SAFETY_WARNING_PENALTY = 3


class BenchmarkScorer:
    @staticmethod
    def memory_score(limits, size_metrics):
        """Keep independent hard limits before applying the combined-size reward."""
        max_budget = limits.max_flash_bytes + limits.max_ram_bytes
        actual_size = size_metrics.flash_bytes + size_metrics.ram_bytes
        ref_size = size_metrics.ref_flash_bytes + size_metrics.ref_ram_bytes
        if (not size_metrics.measured or ref_size <= 0
                or size_metrics.flash_bytes > limits.max_flash_bytes
                or size_metrics.ram_bytes > limits.max_ram_bytes
                or size_metrics.ref_flash_bytes > limits.max_flash_bytes
                or size_metrics.ref_ram_bytes > limits.max_ram_bytes):
            return 0.0
        if actual_size <= ref_size:
            return 100.0
        if actual_size >= max_budget:
            return 0.0
        return max(0.0, 100.0 - 100.0 * (actual_size - ref_size) / max(1, max_budget - ref_size))

    @staticmethod
    def safety_score(safety_metrics):
        penalty = safety_metrics.error_count * SAFETY_ERROR_PENALTY + safety_metrics.warning_count * SAFETY_WARNING_PENALTY
        return 0.0 if penalty >= 100 else 100.0 - penalty

    @staticmethod
    def calculate_scores(
        task: TaskConfig,
        comp_res: CompilationResult,
        test_res: TestResult,
        size_metrics: SizeMetrics,
        safety_metrics: StaticSafetyMetrics,
    ) -> DimensionScores:
        if not comp_res.success or not test_res.completed:
            return DimensionScores(0.0, 0.0, 0.0, 0.0)

        # 1. Functional Score (0.0 - 100.0)
        if test_res.total_tests == 0:
            func_score = 0.0
        else:
            func_score = (test_res.passed_tests / test_res.total_tests) * 100.0

        # 2. Memory Footprint Score (0.0 - 100.0)
        mem_score = BenchmarkScorer.memory_score(task.limits, size_metrics)

        # 3. Code Safety & MISRA Score (0.0 - 100.0)
        safety_score = BenchmarkScorer.safety_score(safety_metrics)

        # 4. Total Composite Score
        # If functional tests fail, memory and safety are scaled down proportionally
        func_factor = func_score / 100.0
        w_func = task.weights.functional
        w_mem = task.weights.memory
        w_safe = task.weights.safety

        total_score = (w_func * func_score) + (w_mem * mem_score * func_factor) + (w_safe * safety_score * func_factor)

        return DimensionScores(
            functional_score=round(func_score, 2),
            memory_score=round(mem_score, 2),
            safety_score=round(safety_score, 2),
            total_score=round(total_score, 2),
        )
