import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestStaticAnalyzer(unittest.TestCase):
    def test_analyzer_selection_is_explicit_and_can_disable_incidental_tools(self):
        with patch.dict("os.environ", {"AIBENCHMARK_ESW_CPPCHECK": "configured-cppcheck"}):
            self.assertEqual(StaticAnalyzer().cppcheck_cmd, "configured-cppcheck")
            self.assertEqual(StaticAnalyzer("explicit-cppcheck").cppcheck_cmd, "explicit-cppcheck")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "candidate.c"
            source.write_text("void f(void) { malloc(1); }", encoding="utf-8")
            with patch.dict("os.environ", {"AIBENCHMARK_ESW_CPPCHECK": "off"}), \
                    patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run") as invoke:
                metrics = StaticAnalyzer().analyze(source)
                invoke.assert_not_called()
                self.assertEqual(metrics.cppcheck_status, "disabled")
                self.assertEqual(metrics.error_count, 1)

    def test_allocation_aliases_are_detected_without_cppcheck(self):
        samples = [
            '#define ALLOC malloc\n#define DEALLOC free\nvoid fn(void) { void *p = ALLOC(1); DEALLOC(p); }',
            '#define ALLOC malloc\n#define NEXT ALLOC\nvoid fn(void) { void *p = NEXT(1); }',
            '#define ALLOC(n) malloc(n)\nvoid fn(void) { void *p = ALLOC(1); }',
            '#define ALLOC (malloc)\nvoid fn(void) { void *p = ALLOC(1); }',
            'void fn(void) { void *(*allocate)(size_t) = malloc; void *p = allocate(1); }',
            'void fn(void) { void (*deallocate)(void *) = &free; deallocate(0); }',
            '#define ALLOC ca\\\nlloc\nvoid fn(void) { void *p = ALLOC(1, 1); }',
            '#define RESIZE realloc\nvoid fn(void) { void *p = RESIZE(0, 1); }',
        ]
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            for sample in samples:
                with self.subTest(sample=sample):
                    source.write_text("#include <stdlib.h>\n" + sample, encoding="utf-8")
                    with patch("aibenchmark_esw.sandbox.static_analyzer.shutil.which", return_value=None):
                        metrics = StaticAnalyzer().analyze(source)
                    self.assertEqual(metrics.error_count, 1)

    def test_allocation_aliases_are_detected_when_cppcheck_fails(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("#define ALLOC malloc\nvoid fn(void) { ALLOC(1); }", encoding="utf-8")
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 1, "", "invalid option")):
                metrics = StaticAnalyzer("cppcheck").analyze(source)
        self.assertEqual(metrics.error_count, 1)
        self.assertEqual(metrics.cppcheck_status, "failed")
        self.assertIn("invalid option", metrics.cppcheck_diagnostic)

    def test_allocation_identifier_substrings_and_header_includes_are_allowed(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("#include <stdlib.h>\nint malloc_count, free_slots, reallocations;", encoding="utf-8")
            metrics = StaticAnalyzer("nonexistent-review-cppcheck").analyze(source)
        self.assertEqual(metrics.error_count, 0)

    def test_comments_in_literals_cannot_hide_allocation(self):
        samples = [
            'const char *url = "https://example.test"; void *allocate(void) { return malloc(16); }',
            'const char *start = "/*"; void *allocate(void) { return malloc(16); } const char *end = "*/";',
            'const char *quote = "\\\"//"; void *allocate(void) { return malloc(16); }',
            "char slash = '/'; void *allocate(void) { return malloc(16); }",
            'void *allocate(void) { return ma\\\nlloc(16); }',
        ]
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            for sample in samples:
                with self.subTest(sample=sample):
                    source.write_text("#include <stdlib.h>\n" + sample, encoding="utf-8")
                    metrics = StaticAnalyzer("nonexistent-review-cppcheck").analyze(source)
                    self.assertEqual(metrics.error_count, 1)

    def test_literal_and_comment_text_do_not_trigger_safety_rules(self):
        code = '''const char *message = "malloc(16); goto end; float unsigned short";
char quote = '\\'';
/* free(ptr); goto invalid; double */
// continued comment \\
malloc(16);
void normal(void) {}
'''
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text(code, encoding="utf-8")
            metrics = StaticAnalyzer("nonexistent-review-cppcheck").analyze(source)
        self.assertEqual(metrics.error_count, 0)
        self.assertEqual(metrics.warning_count, 0)

    def test_embedded_rules_remain_active_with_cppcheck_installed(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("void fn(void) { void *ptr = malloc(16); free(ptr); }", encoding="utf-8")
            analyzer = StaticAnalyzer("cppcheck")
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, "", "")):
                self.assertEqual(analyzer.analyze(source).error_count, 1)

    def test_explicit_diagnostic_format_counts_all_enabled_severities(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("void fn(void) {}", encoding="utf-8")
            output = "error:uninitvar:uninitialized\nwarning:unused:unused\nstyle:style:style\nperformance:perf:perf\nportability:port:port\n"
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, "", output)) as run:
                metrics = StaticAnalyzer("cppcheck").analyze(source, [Path(directory)], "c11")
            self.assertEqual(metrics.error_count, 1)
            self.assertEqual(metrics.warning_count, 4)
            self.assertIn("--std=c11", run.call_args.args[0])
            self.assertIn("--template={severity}:{id}:{message}", run.call_args.args[0])

    def test_failed_cppcheck_falls_back_to_embedded_rules(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("void fn(void) { goto end; end:; }", encoding="utf-8")
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 1, "", "invalid option")):
                self.assertEqual(StaticAnalyzer("cppcheck").analyze(source).warning_count, 1)

    def test_backend_status_distinguishes_disabled_completed_and_failed_runs(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("void fn(void) {}", encoding="utf-8")
            with patch("aibenchmark_esw.sandbox.static_analyzer.shutil.which", return_value=None):
                self.assertEqual(StaticAnalyzer().analyze(source).cppcheck_status, "disabled")
            analyzer = StaticAnalyzer("fixture-cppcheck")
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run", side_effect=OSError("tool missing")):
                failed = analyzer.analyze(source)
            self.assertEqual(failed.cppcheck_status, "failed")
            self.assertIn("tool missing", failed.cppcheck_diagnostic)
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, "", "warning:fixture:diagnostic\n")):
                completed = analyzer.analyze(source)
            self.assertEqual(completed.cppcheck_status, "completed")
            self.assertEqual(completed.warning_count, 1)
            self.assertIsNone(completed.cppcheck_diagnostic)
            self.assertEqual(analyzer.analyze(Path(directory) / "missing.c").cppcheck_status, "not_run")

    def test_cppcheck_timeout_is_reported_with_heuristic_fallback(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "solution.c"
            source.write_text("void fn(void) { goto done; done:; }", encoding="utf-8")
            with patch("aibenchmark_esw.sandbox.static_analyzer.subprocess.run",
                       side_effect=subprocess.TimeoutExpired("cppcheck", 10)):
                metrics = StaticAnalyzer("cppcheck").analyze(source)
            self.assertEqual(metrics.cppcheck_status, "failed")
            self.assertEqual(metrics.warning_count, 1)
            self.assertIn("timed out", metrics.cppcheck_diagnostic)


if __name__ == "__main__":
    unittest.main()
