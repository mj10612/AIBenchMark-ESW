import unittest
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from dataclasses import replace
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestExecutionSandbox(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.sandbox = ExecutionSandbox()

    def unity_output(self, statuses):
        records = "\n".join(f"test.c:{index + 1}:test_{index}:{status}" for index, status in enumerate(statuses))
        failures, ignored = statuses.count("FAIL"), statuses.count("IGNORE")
        return (f"{records}\n{len(statuses)} Tests {failures} Failures {ignored} Ignored\n"
                "AIBenchMark-ESW:fixture:END\n")

    def test_compile_and_pass_reference(self):
        task = self.loader.get_task("tier1_crc16")
        self.assertIsNotNone(task)
        ref_code = self.loader.get_reference_solution(task.id)
        self.assertIsNotNone(ref_code)

        comp_res, test_res = self.sandbox.compile_and_test(task, ref_code)
        self.addCleanup(comp_res.cleanup)
        self.assertTrue(comp_res.success)
        self.assertTrue(test_res.passed)
        self.assertEqual(test_res.failed_tests, 0)
        self.assertGreater(test_res.passed_tests, 0)

    def test_compile_and_fail_starter_stub(self):
        task = self.loader.get_task("tier1_crc16")
        starter_code = self.loader.get_starter_code(task.id)

        comp_res, test_res = self.sandbox.compile_and_test(task, starter_code)
        self.addCleanup(comp_res.cleanup)
        self.assertTrue(comp_res.success)
        # Stub fails assertions
        self.assertFalse(test_res.passed)
        self.assertTrue(test_res.completed)

    def test_artifact_survives_until_explicit_cleanup(self):
        task = self.loader.get_task("tier1_crc16")
        comp, _ = self.sandbox.compile_and_test(task, self.loader.get_reference_solution(task.id))
        self.addCleanup(comp.cleanup)
        binary = comp.binary_path
        self.assertTrue(binary.is_file())
        comp.cleanup()
        self.assertFalse(binary.exists())

    def test_runner_with_arguments_and_local_header_completes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tests = root / "tests"
            tests.mkdir()
            (tests / "helper.h").write_text("int answer(void);\n", encoding="utf-8")
            (tests / "test_answer.c").write_text('''#include "unity.h"
#include "helper.h"
static int runner_argc;
void setUp(void) {}
void tearDown(void) {}
void test_answer(void) {
    TEST_ASSERT_TRUE(runner_argc >= 1);
    TEST_ASSERT_EQUAL_INT(7, answer());
}
int main(int argc, char **argv) {
    (void)argv;
    runner_argc = argc;
    UNITY_BEGIN();
    RUN_TEST(test_answer);
    return UNITY_END();
}
''', encoding="utf-8")
            task = replace(self.loader.get_task("tier1_crc16"), task_dir=root)
            compiled, result = self.sandbox.compile_and_test(task, "int answer(void) { return 7; }")
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(result.passed, result.output)

    def test_crash_after_summary_is_incomplete(self):
        result = self.sandbox._parse_unity_output(self.unity_output(["PASS"] * 5), 7, "fixture")
        self.assertFalse(result.completed)
        self.assertFalse(result.passed)
        self.assertEqual(result.returncode, 7)

    def test_fixture_aborts_run_cleanup_once_and_continue_to_the_next_test(self):
        cases = [
            ("", "", 'TEST_FAIL_MESSAGE("cleanup failed");', 1, 0, 2),
            ("", "", 'TEST_IGNORE_MESSAGE("cleanup ignored");', 0, 1, 2),
            ('TEST_FAIL_MESSAGE("setup failed");', "", "", 1, 0, 1),
            ('TEST_IGNORE_MESSAGE("setup ignored");', "", "", 0, 1, 1),
            ("", 'TEST_FAIL_MESSAGE("body failed");', "", 1, 0, 2),
            ("", 'TEST_IGNORE_MESSAGE("body ignored");', "", 0, 1, 2),
            ("", 'TEST_FAIL_MESSAGE("body failed");', 'TEST_FAIL_MESSAGE("cleanup failed");', 1, 0, 2),
            ("", 'TEST_FAIL_MESSAGE("body failed");', 'TEST_IGNORE_MESSAGE("cleanup ignored");', 1, 0, 2),
            ('TEST_IGNORE_MESSAGE("setup ignored");', "", 'TEST_FAIL_MESSAGE("cleanup failed");', 1, 0, 1),
        ]
        fixture = '''#include "unity.h"
static int setups, bodies, cleanups;
void setUp(void) {
    setups++;
    if (setups == 1) { SETUP_ACTION }
}
void tearDown(void) {
    cleanups++;
    if (cleanups == 1) { CLEANUP_ACTION }
}
void test_first(void) { bodies++; BODY_ACTION }
void test_second(void) { bodies++; TEST_ASSERT_TRUE(1); }
int main(void) {
    int result;
    UNITY_BEGIN();
    RUN_TEST(test_first);
    RUN_TEST(test_second);
    result = UNITY_END();
    printf("COUNTS:%d:%d:%d\\n", setups, bodies, cleanups);
    return result;
}
'''
        for setup, body, cleanup, failures, ignored, bodies in cases:
            with self.subTest(setup=setup, body=body, cleanup=cleanup), TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "tests").mkdir()
                source = fixture.replace("SETUP_ACTION", setup).replace("BODY_ACTION", body)
                source = source.replace("CLEANUP_ACTION", cleanup)
                (root / "tests/test_fixture.c").write_text(source, encoding="utf-8")
                base = self.loader.get_task("tier1_crc16")
                task = replace(base, task_dir=root, limits=replace(base.limits, timeout_seconds=1))
                compiled, result = self.sandbox.compile_and_test(task, "void candidate(void) {}")
                self.addCleanup(compiled.cleanup)
                self.assertTrue(compiled.success, compiled.output)
                self.assertTrue(result.completed, result.output)
                self.assertEqual(result.total_tests, 2)
                self.assertEqual(result.failed_tests, failures)
                self.assertEqual(result.ignored_tests, ignored)
                self.assertEqual(result.passed_tests, 2 - failures - ignored)
                self.assertIn(f"COUNTS:2:{bodies}:2", result.output)
                self.assertIn(":test_second:PASS", result.output)

    def test_early_exit_without_summary_is_incomplete(self):
        result = self.sandbox._parse_unity_output("test.c:10:test_one:PASS\n", 0)
        self.assertFalse(result.completed)
        self.assertFalse(result.passed)

    def test_assertion_failures_are_completed_partial_results(self):
        result = self.sandbox._parse_unity_output(self.unity_output(["PASS"] * 3 + ["FAIL"] * 2), 2, "fixture")
        self.assertTrue(result.completed)
        self.assertEqual(result.passed_tests, 3)

    def test_ignored_tests_do_not_count_as_all_passed(self):
        result = self.sandbox._parse_unity_output(self.unity_output(["PASS"] * 4 + ["IGNORE"]), 0, "fixture")
        self.assertFalse(result.passed)
        self.assertTrue(result.completed)

    def test_completion_requires_matching_token_and_consistent_records(self):
        valid = self.unity_output(["PASS"] * 5)
        self.assertTrue(self.sandbox._parse_unity_output(valid, 0, "fixture").passed)
        for output in [valid.replace("AIBenchMark-ESW:fixture:END", ""),
                       valid.replace("fixture", "wrong-token"),
                       "5 Tests 0 Failures 0 Ignored\nAIBenchMark-ESW:fixture:END\n",
                       "5 Tests 0 Failures 0 Ignored\n" + valid,
                       valid.replace("5 Tests", "6 Tests")]:
            with self.subTest(output=output):
                self.assertFalse(self.sandbox._parse_unity_output(output, 0, "fixture").completed)

    def test_missing_compiler_is_a_failed_result(self):
        task = self.loader.get_task("tier1_crc16")
        comp, result = ExecutionSandbox("nonexistent-review-compiler").compile_and_test(
            task, self.loader.get_reference_solution(task.id))
        self.assertFalse(comp.success)
        self.assertFalse(result.completed)

    def test_compiler_timeout_preserves_both_diagnostic_streams(self):
        task = self.loader.get_task("tier1_crc16")
        for stdout, stderr in ((b"compiler output\n", b"compiler error\xff\n"),
                               ("compiler output\n", "compiler error\n"), (None, None)):
            with self.subTest(stdout=stdout), TemporaryDirectory() as directory:
                error = subprocess.TimeoutExpired("compiler", 30, output=stdout, stderr=stderr)
                with patch("aibenchmark_esw.sandbox.executor.subprocess.run", side_effect=error):
                    result = self.sandbox.compile_object(task, self.loader.get_reference_solution(task.id),
                                                         Path(directory))
                self.assertFalse(result.success)
                self.assertIn("timed out", result.output)
                self.assertEqual(result.effective_standard, "c99")
                if stdout:
                    self.assertIn("compiler output", result.output)
                    self.assertIn("compiler error", result.output)

    def test_test_timeout_preserves_records_without_parsing_them_as_completed(self):
        task = self.loader.get_task("tier1_crc16")
        real_run = subprocess.run
        for as_bytes in (False, True):
            def timeout_after_compile(command, **kwargs):
                if "-o" in command:
                    return real_run(command, **kwargs)
                token = Path(command[0]).parent.glob("aibenchmark_tests_*.c")
                wrapper = next(token).read_text(encoding="utf-8")
                marker = wrapper.split("AIBenchMark-ESW:")[1].split(":END")[0]
                partial = self.unity_output(["PASS"] * 5).replace("fixture", marker)
                if as_bytes:
                    partial = partial.encode("utf-8")
                raise subprocess.TimeoutExpired(command, 1, output=partial)
            with self.subTest(as_bytes=as_bytes), patch(
                    "aibenchmark_esw.sandbox.executor.subprocess.run", side_effect=timeout_after_compile):
                compiled, result = self.sandbox.compile_and_test(task, self.loader.get_reference_solution(task.id))
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertIn(":test_0:PASS", result.output)
            self.assertIn("5 Tests 0 Failures 0 Ignored", result.output)
            self.assertIn("timed out", result.output)
            self.assertFalse(result.completed)
            self.assertFalse(result.passed)
            self.assertEqual(result.passed_tests, 0)

    def test_msvc_rejects_c99_without_explicit_opt_in(self):
        task = self.loader.get_task("tier1_crc16")
        with TemporaryDirectory() as directory:
            with patch("aibenchmark_esw.sandbox.executor.subprocess.run") as run:
                result = ExecutionSandbox("cl").compile_object(
                    task, self.loader.get_reference_solution(task.id), Path(directory))
                run.assert_not_called()
        self.assertFalse(result.success)
        self.assertIn("--allow-standard-fallback", result.output)
        self.assertIsNone(result.effective_standard)

    def test_msvc_opt_in_records_actual_standard(self):
        task = self.loader.get_task("tier1_crc16")
        with TemporaryDirectory() as directory:
            def compile_fixture(command, **kwargs):
                self.assertIn("/std:c11", command)
                output = next(argument[3:] for argument in command if argument.startswith("/Fo"))
                Path(output).write_bytes(b"fixture object")
                return subprocess.CompletedProcess(command, 0, "", "")
            with patch("aibenchmark_esw.sandbox.executor.subprocess.run", side_effect=compile_fixture):
                result = ExecutionSandbox("cl", allow_standard_fallback=True).compile_object(
                    task, self.loader.get_reference_solution(task.id), Path(directory))
        self.assertTrue(result.success)
        self.assertEqual(result.effective_standard, "c11")

    def test_compiler_output_with_invalid_encoding_remains_a_failed_result(self):
        task = self.loader.get_task("tier1_crc16")
        real_run = subprocess.run
        def failing_compiler(command, **kwargs):
            # Exercise decoding rather than mocking a decoded CompletedProcess.
            kwargs["encoding"] = "utf-8"
            return real_run([sys.executable, "-c",
                             "import sys; sys.stdout.buffer.write(b'bad byte: \\xff'); sys.exit(1)"],
                            **kwargs)
        with TemporaryDirectory() as directory:
            with patch("aibenchmark_esw.sandbox.executor.subprocess.run", side_effect=failing_compiler):
                result = self.sandbox.compile_object(task, "invalid C", Path(directory))
        self.assertFalse(result.success)
        self.assertIn("bad byte:", result.output)
        self.assertIn("\\xff", result.output)


if __name__ == "__main__":
    unittest.main()
