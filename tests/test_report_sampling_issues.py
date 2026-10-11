import copy
import csv
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree

from test_aggregation import fixture_report

from aibenchmark_esw import cli
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.metrics.comparison import compare_runs, render_comparison
from aibenchmark_esw.metrics.exports import comparison_junit, summary_html
from aibenchmark_esw.metrics.measurements import measurement_summary
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.metrics.statistics import score_statistics
from aibenchmark_esw.reference_cache import ReferenceCache
from aibenchmark_esw.report_io import atomic_write_text
from aibenchmark_esw.report_schema import validate_report_structure
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


def collection():
    samples = [fixture_report(run_id='s1'), fixture_report(run_id='s2')]
    for sample in samples:
        sample['tasks'][0]['generation'].update(usage={'total_tokens': 100}, cost_usd=1, latency_seconds=.25)
    report = copy.deepcopy(samples[0])
    report['metadata']['run_id'] = 'collection'
    report['samples'] = samples
    report['sampling'] = {'requested': 2, 'completed': 2, 'pending': [], 'pass_k': [1]}
    report['generation_summary'] = measurement_summary([
        item for sample in samples for item in BenchmarkReporter.from_json_dict(sample)])
    return report


class TestReportSamplingIssues(unittest.TestCase):
    def test_summary_must_match_cost_tokens_latency_and_counts(self):
        for key, value in [('total_cost_usd', 0), ('known_total_tokens', 0), ('duration_tasks', 3),
                           ('usage_tasks', 1), ('generation_seconds', 100), ('cost_per_passed_task', 0)]:
            with self.subTest(key=key):
                report = collection()
                report['generation_summary'][key] = value
                with self.assertRaisesRegex(ValueError, 'generation_summary'):
                    BenchmarkReporter.from_json_dict(report)
        report = collection()
        report['generation_summary']['total_cost_usd'] += 1e-10
        BenchmarkReporter.from_json_dict(report)
        for measured in (0, None):
            report = fixture_report()
            report['tasks'][0]['generation'].update(usage={'total_tokens': measured}, cost_usd=measured)
            report['generation_summary'] = measurement_summary(BenchmarkReporter.from_json_dict(report))
            BenchmarkReporter.from_json_dict(report)

    def test_collection_conditions_cannot_hide_child_mismatch(self):
        for key in ('evaluator_sha256', 'dataset_sha256', 'compiler', 'static_analysis', 'scoring_policy'):
            report = collection()
            if isinstance(report['samples'][0]['metadata'][key], dict):
                report['samples'][0]['metadata'][key]['version'] = 'changed'
            else:
                report['samples'][0]['metadata'][key] = 'changed'
            with self.subTest(key=key), self.assertRaises(ValueError):
                BenchmarkReporter.from_json_dict(report)
        report = collection()
        report['samples'][0]['tasks'][0]['provenance']['task_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            BenchmarkReporter.from_json_dict(report)
        report = collection()
        report['samples'][0]['metadata'].update(created_at_utc='2026-10-01T00:00:00Z', source_revision='other')
        report['samples'][0]['metadata']['compiler']['path'] = '/other/bin/compiler'
        report['samples'][0]['tasks'][0]['generation']['resolved_model'] = 'other-snapshot'
        BenchmarkReporter.from_json_dict(report)

    def test_null_samples_and_unpaired_sampling_rejected_but_interruption_preserved(self):
        for value in (None, {}, 'bad', 1):
            report = fixture_report()
            report['samples'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'samples'):
                BenchmarkReporter.from_json_dict(report)
        report = fixture_report()
        report['sampling'] = {}
        with self.assertRaisesRegex(ValueError, 'sampling'):
            BenchmarkReporter.from_json_dict(report)
        report = collection()
        report.pop('generation_summary')
        report['samples'] = []
        report['sampling'].update(completed=0, pending=[0, 1])
        report['metadata']['run_status'] = 'interrupted'
        BenchmarkReporter.from_json_dict(report)
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            compare_runs([report, fixture_report(model='other')])
        self.assertIsNone(score_statistics([])['mean'])

    def test_bad_collection_cli_keeps_output_and_returns_readable_error(self):
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / 'bad.json', Path(directory) / 'output'
            report = fixture_report()
            report['samples'] = None
            source.write_text(json.dumps(report), encoding='utf-8')
            output.write_text('preserve')
            for command in ('report', 'aggregate', 'compare', 'trend'):
                args = [command, '--results', str(source), '--output', str(output)]
                if command == 'compare':
                    args.insert(3, str(source))
                with patch('sys.argv', ['aibenchmark-esw', *args]), redirect_stdout(io.StringIO()), \
                        redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as status:
                    cli.main()
                self.assertEqual(status.exception.code, 1)
                self.assertNotIn('Traceback', error.getvalue())
                self.assertIn('samples', error.getvalue())
                self.assertEqual(output.read_text(), 'preserve')

    def test_passing_functional_samples_with_measurement_errors_fail_pipeline(self):
        with TemporaryDirectory() as directory:
            for count in (1, 2):
                output = Path(directory) / f'{count}.json'
                junit = Path(directory) / f'{count}.xml'
                args = cli.build_parser().parse_args(['run', '--tasks', 'tier1_crc16', '--samples', str(count),
                    '--quiet', '--output', str(output), '--junit-output', str(junit)])
                with patch('aibenchmark_esw.evaluation.SizeAnalyzer.analyze',
                           side_effect=ValueError('measurement unavailable')), redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(args), 1)
                report = json.loads(output.read_text(encoding='utf-8'))
                if count == 2:
                    self.assertEqual(report['sampling']['statistics']['tier1_crc16']['pass_at_k']['1'], 1)
                self.assertTrue(output.is_file())
                ElementTree.parse(junit)

    def test_two_sample_interval_uses_student_t(self):
        stats = score_statistics([90, 92])
        self.assertAlmostEqual(stats['mean_ci95_approx']['lower'], 78.294, places=3)
        self.assertEqual(stats['mean_ci95_approx']['upper'], 100)
        self.assertIn('Student-t', stats['mean_ci95_approx']['method'])
        self.assertIsNone(score_statistics([100])['mean_ci95_approx'])

    def test_summary_html_has_only_applicable_filters_and_junit_is_valid_xml(self):
        document = summary_html('summary', [{'model': 'one', 'score': 90}], {})
        for control in ('status', 'tier', 'category'):
            self.assertNotIn('id="' + control + '"', document)
        self.assertNotIn('data-status="PASS"', document)
        self.assertIn('id="filter"', document)
        report = compare_runs([fixture_report(model='base'), fixture_report(model='candidate')])
        report['task_rows'][1]['model'] = 'candidate\x01'
        report['task_rows'][1]['task_id'] = 'one\x01'
        report['task_rows'][0]['task_id'] = 'one\x01'
        xml = comparison_junit(report, baseline_model='base')
        ElementTree.fromstring(xml)
        self.assertNotIn('\x01', xml)

    def test_attempt_coverage_uses_collection_attempts(self):
        checked = compare_runs([collection(), fixture_report(model='other')])
        for format_name in ('markdown', 'cli'):
            text = render_comparison(checked, format_name)
            self.assertIn('2/2', text)
            self.assertNotIn('2/1', text)

    def test_unmeasured_dimensions_are_unavailable_without_changing_rank_score(self):
        report = fixture_report()
        task = report['tasks'][0]
        task['size_metrics']['measured'] = False
        expected = 100 * (1 - task['weights']['memory'])
        task['scores'].update(memory=0, total=expected)
        checked = compare_runs([report, fixture_report(model='other')])
        row = next(item for item in checked['models'] if item['model'] == report['model_name'])
        self.assertEqual(row['score'], expected)
        self.assertIsNone(row['memory'])
        self.assertEqual(row['memory_measured_attempts'], 0)
        self.assertIn('Unavailable', render_comparison(checked))

    def test_parse_time_pass_k_validation_and_dry_run_preserves_checkpoint(self):
        for value in ('abc', '0', '1,1', '1,'):
            with redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as status:
                cli.build_parser().parse_args(['run', '--samples', '2', '--pass-k', value])
            self.assertEqual(status.exception.code, 2)
            self.assertIn('--pass-k', error.getvalue())
        self.assertEqual(cli.build_parser().parse_args(['run', '--pass-k', '2']).pass_k, [2])
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'checkpoint.json'
            output.write_text('preserve')
            args = cli.build_parser().parse_args(['run', '--tasks', 'tier1_crc16', '--dry-run', '--output', str(output)])
            with self.assertRaisesRegex(ValueError, 'Dry-run output already exists'):
                cli.cmd_run(args)
            self.assertEqual(output.read_text(), 'preserve')

    def test_transient_reference_failure_is_not_cached(self):
        loader, executor, cache = DatasetLoader(), ExecutionSandbox(), ReferenceCache()
        task = loader.get_task('tier1_crc16')
        reference = loader.get_reference_solution(task.id)
        with patch.object(executor, 'compile_and_test', side_effect=OSError('temporarily unavailable')):
            first, hit = cache.validate(task, reference, executor)
        self.assertIsNotNone(first.error)
        recovered, hit = cache.validate(task, reference, executor)
        self.assertIsNone(recovered.error)
        self.assertFalse(hit)

    def test_active_child_preserves_verifiable_spending_and_old_subtotals_are_labeled(self):
        report = collection()
        active = report['samples'].pop()
        active['metadata']['run_status'] = 'interrupted'
        report['sampling'].update(completed=1, pending=[1], active_sample=1, active_report=active)
        report['metadata']['run_status'] = 'interrupted'
        BenchmarkReporter.from_json_dict(report)
        report['sampling']['active_report']['tasks'][0]['generation']['cost_usd'] = 3
        with self.assertRaisesRegex(ValueError, 'generation_summary'):
            BenchmarkReporter.from_json_dict(report)
        report['sampling'].pop('active_report')
        BenchmarkReporter.from_json_dict(report)
        metadata = dict(report['metadata'], sampling=report['sampling'])
        self.assertIn('unverified', BenchmarkReporter.run_warning(metadata))

    def test_unavailable_resume_task_has_a_named_error(self):
        args = cli.build_parser().parse_args(['run', '--resume', 'unused.json'])
        with patch('aibenchmark_esw.resume.load_resume', return_value=fixture_report()), \
                self.assertRaisesRegex(ValueError, 'Saved resume task is unavailable: one'):
            cli._cmd_run_once(args)

    def test_asset_failure_report_remains_schema_valid(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'failed.json'
            args = cli.build_parser().parse_args(['eval', '--task', 'tier1_crc16', '--reference', '--output', str(output)])
            with patch('aibenchmark_esw.cli.validate_task_assets', return_value=['missing source']), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_eval(args), 1)
            report = json.loads(output.read_text(encoding='utf-8'))
            validate_report_structure(report)
            BenchmarkReporter.from_json_dict(report)

    def test_opt_in_regression_gate_saves_evidence_for_all_formats(self):
        with TemporaryDirectory() as directory:
            baseline, candidate = Path(directory) / 'base.json', Path(directory) / 'candidate.json'
            baseline.write_text(json.dumps(fixture_report(100, model='baseline')), encoding='utf-8')
            candidate.write_text(json.dumps(fixture_report(50, model='candidate')), encoding='utf-8')
            for format_name in ('markdown', 'csv', 'csv-long', 'html', 'junit', 'cli'):
                output = Path(directory) / ('comparison.' + format_name)
                tokens = ['compare', '--results', str(baseline), str(candidate), '--baseline-model', 'baseline',
                          '--format', format_name, '--output', str(output), '--fail-on-regression']
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.cmd_compare(cli.build_parser().parse_args(tokens)), 3)
                    self.assertTrue(output.stat().st_size)
                    exact = tokens + ['--regression-threshold', '50']
                    self.assertEqual(cli.cmd_compare(cli.build_parser().parse_args(exact)), 0)
            first = fixture_report(100, 'first')
            second = fixture_report(50, 'second')
            first['metadata']['created_at_utc'] = '2026-10-01T00:00:00Z'
            second['metadata']['created_at_utc'] = '2026-10-02T00:00:00Z'
            baseline.write_text(json.dumps(first), encoding='utf-8')
            candidate.write_text(json.dumps(second), encoding='utf-8')
            output = Path(directory) / 'trend.json'
            args = cli.build_parser().parse_args(['trend', '--results', str(baseline), str(candidate),
                '--fail-on-regression', '--format', 'json', '--output', str(output)])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_trend(args), 3)
            self.assertTrue(json.loads(output.read_text())['groups'][0]['runs'][1]['regressions'])
            second['metadata']['evaluator_sha256'] = 'other'
            candidate.write_text(json.dumps(second), encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_trend(args), 0)

    def test_csv_formula_labels_and_markdown_controls_are_escaped(self):
        for model in ('=HYPERLINK("bad")', '+SUM(1)', '-function()', '@SUM(1)', '\t=cmd'):
            checked = compare_runs([fixture_report(model=model), fixture_report(model='other')])
            for format_name in ('csv', 'csv-long'):
                rows = list(csv.DictReader(io.StringIO(render_comparison(checked, format_name))))
                self.assertTrue(any(row['model'] == "'" + model for row in rows))
        model = 'model|`<script>\r\nextra'
        results = BenchmarkReporter.from_json_dict(fixture_report(model=model))
        text = BenchmarkReporter.generate_markdown(results, model)
        self.assertIn('model\\|\\`&lt;script&gt;  extra', text)
        self.assertNotIn('<script>', text)

    @unittest.skipIf(os.name == 'nt', 'POSIX mode and umask semantics')
    def test_atomic_output_preserves_existing_mode_and_applies_umask_to_new_files(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.md'
            previous = os.umask(0o022)
            try:
                atomic_write_text(output, 'new')
                self.assertEqual(output.stat().st_mode & 0o777, 0o644)
                output.chmod(0o640)
                atomic_write_text(output, 'updated')
                self.assertEqual(output.stat().st_mode & 0o777, 0o640)
            finally:
                os.umask(previous)


if __name__ == '__main__':
    unittest.main()
