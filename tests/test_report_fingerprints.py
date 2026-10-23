import copy
import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_aggregation import fixture_report
from test_collection_exports import collection

from aibenchmark_esw import cli
from aibenchmark_esw.metrics.aggregation import aggregate_runs
from aibenchmark_esw.metrics.comparison import compare_runs
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.resume import load_resume, validate_resume


def fingerprinted_report(run_id='first', model='provider/alias'):
    report = fixture_report(run_id=run_id, model=model)
    report['metadata']['task_fingerprints'] = {'one': 'a' * 64}
    report['tasks'][0]['provenance']['task_sha256'] = 'a' * 64
    return report


class TestReportFingerprints(unittest.TestCase):
    def test_reader_rejects_conflicts_even_without_run_status(self):
        for changed in ('metadata', 'task'):
            for status in ('completed', None):
                with self.subTest(changed=changed, status=status):
                    report = fingerprinted_report()
                    if changed == 'metadata':
                        report['metadata']['task_fingerprints']['one'] = 'b' * 64
                    else:
                        report['tasks'][0]['provenance']['task_sha256'] = 'b' * 64
                    if status is None:
                        report['metadata'].pop('run_status')
                    with self.assertRaisesRegex(ValueError, '[Ff]ingerprint.*one'):
                        BenchmarkReporter.from_json_dict(report)

    def test_comparison_aggregation_and_resume_reject_contradictory_evidence(self):
        report = fingerprinted_report()
        report['metadata']['task_fingerprints']['one'] = 'b' * 64
        operations = {
            'comparison': lambda: compare_runs([report, fingerprinted_report('other', 'other')]),
            'aggregation': lambda: aggregate_runs([report]),
            'resume': lambda: validate_resume(report, copy.deepcopy(report['metadata']), [Namespace(id='one')]),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name), self.assertRaisesRegex(ValueError, '[Ff]ingerprint.*one'):
                operation()

    def test_collection_cannot_hide_the_same_contradiction_in_every_sample(self):
        report = collection([fingerprinted_report('first'), fingerprinted_report('second')])
        for member in [report, *report['samples']]:
            member['metadata']['task_fingerprints']['one'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, '[Ff]ingerprint.*one'):
            BenchmarkReporter.from_json_dict(report)

    def test_fingerprint_metadata_requires_a_mapping(self):
        for invalid in ([], '', False, 1):
            with self.subTest(invalid=invalid):
                report = fingerprinted_report()
                report['metadata']['task_fingerprints'] = invalid
                with self.assertRaisesRegex(ValueError, 'task_fingerprints'):
                    BenchmarkReporter.from_json_dict(report)

    def test_recorded_fingerprints_require_nonempty_strings(self):
        for invalid in ('', ' ', False, 1, [], {}):
            with self.subTest(invalid=invalid):
                report = fingerprinted_report()
                report['metadata']['task_fingerprints']['one'] = invalid
                report['tasks'][0]['provenance']['task_sha256'] = copy.deepcopy(invalid)
                with self.assertRaisesRegex(ValueError, '[Ff]ingerprint.*one'):
                    BenchmarkReporter.from_json_dict(report)

    def test_matching_external_fingerprints_remain_portable(self):
        report = fingerprinted_report()
        original = copy.deepcopy(report)
        self.assertEqual(BenchmarkReporter.from_json_dict(report)[0].provenance['task_sha256'], 'a' * 64)
        comparison = compare_runs([report, fingerprinted_report('other', 'other')])
        self.assertEqual([row['provenance'] for row in comparison['models']], ['Recorded', 'Recorded'])
        self.assertEqual(aggregate_runs([report])['groups'][0]['runs'], 1)
        self.assertEqual(report, original)

    def test_missing_legacy_evidence_remains_unknown(self):
        for missing in ('metadata', 'metadata_null', 'metadata_entry', 'metadata_entry_null',
                        'provenance', 'provenance_null', 'task_entry', 'task_entry_null'):
            with self.subTest(missing=missing):
                report = fingerprinted_report()
                if missing == 'metadata':
                    report['metadata'].pop('task_fingerprints')
                elif missing == 'metadata_null':
                    report['metadata']['task_fingerprints'] = None
                elif missing == 'metadata_entry':
                    report['metadata']['task_fingerprints'] = {}
                elif missing == 'metadata_entry_null':
                    report['metadata']['task_fingerprints']['one'] = None
                elif missing == 'provenance':
                    report['tasks'][0].pop('provenance')
                elif missing == 'provenance_null':
                    report['tasks'][0]['provenance'] = None
                elif missing == 'task_entry':
                    report['tasks'][0]['provenance'] = {}
                else:
                    report['tasks'][0]['provenance']['task_sha256'] = None
                original = copy.deepcopy(report)
                results = BenchmarkReporter.from_json_dict(report)
                if missing.startswith(('provenance', 'task_entry')):
                    self.assertIsNone((results[0].provenance or {}).get('task_sha256'))
                self.assertEqual(report, original)

    def test_resume_rejects_before_restoring_options_or_changing_files(self):
        report = fingerprinted_report()
        report['metadata']['task_fingerprints']['one'] = 'b' * 64
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / 'checkpoint.json', Path(directory) / 'output.json'
            source.write_text(json.dumps(report), encoding='utf-8')
            output.write_text('preserve', encoding='utf-8')
            args = Namespace(resume=source, output=output, model='original', _explicit_options=set())
            original = copy.deepcopy(vars(args))
            saved = source.read_bytes()
            with self.assertRaisesRegex(ValueError, '[Ff]ingerprint.*one'):
                load_resume(args)
            self.assertEqual(vars(args), original)
            self.assertEqual(source.read_bytes(), saved)
            self.assertEqual(output.read_text(encoding='utf-8'), 'preserve')

    def test_cli_rejects_conflicts_before_exporting(self):
        report = fingerprinted_report()
        report['metadata']['task_fingerprints']['one'] = 'b' * 64
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
                self.assertIn('fingerprint', error.getvalue().lower())
                self.assertNotIn('Traceback', error.getvalue())
                self.assertEqual(output.read_text(encoding='utf-8'), 'preserve')
