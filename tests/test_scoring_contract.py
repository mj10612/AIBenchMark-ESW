import unittest
from pathlib import Path

from aibenchmark_esw.metrics.scorer import BenchmarkScorer
from aibenchmark_esw.models import (
    CompilationResult, SizeMetrics, StaticSafetyMetrics, TaskConfig, TaskLimits, TaskWeights, TestResult,
)


class TestDocumentedScoringContract(unittest.TestCase):
    def task(self):
        return TaskConfig("contract", "contract", 1, "test", "c99", "", TaskLimits(1000, 200),
                          TaskWeights(), "solution.c", Path("."))

    def test_unused_ram_cannot_compensate_excess_flash_or_vice_versa(self):
        for size in (SizeMetrics(1001, 0, 500, 100), SizeMetrics(0, 201, 500, 100),
                     SizeMetrics(3000, 0, 500, 100)):
            with self.subTest(size=size):
                self.assertEqual(BenchmarkScorer.memory_score(self.task().limits, size), 0)

    def test_zero_functional_keeps_raw_dimensions_but_gates_composite(self):
        scores = BenchmarkScorer.calculate_scores(self.task(), CompilationResult(True, ""),
            TestResult(total_tests=5, passed_tests=0, failed_tests=5, completed=True),
            SizeMetrics(500, 100, 500, 100), StaticSafetyMetrics())
        self.assertEqual((scores.functional_score, scores.memory_score, scores.safety_score, scores.total_score),
                         (0, 100, 100, 0))
