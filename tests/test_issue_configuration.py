import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_aggregation import fixture_report

from aibenchmark_esw.cli import build_parser, cmd_run
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.models import TaskConfig
from aibenchmark_esw.resume import load_resume


class TestIssueConfiguration(unittest.TestCase):
    def test_unknown_keys_are_rejected_at_each_configuration_level(self):
        cases = [({'target_standrd': 'c11'}, 'target_standrd'),
                 ({'limits': {'max_flash_byte': 1}}, 'limits.max_flash_byte'),
                 ({'limits': {'default': {'max_flash_byte': 1}}}, 'limits.default.max_flash_byte'),
                 ({'limits': {'targets': {'arm:cortex-m0': {'max_ram_byte': 1}}}}, 'limits.targets.arm:cortex-m0.max_ram_byte'),
                 ({'weights': {'functional_weight': 1}}, 'weights.functional_weight')]
        for supplied, diagnostic in cases:
            with self.subTest(supplied=supplied), self.assertRaisesRegex(ValueError, diagnostic):
                TaskConfig.from_dict({'id': 'external', **supplied}, Path('external'))

    def test_optional_defaults_and_legitimate_metadata_still_load(self):
        task = TaskConfig.from_dict({'id': 'external', 'canary': {}, 'audit_canary': {},
                                     'variant': {'version': 1}, 'limits': {'targets': {}}}, Path('external'))
        self.assertEqual(task.limits.max_flash_bytes, 2048)
        self.assertEqual(task.target_standard, 'c99')
        self.assertEqual(len(DatasetLoader().list_tasks()), 15)

    def test_invalid_external_metadata_preserves_outputs_and_valid_tasks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in [('bad', {'id': 'bad', 'target_standrd': 'c11'}), ('valid', {'id': 'valid'})]:
                folder = root / name
                folder.mkdir()
                (folder / 'task.json').write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'target_standrd'):
                DatasetLoader(root)
            diagnostic = DatasetLoader(root, strict=False)
            self.assertEqual([task.id for task in diagnostic.list_tasks()], ['valid'])
            self.assertIn('target_standrd', next(iter(diagnostic.load_errors.values())))
            output = root / 'output.json'
            output.write_bytes(b'original evidence')
            args = build_parser().parse_args(['run', '--tasks-root', str(root), '--output', str(output)])
            with patch('aibenchmark_esw.cli._new_client', side_effect=AssertionError('provider called')):
                with self.assertRaisesRegex(ValueError, 'target_standrd'):
                    cmd_run(args)
            self.assertEqual(output.read_bytes(), b'original evidence')

    def test_resume_restores_hardening_and_rejects_conflicts(self):
        for saved in ('off', 'auto', 'required'):
            for collection in (False, True):
                with self.subTest(saved=saved, collection=collection), TemporaryDirectory() as directory:
                    report = fixture_report()
                    report['metadata']['run_options'] = {'hardening': saved}
                    if collection:
                        report['samples'] = [copy.deepcopy(report)]
                        report['metadata']['run_id'] = 'collection'
                        report['sampling'] = {'requested': 1, 'completed': 1, 'pending': [], 'pass_k': [1]}
                    path = Path(directory) / 'checkpoint.json'
                    path.write_text(json.dumps(report), encoding='utf-8')
                    before = path.read_bytes()
                    args = build_parser().parse_args(['run', '--resume', str(path)])
                    load_resume(args)
                    self.assertEqual(args.hardening, saved)
                    args = build_parser().parse_args(['run', '--resume', str(path), '--hardening', saved])
                    args._explicit_options = {'--hardening'}
                    load_resume(args)
                    args.hardening = 'off' if saved != 'off' else 'auto'
                    with self.assertRaisesRegex(ValueError, '--hardening conflicts'):
                        load_resume(args)
                    self.assertEqual(path.read_bytes(), before)

    def test_legacy_resume_retains_default_hardening(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'checkpoint.json'
            path.write_text(json.dumps(fixture_report()), encoding='utf-8')
            args = build_parser().parse_args(['run', '--resume', str(path)])
            load_resume(args)
            self.assertEqual(args.hardening, 'auto')
