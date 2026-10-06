import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
import venv
import tarfile
import json
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory


class TestSourcePackaging(unittest.TestCase):
    def test_declared_license_and_single_version_source(self):
        root = Path(__file__).resolve().parent.parent
        project = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('license = "Apache-2.0"', project)
        self.assertIn('license-files = ["LICENSE", "NOTICE"]', project)
        self.assertIn('version = {attr = "aibenchmark_esw.__version__"}', project)
        self.assertNotIn('rich>=', project)


@unittest.skipUnless(importlib.util.find_spec("build"), "Distribution groups require build/setuptools/wheel; source metadata remains checked")
class TestPackaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.temporary = TemporaryDirectory(prefix="aibenchmark_package_test_")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.source = cls.work / "project"
        cls.source.mkdir()
        for name in ["pyproject.toml", "setup.py", "MANIFEST.in", "README.md", "LICENSE", "NOTICE"]:
            shutil.copy2(cls.root / name, cls.source / name)
        for name in ["aibenchmark_esw", "tasks", "third_party"]:
            shutil.copytree(cls.root / name, cls.source / name, ignore=shutil.ignore_patterns("__pycache__"))
        artifacts = cls.source / "tasks/tier1_crc16/tests/build"
        for filename in ("CMakeCache.txt", "test_runner.exe", "test_crc16.c.obj", "CMakeFiles/CompilerIdC/CMakeCCompilerId.c"):
            artifact = artifacts / filename
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("generated local build product", encoding="utf-8")
        cls.build = subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=cls.source,
                                   capture_output=True, text=True, timeout=60)
        if cls.build.returncode:
            raise RuntimeError("sdist/wheel build stage: " + cls.build.stdout + cls.build.stderr)
        cls.sdist = next((cls.source / "dist").glob("*.tar.gz"))
        cls.wheel = next((cls.source / "dist").glob("*.whl"))
        cls.installed_wheel = cls.work / cls.wheel.name
        shutil.copy2(cls.wheel, cls.installed_wheel)
        with zipfile.ZipFile(cls.wheel) as archive:
            cls.names = archive.namelist()
        cls.expected_ids = {json.loads(path.read_text(encoding="utf-8"))["id"]
                            for path in (cls.root / "tasks").glob("*/task.json")}
        cls.install_error = None
        try:
            environment = cls.work / "environment"
            venv.EnvBuilder(with_pip=True).create(environment)
            scripts = environment / ("Scripts" if os.name == "nt" else "bin")
            python = scripts / ("python.exe" if os.name == "nt" else "python")
            cls.install = subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(cls.installed_wheel)],
                cwd=cls.work, capture_output=True, text=True, timeout=30)
            cls.command = scripts / ("aibenchmark-esw.exe" if os.name == "nt" else "aibenchmark-esw")
        except (OSError, subprocess.SubprocessError) as error:
            cls.install_error = str(error)

    def run_installed(self, *arguments):
        self.assertIsNone(self.install_error, "venv/install stage: " + str(self.install_error))
        self.assertEqual(self.install.returncode, 0, "wheel install stage: " + self.install.stdout + self.install.stderr)
        return subprocess.run([str(self.command), *map(str, arguments)], cwd=self.work, capture_output=True, text=True, timeout=30)

    def test_sdist_excludes_build_artifacts_and_includes_schema(self):
        with tarfile.open(self.sdist) as archive:
            names = archive.getnames()
            self.assertFalse(any("/tests/build/" in name for name in names), "sdist artifact filtering")
            self.assertTrue(any(name.endswith("schemas/report-v2.schema.json") for name in names), "sdist schema")

    def test_wheel_contains_dataset_unity_subpackages_and_schema(self):
        with zipfile.ZipFile(self.installed_wheel) as archive:
            self.assertEqual({json.loads(archive.read(name))["id"] for name in self.names if name.endswith("task.json")}, self.expected_ids, "wheel task IDs")
        self.assertIn("aibenchmark_esw/_data/third_party/unity/unity.c", self.names)
        self.assertFalse(any("/tests/build/" in name for name in self.names), "wheel artifact filtering")
        self.assertTrue(any(name.endswith("tier1_crc16/tests/CMakeLists.txt") for name in self.names))
        for name in ("llm/__init__.py", "metrics/__init__.py", "sandbox/__init__.py", "schemas/report-v2.schema.json", "py.typed"):
            self.assertIn("aibenchmark_esw/" + name, self.names, "wheel package asset: " + name)

    def test_wheel_license_metadata(self):
        with zipfile.ZipFile(self.installed_wheel) as archive:
            metadata_name = next(name for name in self.names if name.endswith(".dist-info/METADATA"))
            metadata = BytesParser().parsebytes(archive.read(metadata_name))
            self.assertEqual(metadata["License-Expression"], "Apache-2.0")
            self.assertEqual(set(metadata.get_all("License-File")), {"LICENSE", "NOTICE"})
            from aibenchmark_esw import __version__
            self.assertEqual(metadata["Version"], __version__, "distribution/runtime version")
            for name in ("LICENSE", "NOTICE"):
                self.assertTrue(any(item.endswith(f".dist-info/licenses/{name}") for item in self.names))

    def test_wheel_rebuild_removes_stale_data(self):
        stale = self.source / "build/lib/aibenchmark_esw/_data/tasks/old_task/tests/build/stale.c"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("obsolete build product", encoding="utf-8")
        direct = subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation"], cwd=self.source, capture_output=True, text=True, timeout=60)
        self.assertEqual(direct.returncode, 0, "direct wheel rebuild stage: " + direct.stdout + direct.stderr)
        with zipfile.ZipFile(self.wheel) as archive:
            self.assertEqual(set(archive.namelist()), set(self.names), "deterministic wheel contents")

    def test_installed_console_script_validates_dataset(self):
        result = self.run_installed("validate")
        self.assertEqual(result.returncode, 0, "installed validate stage: " + result.stdout + result.stderr)
        self.assertIn(f"{len(self.expected_ids)} passed, 0 failed", result.stdout)

    def test_installed_baseline_run(self):
        path = self.work / "baseline.json"
        result = self.run_installed("run", "--model", "baseline", "--output", path)
        self.assertEqual(result.returncode, 0, "installed baseline stage: " + result.stdout + result.stderr)
        self.assertIn("Pass@1: 100.0%", result.stdout)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({task["task_id"] for task in data["tasks"]}, self.expected_ids)
        for task in data["tasks"]:
            self.assertTrue(task["size_metrics"]["measured"])
            self.assertGreater(task["size_metrics"]["flash_bytes"], 0)

    def test_external_dataset_from_installed_wheel(self):
        root = self.work / "external_tasks"
        task = root / "custom_crc"
        shutil.copytree(self.root / "tasks/tier1_crc16", task)
        config_path = task / "task.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["id"] = "custom_crc"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        path = self.work / "external.json"
        result = self.run_installed("run", "--tasks-root", root, "--tasks", "custom_crc", "--output", path)
        self.assertEqual(result.returncode, 0, "installed external dataset stage: " + result.stdout + result.stderr)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["metadata"]["selected_tasks"], ["custom_crc"])
        self.assertEqual(data["overall_score"], 100)


if __name__ == "__main__":
    unittest.main()
