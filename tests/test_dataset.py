import unittest
from aibenchmark_esw.dataset import DatasetLoader


class TestDatasetLoader(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()

    def test_list_all_tasks(self):
        tasks = self.loader.list_tasks()
        self.assertGreaterEqual(len(tasks), 5)
        task_ids = [t.id for t in tasks]
        self.assertIn("tier1_ring_buffer", task_ids)
        self.assertIn("tier1_crc16", task_ids)
        self.assertIn("tier2_debounce_fsm", task_ids)
        self.assertIn("tier3_i2c_sensor", task_ids)
        self.assertIn("tier4_bitmask_fix", task_ids)

    def test_filter_by_tier(self):
        tier1_tasks = self.loader.list_tasks(tier=1)
        self.assertTrue(all(t.tier == 1 for t in tier1_tasks))
        self.assertGreaterEqual(len(tier1_tasks), 2)

    def test_task_metadata_and_prompt(self):
        task = self.loader.get_task("tier1_ring_buffer")
        self.assertIsNotNone(task)
        self.assertEqual(task.tier, 1)
        self.assertEqual(task.target_standard, "c99")
        self.assertIn("ring_buffer", task.prompt.lower())

    def test_get_reference_and_starter_code(self):
        ref = self.loader.get_reference_solution("tier1_crc16")
        self.assertIsNotNone(ref)
        self.assertIn("crc16_ccitt", ref)

        starter = self.loader.get_starter_code("tier1_crc16")
        self.assertIsNotNone(starter)


if __name__ == "__main__":
    unittest.main()
