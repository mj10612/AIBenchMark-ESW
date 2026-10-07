import unittest

from aibenchmark_esw.dataset import DatasetLoader, validate_task_assets
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


NEW_TASKS = {
    "tier4_dma_buffer": 5,
    "tier3_spi_flash": 6,
    "tier4_uart_frame_fix": 7,
    "tier2_fixed_control": 7,
    "tier3_flash_update": 6,
}


class TestFirmwareTasks(unittest.TestCase):
    def test_new_references_fit_measured_static_object_budgets_without_safety_findings(self):
        loader = DatasetLoader()
        executor = ExecutionSandbox()
        for task_id in NEW_TASKS:
            with self.subTest(task=task_id):
                task = loader.get_task(task_id)
                reference = loader.get_reference_solution(task_id)
                result = evaluate_task(task, reference, reference, "baseline", executor,
                                       StaticAnalyzer(cppcheck_cmd="off"))
                self.assertTrue(result.test_result.passed, result.error_log)
                self.assertEqual(result.scores.total_score, 100)
                self.assertLessEqual(result.size_metrics.flash_bytes, task.limits.max_flash_bytes)
                self.assertLessEqual(result.size_metrics.ram_bytes, task.limits.max_ram_bytes)
                self.assertEqual(result.safety_metrics.error_count, 0)
                self.assertEqual(result.safety_metrics.warning_count, 0)

    def test_references_pass_and_buggy_starters_fail_completed_suites(self):
        loader = DatasetLoader()
        for task_id, count in NEW_TASKS.items():
            with self.subTest(task=task_id):
                task = loader.get_task(task_id)
                self.assertIsNotNone(task)
                self.assertEqual(validate_task_assets(task), [])
                for source, expected in ((loader.get_reference_solution(task_id), True),
                                         (loader.get_starter_code(task_id), False)):
                    compiled, result = ExecutionSandbox().compile_and_test(task, source)
                    self.addCleanup(compiled.cleanup)
                    self.assertTrue(compiled.success, compiled.output)
                    self.assertTrue(result.completed, result.output)
                    self.assertEqual(result.total_tests, count)
                    self.assertEqual(result.passed, expected, result.output)
