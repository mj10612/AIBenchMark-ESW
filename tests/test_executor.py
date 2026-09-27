import unittest
from embeval.dataset import DatasetLoader
from embeval.sandbox.executor import ExecutionSandbox


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
        self.assertTrue(comp_res.success)
        self.assertTrue(test_res.passed)
        self.assertEqual(test_res.failed_tests, 0)
        self.assertGreater(test_res.passed_tests, 0)

    def test_compile_and_fail_starter_stub(self):
        task = self.loader.get_task("tier1_crc16")
        starter_code = self.loader.get_starter_code(task.id)

        comp_res, test_res = self.sandbox.compile_and_test(task, starter_code)
        self.assertTrue(comp_res.success)
        # Stub fails assertions
        self.assertFalse(test_res.passed)


if __name__ == "__main__":
    unittest.main()
