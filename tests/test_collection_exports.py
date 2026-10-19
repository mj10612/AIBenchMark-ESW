import copy
import io
import json
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.github_summary import github_summary
from aibenchmark_esw.metrics.junit import render_junit
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.sampling import sampling_statistics


def collection(samples, active=None, status='completed', requested=2):
    report = copy.deepcopy(samples[0] if samples else active)
    report['metadata'].update(run_id='collection', run_status=status)
    report['samples'] = samples
    report['sampling'] = dict(requested=requested, completed=len(samples),
        pending=list(range(len(samples), requested)), pass_k=[1, 2],
        statistics=sampling_statistics(samples, [1, 2]), active_sample=len(samples) if active else None)
    if active:
        report['sampling']['active_report'] = active
    return report


class TestCollectionExports(unittest.TestCase):
    def test_xml_control_characters_cannot_merge_distinct_sample_ids(self):
        from aibenchmark_esw.metrics.junit import render_collection_junit
        report = collection([fixture_report(100, 'a\x00b'), fixture_report(100, 'ab')])
        suite = ET.fromstring(render_collection_junit(report))
        identities = {(case.get('classname'), case.get('name')) for case in suite.findall('testcase')}
        self.assertEqual(len(identities), 2)
        self.assertTrue(any('a%00b' in classname for classname, _ in identities))

    def test_junit_flat_results_keep_sample_identity(self):
        results = []
        for sample in [fixture_report(100, 'sample-1'), fixture_report(0, 'sample-2')]:
            values = BenchmarkReporter.from_json_dict(sample)
            for value in values:
                value.provenance['sample_run_id'] = sample['metadata']['run_id']
            results.extend(values)
        suite = ET.fromstring(render_junit(results, 'provider/alias'))
        cases = suite.findall('testcase')
        self.assertEqual(len({(case.get('classname'), case.get('name')) for case in cases}), 2)
        self.assertEqual(suite.get('failures'), '1')
        self.assertEqual({case.find("properties/property[@name='sample_run_id']").get('value') for case in cases}, {'sample-1', 'sample-2'})

    def test_summary_reports_collection_mean_and_coverage(self):
        summary = github_summary(collection([fixture_report(100, 'sample-1'), fixture_report(0, 'sample-2')]))
        self.assertIn('Run status: completed', summary)
        self.assertIn('1/2', summary)
        self.assertIn('50.00', summary)
        self.assertIn('Pass@2', summary)

    def test_active_pending_slots_are_skipped_and_not_scored(self):
        active = fixture_report(0, 'active')
        active['metadata'].update(run_status='interrupted', pending_tasks=['one'])
        active['tasks'][0]['test_result'].update(total=0, passed=0, failed=0, completed=False, returncode=None)
        active['tasks'][0]['scores'] = dict.fromkeys(('functional', 'memory', 'safety', 'total'), 0)
        report = collection([], active, 'interrupted')
        from aibenchmark_esw.metrics import junit
        self.assertTrue(hasattr(junit, 'render_collection_junit'))
        suite = ET.fromstring(junit.render_collection_junit(report))
        self.assertEqual(suite.get('tests'), '1')
        self.assertEqual(suite.get('skipped'), '1')
        summary = github_summary(report)
        self.assertIn('Run status: interrupted', summary)
        self.assertIn('0/0', summary)
        self.assertIn('Pending', summary)
        self.assertIn('Unavailable', summary)

    def test_active_failure_and_completed_pass_both_remain_visible(self):
        from aibenchmark_esw.metrics.junit import render_collection_junit
        active = fixture_report(0, 'active')
        active['metadata']['run_status'] = 'aborted'
        report = collection([fixture_report(100, 'done')], active, 'aborted')
        suite = ET.fromstring(render_collection_junit(report))
        self.assertEqual(suite.get('tests'), '2')
        self.assertEqual(suite.get('failures'), '1')
        self.assertEqual(suite.get('skipped'), '0')
        summary = github_summary(report)
        self.assertIn('Run status: aborted', summary)
        self.assertIn('1/2', summary)
        self.assertIn('50.00', summary)

    def test_collection_functional_pass_and_evaluation_error_are_separate(self):
        first, second = fixture_report(100, 'one'), fixture_report(100, 'two')
        second['tasks'][0]['error_log'] = 'measurement unavailable'
        report = collection([first, second])
        report['model_name'] = '<model>|`label`'
        report['tasks'][0]['model_name'] = report['model_name']
        for sample in report['samples']:
            sample['model_name'] = report['model_name']
            sample['tasks'][0]['model_name'] = report['model_name']
        summary = github_summary(report)
        self.assertIn('2/2 | 0 | 1 | 100.00', summary)
        self.assertIn('&lt;model&gt;\\|\\`label\\`', summary)

    def test_report_regenerated_collection_junit_agrees_with_direct_renderer(self):
        from aibenchmark_esw import cli
        from aibenchmark_esw.metrics.junit import render_collection_junit
        active = fixture_report(0, 'active')
        active['metadata']['run_status'] = 'interrupted'
        report = collection([], active, 'interrupted')
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / 'collection.json', Path(directory) / 'collection.xml'
            source.write_text(json.dumps(report), encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                result = cli.cmd_report(cli.build_parser().parse_args(['report', '--results', str(source),
                    '--format', 'junit', '--output', str(output)]))
            self.assertEqual(result, 0)
            self.assertEqual(output.read_text(encoding='utf-8'), render_collection_junit(report))
