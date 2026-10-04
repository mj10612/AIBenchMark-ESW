import json
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.provenance import collect_run_metadata, task_sha256, text_sha256
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestProvenance(unittest.TestCase):
    def setUp(self):
        self.task = DatasetLoader().get_task("tier1_crc16")
        self.executor = ExecutionSandbox()

    def test_fingerprint_ignores_checkout_location_and_line_endings(self):
        expected = task_sha256(self.task, self.executor.unity_dir)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "task"
            unity = root / "unity"
            shutil.copytree(self.task.task_dir, copied)
            shutil.copytree(self.executor.unity_dir, unity)
            for path in list(copied.rglob("*")) + list(unity.glob("*")):
                if path.is_file():
                    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
            self.assertEqual(task_sha256(replace(self.task, task_dir=copied), unity), expected)
            (copied / "tests/build").mkdir()
            (copied / "tests/build/generated.c").write_text("generated", encoding="utf-8")
            self.assertEqual(task_sha256(replace(self.task, task_dir=copied), unity), expected)

    def test_configuration_source_and_harness_changes_change_fingerprints(self):
        expected = task_sha256(self.task, self.executor.unity_dir)
        self.assertNotEqual(expected, task_sha256(replace(self.task, target_standard="c11"), self.executor.unity_dir))
        self.assertNotEqual(expected, task_sha256(replace(self.task, limits=replace(
            self.task.limits, max_ram_bytes=129)), self.executor.unity_dir))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "task"
            unity = root / "unity"
            shutil.copytree(self.task.task_dir, copied)
            shutil.copytree(self.executor.unity_dir, unity)
            config = replace(self.task, task_dir=copied)
            (copied / "tests/test_crc16.c").write_text("changed tests", encoding="utf-8")
            self.assertNotEqual(expected, task_sha256(config, unity))
            (unity / "unity.c").write_text("changed harness", encoding="utf-8")
            self.assertNotEqual(task_sha256(self.task, self.executor.unity_dir), task_sha256(self.task, unity))

    def test_metadata_does_not_collect_environment_credentials(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "private-openai-key", "ANTHROPIC_API_KEY": "private-claude-key"}):
            metadata = collect_run_metadata([self.task], self.executor, {"temperature": None})
        encoded = json.dumps(metadata)
        self.assertNotIn("private-openai-key", encoded)
        self.assertNotIn("private-claude-key", encoded)
        self.assertEqual(metadata["compiler"]["name"], Path(self.executor.compiler_path).stem.lower())
        self.assertEqual(len(metadata["dataset_sha256"]), 64)
        self.assertEqual(len(metadata["evaluator_sha256"]), 64)
        self.assertEqual(metadata["selected_tasks"], ["tier1_crc16"])

    def test_candidate_hash_normalizes_newlines(self):
        self.assertEqual(text_sha256("int x;\r\n"), text_sha256("int x;\n"))

    def test_metadata_records_selected_static_analyzer_and_version(self):
        analyzer = StaticAnalyzer("fixture-cppcheck")
        def output(command):
            return "Cppcheck 2.fixture" if command[0] == "fixture-cppcheck" else None
        with patch("aibenchmark_esw.provenance._command_output", side_effect=output):
            metadata = collect_run_metadata([self.task], self.executor, static_analyzer=analyzer)
        self.assertEqual(metadata["static_analysis"],
                         {"engine": "builtin+cppcheck", "cppcheck_version": "Cppcheck 2.fixture"})
        with patch("aibenchmark_esw.sandbox.static_analyzer.shutil.which", return_value=None):
            metadata = collect_run_metadata([self.task], self.executor, static_analyzer=StaticAnalyzer())
        self.assertEqual(metadata["static_analysis"], {"engine": "builtin", "cppcheck_version": None})
