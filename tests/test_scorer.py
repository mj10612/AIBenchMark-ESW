import unittest
from pathlib import Path
from aibenchmark_esw.models import (
    TaskConfig,
    TaskLimits,
    TaskWeights,
    CompilationResult,
    TestResult,
    SizeMetrics,
    StaticSafetyMetrics,
)
from aibenchmark_esw.metrics.scorer import BenchmarkScorer


class TestBenchmarkScorer(unittest.TestCase):
    def setUp(self):
        self.task = TaskConfig(
            id="test_task",
            name="Test Task",
            tier=1,
            category="test",
            target_standard="c99",
            description="Test task description",
            limits=TaskLimits(max_flash_bytes=1000, max_ram_bytes=200),
            weights=TaskWeights(functional=0.6, memory=0.2, safety=0.2),
            entry_file="src/test.c",
            task_dir=Path("."),
        )

    def test_perfect_score(self):
        comp = CompilationResult(success=True, output="")
        tests = TestResult(total_tests=10, passed_tests=10, failed_tests=0, passed=True, completed=True)
        size = SizeMetrics(flash_bytes=500, ram_bytes=100, ref_flash_bytes=500, ref_ram_bytes=100)
        safety = StaticSafetyMetrics(error_count=0, warning_count=0)

        scores = BenchmarkScorer.calculate_scores(self.task, comp, tests, size, safety)
        self.assertEqual(scores.functional_score, 100.0)
        self.assertEqual(scores.memory_score, 100.0)
        self.assertEqual(scores.safety_score, 100.0)
        self.assertEqual(scores.total_score, 100.0)

    def test_compilation_failure_zero_score(self):
        comp = CompilationResult(success=False, output="syntax error")
        tests = TestResult()
        size = SizeMetrics()
        safety = StaticSafetyMetrics()

        scores = BenchmarkScorer.calculate_scores(self.task, comp, tests, size, safety)
        self.assertEqual(scores.total_score, 0.0)
        self.assertEqual(scores.functional_score, 0.0)

    def test_partial_tests_passed(self):
        comp = CompilationResult(success=True, output="")
        tests = TestResult(total_tests=10, passed_tests=5, failed_tests=5, passed=False, completed=True)
        size = SizeMetrics(flash_bytes=500, ram_bytes=100, ref_flash_bytes=500, ref_ram_bytes=100)
        safety = StaticSafetyMetrics(error_count=0, warning_count=0)

        scores = BenchmarkScorer.calculate_scores(self.task, comp, tests, size, safety)
        self.assertEqual(scores.functional_score, 50.0)
        # Functional is 50.0 * 0.6 = 30.0
        # Memory is 100.0 * 0.2 * (50/100) = 10.0
        # Safety is 100.0 * 0.2 * (50/100) = 10.0
        # Total = 50.0
        self.assertEqual(scores.total_score, 50.0)

    def test_safety_violations_deductions(self):
        comp = CompilationResult(success=True, output="")
        tests = TestResult(total_tests=5, passed_tests=5, failed_tests=0, passed=True, completed=True)
        size = SizeMetrics(flash_bytes=500, ram_bytes=100, ref_flash_bytes=500, ref_ram_bytes=100)
        # 1 error (-15), 2 warnings (-6) -> safety = 100 - 21 = 79.0
        safety = StaticSafetyMetrics(error_count=1, warning_count=2)

        scores = BenchmarkScorer.calculate_scores(self.task, comp, tests, size, safety)
        self.assertEqual(scores.safety_score, 79.0)
        expected_total = (0.6 * 100.0) + (0.2 * 100.0) + (0.2 * 79.0)
        self.assertAlmostEqual(scores.total_score, expected_total, places=1)

    def test_abnormal_exit_has_zero_scores(self):
        scores = BenchmarkScorer.calculate_scores(
            self.task, CompilationResult(True, ""),
            TestResult(total_tests=10, passed_tests=10, completed=False, returncode=7),
            SizeMetrics(500, 100, 500, 100), StaticSafetyMetrics())
        self.assertEqual(scores.total_score, 0)
        self.assertEqual(scores.functional_score, 0)

    def test_missing_memory_measurement_is_not_perfect(self):
        for size in [SizeMetrics(measured=False), SizeMetrics()]:
            with self.subTest(size=size):
                scores = BenchmarkScorer.calculate_scores(
                    self.task, CompilationResult(True, ""),
                    TestResult(total_tests=1, passed_tests=1, passed=True, completed=True), size,
                    StaticSafetyMetrics())
                self.assertEqual(scores.memory_score, 0)

    def test_individual_ram_limit_is_enforced(self):
        scores = BenchmarkScorer.calculate_scores(
            self.task, CompilationResult(True, ""),
            TestResult(total_tests=1, passed_tests=1, passed=True, completed=True),
            SizeMetrics(400, 201, 500, 100), StaticSafetyMetrics())
        self.assertEqual(scores.memory_score, 0)

    def test_reference_resource_limits_cannot_inflate_memory_score(self):
        for size in (SizeMetrics(500, 100, 1001, 0), SizeMetrics(500, 100, 500, 201)):
            with self.subTest(size=size):
                scores = BenchmarkScorer.calculate_scores(
                    self.task, CompilationResult(True, ""),
                    TestResult(total_tests=1, passed_tests=1, passed=True, completed=True),
                    size, StaticSafetyMetrics())
                self.assertEqual(scores.memory_score, 0)

    def test_result_without_explicit_completion_cannot_score(self):
        result = TestResult(total_tests=10, passed_tests=10, passed=True)
        self.assertFalse(result.completed)
        scores = BenchmarkScorer.calculate_scores(
            self.task, CompilationResult(True, ""), result,
            SizeMetrics(500, 100, 500, 100), StaticSafetyMetrics())
        self.assertEqual(scores.total_score, 0)


if __name__ == "__main__":
    unittest.main()
