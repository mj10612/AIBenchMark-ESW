import unittest

from aibenchmark_esw.dataset import DatasetLoader, validate_task_assets
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestCOBSTask(unittest.TestCase):
    def test_reference_passes_and_fits_object_budgets(self):
        loader = DatasetLoader()
        task = loader.get_task("tier2_cobs_codec")
        self.assertEqual(validate_task_assets(task), [])
        reference = loader.get_reference_solution(task.id)
        result = evaluate_task(task, reference, reference, "baseline", ExecutionSandbox(),
                               StaticAnalyzer(cppcheck_cmd="off"))
        self.assertTrue(result.test_result.passed, result.error_log)
        self.assertEqual(result.test_result.total_tests, 9)
        self.assertEqual(result.scores.total_score, 100)
        self.assertLessEqual(result.size_metrics.flash_bytes, task.limits.max_flash_bytes)
        self.assertEqual(result.size_metrics.ram_bytes, 0)

    def test_starter_compiles_but_fails_completed_suite(self):
        loader = DatasetLoader()
        task = loader.get_task("tier2_cobs_codec")
        compiled, result = ExecutionSandbox().compile_and_test(task, loader.get_starter_code(task.id))
        self.addCleanup(compiled.cleanup)
        self.assertTrue(compiled.success, compiled.output)
        self.assertTrue(result.completed, result.output)
        self.assertFalse(result.passed)
