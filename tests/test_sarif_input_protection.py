import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from test_aggregation import fixture_report

from aibenchmark_esw.cli import build_parser, cmd_report
from aibenchmark_esw.provenance import text_sha256


class TestSarifInputProtection(unittest.TestCase):
    def test_cli_preserves_mapping_and_candidate_inputs(self):
        for mode in ('mapping', 'relative', 'absolute', 'provenance', 'sample', 'no-findings'):
            for alias in ('direct', 'hardlink', 'symlink'):
                with self.subTest(mode=mode, alias=alias), TemporaryDirectory() as directory:
                    root = Path(directory)
                    candidate = root / 'candidate.c'
                    source = 'int answer(void) { return 0; }\n'
                    candidate.write_text(source, encoding='utf-8')
                    report = fixture_report()
                    report['tasks'][0]['provenance']['candidate_sha256'] = text_sha256(source)
                    if mode != 'no-findings':
                        task = report['tasks'][0]
                        task['safety_metrics'].update(warning_count=1, findings=[dict(
                            rule_id='probe', engine='builtin', severity='warning',
                            message='diagnostic', file='candidate.c', line=1)])
                        task['scores'].update(safety=97, total=99.4)
                        report['overall_score'] = 99.4
                    mapping = root / 'mapping.json'
                    key = 'one:run-1' if mode == 'sample' else 'one'
                    mapping.write_text(json.dumps({key: str(candidate) if mode == 'absolute' else 'candidate.c'}), encoding='utf-8')
                    if mode == 'provenance':
                        report['tasks'][0]['provenance']['candidate_source'] = str(candidate)
                    if mode == 'sample':
                        report['samples'] = [json.loads(json.dumps(report))]
                        report['metadata']['run_id'] = 'collection'
                        report['sampling'] = {'requested': 1, 'completed': 1, 'pending': [], 'pass_k': [1]}
                    results = root / 'report.json'
                    results.write_text(json.dumps(report), encoding='utf-8')
                    target = mapping if mode in ('mapping', 'no-findings') else candidate
                    output = target
                    if alias != 'direct':
                        output = root / 'alias'
                        try:
                            if alias == 'hardlink':
                                os.link(target, output)
                            else:
                                output.symlink_to(target)
                        except OSError:
                            continue  # Symlink privileges are optional on Windows.
                    before = {path: path.read_bytes() for path in (candidate, mapping, results, output)}
                    argv = ['report', '--results', str(results), '--format', 'sarif', '--source-root', str(root), '--output', str(output)]
                    if mode != 'provenance':
                        argv += ['--source-mapping', str(mapping)]
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
                        status = cmd_report(build_parser().parse_args(argv))
                    self.assertEqual(status, 1, errors.getvalue())
                    self.assertIn('overwrite an input file', errors.getvalue())
                    for path, contents in before.items():
                        self.assertEqual(path.read_bytes(), contents)

    def test_cli_allows_distinct_output_inside_source_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'candidate.c'
            source.write_text('int answer(void) { return 0; }\n', encoding='utf-8')
            report = fixture_report()
            report['tasks'][0]['provenance'].update(candidate_source=str(source), candidate_sha256=text_sha256(source.read_text()))
            results = root / 'report.json'
            results.write_text(json.dumps(report), encoding='utf-8')
            output = root / 'export.sarif'
            before = source.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                status = cmd_report(build_parser().parse_args(['report', '--results', str(results), '--format', 'sarif', '--source-root', str(root), '--output', str(output)]))
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.read_text())['version'], '2.1.0')
            self.assertEqual(source.read_bytes(), before)
