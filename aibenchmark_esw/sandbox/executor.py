import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from aibenchmark_esw.models import TaskConfig, CompilationResult, TestResult
from aibenchmark_esw.resources import data_root


class ExecutionSandbox:
    def __init__(self, compiler_path: Optional[str] = None, allow_standard_fallback: bool = False):
        self.compiler_path = compiler_path or self._find_c_compiler()
        self.unity_dir = data_root() / "third_party" / "unity"
        self.allow_standard_fallback = allow_standard_fallback

    def _find_c_compiler(self) -> str:
        for cmd in ["gcc", "clang", "tcc", "cl"]:
            path = shutil.which(cmd)
            if path:
                return path
        user_profile = os.environ.get("USERPROFILE", "")
        if user_profile:
            for relative in ["tcc/current/tcc/tcc.exe", "gcc/current/bin/gcc.exe"]:
                path = Path(user_profile) / "scoop" / "apps" / relative
                if path.is_file():
                    return str(path)
        return "gcc"

    def _compile(self, task: TaskConfig, sources, output: Path, object_only=False) -> CompilationResult:
        output = output.resolve()
        compiler_name = Path(self.compiler_path).stem.lower()
        includes = [task.task_dir.resolve() / "include", self.unity_dir.resolve()]
        sources = [str(Path(source).resolve()) for source in sources]
        standard = task.target_standard
        if compiler_name == "cl":
            if standard == "c99":
                if not self.allow_standard_fallback:
                    message = ("MSVC does not support strict C99. Use GCC/Clang/TCC or "
                               "--allow-standard-fallback to explicitly evaluate as C11.")
                    return CompilationResult(False, message, error_message="Unsupported C standard")
                standard = "c11"
            cmd = [self.compiler_path, "/nologo", "/TC", f"/std:{standard}", "/O1"]
            cmd += [f"/I{directory}" for directory in includes]
            if object_only:
                cmd += ["/c", f"/Fo{output}"]
            else:
                cmd += [f"/Fe{output}", f"/Fo{output.parent}{os.sep}"]
            cmd += sources
        else:
            cmd = [self.compiler_path, f"-std={task.target_standard}"]
            if compiler_name != "tcc":
                cmd.append("-Os")
            for directory in includes:
                cmd += ["-I", str(directory)]
            if object_only:
                cmd.append("-c")
            cmd += sources + ["-o", str(output)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, errors="backslashreplace", timeout=30,
                                  cwd=str(output.parent))
            log = proc.stdout + proc.stderr
            if proc.returncode != 0 or not output.is_file():
                return CompilationResult(False, log, error_message="Compilation failed",
                                         effective_standard=standard)
            return CompilationResult(True, log, binary_path=output, effective_standard=standard)
        except (OSError, subprocess.TimeoutExpired) as error:
            return CompilationResult(False, str(error), error_message="Compiler unavailable or timed out",
                                     effective_standard=standard)

    def compile_object(self, task: TaskConfig, solution_code: str,
                       workspace: Path, name: str = "candidate") -> CompilationResult:
        """Compile only the implementation, excluding the test harness and runtime."""
        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        source = workspace / f"{name}.c"
        source.write_text(solution_code, encoding="utf-8")
        return self._compile(task, [source], workspace / f"{name}.o", object_only=True)

    def compile_and_test(self, task: TaskConfig, solution_code: str,
                         custom_workspace: Optional[Path] = None) -> Tuple[CompilationResult, TestResult]:
        """The result owns automatic artifacts until cleanup() or garbage collection."""
        workspace = None
        retained = False
        if custom_workspace is None:
            workspace = tempfile.TemporaryDirectory(prefix=f"aibenchmark_esw_{task.id}_")
            work_dir = Path(workspace.name)
        else:
            work_dir = Path(custom_workspace).resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
        try:
            tests = sorted((task.task_dir / "tests").glob("test_*.c"))
            if not tests:
                message = f"No test_*.c found in {task.task_dir / 'tests'}"
                return CompilationResult(False, message), TestResult(output=message, completed=False)
            sol_file = work_dir / Path(task.entry_file).name
            sol_file.write_text(solution_code, encoding="utf-8")
            suffix = ".exe" if os.name == "nt" else ""
            binary_path = work_dir / f"test_{task.id}{suffix}"
            comp_result = self._compile(task, tests + [sol_file, self.unity_dir / "unity.c"], binary_path)
            if not comp_result.success:
                return comp_result, TestResult(output="Compilation failed", completed=False)

            comp_result._workspace = workspace
            retained = True
            try:
                proc = subprocess.run([str(binary_path)], capture_output=True, text=True, errors="backslashreplace",
                                      timeout=task.limits.timeout_seconds, cwd=str(work_dir))
                test_result = self._parse_unity_output(proc.stdout + "\n" + proc.stderr, proc.returncode)
            except (OSError, subprocess.TimeoutExpired) as error:
                test_result = TestResult(output=str(error), completed=False)
            return comp_result, test_result
        finally:
            if workspace is not None and not retained:
                workspace.cleanup()

    def _parse_unity_output(self, output: str, returncode: int) -> TestResult:
        match = re.search(r"(?m)^\s*(\d+)\s+Tests\s+(\d+)\s+Failures\s+(\d+)\s+Ignored\s*$", output)
        if match:
            total, failures, ignored = map(int, match.groups())
            passed = total - failures - ignored
        else:
            statuses = re.findall(r"(?m)^.*:\d+:[^:\r\n]+:(PASS|FAIL|IGNORE)\s*$", output)
            passed, failures, ignored = (statuses.count(status) for status in ("PASS", "FAIL", "IGNORE"))
            total = passed + failures + ignored

        # Unity returns its failure count; other statuses mean abnormal termination.
        completed = bool(match) and total > 0 and passed >= 0 and returncode == failures
        all_passed = completed and failures == 0 and ignored == 0
        return TestResult(total_tests=total, passed_tests=max(0, passed), failed_tests=failures,
                          ignored_tests=ignored, output=output, passed=all_passed,
                          completed=completed, returncode=returncode)
