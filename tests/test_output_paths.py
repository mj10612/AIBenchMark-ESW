import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw import cli
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.output_paths import validate_output_paths


class TestOutputPaths(unittest.TestCase):
    def test_eval_cannot_replace_its_source_or_hard_link(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "candidate.c"
            source.write_text(DatasetLoader().get_reference_solution("tier1_crc16"), encoding="utf-8")
            alias = Path(directory) / "alias.json"
            os.link(source, alias)
            original = source.read_bytes()
            for output in (source, source.parent / "." / source.name, alias):
                args = cli.build_parser().parse_args(["eval", "--task", "tier1_crc16",
                    "--solution", str(source), "--output", str(output)])
                with self.subTest(output=output), patch.object(cli, "evaluate_task") as evaluate:
                    with self.assertRaisesRegex(ValueError, "overwrite an input"):
                        cli.cmd_eval(args)
                    evaluate.assert_not_called()
                    self.assertEqual(source.read_bytes(), original)
                    self.assertEqual(alias.read_bytes(), original)

    def test_benchmark_inputs_and_new_files_inside_roots_are_protected(self):
        loader = DatasetLoader()
        for root in cli._input_roots(loader):
            output = root / "must-not-be-created.json"
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, "benchmark inputs"):
                validate_output_paths([output], protected_roots=cli._input_roots(loader))
            self.assertFalse(output.exists())
        with TemporaryDirectory() as directory:
            root = Path(directory) / "tasks"
            root.mkdir()
            source = root / "reference.c"
            source.write_text("original", encoding="utf-8")
            alias = Path(directory) / "alias.c"
            os.link(source, alias)
            with self.assertRaisesRegex(ValueError, "overwrite an input"):
                validate_output_paths([alias], protected_roots=[root])
            self.assertEqual(source.read_text(), "original")

    def test_run_rejects_collisions_and_invalid_save_directory_before_generation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "file"
            existing.write_text("keep", encoding="utf-8")
            cases = [
                ["--save-solutions", directory, "--output", str(root / "tier1_crc16.c")],
                ["--save-solutions", str(existing)],
                ["--save-solutions", str(DatasetLoader().tasks_root)],
            ]
            for flags in cases:
                args = cli.build_parser().parse_args(["run", "--model", "mock",
                    "--tasks", "tier1_crc16", *flags])
                with self.subTest(flags=flags), patch.object(cli.LLMClient, "generate_solution") as generate:
                    with self.assertRaises((ValueError, OSError)), redirect_stdout(io.StringIO()):
                        cli.cmd_run(args)
                    generate.assert_not_called()
            self.assertEqual(existing.read_text(), "keep")
            self.assertFalse((root / "tier1_crc16.c").exists())

    def test_compare_cannot_overwrite_an_input_or_hard_link(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "one.json", root / "two.json"]
            data = json.loads(Path("results/baseline.json").read_text(encoding="utf-8"))
            for index, path in enumerate(paths):
                data["model_name"] = f"model-{index}"
                for task in data["tasks"]:
                    task["model_name"] = data["model_name"]
                path.write_text(json.dumps(data), encoding="utf-8")
            originals = [path.read_bytes() for path in paths]
            alias = root / "alias.md"
            os.link(paths[0], alias)
            for output in (*paths, alias):
                args = cli.build_parser().parse_args(["compare", "--results", *map(str, paths),
                                                     "--output", str(output)])
                with self.subTest(output=output), redirect_stderr(io.StringIO()) as errors:
                    self.assertEqual(cli.cmd_compare(args), 1)
                self.assertIn("overwrite an input", errors.getvalue())
                self.assertEqual([path.read_bytes() for path in paths], originals)

    def test_existing_output_reports_can_still_be_replaced(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            output.write_text("old output", encoding="utf-8")
            args = cli.build_parser().parse_args(["run", "--tasks", "tier1_crc16", "--output", str(output)])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_run(args), 0)
            self.assertEqual(json.loads(output.read_text())["overall_score"], 100)
