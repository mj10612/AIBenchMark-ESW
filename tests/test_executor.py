import unittest
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestExecutionSandbox(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.sandbox = ExecutionSandbox()

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

    def test_artifact_survives_until_explicit_cleanup(self):
        task = self.loader.get_task("tier1_crc16")
        comp, _ = self.sandbox.compile_and_test(task, self.loader.get_reference_solution(task.id))
        self.addCleanup(comp.cleanup)
        binary = comp.binary_path
        self.assertTrue(binary.is_file())
        comp.cleanup()
        self.assertFalse(binary.exists())

    def test_crash_after_summary_is_incomplete(self):
        result = self.sandbox._parse_unity_output("5 Tests 0 Failures 0 Ignored\nOK\n", 7)
        self.assertFalse(result.completed)
        self.assertFalse(result.passed)
        self.assertEqual(result.returncode, 7)

    def test_early_exit_without_summary_is_incomplete(self):
        result = self.sandbox._parse_unity_output("test.c:10:test_one:PASS\n", 0)
        self.assertFalse(result.completed)
        self.assertFalse(result.passed)

    def test_assertion_failures_are_completed_partial_results(self):
        result = self.sandbox._parse_unity_output("5 Tests 2 Failures 0 Ignored\nFAIL\n", 2)
        self.assertTrue(result.completed)
        self.assertEqual(result.passed_tests, 3)

    def test_ignored_tests_do_not_count_as_all_passed(self):
        result = self.sandbox._parse_unity_output("5 Tests 0 Failures 1 Ignored\nOK\n", 0)
        self.assertFalse(result.passed)

    def test_missing_compiler_is_a_failed_result(self):
        task = self.loader.get_task("tier1_crc16")
        comp, result = ExecutionSandbox("nonexistent-review-compiler").compile_and_test(
            task, self.loader.get_reference_solution(task.id))
        self.assertFalse(comp.success)
        self.assertFalse(result.completed)


if __name__ == "__main__":
    unittest.main()
