import hashlib
import importlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw import cli


class TestTaskVariants(unittest.TestCase):
    def test_actual_run_cli_reproduces_seeded_hashes_and_distinguishes_seeds(self):
        hashes = []
        with TemporaryDirectory() as directory:
            for index, seed in enumerate((42, 42, 43)):
                output = Path(directory) / f"run-{index}.json"
                args = cli.build_parser().parse_args(["run", "--model", "baseline", "--tasks",
                    "tier1_crc16", "--variant-seed", str(seed), "--output", str(output)])
                with patch.object(cli.LLMClient, "generate_solution") as generate, redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(args), 0)
                    generate.assert_not_called()
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["metadata"]["contamination_controls"]["variant_seed"], seed)
                self.assertEqual(report["tasks"][0]["scores"]["total"], 100)
                hashes.append(report["metadata"]["task_fingerprints"]["tier1_crc16"])
        self.assertEqual(hashes[0], hashes[1])
        self.assertNotEqual(hashes[0], hashes[2])

    def test_actual_run_cli_heldout_bytes_are_excluded_from_provider_messages_and_report(self):
        task = DatasetLoader().get_task("tier1_crc16")
        reference = task.reference_path.read_text(encoding="utf-8")
        marker = "PRIVATE_TEST_CONTENT_91F4C2"
        with TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            tests = root / task.id / "tests"
            shutil.copytree(task.task_dir / "tests", tests)
            path = tests / "test_crc16.c"
            path.write_text(path.read_text(encoding="utf-8") + f"\n/* {marker} */\n", encoding="utf-8")
            output = Path(directory) / "run.json"
            args = cli.build_parser().parse_args(["run", "--model", "mock", "--tasks", task.id,
                "--heldout-tests", str(root), "--output", str(output)])
            with patch.object(cli.LLMClient, "generate_solution", return_value=reference) as generate:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(args), 0)
                self.assertEqual(generate.call_count, 1)
                self.assertNotIn(marker, json.dumps(generate.call_args.args[0]))
            report_text = output.read_text(encoding="utf-8")
            self.assertNotIn(marker, report_text)
            evidence = json.loads(report_text)["metadata"]["contamination_controls"]
            self.assertTrue(evidence["heldout_tests_used"])
            self.assertEqual(len(evidence["heldout_sha256"]), 64)

    def module(self):
        import aibenchmark_esw
        self.assertTrue((Path(aibenchmark_esw.__file__).parent / "task_variants.py").is_file())
        return importlib.import_module("aibenchmark_esw.task_variants")

    def test_seeded_crc_variant_is_reproducible_and_reference_passes(self):
        variants = self.module()
        task = DatasetLoader().get_task("tier1_crc16")
        original = task.reference_path.read_bytes()
        fingerprints = []
        for _ in range(2):
            with variants.prepare_task_variants([task], variant_seed=42) as (tasks, evidence):
                self.assertEqual(evidence["variant_seed"], 42)
                self.assertFalse(evidence["heldout_tests_used"])
                self.assertNotEqual(tasks[0].reference_path.read_bytes(), original)
                fingerprints.append(hashlib.sha256(tasks[0].reference_path.read_bytes()).hexdigest())
                compiled, result = ExecutionSandbox().compile_and_test(tasks[0], tasks[0].reference_path.read_text())
                self.addCleanup(compiled.cleanup)
                self.assertTrue(compiled.success, compiled.output)
                self.assertTrue(result.passed, result.output)
        self.assertEqual(fingerprints[0], fingerprints[1])
        self.assertEqual(task.reference_path.read_bytes(), original)

    def test_heldout_suite_is_overlaid_without_changing_public_prompt_headers(self):
        variants = self.module()
        task = DatasetLoader().get_task("tier1_crc16")
        with TemporaryDirectory() as directory:
            tests = Path(directory) / task.id / "tests"
            shutil.copytree(task.task_dir / "tests", tests)
            (tests / "test_crc16.c").write_text((tests / "test_crc16.c").read_text()+"\n/* PRIVATE_ONLY */\n")
            with variants.prepare_task_variants([task], heldout_tests=Path(directory)) as (tasks, evidence):
                self.assertTrue(evidence["heldout_tests_used"])
                self.assertEqual(len(evidence["heldout_sha256"]), 64)
                self.assertEqual(tasks[0].prompt, task.prompt)
                self.assertNotIn("PRIVATE_ONLY", tasks[0].prompt)
                self.assertEqual((tasks[0].task_dir / "include/crc16.h").read_bytes(),
                                 (task.task_dir / "include/crc16.h").read_bytes())
                self.assertIn("PRIVATE_ONLY", (tasks[0].task_dir / "tests/test_crc16.c").read_text())

    def test_similarity_ignores_comments_and_spacing_but_preserves_literals(self):
        variants = self.module()
        self.assertTrue(variants.reference_similarity("int f(){return 1;}", "/* note */ int f ( ) { return 1; }"))
        self.assertFalse(variants.reference_similarity('char *s="one";', 'char *s="two";'))
        self.assertFalse(variants.reference_similarity("int f(){return 1;}", "int f(){return 2;}"))

    def test_every_public_task_text_asset_has_its_audit_canary(self):
        for task in DatasetLoader().list_tasks():
            canary = "AIBENCHMARK_ESW_CANARY_V1_" + task.id
            for path in task.task_dir.rglob("*"):
                if path.is_file() and path.suffix in (".c", ".h", ".md", ".json", ".txt"):
                    with self.subTest(task=task.id, asset=path.name):
                        self.assertIn(canary, path.read_text(encoding="utf-8"))

    def test_unknown_and_empty_heldout_overlays_are_rejected(self):
        variants = self.module()
        task = DatasetLoader().get_task("tier1_crc16")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError), variants.prepare_task_variants([task], heldout_tests=root):
                pass
            (root / "unknown").mkdir()
            with self.assertRaises(ValueError), variants.prepare_task_variants([task], heldout_tests=root):
                pass
