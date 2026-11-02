import csv
import io
import unittest

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.trend import render_trend, trend_runs


class TestTrendProvenance(unittest.TestCase):
    def test_replay_origin_survives_all_history_exports(self):
        report = fixture_report()
        report['metadata'].update(created_at_utc='2026-11-03T00:00:00Z', run_mode='replay',
                                  origin_run_id='original-run', origin_model_name='original-model')
        report['tasks'][0]['generation'] = None
        summary = trend_runs([report])
        row = summary['groups'][0]['runs'][0]
        self.assertEqual(row['run_mode'], 'replay')
        self.assertEqual(row['origin_run_id'], 'original-run')
        self.assertEqual(row['origin_model_name'], 'original-model')
        for format_name in ('json', 'csv', 'html', 'markdown', 'cli'):
            with self.subTest(format_name=format_name):
                text = render_trend(summary, format_name)
                self.assertIn('replay', text)
                self.assertIn('original-run', text)
        csv_row = next(csv.DictReader(io.StringIO(render_trend(summary, 'csv'))))
        self.assertEqual(csv_row['run_mode'], 'replay')
        self.assertIn('no new generation or spend', render_trend(summary))

    def test_legacy_mode_follows_comparison_inference(self):
        for generated, expected in ((True, 'generation'), (False, 'local')):
            with self.subTest(expected=expected):
                report = fixture_report()
                report['metadata']['created_at_utc'] = '2026-11-03T00:00:00Z'
                if not generated:
                    del report['metadata']['generation_settings']
                row = trend_runs([report])['groups'][0]['runs'][0]
                self.assertEqual(row['run_mode'], expected)
                self.assertIsNone(row['origin_run_id'])
