"""Bundle the task dataset and C harness without duplicating checkout files."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist


def include_benchmark_file(path):
    path = Path(path)
    if not path.parts or path.parts[0] not in ("tasks", "third_party"):
        return True
    if any(part.lower() in ("build", "dist", "cmakefiles", "__pycache__")
           or part.startswith(".") for part in path.parts[1:-1]):
        return False
    if path.name.startswith("_temp_"):
        return False
    extensions = (".json", ".md", ".h", ".c") if path.parts[0] == "tasks" else (".h", ".c")
    return path.name == "CMakeLists.txt" or path.suffix.lower() in extensions


class BuildWithBenchmarkData(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        destination = Path(self.build_lib) / "aibenchmark_esw" / "_data"
        if destination.exists():
            if destination.is_symlink() or not destination.resolve().is_relative_to(Path(self.build_lib).resolve()):
                raise ValueError("Benchmark data output must stay within build_lib")
            shutil.rmtree(destination)
        for name in ("tasks", "third_party"):
            for source in (root / name).rglob("*"):
                relative = source.relative_to(root)
                if source.is_file() and include_benchmark_file(relative):
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)


class SdistWithBenchmarkData(sdist):
    def make_distribution(self):
        self.filelist.files[:] = [path for path in self.filelist.files if include_benchmark_file(path)]
        # Keep cached source metadata consistent with the filtered archive.
        sources = Path(self.get_finalized_command("egg_info").egg_info) / "SOURCES.txt"
        sources.write_text("\n".join(sorted(self.filelist.files)) + "\n", encoding="utf-8")
        super().make_distribution()


setup(cmdclass={"build_py": BuildWithBenchmarkData, "sdist": SdistWithBenchmarkData})
