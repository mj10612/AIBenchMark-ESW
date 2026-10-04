import re
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
from aibenchmark_esw.models import StaticSafetyMetrics
from aibenchmark_esw.sandbox.c_source import mask_noncode


class StaticAnalyzer:
    def __init__(self, cppcheck_cmd: Optional[str] = None):
        configured = cppcheck_cmd if cppcheck_cmd is not None else os.environ.get("AIBENCHMARK_ESW_CPPCHECK")
        self.cppcheck_cmd = None if configured == "off" else configured or shutil.which("cppcheck")
        self.last_cppcheck_error = None

    def analyze(self, source_path: Path, include_dirs: Optional[List[Path]] = None,
                standard: str = "c99") -> StaticSafetyMetrics:
        """
        Always check embedded rules; add cppcheck diagnostics when available.
        """
        metrics = self._heuristic_check(source_path)
        metrics.cppcheck_status = "disabled" if not self.cppcheck_cmd else "not_run"
        if self.cppcheck_cmd and source_path.exists():
            self.last_cppcheck_error = None
            cppcheck_metrics = self._run_cppcheck(source_path, include_dirs, standard)
            if cppcheck_metrics is not None:
                metrics.cppcheck_status = "completed"
                metrics.error_count += cppcheck_metrics.error_count
                metrics.warning_count += cppcheck_metrics.warning_count
                metrics.violations.extend(cppcheck_metrics.violations)
            else:
                metrics.cppcheck_status = "failed"
                metrics.cppcheck_diagnostic = self.last_cppcheck_error or "cppcheck did not complete"
        return metrics

    def _run_cppcheck(self, source_path: Path, include_dirs: Optional[List[Path]] = None,
                      standard: str = "c99") -> Optional[StaticSafetyMetrics]:
        try:
            cmd = [
                self.cppcheck_cmd,
                "--enable=warning,style,performance,portability",
                "--inconclusive",
                f"--std={standard}",
                "--template={severity}:{id}:{message}",
                "--quiet",
            ]
            for directory in include_dirs or []:
                cmd += ["-I", str(directory)]
            cmd.append(str(source_path))
            proc = subprocess.run(cmd, capture_output=True, text=True, errors="backslashreplace", timeout=10)
            if proc.returncode != 0:
                self.last_cppcheck_error = f"cppcheck exited with {proc.returncode}: {(proc.stdout + proc.stderr).strip()}"
                return None
            errors = 0
            warnings = 0
            violations = []

            for line in proc.stderr.splitlines():
                if line.startswith("error:"):
                    errors += 1
                    violations.append(line.strip())
                elif line.startswith(("warning:", "style:", "performance:", "portability:")):
                    warnings += 1
                    violations.append(line.strip())

            return StaticSafetyMetrics(
                error_count=errors,
                warning_count=warnings,
                violations=violations,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
            self.last_cppcheck_error = str(error)
            return None

    def _heuristic_check(self, source_path: Path) -> StaticSafetyMetrics:
        if not source_path.exists():
            return StaticSafetyMetrics()

        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        errors = 0
        warnings = 0
        violations = []

        cleaned_code = mask_noncode(code)

        # Reject named allocation API references as well as direct calls.
        # Object macros and function-pointer bindings need no '(' after the
        # allocator name; scanning identifier tokens also catches those aliases.
        identifiers = set(re.findall(r"[a-zA-Z_]\w*", cleaned_code))
        if identifiers.intersection({"malloc", "calloc", "realloc", "free"}):
            errors += 1
            violations.append("MISRA-C Violation: Dynamic memory allocation API reference (malloc/calloc/realloc/free) detected.")

        # 2. Uncontrolled Goto (MISRA Rule 15.1)
        if re.search(r"\bgoto\s+[a-zA-Z_]", cleaned_code):
            warnings += 1
            violations.append("MISRA-C Advisory: Use of 'goto' statement.")

        # 3. Floating point in core routines (if integer-only target)
        if re.search(r"\b(double|float)\b", cleaned_code):
            warnings += 1
            violations.append("Notice: Floating-point types used in resource-constrained task.")

        # 4. Standard variable types instead of fixed-width (MISRA Rule 4.6)
        if re.search(r"\b(unsigned\s+int|signed\s+int|unsigned\s+short)\b", cleaned_code):
            warnings += 1
            violations.append("MISRA-C Rule 4.6: Basic numerical types should use fixed-width typedefs.")

        return StaticSafetyMetrics(
            error_count=errors,
            warning_count=warnings,
            violations=violations,
        )
