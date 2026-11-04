import gc
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.models import CompilationResult, TestResult
from aibenchmark_esw.reference_cache import ReferenceCache
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestReferenceLockRetention(unittest.TestCase):
    def setUp(self):
        self.task = DatasetLoader().get_task('tier1_crc16')
        self.executor = ExecutionSandbox(compiler_path='tcc')
        self.cache = ReferenceCache()

    def test_failed_unique_inputs_do_not_retain_idle_locks(self):
        failed = (CompilationResult(False, 'temporary failure'), TestResult())
        with patch.object(self.executor, 'compile_and_test', return_value=failed):
            for index in range(100):
                result, hit = self.cache.validate(self.task, f'int f{index}(void){{return 0;}}', self.executor)
                self.assertFalse(hit)
                self.assertIsNotNone(result.error)
        gc.collect()
        self.assertEqual(len(self.cache._records), 0)
        self.assertEqual(len(self.cache._locks), 0)

    def test_concurrent_identical_failures_share_a_lock_until_all_users_finish(self):
        first_started, release = threading.Event(), threading.Event()
        active = 0
        maximum = 0
        guard = threading.Lock()

        def compile_failure(*args):
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
            first_started.set()
            self.assertTrue(release.wait(5))
            with guard:
                active -= 1
            return CompilationResult(False, 'temporary failure'), TestResult()

        with patch.object(self.executor, 'compile_and_test', side_effect=compile_failure), \
                ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.cache.validate, self.task, 'same code', self.executor) for _ in range(4)]
            try:
                self.assertTrue(first_started.wait(5))
                self.assertEqual(len(self.cache._locks), 1)
            finally:
                release.set()
            for future in futures:
                self.assertIsNotNone(future.result(timeout=5)[0].error)
        self.assertEqual(maximum, 1)
        gc.collect()
        self.assertEqual(len(self.cache._locks), 0)

    def test_unexpected_exception_releases_lock(self):
        with patch.object(self.executor, 'compile_and_test', Mock(side_effect=RuntimeError('unexpected'))):
            with self.assertRaisesRegex(RuntimeError, 'unexpected'):
                self.cache.validate(self.task, 'same code', self.executor)
        gc.collect()
        self.assertEqual(len(self.cache._locks), 0)
