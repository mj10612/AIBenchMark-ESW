import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from test_aggregation import fixture_report

from aibenchmark_esw import cli
from aibenchmark_esw.metrics.comparison import compare_runs
from aibenchmark_esw.metrics.exports import comparison_junit


def comparison_reports(task_ids, models=(('baseline', 100), ('candidate', 0))):
    reports = []
    for model, score in models:
        report = fixture_report(score, run_id=model, model=model)
        original = report['tasks'][0]
        policy = report['metadata']['scoring_policy']['tasks']['one']
        report['tasks'] = []
        for task_id in task_ids:
            task = copy.deepcopy(original)
            task['task_id'] = task_id
            task['provenance']['task_sha256'] = 'task-' + task_id
            report['tasks'].append(task)
        report['metadata']['selected_tasks'] = list(task_ids)
        report['metadata']['scoring_policy']['tasks'] = {
            task_id: copy.deepcopy(policy) for task_id in task_ids}
        reports.append(report)
    return reports


class TestComparisonJUnitIdentity(unittest.TestCase):
    def assert_unique_identities(self, suite):
        cases = suite.findall('testcase')
        identities = [(case.get('classname'), case.get('name')) for case in cases]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(int(suite.get('tests')), len(cases))

    def test_statistics_cannot_replace_regressing_task_cases(self):
        for task_ids in (['paired-task-statistics'],
                         ['paired-task-statistics', 'paired-task-statistics-1', 'paired-task-statistics-2']):
            with self.subTest(tasks=task_ids):
                reports = comparison_reports(task_ids)
                suite = ET.fromstring(comparison_junit(compare_runs(reports), 'baseline'))
                self.assert_unique_identities(suite)
                self.assertEqual(suite.get('failures'), str(len(task_ids)))
                self.assertEqual(len(suite.findall('testcase')), 2 * len(task_ids) + 1)
                candidate = [case for case in suite.findall('testcase') if case.get('classname') == 'candidate']
                for task_id in task_ids:
                    case = next(case for case in candidate if case.get('name') == task_id)
                    self.assertEqual(case.find('failure').get('type'), 'score-regression')
                    self.assertIn('delta -100', case.findtext('system-out'))
                statistics = next(case for case in candidate if case.get('name') not in task_ids)
                self.assertIsNone(statistics.find('failure'))
                evidence = json.loads(statistics.findtext('system-out'))
                self.assertEqual(evidence['matched_tasks'], len(task_ids))
                self.assertEqual(evidence['task_deltas'], dict.fromkeys(task_ids, -100))

    def test_multiple_models_keep_separate_task_and_statistics_identities(self):
        reports = comparison_reports(['paired-task-statistics'],
                                     (('baseline', 100), ('candidate<&>', 0), ('other', 50)))
        suite = ET.fromstring(comparison_junit(compare_runs(reports), 'baseline'))
        self.assert_unique_identities(suite)
        self.assertEqual((suite.get('tests'), suite.get('failures')), ('5', '2'))
        for model, delta in (('candidate<&>', -100), ('other', -50)):
            cases = [case for case in suite.findall('testcase') if case.get('classname') == model]
            task = next(case for case in cases if case.get('name') == 'paired-task-statistics')
            self.assertIsNotNone(task.find('failure'))
            statistics = next(case for case in cases if case is not task)
            self.assertEqual(json.loads(statistics.findtext('system-out'))['median_delta'], delta)

    def test_identity_allocation_uses_xml_normalized_task_names(self):
        reports = comparison_reports(['paired-task-statistics\x00'])
        suite = ET.fromstring(comparison_junit(compare_runs(reports), 'baseline'))
        self.assert_unique_identities(suite)
        failure = suite.find('testcase/failure')
        self.assertIsNotNone(failure)
        self.assertEqual(suite.get('failures'), '1')

    def test_offline_cli_export_preserves_unique_regression_evidence(self):
        reports = comparison_reports(['paired-task-statistics'])
        with TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = [root / 'baseline.json', root / 'candidate.json']
            for path, report in zip(inputs, reports):
                path.write_text(json.dumps(report), encoding='utf-8')
            output = root / 'comparison.xml'
            args = cli.build_parser().parse_args([
                'compare', '--results', *map(str, inputs), '--format', 'junit',
                '--baseline-model', 'baseline', '--fail-on-regression', '--output', str(output)])
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                status = cli.cmd_compare(args)
            self.assertEqual(status, 3)
            suite = ET.parse(output).getroot()
            self.assert_unique_identities(suite)
            self.assertEqual((suite.get('tests'), suite.get('failures')), ('3', '1'))
            failures = [case for case in suite.findall('testcase') if case.find('failure') is not None]
            self.assertEqual([(case.get('classname'), case.get('name')) for case in failures],
                             [('candidate', 'paired-task-statistics')])
