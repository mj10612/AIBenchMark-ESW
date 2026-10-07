import os
import re
import shutil
import tempfile
import subprocess
import uuid
import json
import locale
import math
from pathlib import Path
from typing import Optional, Tuple

from aibenchmark_esw.models import TaskConfig, CompilationResult, TestResult
from aibenchmark_esw.resources import data_root
from aibenchmark_esw.sandbox.c_source import mask_noncode
from aibenchmark_esw.sandbox.process_runner import run_bounded, OutputLimitExceeded, ExecutionCancelled


def _timeout_output(error: subprocess.TimeoutExpired) -> str:
    """TimeoutExpired can contain bytes even when subprocess uses text mode."""
    streams = []
    for stream in (error.stdout, error.stderr):
        decoded: Optional[str]
        if isinstance(stream, bytes):
            decoded = stream.decode(locale.getpreferredencoding(False), errors="backslashreplace")
        else:
            decoded = stream
        if decoded:
            streams.append(decoded)
    partial = "".join(streams)
    if not partial:
        return str(error)
    return partial + ("" if partial.endswith("\n") else "\n") + str(error)


class ExecutionSandbox:
    def __init__(self, compiler_path: Optional[str] = None, allow_standard_fallback: bool = False,
                 compile_timeout_seconds: float = 30, max_output_bytes: int = 1048576,
                 isolation: str = "native", memory_limit_bytes: Optional[int] = None,
                 sanitizers=(), target=None, cross_compiler=None, warnings=False,
                 container_engine=None, container_image="gcc:14", container_runtime=None):
        self.compiler_path = compiler_path or os.environ.get("AIBENCHMARK_ESW_COMPILER") or (
            "gcc" if isolation == "container" else self._find_c_compiler())
        if Path(self.compiler_path).is_file():
            self.compiler_path = str(Path(self.compiler_path).resolve())
        self.unity_dir = data_root() / "third_party" / "unity"
        self.allow_standard_fallback = allow_standard_fallback
        if (isinstance(compile_timeout_seconds, bool) or not isinstance(compile_timeout_seconds, (float, int))
                or not math.isfinite(compile_timeout_seconds) or compile_timeout_seconds <= 0):
            raise ValueError("compile_timeout_seconds must be a finite positive number")
        if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int) or max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be a positive integer")
        if isolation not in ("native", "process", "container", "bwrap"):
            raise ValueError("isolation must be native, process, container or bwrap")
        if memory_limit_bytes is not None:
            if isinstance(memory_limit_bytes, bool) or not isinstance(memory_limit_bytes, int) or memory_limit_bytes <= 0:
                raise ValueError("memory_limit_bytes must be a positive integer")
            if isolation == "native":
                raise ValueError("memory_limit_bytes requires process or external isolation")
        if isinstance(sanitizers, str):
            sanitizers = sanitizers.split(",") if sanitizers else ()
        self.sanitizers = tuple(sorted(set(sanitizers)))
        if set(self.sanitizers) - {"address", "undefined"}:
            raise ValueError("sanitizers must contain only address and/or undefined")
        self.compile_timeout_seconds = compile_timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.isolation = isolation
        self.memory_limit_bytes = memory_limit_bytes
        self.cancel_event = None
        self.warnings = bool(warnings)
        self.containment = None
        if isolation in ("container", "bwrap"):
            from aibenchmark_esw.sandbox.containment import ContainmentBackend
            self.containment = ContainmentBackend(isolation, container_engine, container_image, container_runtime)
        self.cross = None
        if target is not None:
            from aibenchmark_esw.sandbox.cross_compiler import CrossCompiler
            self.cross = CrossCompiler(target, cross_compiler, compile_timeout_seconds,
                                       max_output_bytes, isolation, memory_limit_bytes,
                                       self._run_contained if self.containment else None)

    def warning_flags(self):
        if not self.warnings:
            return []
        name = Path(self.compiler_path).stem.lower()
        return ["/W4"] if name in ("cl", "clang-cl") else ["-Wall", "-Wextra", "-Wconversion", "-Wshadow"] if name != "tcc" else ["-Wall"]

    def _run_contained(self, command, **options):
        assert self.containment is not None
        return self.containment.run(command, **options)

    def compiler_identity(self):
        """Return identity for the compiler actually executed, including images."""
        command = [self.compiler_path, "/?" if Path(self.compiler_path).stem.lower() == "cl" else
                   "-v" if Path(self.compiler_path).stem.lower() == "tcc" else "--version"]
        try:
            with tempfile.TemporaryDirectory(prefix="aibenchmark_compiler_probe_") as directory:
                runner = self._run_contained if self.containment else run_bounded
                result = runner(command, cwd=directory, timeout=10, max_output_bytes=65536)
                output = result.stdout.decode(locale.getpreferredencoding(False), errors="backslashreplace")
                lines = output.strip().splitlines()
                version = lines[0] if result.returncode == 0 and lines else None
        except (OSError, ValueError, subprocess.SubprocessError):
            version = None
        return {"name": Path(self.compiler_path).stem.lower(), "version": version,
                "path": self.compiler_path, "allow_standard_fallback": self.allow_standard_fallback,
                "target": self.cross.settings() if self.cross else None}

    def execution_settings(self):
        return {"compile_timeout_seconds": self.compile_timeout_seconds,
                "max_output_bytes": self.max_output_bytes, "isolation": self.isolation,
                "memory_limit_bytes": self.memory_limit_bytes, "sanitizers": list(self.sanitizers),
                "compiler_warnings": self.warnings, "warning_flags": self.warning_flags(),
                "containment": self.containment.settings() if self.containment else None,
                "process_backend": "windows-job" if os.name == "nt" else "posix-session",
                "cpu_limit": "task-timeout" if self.isolation == "process" else None,
                "footprint": self.cross.settings() if self.cross else {"target": "host", "measurement": "host-object"}}

    def _find_c_compiler(self) -> str:
        for cmd in ["gcc", "clang", "tcc", "cl"]:
            path = shutil.which(cmd)
            if path:
                return path
        user_profile = os.environ.get("USERPROFILE", "")
        if user_profile:
            for relative in ["tcc/current/tcc/tcc.exe", "gcc/current/bin/gcc.exe"]:
                bundled_path = Path(user_profile) / "scoop" / "apps" / relative
                if bundled_path.is_file():
                    return str(bundled_path)
        return "gcc"

    def _compile(self, task: TaskConfig, sources, output: Path, object_only=False,
                  extra_includes=()) -> CompilationResult:
        output = output.resolve()
        compiler_name = Path(self.compiler_path).stem.lower()
        includes = [task.task_dir.resolve() / "include", self.unity_dir.resolve()]
        includes += [Path(directory).resolve() for directory in extra_includes]
        includes = [directory for directory in includes if directory.is_dir()]
        sources = [str(Path(source).resolve()) for source in sources]
        standard = task.target_standard
        if self.sanitizers and not object_only and (compiler_name in ("tcc", "cl", "clang-cl")):
            message = "Sanitizers require a GCC/Clang driver with the requested sanitizer runtime installed"
            return CompilationResult(False, message, error_message="Unsupported sanitizer toolchain")
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
            if self.sanitizers and not object_only:
                cmd += ["-fsanitize=" + ",".join(self.sanitizers), "-fno-sanitize-recover=all",
                        "-fno-omit-frame-pointer", "-g"]
        try:
            cmd += self.warning_flags()
            runner = self._run_contained if self.containment else run_bounded
            proc = runner(cmd, timeout=self.compile_timeout_seconds, max_output_bytes=self.max_output_bytes,
                          cwd=str(output.parent), isolation=self.isolation,
                          memory_limit_bytes=self.memory_limit_bytes, cancel_event=self.cancel_event)
            log = proc.stdout.decode(locale.getpreferredencoding(False), errors="backslashreplace")
            findings = self._warning_findings(log, sources)
            if proc.returncode != 0 or not output.is_file():
                return CompilationResult(False, log, error_message="Compilation failed",
                                         effective_standard=standard, findings=findings, warning_flags=self.warning_flags())
            return CompilationResult(True, log, binary_path=output, effective_standard=standard,
                                     findings=findings, warning_flags=self.warning_flags())
        except subprocess.TimeoutExpired as error:
            return CompilationResult(False, _timeout_output(error), error_message="Compilation timed out",
                                     effective_standard=standard)
        except (OutputLimitExceeded, ExecutionCancelled) as error:
            log = error.output.decode(locale.getpreferredencoding(False), errors="backslashreplace")
            return CompilationResult(False, log + "\n" + str(error), error_message=str(error),
                                     effective_standard=standard)
        except (OSError, ValueError) as error:
            return CompilationResult(False, str(error), error_message="Compiler unavailable or timed out",
                                     effective_standard=standard)

    def _warning_findings(self, log, sources):
        if not self.warnings:
            return []
        owned = {Path(source).name for source in sources
                 if not Path(source).name.startswith("aibenchmark_tests_") and Path(source).name != "unity.c"}
        findings = []
        for diagnostic in log.splitlines():
            match = re.match(r"^(.*?):(\d+)(?::\d+)?:\s*warning:\s*(.*)", diagnostic)
            msvc = re.match(r"^(.*?)\((\d+)(?:,\d+)?\):\s*warning\s+(C\d+):\s*(.*)", diagnostic)
            if match:
                file, line, message = match.groups()
                flag = re.search(r"\[(-W[^\]]+)\]\s*$", message)
                rule = flag.group(1) if flag else "warning"
            elif msvc:
                file, line, rule, message = msvc.groups()
            else:
                continue
            file = Path(file).name
            if file not in owned:
                continue
            findings.append({"rule_id": "compiler." + rule, "engine": "compiler", "severity": "warning",
                             "message": message, "file": file, "line": int(line)})
        return findings

    def compile_object(self, task: TaskConfig, solution_code: str,
                       workspace: Path, name: str = "candidate") -> CompilationResult:
        """Compile only the implementation, excluding the test harness and runtime."""
        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        source = workspace / f"{name}.c"
        source.write_text(solution_code, encoding="utf-8")
        if self.cross:
            self.cross.cancel_event = self.cancel_event
            return self.cross.compile(task, source, workspace / f"{name}.o")
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
            if re.search(r"\bmain\s*\([^;{}]*\)\s*\{", mask_noncode(solution_code)):
                message = "Candidate source defines a main() function, conflicting with the separate test harness runner. Return only the implementation."
                return CompilationResult(False, message, error_message=message), TestResult(output=message, completed=False)
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
                wrapped = work_dir / f"aibenchmark_tests_{index}.c"
                wrapped.write_text(
                    '#include <stdio.h>\n#define main aibenchmark_suite_main\n'
                    + f"#line 1 {json.dumps(test.resolve().as_posix())}\n" + source
                    + '\n#undef main\n#line 1 "aibenchmark_harness.c"\n'
                    + "int main(int argc, char **argv) {\n"
                    + '    FILE *aibenchmark_channel = argc > 1 ? fopen(argv[1], "wb") : NULL;\n'
                    + '    if (!aibenchmark_channel) return 125;\n'
                    + f"    int result = aibenchmark_suite_main({arguments});\n"
                    + f'    fputs("AIBenchMark-ESW:{completion_token}:END\\n", aibenchmark_channel);\n'
                    + '    if (fclose(aibenchmark_channel) != 0) return 125;\n'
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
                environment = None
                if self.sanitizers:
                    environment = os.environ.copy()
                    # Explicitly prevent recovery or redirected diagnostics from
                    # inherited host sanitizer configuration.
                    environment["ASAN_OPTIONS"] = "halt_on_error=1:abort_on_error=1:detect_leaks=0"
                    environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
                scratch = work_dir / "scratch"
                scratch.mkdir(exist_ok=True)
                receipt = work_dir / "harness.receipt"
                runner = self._run_contained if self.containment else run_bounded
                proc = runner([str(binary_path), str(receipt)], timeout=task.limits.timeout_seconds,
                                   max_output_bytes=self.max_output_bytes, cwd=str(scratch), env=environment,
                                   isolation=self.isolation, memory_limit_bytes=self.memory_limit_bytes,
                                   cancel_event=self.cancel_event)
                output = proc.stdout.decode(locale.getpreferredencoding(False), errors="backslashreplace")
                # Receipt is produced only after the trusted suite returns.
                # Native code still shares the address space and filesystem;
                # this separate channel prevents the cwd/stdout exploit, not
                # arbitrary hostile native code from forging the verdict.
                expected = f"AIBenchMark-ESW:{completion_token}:END\n".encode()
                completed_channel = False
                if receipt.is_file():
                    with receipt.open("rb") as channel:
                        completed_channel = channel.read(len(expected) + 1) == expected
                if completed_channel:
                    output += "\n" + expected.decode()
                test_result = self._parse_unity_output(output, proc.returncode,
                                                       completion_token if completed_channel else None)
                if self.sanitizers and re.search(r"AddressSanitizer|UndefinedBehaviorSanitizer|runtime error:", output):
                    test_result.completed = test_result.passed = False
            except subprocess.TimeoutExpired as error:
                # Partial records are diagnostics only; a timeout never completes
                # a suite, even if its buffered output resembles a valid summary.
                test_result = TestResult(output=_timeout_output(error), completed=False)
            except (OutputLimitExceeded, ExecutionCancelled) as error:
                output = error.output.decode(locale.getpreferredencoding(False), errors="backslashreplace")
                test_result = TestResult(output=output + "\n" + str(error), completed=False)
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
                     and observed == (passed, failures, ignored)
                     and returncode == (failures if os.name == "nt" else failures % 256)
                     and len(markers) == 1 and markers[0].start() > match.end())
        all_passed = completed and failures == 0 and ignored == 0
        return TestResult(total_tests=total, passed_tests=max(0, passed), failed_tests=failures,
                          ignored_tests=ignored, output=output, passed=all_passed,
                          completed=completed, returncode=returncode)
