import copy
import csv
import io
import unittest

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.aggregation import aggregate_runs, render_aggregation


class TestAggregationDimensionCounts(unittest.TestCase):
    def report(self, run_id, missing=False):
        report = fixture_report(100, run_id)
        second = copy.deepcopy(report['tasks'][0])
        second['task_id'] = 'two'
        second['provenance']['task_sha256'] = 'task-two'
        report['tasks'].append(second)
        report['metadata']['selected_tasks'].append('two')
        policy = report['metadata']['scoring_policy']['tasks']
        policy['two'] = copy.deepcopy(policy['one'])
        if missing:
            second['size_metrics']['measured'] = False
            second['scores'].update(memory=0, total=80)
            report['overall_score'] = 90
        return report

    def test_dimension_run_counts_differ_from_task_measurement_coverage(self):
        summary = aggregate_runs([self.report('good'), self.report('partial', True)])
        group = summary['groups'][0]
        stats = group['statistics']['memory']
        self.assertEqual(stats['contributing_runs'], 1)
        self.assertEqual(stats['excluded_runs'], 1)
        self.assertEqual(stats['mean'], 100)
        self.assertEqual(group['memory_measured_attempts'], 3)
        self.assertEqual(group['task_attempts'], 4)
        self.assertEqual(group['statistics']['score']['contributing_runs'], 2)
        row = next(csv.DictReader(io.StringIO(render_aggregation(summary, 'csv'))))
        self.assertEqual(row['memory_contributing_runs'], '1')
        self.assertEqual(row['memory_excluded_runs'], '1')
        for format_name in ('markdown', 'cli'):
            self.assertIn('memory 1/2', render_aggregation(summary, format_name))

    def test_zero_contributing_runs_remain_unavailable(self):
        summary = aggregate_runs([self.report('partial', True)])
        stats = summary['groups'][0]['statistics']['memory']
        self.assertEqual(stats['contributing_runs'], 0)
        self.assertEqual(stats['excluded_runs'], 1)
        self.assertIsNone(stats['mean'])
