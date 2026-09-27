from aibenchmark_esw.models import (
    TaskConfig,
    CompilationResult,
    TestResult,
    SizeMetrics,
    StaticSafetyMetrics,
    DimensionScores,
)


class BenchmarkScorer:
    @staticmethod
    def calculate_scores(
        task: TaskConfig,
        comp_res: CompilationResult,
        test_res: TestResult,
        size_metrics: SizeMetrics,
        safety_metrics: StaticSafetyMetrics,
    ) -> DimensionScores:
        if not comp_res.success:
            return DimensionScores(0.0, 0.0, 0.0, 0.0)

        # 1. Functional Score (0.0 - 100.0)
        if test_res.total_tests == 0:
            func_score = 0.0
        else:
            func_score = (test_res.passed_tests / test_res.total_tests) * 100.0

        # 2. Memory Footprint Score (0.0 - 100.0)
        max_budget = task.limits.max_flash_bytes + task.limits.max_ram_bytes
        actual_size = size_metrics.flash_bytes + size_metrics.ram_bytes
        ref_size = size_metrics.ref_flash_bytes + size_metrics.ref_ram_bytes

        if ref_size <= 0:
            ref_size = max(1, max_budget // 2)

        if actual_size <= ref_size:
            mem_score = 100.0
        elif actual_size >= max_budget:
            mem_score = 0.0
        else:
            # Linear penalty between ref_size and max_budget
            denom = max(1, max_budget - ref_size)
            excess_ratio = (actual_size - ref_size) / denom
            mem_score = max(0.0, 100.0 - (100.0 * excess_ratio))

        # 3. Code Safety & MISRA Score (0.0 - 100.0)
        penalty = (safety_metrics.error_count * 15.0) + (safety_metrics.warning_count * 3.0)
        safety_score = max(0.0, 100.0 - penalty)

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
