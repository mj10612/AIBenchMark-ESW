import os
import shutil
import subprocess
import re
import math
from pathlib import Path
from typing import Optional, List
from aibenchmark_esw.models import StaticSafetyMetrics
from aibenchmark_esw.sandbox.c_source import code_tokens, mask_noncode, original_line


class StaticAnalyzer:
    def configuration(self):
        rules = ["allocation-reference", "misra.15.1", "floating-types", "misra.4.6",
                 "host-process", "host-network", "host-filesystem"]
        if self.extended_rules:
            rules += ["stdio", "nonlocal-control", "nondeterminism", "misra.17.2", "misra.18.8",
                      "heavy-library", "busy-wait"]
        return {"version": 2, "builtin_rules": rules, "extended_rules": self.extended_rules,
                "timeout_seconds": self.timeout_seconds,
                "basic_type_exceptions": ["plain int (status/main APIs)", "plain char (character data)"],
                "cppcheck_enabled": ["warning", "style", "performance", "portability"],
                "inconclusive": True, "standard": "task effective standard",
                "error_severities": ["error"], "warning_severities": ["warning", "style", "performance", "portability"]}

    def __init__(self, cppcheck_cmd: Optional[str] = None, timeout_seconds=30, extended_rules=False):
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be finite and positive")
        self.timeout_seconds, self.extended_rules = timeout_seconds, extended_rules
        self.last_cppcheck_timeout = False
        configured = cppcheck_cmd if cppcheck_cmd is not None else os.environ.get("AIBENCHMARK_ESW_CPPCHECK")
        self.cppcheck_cmd = None if configured == "off" else configured or shutil.which("cppcheck")
        self.last_cppcheck_error: Optional[str] = None

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
                metrics.findings.extend(cppcheck_metrics.findings)
            else:
                metrics.cppcheck_status = "timeout" if self.last_cppcheck_timeout else "failed"
                metrics.cppcheck_diagnostic = self.last_cppcheck_error or "cppcheck did not complete"
        return metrics

    def _run_cppcheck(self, source_path: Path, include_dirs: Optional[List[Path]] = None,
                      standard: str = "c99") -> Optional[StaticSafetyMetrics]:
        self.last_cppcheck_timeout = False
        try:
            assert self.cppcheck_cmd is not None
            cmd = [
                self.cppcheck_cmd,
                "--enable=warning,style,performance,portability",
                "--inconclusive",
                f"--std={standard}",
                "--template={severity}:{id}:{file}:{line}:{message}",
                "--quiet",
            ]
            for directory in include_dirs or []:
                cmd += ["-I", str(directory)]
            cmd.append(str(source_path))
            proc = subprocess.run(cmd, capture_output=True, text=True, errors="backslashreplace",
                                  timeout=self.timeout_seconds, stdin=subprocess.DEVNULL)
            if proc.returncode != 0:
                self.last_cppcheck_error = f"cppcheck exited with {proc.returncode}: {(proc.stdout + proc.stderr).strip()}"
                return None
            errors = 0
            warnings = 0
            violations = []
            findings = []

            for line in proc.stderr.splitlines():
                if line.startswith("error:"):
                    errors += 1
                    violations.append(line.strip())
                elif line.startswith(("warning:", "style:", "performance:", "portability:")):
                    warnings += 1
                    violations.append(line.strip())
                else:
                    continue
                parts = line.split(":", 2)
                location = re.match(r"(.*):(\d+):(.*)", parts[2]) if len(parts) == 3 else None
                findings.append({"rule_id": parts[1], "engine": "cppcheck", "severity": parts[0],
                    "message": location.group(3) if location else parts[2],
                    "file": Path(location.group(1)).name if location else source_path.name,
                    "line": int(location.group(2)) if location else None})

            return StaticSafetyMetrics(
                error_count=errors,
                warning_count=warnings,
                violations=violations,
                findings=findings,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
            self.last_cppcheck_timeout = isinstance(error, subprocess.TimeoutExpired)
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

        tokens = code_tokens(code)

        # Reject named allocation API references as well as direct calls.
        # Object macros and function-pointer bindings need no '(' after the
        # allocator name; scanning identifier tokens also catches those aliases.
        identifiers = set(tokens)
        masked = mask_noncode(code)
        # Struct declarations and member accesses name storage, not allocators.
        no_structs = re.sub(r"\b(?:struct|union)\s*\w*\s*\{[^{}]*\}", lambda m: " " * len(m.group()), masked)
        allocation_tokens = re.findall(r"[A-Za-z_]\w*|->|[^\s]", no_structs)
        allocation_references = {token for index, token in enumerate(allocation_tokens)
                                 if index == 0 or allocation_tokens[index - 1] not in (".", "->")}
        if allocation_references.intersection({"malloc", "calloc", "realloc", "free"}):
            errors += 1
            violations.append("MISRA-C Violation: Dynamic memory allocation API reference (malloc/calloc/realloc/free) detected.")

        # 2. Uncontrolled Goto (MISRA Rule 15.1)
        if "goto" in identifiers:
            warnings += 1
            violations.append("MISRA-C Advisory: Use of 'goto' statement.")

        # 3. Floating point in core routines (if integer-only target)
        if identifiers.intersection({"double", "float"}):
            warnings += 1
            violations.append("Notice: Floating-point types used in resource-constrained task.")

        # 4. Standard variable types instead of fixed-width (MISRA Rule 4.6)
        pairs = set(zip(tokens, tokens[1:]))
        if (identifiers.intersection({"long", "short"}) or
                pairs.intersection({(sign, kind) for sign in ("unsigned", "signed") for kind in ("int", "char", "short", "long")})):
            warnings += 1
            violations.append("MISRA-C Rule 4.6: Basic numerical types should use fixed-width typedefs.")

        # Host-capability rules are conservative named-reference checks, just
        # like allocation aliases. Object member access is not a host API call.
        # Local declarations include typedef-based parameters/callbacks. A
        # lexical check is deliberately conservative, not a complete C parser.
        declared = {match.group(1) for match in re.finditer(
            r"\b(?:[A-Za-z_]\w*)\s+(?:\*\s*)*([A-Za-z_]\w*)\s*(?=[=;,)]|\([^;{}]*\)\s*\{)", no_structs)
                    if match.group().split()[0] not in ("return", "case", "goto")}
        references = {token for index, token in enumerate(tokens)
                      if (index == 0 or tokens[index - 1] not in (".", "->"))
                      and token not in declared
                      and ((index + 1 < len(tokens) and tokens[index + 1] == "(")
                           or (index > 0 and tokens[index - 1] in ("&", "=")))}
        references |= set(re.findall(r"(?m)^\s*#\s*define\s+\w+\s+(\w+)\b", masked))
        categories = {
            "process execution": {"system", "popen", "_popen", "fork", "vfork", "posix_spawn",
                                  "posix_spawnp", "execl", "execlp", "execle", "execv", "execvp",
                                  "execvpe", "execve", "CreateProcessA", "CreateProcessW", "ShellExecuteA",
                                  "ShellExecuteW", "WinExec"},
            "network access": {"socket", "socketpair", "connect", "bind", "listen", "accept",
                               "send", "sendto", "recv", "recvfrom", "getaddrinfo", "WSASocketA",
                               "WSASocketW"},
            "filesystem access": {"fopen", "freopen", "fread", "fwrite", "open", "creat", "read",
                                  "write", "unlink", "remove", "rename", "CreateFileA", "CreateFileW",
                                  "opendir", "readdir", "closedir"},
        }
        headers = set(re.findall(r"(?m)^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]",
                                 mask_noncode(code, keep_includes=True)))
        category_headers = {"process execution": {"sys/wait.h", "spawn.h"},
                            "network access": {"sys/socket.h", "winsock2.h", "netdb.h"},
                            "filesystem access": {"unistd.h", "fcntl.h", "dirent.h"}}
        for category, names in categories.items():
            found = sorted(references.intersection(names))
            if found or headers.intersection(category_headers[category]):
                errors += 1
                violations.append(f"Embedded safety: Host {category} API reference ({', '.join(found)}) detected.")

        findings = []
        for message in violations:
            if "allocation" in message:
                rule, severity, names = "builtin.allocation-reference", "error", {"malloc", "calloc", "realloc", "free"}
            elif "goto" in message:
                rule, severity, names = "builtin.misra.15.1", "warning", {"goto"}
            elif "Floating" in message:
                rule, severity, names = "builtin.floating-types", "warning", {"float", "double"}
            elif "4.6" in message:
                rule, severity, names = "builtin.misra.4.6", "warning", {"unsigned", "signed", "short", "long"}
            else:
                category = next(name for name in categories if name in message)
                rule, severity, names = "builtin.host-" + category.split()[0], "error", categories[category]
            match = re.search(r"\b(?:" + "|".join(re.escape(name) for name in sorted(names)) + r")\b", masked)
            findings.append({"rule_id": rule, "engine": "builtin", "severity": severity, "message": message,
                             "file": source_path.name, "line": original_line(code, match.start()) if match else None})
        if self.extended_rules:
            for rule, position, message in self._extended_findings(masked, headers, references):
                warnings += 1
                violations.append(message)
                findings.append({"rule_id": "builtin." + rule, "engine": "builtin", "severity": "warning",
                                 "message": message, "file": source_path.name,
                                 "line": original_line(code, position) if position is not None else None})
        return StaticSafetyMetrics(
            error_count=errors,
            warning_count=warnings,
            violations=violations,
            findings=findings,
        )

    def _extended_findings(self, masked, headers, references):
        groups = {"stdio": {"printf", "fprintf", "sprintf", "snprintf", "vprintf", "vfprintf", "vsprintf", "vsnprintf",
                            "puts", "fputs", "putchar", "fputc", "putc", "scanf", "fscanf", "sscanf", "vscanf", "vfscanf",
                            "vsscanf", "getchar", "getc", "fgets", "gets", "perror"},
                  "nonlocal-control": {"exit", "_Exit", "abort", "atexit", "quick_exit", "at_quick_exit",
                                       "setjmp", "longjmp", "signal", "raise"},
                  "nondeterminism": {"rand", "srand", "time", "clock"},
                  "misra.18.8": {"alloca", "_alloca"}}
        for rule, names in groups.items():
            found = references & names
            if found:
                match = re.search(r"\b(?:" + "|".join(sorted(found)) + r")\b", masked)
                yield rule, match.start() if match else None, "Embedded safety: " + rule + " API reference (" + ", ".join(sorted(found)) + ")"
        if headers & {"math.h", "complex.h"}:
            yield "heavy-library", None, "Embedded safety: math/complex library dependency"
        # Capture definitions and their balanced bodies, then detect call-graph
        # cycles, including mutual recursion. Members are excluded from edges.
        graph, locations = {}, {}
        for definition in re.finditer(r"\b(\w+)\s*\([^;{}]*\)\s*\{", masked):
            name = definition.group(1)
            if name in {"if", "while", "for", "switch"}:
                continue
            level, end = 1, definition.end()
            while end < len(masked) and level:
                level += (masked[end] == "{") - (masked[end] == "}")
                end += 1
            body = masked[definition.end():end]
            graph[name] = set(re.findall(r"(?<![.\w])(?<!->)\b(\w+)\s*\(", body))
            locations[name] = definition.start()
        def cyclic(start):
            pending, seen = list(graph.get(start, ())), set()
            while pending:
                child = pending.pop()
                if child == start:
                    return True
                if child not in seen:
                    seen.add(child)
                    pending.extend(graph.get(child, ()))
            return False
        recursive = sorted(name for name in graph if cyclic(name))
        if recursive:
            yield "misra.17.2", locations[recursive[0]], "MISRA-C Rule 17.2: Recursive call cycle (" + ", ".join(recursive) + ")"
        vla = next((match for match in re.finditer(r"\b(?:[A-Za-z_]\w*)\s+\w+\s*\[([^\]]+)\]", masked)
                    if any(not name.isupper() for name in re.findall(r"\b[A-Za-z_]\w*\b", match.group(1)))), None)
        if vla:
            yield "misra.18.8", vla.start(), "MISRA-C Rule 18.8: Possible variable-length array"
        busy = re.search(r"\bwhile\s*\(\s*(?:1|true)\s*\)|\bfor\s*\(\s*;\s*;\s*\)", masked)
        if busy:
            # A lexical advisory; loops with an explicit escape are accepted.
            tail = masked[busy.end():]
            if not re.search(r"\b(?:break|return)\b", tail):
                yield "busy-wait", busy.start(), "Embedded safety: Unbounded busy-wait loop"
