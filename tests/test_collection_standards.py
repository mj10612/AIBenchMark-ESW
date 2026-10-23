import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_aggregation import fixture_report
from test_collection_exports import collection

from aibenchmark_esw import cli
from aibenchmark_esw.metrics.comparison import compare_runs
from aibenchmark_esw.metrics.reporter import BenchmarkReporter


class TestCollectionStandards(unittest.TestCase):
    def test_wrapper_cannot_contradict_all_completed_samples(self):
        samples = [fixture_report(run_id='first'), fixture_report(run_id='second')]
        for sample in samples:
            sample['tasks'][0]['effective_standard'] = 'c11'
        report = collection(samples)
        report['tasks'][0]['effective_standard'] = 'c99'
        with self.assertRaisesRegex(ValueError, 'effective_standard'):
            BenchmarkReporter.from_json_dict(report)
        with self.assertRaisesRegex(ValueError, 'effective_standard'):
            compare_runs([report, fixture_report(model='other')])

    def test_unknown_wrapper_cannot_hide_conflicting_sample_standards(self):
        report = collection([fixture_report(run_id='first'), fixture_report(run_id='second')])
        report['tasks'][0]['effective_standard'] = None
        report['samples'][1]['tasks'][0]['effective_standard'] = 'c11'
        with self.assertRaisesRegex(ValueError, 'effective_standard'):
            BenchmarkReporter.from_json_dict(report)

    def test_comparison_checks_known_samples_when_first_sample_did_not_compile(self):
        failed = fixture_report(0, run_id='failed')
        failed['tasks'][0].update(compiled=False, effective_standard=None)
        failed['tasks'][0]['test_result'].update(
            total=0, passed=0, failed=0, completed=False, returncode=None)
        failed['tasks'][0]['scores'] = dict.fromkeys(('functional', 'memory', 'safety', 'total'), 0)
        compiled = fixture_report(run_id='compiled')
        compiled['tasks'][0]['effective_standard'] = 'c11'
        report = collection([failed, compiled])
        results = BenchmarkReporter.from_json_dict(report)
        self.assertIsNone(results[0].effective_standard)
        with self.assertRaisesRegex(ValueError, 'C standards'):
            compare_runs([report, fixture_report(model='other')])
        compatible = fixture_report(model='other')
        compatible['tasks'][0]['effective_standard'] = 'c11'
        comparison = compare_runs([report, compatible])
        row = next(row for row in comparison['models'] if row['model'] == report['model_name'])
        self.assertEqual(row['samples'], 2)
        self.assertEqual(row['pass_at_1_pct'], 50)

    def test_active_sample_cannot_contradict_completed_standard(self):
        active = fixture_report(run_id='active')
        active['metadata']['run_status'] = 'interrupted'
        active['tasks'][0]['effective_standard'] = 'c11'
        report = collection([fixture_report(run_id='completed')], active, 'interrupted')
        with self.assertRaisesRegex(ValueError, 'effective_standard'):
            BenchmarkReporter.from_json_dict(report)

    def test_unknown_pending_standard_remains_unavailable(self):
        for absent in (False, True):
            with self.subTest(absent=absent):
                active = fixture_report(0, run_id='active')
                active['metadata'].update(run_status='interrupted', pending_tasks=['one'])
                task = active['tasks'][0]
                task.update(compiled=False, effective_standard=None)
                task['test_result'].update(total=0, passed=0, failed=0, completed=False, returncode=None)
                task['scores'] = dict.fromkeys(('functional', 'memory', 'safety', 'total'), 0)
                if absent:
                    task.pop('effective_standard')
                report = collection([fixture_report(run_id='completed')], active, 'interrupted')
                BenchmarkReporter.from_json_dict(report)
                self.assertIsNone(BenchmarkReporter.from_json_dict(active)[0].effective_standard)

    def test_consistent_fallback_standard_is_accepted(self):
        samples = [fixture_report(run_id='first'), fixture_report(run_id='second')]
        for sample in samples:
            sample['tasks'][0]['effective_standard'] = 'c11'
        report = collection(samples)
        self.assertEqual(BenchmarkReporter.from_json_dict(report)[0].effective_standard, 'c11')
        other = fixture_report(model='other')
        other['tasks'][0]['effective_standard'] = 'c11'
        self.assertEqual(len(compare_runs([report, other])['models']), 2)

    def test_cli_rejects_contradiction_before_replacing_export(self):
        report = collection([fixture_report(run_id='first'), fixture_report(run_id='second')])
        report['tasks'][0]['effective_standard'] = 'c11'
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / 'report.json', Path(directory) / 'report.md'
            source.write_text(json.dumps(report), encoding='utf-8')
            output.write_text('preserve', encoding='utf-8')
            for arguments in (
                ['validate-report', str(source)],
                ['report', '--results', str(source), '--format', 'markdown', '--output', str(output)],
            ):
                with self.subTest(arguments=arguments), patch('sys.argv', ['aibenchmark-esw', *arguments]), \
                        redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as error, \
                        self.assertRaises(SystemExit) as status:
                    cli.main()
                self.assertEqual(status.exception.code, 1)
                self.assertIn('effective_standard', error.getvalue())
                self.assertNotIn('Traceback', error.getvalue())
                self.assertEqual(output.read_text(encoding='utf-8'), 'preserve')
