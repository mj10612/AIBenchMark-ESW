import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from aibenchmark_esw import cli


class TestResumeOutputPaths(unittest.TestCase):
    def create_checkpoint(self, path, samples):
        args = cli.build_parser().parse_args(['run', '--model', 'baseline', '--tasks', 'tier1_crc16',
            '--samples', str(samples), '--output', str(path), '--quiet'])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_run(args), 0)

    def test_junit_cannot_replace_resume_checkpoint_or_sample_aliases(self):
        for samples in (1, 2):
            with TemporaryDirectory() as directory:
                root = Path(directory)
                original = root / 'original.json'
                self.create_checkpoint(original, samples)
                snapshots = {path.relative_to(root): path.read_bytes() for path in root.rglob('*.json')}
                for target in snapshots:
                    for alias in ('direct', 'relative', 'hardlink', 'symlink'):
                        with self.subTest(samples=samples, target=target, alias=alias), TemporaryDirectory() as case:
                            case_root = Path(case)
                            for name, contents in snapshots.items():
                                path = case_root / name
                                path.parent.mkdir(parents=True, exist_ok=True)
                                path.write_bytes(contents)
                            checkpoint = case_root / original.name
                            protected = case_root / target
                            junit = protected
                            if alias == 'relative':
                                # Keep the parent traversal so the CLI must compare resolved identities.
                                nested = case_root / 'nested'
                                nested.mkdir()
                                junit = nested / '..' / target
                            elif alias in ('hardlink', 'symlink'):
                                junit = case_root / 'alias.xml'
                                try:
                                    if alias == 'hardlink':
                                        os.link(protected, junit)
                                    else:
                                        junit.symlink_to(protected)
                                except OSError as error:
                                    self.skipTest(f'{alias} unavailable: {error}')
                            output = case_root / 'new.json'
                            output.write_text('previous output', encoding='utf-8')
                            before = {case_root / name: contents for name, contents in snapshots.items()}
                            before.update({junit: junit.read_bytes(), output: output.read_bytes()})
                            args = cli.build_parser().parse_args(['run', '--resume', str(checkpoint),
                                '--output', str(output), '--junit-output', str(junit), '--quiet'])
                            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'overwrite an input'):
                                cli.cmd_run(args)
                            for path, contents in before.items():
                                self.assertEqual(path.read_bytes(), contents)
                            self.assertFalse(Path(str(output) + '.samples').exists())

    def test_resume_allows_json_updates_and_distinct_junit_output(self):
        for samples in (1, 2):
            for destination in ('implicit', 'explicit', 'new'):
                with self.subTest(samples=samples, destination=destination), TemporaryDirectory() as directory:
                    root = Path(directory)
                    checkpoint = root / 'resume.json'
                    self.create_checkpoint(checkpoint, samples)
                    before = checkpoint.read_bytes()
                    run_id = json.loads(before)['metadata']['run_id']
                    junit = root / 'report.xml'
                    argv = ['run', '--resume', str(checkpoint), '--junit-output', str(junit), '--quiet']
                    output = root / 'new.json' if destination == 'new' else checkpoint
                    if destination != 'implicit':
                        argv += ['--output', str(output)]
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(cli.cmd_run(cli.build_parser().parse_args(argv)), 0)
                    report = json.loads(output.read_text(encoding='utf-8'))
                    self.assertEqual(report['metadata']['run_id'], run_id)
                    self.assertEqual(report['metadata']['run_status'], 'completed')
                    self.assertEqual(ElementTree.parse(junit).getroot().get('tests'), str(samples))
                    if destination == 'new':
                        self.assertEqual(checkpoint.read_bytes(), before)
