"""Bundle the task dataset and C harness without duplicating checkout files."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithBenchmarkData(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        destination = Path(self.build_lib) / "aibenchmark_esw" / "_data"
        for name in ("tasks", "third_party"):
            shutil.copytree(root / name, destination / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "_temp_*.c"))


setup(cmdclass={"build_py": BuildWithBenchmarkData})
