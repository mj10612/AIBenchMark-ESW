import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from embeval.models import TaskConfig, CompilationResult, TestResult


class ExecutionSandbox:
    def __init__(self, compiler_path: Optional[str] = None):
        self.compiler_path = compiler_path or self._find_c_compiler()
        self.unity_dir = self._find_unity_dir()

    def _find_c_compiler(self) -> str:
        # Check standard PATH
        for cmd in ["gcc", "clang", "tcc", "cl"]:
            path = shutil.which(cmd)
            if path:
                return path

        # Check common Windows Scoop locations
        user_profile = os.environ.get("USERPROFILE", "")
        if user_profile:
            tcc_scoop = Path(user_profile) / "scoop" / "apps" / "tcc" / "current" / "tcc" / "tcc.exe"
            if tcc_scoop.is_file():
                return str(tcc_scoop)
            gcc_scoop = Path(user_profile) / "scoop" / "apps" / "gcc" / "current" / "bin" / "gcc.exe"
            if gcc_scoop.is_file():
                return str(gcc_scoop)

        return "gcc"  # fallback default

    def _find_unity_dir(self) -> Path:
        project_root = Path(__file__).resolve().parent.parent.parent
        return project_root / "third_party" / "unity"

    def compile_and_test(
        self,
        task: TaskConfig,
        solution_code: str,
        custom_workspace: Optional[Path] = None,
    ) -> Tuple[CompilationResult, TestResult]:
        """
        Injects solution_code, compiles with Unity test harness, and executes the suite.
        """
        temp_dir = None
        if custom_workspace:
            work_dir = Path(custom_workspace)
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = tempfile.mkdtemp(prefix=f"embeval_{task.id}_")
            work_dir = Path(temp_dir)

        try:
            # 1. Prepare files
            include_dir = task.task_dir / "include"
            tests_dir = task.task_dir / "tests"
            test_c_files = list(tests_dir.glob("test_*.c"))
            if not test_c_files:
                raise FileNotFoundError(f"No test_*.c found in {tests_dir}")
            test_c = test_c_files[0]

            unity_c = self.unity_dir / "unity.c"
            sol_file = work_dir / Path(task.entry_file).name
            with open(sol_file, "w", encoding="utf-8") as f:
                f.write(solution_code)

            binary_ext = ".exe" if os.name == "nt" else ""
            binary_path = work_dir / f"test_{task.id}{binary_ext}"

            # 2. Compile
            compile_cmd = [
                self.compiler_path,
                "-I", str(include_dir),
                "-I", str(self.unity_dir),
                str(test_c),
                str(sol_file),
                str(unity_c),
                "-o", str(binary_path),
            ]

            comp_proc = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if comp_proc.returncode != 0 or not binary_path.exists():
                return (
                    CompilationResult(
                        success=False,
                        output=comp_proc.stdout + "\n" + comp_proc.stderr,
                        error_message="Compilation failed",
                    ),
                    TestResult(passed=False, output="Compilation failed"),
                )

            comp_result = CompilationResult(
                success=True,
                output=comp_proc.stdout,
                binary_path=binary_path,
            )

            # 3. Execute
            try:
                run_proc = subprocess.run(
                    [str(binary_path)],
                    capture_output=True,
                    text=True,
                    timeout=task.limits.timeout_seconds,
                    cwd=str(work_dir),
                )
                test_output = run_proc.stdout + "\n" + run_proc.stderr
                test_result = self._parse_unity_output(test_output, run_proc.returncode)
            except subprocess.TimeoutExpired:
                test_result = TestResult(
                    total_tests=0,
                    passed_tests=0,
                    failed_tests=1,
                    output=f"Execution timed out after {task.limits.timeout_seconds}s",
                    passed=False,
                )

            return comp_result, test_result

        finally:
            if temp_dir and Path(temp_dir).exists():
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _parse_unity_output(self, output: str, returncode: int) -> TestResult:
        # Example Unity summary:
        # 6 Tests 0 Failures 0 Ignored
        # OK
        passed_count = len(re.findall(r":PASS\b", output))
        failed_count = len(re.findall(r":FAIL\b", output))
        ignored_count = len(re.findall(r":IGNORE\b", output))

        match = re.search(r"(\d+)\s+Tests\s+(\d+)\s+Failures\s+(\d+)\s+Ignored", output)
        if match:
            total = int(match.group(1))
            failures = int(match.group(2))
            ignored = int(match.group(3))
            passed = total - failures - ignored
        else:
            passed = passed_count
            failures = failed_count
            ignored = ignored_count
            total = passed + failures + ignored

        is_passed = (returncode == 0) and (failures == 0) and (total > 0)
        return TestResult(
            total_tests=total,
            passed_tests=passed,
            failed_tests=failures,
            ignored_tests=ignored,
            output=output,
            passed=is_passed,
        )
