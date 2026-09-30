import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
import venv
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
            build = subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=source,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            wheel = next((source / "dist").glob("*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                self.assertEqual(len([name for name in names if name.endswith("task.json")]), 5)
                self.assertIn("aibenchmark_esw/_data/third_party/unity/unity.c", names)
                metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
                metadata = BytesParser().parsebytes(archive.read(metadata_name))
                self.assertEqual(metadata["License-Expression"], "Apache-2.0")
                self.assertEqual(set(metadata.get_all("License-File")), {"LICENSE", "NOTICE"})
                for name in ("LICENSE", "NOTICE"):
                    self.assertTrue(any(item.endswith(f".dist-info/licenses/{name}") for item in names))
            environment = work / "environment"
            venv.EnvBuilder(with_pip=True).create(environment)
            scripts = environment / ("Scripts" if os.name == "nt" else "bin")
            python = scripts / ("python.exe" if os.name == "nt" else "python")
            install = subprocess.run([str(python), "-m", "pip", "install", "--no-index",
                                      "--no-deps", str(wheel)], cwd=work,
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            command = scripts / ("aibenchmark-esw.exe" if os.name == "nt" else "aibenchmark-esw")
            smoke = subprocess.run([str(command), "run", "--model", "baseline"], cwd=work,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
            self.assertIn("Pass@1: 100.0%", smoke.stdout)
            self.assertNotIn("0/0B", smoke.stdout)


if __name__ == "__main__":
    unittest.main()
