import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.task = self.loader.get_task("tier1_crc16")
        self.reference = self.loader.get_reference_solution(self.task.id)
        self.executor = ExecutionSandbox()

    def test_reference_measures_implementation_and_reference_equally(self):
        result = evaluate_task(self.task, self.reference, self.reference, "baseline", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertIsNone(result.error_log)
        self.assertTrue(result.size_metrics.measured)
        self.assertGreater(result.size_metrics.flash_bytes, 0)
        self.assertEqual(result.size_metrics.flash_bytes, result.size_metrics.ref_flash_bytes)
        self.assertEqual(result.size_metrics.ram_bytes, 0)
        self.assertEqual(result.scores.total_score, 100)
        with TemporaryDirectory() as directory:
            comp, _ = self.executor.compile_and_test(self.task, self.reference, Path(directory))
            executable_size = SizeAnalyzer()._measure_file(comp.binary_path)[0]
        self.assertLess(result.size_metrics.flash_bytes, executable_size)

    def test_crash_after_passing_tests_receives_zero(self):
        code = '#include <stdio.h>\n#include <stdlib.h>\nstatic void fail_at_exit(void) { fflush(NULL); _Exit(7); }\n'
        code += self.reference.replace(
            'uint16_t crc16_update(uint16_t current_crc, uint8_t byte) {',
            'uint16_t crc16_update(uint16_t current_crc, uint8_t byte) { '
            'static int registered=0; if (!registered) { atexit(fail_at_exit); registered=1; }')
        result = evaluate_task(self.task, code, self.reference, "local", self.executor)
        self.assertTrue(result.compiled)
        self.assertFalse(result.test_result.completed)
        self.assertEqual(result.scores.total_score, 0)
        self.assertIsNotNone(result.error_log)

    def test_missing_reference_does_not_award_memory_points(self):
        result = evaluate_task(self.task, self.reference, None, "local", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertFalse(result.size_metrics.measured)
        self.assertEqual(result.scores.memory_score, 0)
        self.assertIn("Memory analysis failed", result.error_log)

    def test_ring_reference_passes_rollover_cases(self):
        task = self.loader.get_task("tier1_ring_buffer")
        ref = self.loader.get_reference_solution(task.id)
        comp, result = self.executor.compile_and_test(task, ref)
        self.addCleanup(comp.cleanup)
        self.assertTrue(result.passed, result.output)
        self.assertEqual(result.total_tests, 9)


if __name__ == "__main__":
    unittest.main()
