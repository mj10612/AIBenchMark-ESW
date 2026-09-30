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


@unittest.skipUnless(importlib.util.find_spec("build"), "Install build/setuptools/wheel for packaging validation")
class TestPackaging(unittest.TestCase):
    def test_wheel_from_sdist_contains_usable_dataset_and_harness(self):
        root = Path(__file__).resolve().parent.parent
        with TemporaryDirectory(prefix="aibenchmark_package_test_") as directory:
            work = Path(directory)
            source = work / "project"
            source.mkdir()
            for name in ["pyproject.toml", "setup.py", "MANIFEST.in", "README.md", "LICENSE", "NOTICE"]:
                shutil.copy2(root / name, source / name)
            for name in ["aibenchmark_esw", "tasks", "third_party"]:
                shutil.copytree(root / name, source / name, ignore=shutil.ignore_patterns("__pycache__"))
            artifacts = source / "tasks/tier1_crc16/tests/build"
            for filename in ("CMakeCache.txt", "test_runner.exe", "test_crc16.c.obj", "CMakeFiles/CompilerIdC/CMakeCCompilerId.c"):
                artifact = artifacts / filename
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("generated local build product", encoding="utf-8")
            build = subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=source,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            sdist = next((source / "dist").glob("*.tar.gz"))
            with tarfile.open(sdist) as archive:
                self.assertFalse(any("/tests/build/" in name for name in archive.getnames()))
            wheel = next((source / "dist").glob("*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                self.assertEqual(len([name for name in names if name.endswith("task.json")]), 5)
                self.assertIn("aibenchmark_esw/_data/third_party/unity/unity.c", names)
                self.assertFalse(any("/tests/build/" in name for name in names))
                self.assertTrue(any(name.endswith("tier1_crc16/tests/CMakeLists.txt") for name in names))
                metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
                metadata = BytesParser().parsebytes(archive.read(metadata_name))
                self.assertEqual(metadata["License-Expression"], "Apache-2.0")
                self.assertEqual(set(metadata.get_all("License-File")), {"LICENSE", "NOTICE"})
                for name in ("LICENSE", "NOTICE"):
                    self.assertTrue(any(item.endswith(f".dist-info/licenses/{name}") for item in names))
            installed_wheel_dir = work / "sdist_wheel"
            installed_wheel_dir.mkdir()
            installed_wheel = installed_wheel_dir / wheel.name
            shutil.copy2(wheel, installed_wheel)
            stale = source / "build/lib/aibenchmark_esw/_data/tasks/old_task/tests/build/stale.c"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("obsolete build product", encoding="utf-8")
            direct = subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation"], cwd=source,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(direct.returncode, 0, direct.stdout + direct.stderr)
            with zipfile.ZipFile(wheel) as archive:
                self.assertEqual(set(archive.namelist()), set(names))
            environment = work / "environment"
            venv.EnvBuilder(with_pip=True).create(environment)
            scripts = environment / ("Scripts" if os.name == "nt" else "bin")
            python = scripts / ("python.exe" if os.name == "nt" else "python")
            install = subprocess.run([str(python), "-m", "pip", "install", "--no-index",
                                      "--no-deps", str(installed_wheel)], cwd=work,
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            command = scripts / ("aibenchmark-esw.exe" if os.name == "nt" else "aibenchmark-esw")
            results = work / "baseline.json"
            smoke = subprocess.run([str(command), "run", "--model", "baseline", "--output", str(results)], cwd=work,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
            self.assertIn("Pass@1: 100.0%", smoke.stdout)
            data = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(len(data["tasks"]), 5)
            for task in data["tasks"]:
                self.assertTrue(task["size_metrics"]["measured"])
                self.assertGreater(task["size_metrics"]["flash_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
