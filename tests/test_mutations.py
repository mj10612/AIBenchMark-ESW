import hashlib
import unittest
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.mutations import MUTATIONS, Mutation, run_mutations
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from dataclasses import replace


class TestMutationAdequacy(unittest.TestCase):
    def test_compile_failures_and_timeouts_are_invalid_never_killed(self):
        loader = DatasetLoader()
        original = loader.get_task("tier1_crc16")
        task = replace(original, limits=replace(original.limits, timeout_seconds=1))
        invalid = Mutation("compile-error", "Non-C fixture", (("return crc;", "INVALID_SOURCE!!! return crc;"),))
        timeout = Mutation("timeout", "Incomplete suite", (("return crc;", "while (1) {} return crc;"),))
        with patch.dict(MUTATIONS, {task.id: (invalid, timeout)}):
            report = run_mutations([task], loader)
        self.assertFalse(report["passed"])
        self.assertEqual(report["tasks"][0]["invalid"], 2)
        self.assertEqual(report["tasks"][0]["killed"], 0)

    def test_every_bundled_task_kills_reviewed_faults_without_modifying_sources(self):
        loader = DatasetLoader()
        tasks = loader.list_tasks()
        self.assertEqual({task.id for task in tasks}, set(MUTATIONS))
        before = {task.id: hashlib.sha256(task.reference_path.read_bytes()).hexdigest() for task in tasks}
        report = run_mutations(tasks, loader, ExecutionSandbox())
        self.assertTrue(report["passed"], report)
        self.assertTrue(report["compiler"])
        self.assertTrue(report["evaluator_sha256"])
        for row in report["tasks"]:
            self.assertGreater(row["killed"], 0, row)
            self.assertEqual(row["survived"], 0, row)
            self.assertEqual(row["invalid"], 0, row)
        after = {task.id: hashlib.sha256(task.reference_path.read_bytes()).hexdigest() for task in tasks}
        self.assertEqual(before, after)

    def test_survival_and_stale_mutations_fail_the_adequacy_report(self):
        loader = DatasetLoader()
        task = loader.get_task("tier1_crc16")
        # Use a harmless whitespace change for a compiling, surviving fixture.
        equivalent = Mutation("equivalent", "A live mutant must fail adequacy", (("return crc;", "return  crc;"),))
        stale = Mutation("stale", "An obsolete fixture must not count as killed", (("ABSENT_ANCHOR", "0"),))
        with patch.dict(MUTATIONS, {task.id: (equivalent, stale)}):
            report = run_mutations([task], loader)
        self.assertFalse(report["passed"])
        self.assertEqual(report["tasks"][0]["survived"], 1)
        self.assertEqual(report["tasks"][0]["invalid"], 1)
        self.assertEqual(report["tasks"][0]["killed"], 0)
