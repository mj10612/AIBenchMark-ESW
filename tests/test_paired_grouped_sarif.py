import copy
import csv
import io
import json
import statistics
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.comparison import compare_runs, render_comparison
from aibenchmark_esw.metrics.exports import generate_sarif
from aibenchmark_esw.metrics.groups import grouped_scores
from aibenchmark_esw.metrics.paired import paired_statistics
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.provenance import text_sha256


class TestPairedGroupedSarif(unittest.TestCase):
    def test_same_location_keeps_distinct_messages_and_severities(self):
        result = BenchmarkReporter.from_json_dict(fixture_report())[0]
        source = 'int f(void) { int a, b; return 0; }\n'
        result.safety_metrics.findings = [
            dict(rule_id='compiler.-Wunused-variable', engine='compiler',
                 severity=severity, message=message, file='candidate.c', line=1,
                 source_origin='candidate')
            for severity, message in (('warning', 'unused variable a'),
                                      ('warning', 'unused variable b'),
                                      ('error', 'unused variable a'))]
        result.provenance = {'candidate_sha256': text_sha256(source), 'sample_run_id': 'first'}
        second = copy.deepcopy(result)
        second.provenance['sample_run_id'] = 'second'
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'candidate.c').write_text(source, encoding='utf-8')
            for verified in (True, False):
                with self.subTest(verified=verified):
                    mapping = {result.task_id: 'candidate.c'} if verified else {}
                    findings = json.loads(generate_sarif(
                        [result, second], source_root=root, source_mapping=mapping))['runs'][0]['results']
                    self.assertEqual(len(findings), 3 if verified else 6)
                    self.assertEqual({(finding['properties']['severity'], finding['message']['text'])
                                      for finding in findings},
                                     {('warning', 'unused variable a'),
                                      ('warning', 'unused variable b'),
                                      ('error', 'unused variable a')})
                    if verified:
                        self.assertEqual(len({finding['partialFingerprints']['candidateLocation/v1']
                                              for finding in findings}), 3)
                        for finding in findings:
                            self.assertEqual(finding['properties']['sample_run_ids'], ['first', 'second'])

    def test_exact_p_values_ties_zeros_effect_and_bootstrap(self):
        # Published SciPy example, with distinct nonzero paired ranks.
        self.assertEqual(paired_statistics([6, 8, 14, 16, 23, 24, 28, 29, 41, -48, 49, 56, 60, -67, 75])['p_value'], 0.041259765625)
        same = paired_statistics([0, 0, 0])
        self.assertEqual(same['p_value'], 1)
        self.assertEqual(same['cohens_dz'], 0)
        positive = paired_statistics([1]*6)
        self.assertEqual(positive['p_value'], 2/64)
        self.assertIsNone(positive['cohens_dz'])
        self.assertEqual(positive['median_delta_ci95'], [1, 1])
        self.assertEqual(paired_statistics([-1]*6)['p_value'], positive['p_value'])
        varied = paired_statistics([1, 2, 3, 4])
        self.assertAlmostEqual(varied['cohens_dz'], 2.5/statistics.stdev([1, 2, 3, 4]))
        self.assertEqual(varied, paired_statistics([1, 2, 3, 4]))
        self.assertIsNone(paired_statistics([1])['median_delta_ci95'])
        self.assertLess(paired_statistics([1]*51)['p_value'], 0.001)

    def test_weighted_ranking_breakdowns_and_paired_exports(self):
        one = BenchmarkReporter.from_json_dict(fixture_report())[0]
        two = copy.deepcopy(one)
        two.task_id = 'hard'
        two.tier = 4
        failed = BenchmarkReporter.from_json_dict(fixture_report(0))[0]
        failed_hard = copy.deepcopy(failed)
        failed_hard.task_id = 'hard'
        failed_hard.tier = 4
        metadata = {'task_categories': {one.task_id: 'core_fundamentals', 'hard': 'concurrency'}}
        a = BenchmarkReporter.to_json_dict([one, failed_hard], 'easy', metadata)
        b = BenchmarkReporter.to_json_dict([failed, two], 'hard', metadata)
        for report in (a, b):
            for task in report['tasks']:
                task['model_name'] = report['model_name']
        comparison = compare_runs([a, b])
        self.assertEqual([row['model'] for row in comparison['models']], ['hard', 'easy'])
        self.assertEqual([row['score'] for row in comparison['models']], [50, 50])
        self.assertEqual([row['tier_weighted_score'] for row in comparison['models']], [80, 20])
        groups = comparison['models'][1]
        self.assertEqual(groups['by_tier']['4']['delta_vs_baseline'], -100)
        self.assertEqual(groups['by_category']['concurrency']['pass_at_1_pct'], 0)
        pair = comparison['paired']['comparisons'][0]
        self.assertEqual(pair['matched_tasks'], 2)
        self.assertEqual(pair['unmatched_tasks'], 0)
        self.assertEqual(pair['task_deltas']['hard'], -100)
        self.assertIn('Paired task differences', render_comparison(comparison, 'markdown'))
        self.assertIn('Paired task differences', render_comparison(comparison, 'html'))
        rows = list(csv.DictReader(io.StringIO(render_comparison(comparison, 'csv-long'))))
        self.assertEqual({row['scope'] for row in rows}, {'task', 'by_tier', 'by_category'})
        suite = ElementTree.fromstring(render_comparison(comparison, 'junit'))
        self.assertEqual(suite.attrib['tests'], '5')
        informational = suite.find("testcase[@name='paired-task-statistics']")
        self.assertIsNone(informational.find('failure'))
        self.assertEqual(json.loads(informational.find('system-out').text)['matched_tasks'], 2)
        self.assertEqual(grouped_scores([one, failed_hard], metadata)['tier_weighted_score'], 20)

    def test_tampered_weighted_summary_and_incompatible_tier_are_rejected(self):
        report = fixture_report()
        results = BenchmarkReporter.from_json_dict(report)
        published = BenchmarkReporter.to_json_dict(results, report['model_name'], report['metadata'])
        published['tier_weighted_score'] = 99
        with self.assertRaisesRegex(ValueError, 'tier_weighted_score'):
            BenchmarkReporter.from_json_dict(published)
        other = fixture_report(model='other')
        other['tasks'][0]['tier'] = 4
        with self.assertRaisesRegex(ValueError, 'tiers'):
            compare_runs([report, other])

    def test_persistent_source_hash_uri_fingerprints_and_sample_deduplication(self):
        result = BenchmarkReporter.from_json_dict(fixture_report())[0]
        result.safety_metrics.findings = [dict(rule_id='probe', engine='builtin', severity='warning', message='diagnostic', file='candidate.c', line=2, source_origin='candidate')]
        source = 'int answer(void){\nreturn 0;\n}\n'
        result.provenance = {'candidate_sha256': text_sha256(source), 'sample_run_id': 'first'}
        second = copy.deepcopy(result)
        second.provenance['sample_run_id'] = 'second'
        with TemporaryDirectory() as directory:
            root = Path(directory)
            saved = root / 'nested' / '코드 space.c'
            saved.parent.mkdir()
            saved.write_text(source, encoding='utf-8')
            mapping = {result.task_id: saved.relative_to(root).as_posix()}
            first = json.loads(generate_sarif([result, second], source_root=root, source_mapping=mapping))['runs'][0]['results']
            self.assertEqual(len(first), 1)
            result.provenance['candidate_source'] = str(saved)
            absolute = json.loads(generate_sarif([result], source_root=root))['runs'][0]['results'][0]
            self.assertEqual(first[0]['partialFingerprints'], absolute['partialFingerprints'])
            self.assertEqual(first[0]['properties']['sample_run_ids'], ['first', 'second'])
            self.assertIn('%20', first[0]['locations'][0]['physicalLocation']['artifactLocation']['uri'])
            rerun = json.loads(generate_sarif([second], source_root=root, source_mapping=mapping))['runs'][0]['results'][0]
            self.assertEqual(first[0]['partialFingerprints'], rerun['partialFingerprints'])
            separate = root / 'other' / saved.name
            separate.parent.mkdir()
            separate.write_text(source, encoding='utf-8')
            distinct_mapping = {result.task_id + ':first': saved.relative_to(root).as_posix(),
                                result.task_id + ':second': separate.relative_to(root).as_posix()}
            distinct = json.loads(generate_sarif([result, second], source_root=root, source_mapping=distinct_mapping))['runs'][0]['results']
            self.assertEqual(len(distinct), 2)
            self.assertNotEqual(distinct[0]['partialFingerprints'], distinct[1]['partialFingerprints'])
            saved.write_text('changed', encoding='utf-8')
            mismatch = json.loads(generate_sarif([result], source_root=root, source_mapping=mapping))['runs'][0]['results'][0]
            self.assertNotIn('locations', mismatch)
            self.assertNotIn('partialFingerprints', mismatch)
            self.assertEqual(mismatch['properties']['source_mapping'], 'diagnostic-only')
            saved.unlink()
            missing = json.loads(generate_sarif([result], source_root=root, source_mapping=mapping))['runs'][0]['results'][0]
            self.assertIn('missing', missing['properties']['mapping_diagnostic'])
