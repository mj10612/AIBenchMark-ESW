import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
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

    def test_custom_root_must_exist_and_be_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                DatasetLoader(root / "missing")
            file = root / "file"
            file.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(NotADirectoryError):
                DatasetLoader(file)

    def test_invalid_task_is_logged_and_rejected_instead_of_skipped(self):
        with TemporaryDirectory() as directory:
            task_dir = Path(directory) / "broken"
            task_dir.mkdir()
            (task_dir / "task.json").write_text("{invalid JSON", encoding="utf-8")
            with self.assertLogs("aibenchmark_esw.dataset", level="ERROR") as logs:
                with self.assertRaisesRegex(ValueError, "Invalid task"):
                    DatasetLoader(Path(directory))
            self.assertIn("broken", logs.output[0])

    def test_explicit_reference_path(self):
        with TemporaryDirectory() as directory:
            task_dir = Path(directory) / "custom"
            task_dir.mkdir()
            (task_dir / "gold.c").write_text("int correct(void) { return 1; }", encoding="utf-8")
            data = {"id": "custom", "entry_file": "src/solution.c", "reference_file": "gold.c"}
            (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")
            loader = DatasetLoader(Path(directory))
            self.assertIn("int correct", loader.get_reference_solution("custom"))

    def test_invalid_metadata_weights_and_paths_are_rejected(self):
        for fields in [{"weights": {"functional": 1, "memory": 1, "safety": 1}},
                       {"reference_file": "../outside.c"},
                       {"reference_file": "C:\\outside.c"},
                       {"limits": {"timeout_seconds": 0}}]:
            with self.subTest(fields=fields), TemporaryDirectory() as directory:
                task_dir = Path(directory) / "invalid"
                task_dir.mkdir()
                (task_dir / "task.json").write_text(json.dumps({"id": "invalid", **fields}), encoding="utf-8")
                with self.assertLogs("aibenchmark_esw.dataset", level="ERROR"):
                    with self.assertRaises(ValueError):
                        DatasetLoader(Path(directory))

    def test_duplicate_task_ids_are_rejected(self):
        with TemporaryDirectory() as directory:
            for name in ("first", "second"):
                task_dir = Path(directory) / name
                task_dir.mkdir()
                (task_dir / "task.json").write_text('{"id":"duplicate"}', encoding="utf-8")
            with self.assertLogs("aibenchmark_esw.dataset", level="ERROR"):
                with self.assertRaisesRegex(ValueError, "Duplicate task id"):
                    DatasetLoader(Path(directory))


if __name__ == "__main__":
    unittest.main()
