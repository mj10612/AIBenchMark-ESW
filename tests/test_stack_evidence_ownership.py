import copy
import unittest
from concurrent.futures import ThreadPoolExecutor

from compiler_tools import find_clang
from test_aggregation import fixture_report

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.reference_cache import ReferenceCache
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.stack_usage import (
    parse_stack_usage,
    unavailable_stack_usage,
)
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestStackEvidenceSnapshots(unittest.TestCase):
    def test_serialized_stack_snapshots_are_independent(self):
        for evidence in (parse_stack_usage('candidate.c:1:fn\t32\tstatic'),
                         unavailable_stack_usage('Unsupported compiler')):
            with self.subTest(status=evidence['status']):
                evidence['provenance'] = {'target': 'host', 'compiler': {'version': '1'}, 'flags': ['-Os']}
                result = BenchmarkReporter.from_json_dict(fixture_report())[0]
                result.stack_usage = {role: copy.deepcopy(evidence) for role in ('candidate', 'reference')}
                direct = result.to_dict()
                report = BenchmarkReporter.to_json_dict([result], result.model_name)
                direct['stack_usage']['reference']['provenance']['compiler']['version'] = 'changed'
                direct['stack_usage']['candidate']['functions'].clear()
                self.assertEqual(result.stack_usage['reference']['provenance']['compiler']['version'], '1')
                self.assertEqual(result.stack_usage['candidate']['functions'], evidence['functions'])
                exported = report['tasks'][0]['stack_usage']
                self.assertEqual(exported['reference']['provenance']['compiler']['version'], '1')
                exported['candidate']['provenance']['flags'].append('-fchanged')
                self.assertEqual(result.stack_usage['candidate']['provenance']['flags'], ['-Os'])
                self.assertEqual(direct['stack_usage']['candidate']['provenance']['flags'], ['-Os'])


@unittest.skipUnless(find_clang(), 'Stack evidence integration requires Clang')
class TestCachedStackEvidence(unittest.TestCase):
    def setUp(self):
        self.task = DatasetLoader().get_task('tier3_spi_flash')
        self.code = self.task.reference_path.read_text(encoding='utf-8')
        self.executor = ExecutionSandbox(compiler_path=find_clang(), stack_usage=True)
        self.cache = ReferenceCache()
        self.analyzer = StaticAnalyzer(cppcheck_cmd='off')

    def evaluate(self):
        result = evaluate_task(self.task, self.code, self.code, 'reference', self.executor,
                               self.analyzer, reference_cache=self.cache)
        self.assertIsNone(result.error_log)
        self.assertEqual(result.scores.total_score, 100)
        self.assertEqual(result.stack_usage['candidate']['status'], 'measured')
        return result

    def test_golden_candidate_and_reference_roles_are_independent(self):
        result = self.evaluate()
        expected = copy.deepcopy(result.stack_usage['reference'])
        result.stack_usage['candidate']['functions'][0]['bytes'] = 999999
        result.stack_usage['candidate']['provenance']['target'] = 'arm:cortex-m0'
        self.assertEqual(result.stack_usage['reference'], expected)
        later = self.evaluate()
        self.assertTrue(later.provenance['reference_cache_hit'])
        self.assertEqual(later.stack_usage['reference'], expected)

    def test_result_and_export_mutations_cannot_poison_later_evaluations(self):
        first = self.evaluate()
        expected = copy.deepcopy(first.stack_usage['reference'])
        first.stack_usage['reference']['functions'][0]['bytes'] = 999999
        first.stack_usage['reference']['bounded_functions'] = 0
        first.stack_usage['reference']['provenance']['compiler']['version'] = 'changed'
        exported = first.to_dict()
        exported['stack_usage']['reference']['provenance']['target'] = 'arm:cortex-m0'
        second = self.evaluate()
        self.assertTrue(second.provenance['reference_cache_hit'])
        self.assertEqual(second.stack_usage['reference'], expected)
        candidate = second.stack_usage['candidate']
        self.assertEqual(candidate['functions'], expected['functions'])
        self.assertEqual(candidate['provenance']['target'], 'host')
        self.assertEqual(candidate['provenance']['compiler'], expected['provenance']['compiler'])

    def test_parallel_cache_hits_return_independent_stack_records(self):
        expected = copy.deepcopy(self.evaluate().stack_usage['reference'])
        with ThreadPoolExecutor(max_workers=4) as workers:
            records = list(workers.map(lambda _: self.cache.validate(self.task, self.code, self.executor), range(4)))
        self.assertTrue(all(hit for _, hit in records))
        records[0][0].stack_usage['functions'].clear()
        records[0][0].stack_usage['provenance']['target'] = 'arm:cortex-m0'
        self.assertEqual(records[1][0].stack_usage, expected)
        fresh, hit = self.cache.validate(self.task, self.code, self.executor)
        self.assertTrue(hit)
        self.assertEqual(fresh.stack_usage, expected)
