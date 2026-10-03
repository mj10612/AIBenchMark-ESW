import os
import re
import shutil
import tempfile
import subprocess
import uuid
import json
import locale
from pathlib import Path
from typing import Optional, Tuple

from aibenchmark_esw.models import TaskConfig, CompilationResult, TestResult
from aibenchmark_esw.resources import data_root
from aibenchmark_esw.sandbox.c_source import mask_noncode


def _timeout_output(error: subprocess.TimeoutExpired) -> str:
    """TimeoutExpired can contain bytes even when subprocess uses text mode."""
    streams = []
    for stream in (error.stdout, error.stderr):
        if isinstance(stream, bytes):
            stream = stream.decode(locale.getpreferredencoding(False), errors="backslashreplace")
        if stream:
            streams.append(stream)
    partial = "".join(streams)
    if not partial:
        return str(error)
    return partial + ("" if partial.endswith("\n") else "\n") + str(error)


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

    def _compile(self, task: TaskConfig, sources, output: Path, object_only=False,
                  extra_includes=()) -> CompilationResult:
        output = output.resolve()
        compiler_name = Path(self.compiler_path).stem.lower()
        includes = [task.task_dir.resolve() / "include", self.unity_dir.resolve()]
        includes += [Path(directory).resolve() for directory in extra_includes]
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
        except subprocess.TimeoutExpired as error:
            return CompilationResult(False, _timeout_output(error), error_message="Compilation timed out",
                                     effective_standard=standard)
        except OSError as error:
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
            completion_token = uuid.uuid4().hex
            wrapped_tests = []
            runners = 0
            for index, test in enumerate(tests):
                source = test.read_text(encoding="utf-8")
                main = re.search(r"\bmain\s*\(([^)]*)\)\s*\{", mask_noncode(source))
                if main is None:
                    wrapped_tests.append(test)
                    continue
                runners += 1
                parameters = main.group(1).strip()
                if parameters in ("", "void"):
                    arguments = ""
                elif parameters.count(",") == 1:
                    arguments = "argc, argv"
                else:
                    message = "Test runner main must take void or argc/argv parameters"
                    return CompilationResult(False, message), TestResult(output=message)
                wrapped = work_dir / f"aibenchmark_tests_{completion_token}_{index}.c"
                wrapped.write_text(
                    '#include <stdio.h>\n#define main aibenchmark_suite_main\n'
                    + f"#line 1 {json.dumps(test.resolve().as_posix())}\n" + source
                    + '\n#undef main\n#line 1 "aibenchmark_harness.c"\n'
                    + "int main(int argc, char **argv) {\n"
                    + f"    int result = aibenchmark_suite_main({arguments});\n"
                    + f'    printf("AIBenchMark-ESW:{completion_token}:END\\n");\n'
                    + "    return result;\n}\n", encoding="utf-8",
                )
                wrapped_tests.append(wrapped)
            if runners != 1:
                message = "Exactly one test runner main is required"
                return CompilationResult(False, message), TestResult(output=message)
            suffix = ".exe" if os.name == "nt" else ""
            binary_path = work_dir / f"test_{task.id}{suffix}"
            comp_result = self._compile(task, wrapped_tests + [sol_file, self.unity_dir / "unity.c"], binary_path,
                                        extra_includes=[test.parent for test in tests])
            if not comp_result.success:
                return comp_result, TestResult(output="Compilation failed", completed=False)

            comp_result._workspace = workspace
            retained = True
            try:
                proc = subprocess.run([str(binary_path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, errors="backslashreplace",
                                      timeout=task.limits.timeout_seconds, cwd=str(work_dir))
                test_result = self._parse_unity_output(proc.stdout, proc.returncode, completion_token)
            except subprocess.TimeoutExpired as error:
                # Partial records are diagnostics only; a timeout never completes
                # a suite, even if its buffered output resembles a valid summary.
                test_result = TestResult(output=_timeout_output(error), completed=False)
            except OSError as error:
                test_result = TestResult(output=str(error), completed=False)
            return comp_result, test_result
        finally:
            if workspace is not None and not retained:
                workspace.cleanup()

    def _parse_unity_output(self, output: str, returncode: int,
                            completion_token: Optional[str] = None) -> TestResult:
        summaries = list(re.finditer(
            r"(?m)^\s*(\d+)\s+Tests\s+(\d+)\s+Failures\s+(\d+)\s+Ignored\s*$", output))
        statuses = re.findall(r"(?m)^.*:\d+:[^:\r\n]+:(PASS|FAIL|IGNORE)\s*$", output)
        observed = tuple(statuses.count(status) for status in ("PASS", "FAIL", "IGNORE"))
        match = summaries[0] if len(summaries) == 1 else None
        if match is not None:
            total, failures, ignored = map(int, match.groups())
            passed = total - failures - ignored
        else:
            passed, failures, ignored = observed
            total = passed + failures + ignored

        marker = f"AIBenchMark-ESW:{completion_token}:END" if completion_token else None
        markers = list(re.finditer(rf"(?m)^{re.escape(marker)}\s*$", output)) if marker else []
        # A summary alone is candidate-controlled output. Require the harness
        # completion marker, consistent per-test records, and Unity's exit code.
        completed = (match is not None and total > 0 and passed >= 0
                     and observed == (passed, failures, ignored) and returncode == failures
                     and len(markers) == 1 and markers[0].start() > match.end())
        all_passed = completed and failures == 0 and ignored == 0
        return TestResult(total_tests=total, passed_tests=max(0, passed), failed_tests=failures,
                          ignored_tests=ignored, output=output, passed=all_passed,
                          completed=completed, returncode=returncode)
