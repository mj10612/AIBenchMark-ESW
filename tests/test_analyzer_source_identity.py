import json
import subprocess
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.metrics.sarif_sources import generate_sarif
from aibenchmark_esw.provenance import text_sha256
from aibenchmark_esw.sandbox.process_runner import OutputLimitExceeded
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestAnalyzerSourceIdentity(unittest.TestCase):
    def test_concurrent_failure_status_stays_with_invocation(self):
        analyzer = StaticAnalyzer(cppcheck_cmd='fake-cppcheck')
        paused, release = threading.Event(), threading.Event()
        original = analyzer._run_cppcheck

        def run(cmd, **kwargs):
            if Path(cmd[-1]).name == 'a.c':
                raise subprocess.TimeoutExpired('A-specific command', 30)
            return SimpleNamespace(stdout=b'', stderr=b'B-specific failure', returncode=7)

        def wrapped(source, *args):
            value = original(source, *args)
            if source.name == 'a.c':
                paused.set()
                self.assertTrue(release.wait(5))
            return value

        with TemporaryDirectory() as directory, patch('aibenchmark_esw.sandbox.static_analyzer.run_bounded', run), patch.object(analyzer, '_run_cppcheck', wrapped):
            a, b = Path(directory) / 'a.c', Path(directory) / 'b.c'
            a.write_text('int a;')
            b.write_text('int b;')
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = pool.submit(analyzer.analyze, a)
                try:
                    self.assertTrue(paused.wait(5))
                    other = pool.submit(analyzer.analyze, b).result(timeout=5)
                finally:
                    release.set()
                first = pending.result(timeout=5)
        self.assertEqual(first.cppcheck_status, 'timeout')
        self.assertIn('A-specific', first.cppcheck_diagnostic)
        self.assertEqual(other.cppcheck_status, 'failed')
        self.assertIn('B-specific', other.cppcheck_diagnostic)

    def test_cppcheck_preserves_header_identity_and_candidate_origin(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'candidate.c'
            source.write_text('int candidate;')
            header = source.parent / 'include' / 'candidate.c'
            output = f'warning:probe:{header}:1:header\nwarning:probe:{source}:1:source\nwarning:probe:candidate.c:1:ambiguous\n'.encode()
            with patch('aibenchmark_esw.sandbox.static_analyzer.run_bounded', return_value=SimpleNamespace(stdout=output, stderr=b'', returncode=0)):
                findings = StaticAnalyzer(cppcheck_cmd='fake').analyze(source).findings
            self.assertEqual(findings[0]['file'], str(header))
            self.assertEqual([item['source_origin'] for item in findings], ['other', 'candidate', 'unknown'])

    def test_output_limit_and_success_remain_independent(self):
        analyzer = StaticAnalyzer(cppcheck_cmd='fake')
        paused, release = threading.Event(), threading.Event()
        original = analyzer._run_cppcheck

        def run(cmd, **kwargs):
            if Path(cmd[-1]).name == 'limited.c':
                raise OutputLimitExceeded(b'overflow', 10)
            return SimpleNamespace(stdout=b'', stderr=b'', returncode=0)

        def wrapped(source, *args):
            value = original(source, *args)
            if source.name == 'limited.c':
                paused.set()
                self.assertTrue(release.wait(5))
            return value

        with TemporaryDirectory() as directory, patch('aibenchmark_esw.sandbox.static_analyzer.run_bounded', run), patch.object(analyzer, '_run_cppcheck', wrapped):
            limited, success = Path(directory) / 'limited.c', Path(directory) / 'success.c'
            limited.write_text('int limited;')
            success.write_text('int success;')
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = pool.submit(analyzer.analyze, limited)
                try:
                    self.assertTrue(paused.wait(5))
                    completed = pool.submit(analyzer.analyze, success).result(timeout=5)
                finally:
                    release.set()
                failed = pending.result(timeout=5)
        self.assertEqual(failed.cppcheck_status, 'failed')
        self.assertIn('Output limit', failed.cppcheck_diagnostic)
        self.assertEqual(completed.cppcheck_status, 'completed')
        self.assertIsNone(completed.cppcheck_diagnostic)

    def test_source_origin_roundtrips_and_invalid_origin_rejected(self):
        report = fixture_report()
        safety = report['tasks'][0]['safety_metrics']
        safety.update(warning_count=1, findings=[dict(rule_id='probe', engine='cppcheck', severity='warning', message='probe', file='temporary.c', source_origin='candidate')])
        report['tasks'][0]['scores'].update(safety=97, total=99.4)
        parsed = BenchmarkReporter.from_json_dict(report)
        self.assertEqual(parsed[0].safety_metrics.findings[0]['source_origin'], 'candidate')
        safety['findings'][0]['source_origin'] = 'unverified'
        with self.assertRaisesRegex(ValueError, 'source_origin'):
            BenchmarkReporter.from_json_dict(report)

    def test_only_verified_candidate_origin_and_valid_lines_publish(self):
        result = BenchmarkReporter.from_json_dict(fixture_report())[0]
        source = 'int candidate(void) { return 0; }\n'
        result.provenance = {'candidate_sha256': text_sha256(source)}
        cases = [
            ('api.h', 40, None, False),
            ('include/candidate.c', 1, None, False),
            ('candidate.c', 1, None, False),
            ('temporary.c', 1, 'candidate', True),
            ('temporary.c', 2, 'candidate', False),
            ('api.h', 1, 'other', False),
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'candidate.c').write_text(source)
            cases.append((str(root / 'candidate.c'), 1, None, True))
            for file, line, origin, located in cases:
                with self.subTest(file=file, line=line, origin=origin):
                    finding = dict(rule_id='probe', engine='cppcheck', severity='warning', message='probe', file=file, line=line)
                    if origin:
                        finding['source_origin'] = origin
                    result.safety_metrics.findings = [finding]
                    entry = json.loads(generate_sarif([result], source_root=root, source_mapping={result.task_id: 'candidate.c'}))['runs'][0]['results'][0]
                    self.assertEqual('locations' in entry, located)
                    self.assertEqual(entry['properties']['source_mapping'], 'verified' if located else 'diagnostic-only')
                    if not located:
                        self.assertTrue(entry['properties']['mapping_diagnostic'])

    def test_distinct_messages_and_header_paths_are_not_collapsed(self):
        result = BenchmarkReporter.from_json_dict(fixture_report())[0]
        source = 'int candidate;\n'
        result.provenance = {'candidate_sha256': text_sha256(source)}
        base = dict(rule_id='probe', engine='cppcheck', severity='warning', line=1)
        result.safety_metrics.findings = [
            dict(base, file='temporary.c', source_origin='candidate', message='first'),
            dict(base, file='temporary.c', source_origin='candidate', message='second'),
            dict(base, file='include/a.h', source_origin='other', message='header'),
            dict(base, file='other/a.h', source_origin='other', message='header'),
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'candidate.c').write_text(source)
            entries = json.loads(generate_sarif([result], source_root=root, source_mapping={result.task_id: 'candidate.c'}))['runs'][0]['results']
        self.assertEqual(len(entries), 4)
        self.assertNotEqual(entries[0]['partialFingerprints'], entries[1]['partialFingerprints'])
