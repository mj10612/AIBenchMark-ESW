import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from aibenchmark_esw.models import StaticSafetyMetrics


class StaticAnalyzer:
    def __init__(self, cppcheck_cmd: Optional[str] = None):
        self.cppcheck_cmd = cppcheck_cmd or shutil.which("cppcheck")

    def analyze(self, source_path: Path) -> StaticSafetyMetrics:
        """
        Runs cppcheck if available; otherwise uses embedded C safety heuristics.
        """
        if self.cppcheck_cmd and source_path.exists():
            metrics = self._run_cppcheck(source_path)
            if metrics is not None:
                return metrics

        return self._heuristic_check(source_path)

    def _run_cppcheck(self, source_path: Path) -> Optional[StaticSafetyMetrics]:
        try:
            cmd = [
                self.cppcheck_cmd,
                "--enable=warning,style,performance,portability",
                "--inconclusive",
                "--std=c99",
                "--quiet",
                str(source_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            errors = 0
            warnings = 0
            violations = []

            for line in proc.stderr.splitlines():
                if ": error:" in line:
                    errors += 1
                    violations.append(line.strip())
                elif ": warning:" in line or ": style:" in line:
                    warnings += 1
                    violations.append(line.strip())

            return StaticSafetyMetrics(
                error_count=errors,
                warning_count=warnings,
                violations=violations,
            )
        except Exception:
            return None

    def _heuristic_check(self, source_path: Path) -> StaticSafetyMetrics:
        if not source_path.exists():
            return StaticSafetyMetrics()

        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        errors = 0
        warnings = 0
        violations = []

        # Remove single-line and multi-line comments before analysis
        cleaned_code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        cleaned_code = re.sub(r"//.*", "", cleaned_code)

        # 1. Dynamic Memory Allocation check (Forbidden in safety-critical embedded systems)
        if re.search(r"\b(malloc|calloc|realloc|free)\s*\(", cleaned_code):
            errors += 1
            violations.append("MISRA-C Violation: Dynamic memory allocation (malloc/free) detected.")

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
