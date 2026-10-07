import unittest

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestDatasetBoundaries(unittest.TestCase):
    def test_reviewed_boundary_faults_fail_completed_assertions(self):
        loader = DatasetLoader()
        faults = {
            "tier1_ring_buffer": [
                ("capacity <= SIZE_MAX / 2U", "capacity != SIZE_MAX"),
                ("size_t head = rb->head;", "uint8_t head = (uint8_t)rb->head;")],
            "tier1_crc16": [("i < length", "i < (uint16_t)length")],
            "tier4_bitmask_fix": [
                ("if (ctrl == NULL || irq_num >= MAX_IRQS || priority > PRIORITY_MASK) {",
                 "if (ctrl == NULL || irq_num >= MAX_IRQS || priority > PRIORITY_MASK) { if (ctrl) {ctrl->status_reg = 0; ctrl->priority_reg = 0;}")],
            "tier2_debounce_fsm": [
                ("raw_pin_level != 0U", "raw_pin_level == 1U"),
                ("fsm->press_duration >= fsm->hold_threshold", "fsm->press_duration > fsm->hold_threshold"),
                ("(fsm->hold_threshold > 0U) &&", "")],
        }
        for task_id, mutations in faults.items():
            for before, after in mutations:
                with self.subTest(task=task_id, fault=before):
                    reference = loader.get_reference_solution(task_id)
                    self.assertIn(before, reference)
                    compiled, result = ExecutionSandbox().compile_and_test(
                        loader.get_task(task_id), reference.replace(before, after))
                    self.addCleanup(compiled.cleanup)
                    self.assertTrue(compiled.success, compiled.output)
                    self.assertTrue(result.completed, result.output)
                    self.assertGreater(result.failed_tests, 0, result.output)
