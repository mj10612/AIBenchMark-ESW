import unittest

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestPrivateOracle(unittest.TestCase):
    def test_direct_state_write_is_rejected_and_shadow_state_cannot_forge_score(self):
        task = DatasetLoader().get_task('tier1_crc16')
        executor = ExecutionSandbox()
        # Match the real public entry so failure specifically identifies Unity.
        reference = task.reference_path.read_text()
        source = '#include "unity.h"\n' + reference.replace('return crc;', 'Unity.TestFailures=0; return crc;')
        compilation, tests = executor.compile_and_test(task, source)
        self.addCleanup(compilation.cleanup)
        self.assertFalse(compilation.success)
        self.assertIn('Unity', compilation.output)
        shadow = '#include "unity.h"\nUNITY_STORAGE_T Unity;\n' + reference.replace('return crc;', 'Unity.TestFailures=0; return 0;')
        compilation, tests = executor.compile_and_test(task, shadow)
        self.addCleanup(compilation.cleanup)
        self.assertTrue(compilation.success, compilation.output)
        self.assertFalse(tests.passed)

    def test_restarting_runner_cannot_erase_failures(self):
        task = DatasetLoader().get_task('tier1_crc16')
        source = '#include "unity.h"\n' + task.reference_path.read_text().replace('return crc;', 'UnityBegin("forged"); return crc;')
        compilation, tests = ExecutionSandbox().compile_and_test(task, source)
        self.addCleanup(compilation.cleanup)
        self.assertTrue(compilation.success, compilation.output)
        self.assertFalse(tests.passed)
