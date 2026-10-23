import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from aibenchmark_esw.cli import main
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.models import TaskConfig


class TestMixedTaskLimits(unittest.TestCase):
    def test_cli_rejects_mixed_limits_before_provider_calls_or_output_replacement(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / 'tasks' / 'external'
            task.mkdir(parents=True)
            (task / 'task.json').write_text(json.dumps({
                'id': 'external', 'limits': {'max_flash_bytes': 1, 'default': {}}}), encoding='utf-8')
            output = root / 'report.json'
            output.write_text('preserve checkpoint', encoding='utf-8')
            provider = Mock()
            with patch.dict('sys.modules', {'litellm': provider}), patch('sys.argv', [
                    'aibenchmark-esw', 'run', '--model', 'mock', '--tasks-root', str(root / 'tasks'),
                    '--output', str(output)]), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main()
            self.assertNotEqual(error.exception.code, 0)
            provider.completion.assert_not_called()
            self.assertEqual(output.read_text(encoding='utf-8'), 'preserve checkpoint')

    def test_mixed_default_and_flat_limits_are_rejected_in_both_loader_modes(self):
        for field in ('max_flash_bytes', 'max_ram_bytes', 'timeout_seconds'):
            for value in (0, 1):
                with self.subTest(field=field, value=value), TemporaryDirectory() as directory:
                    root = Path(directory)
                    task_dir = root / 'external'
                    task_dir.mkdir()
                    data = {'id': 'external', 'limits': {field: value, 'default': {}}}
                    (task_dir / 'task.json').write_text(json.dumps(data), encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'limits.' + field):
                        TaskConfig.from_dict(data, task_dir)
                    with self.assertRaisesRegex(ValueError, 'limits.' + field):
                        DatasetLoader(root)
                    loader = DatasetLoader(root, strict=False)
                    self.assertEqual(loader.list_tasks(), [])
                    self.assertIn('limits.' + field, loader.load_errors[str(task_dir)])

    def test_supported_limit_shapes_preserve_explicit_values(self):
        for limits in (
            {'max_flash_bytes': 1, 'timeout_seconds': 1},
            {'default': {'max_flash_bytes': 1, 'timeout_seconds': 1}},
            {'max_flash_bytes': 1, 'timeout_seconds': 1, 'targets': {'arm:cortex-m0': {'max_flash_bytes': 2}}},
            {'default': {'max_flash_bytes': 1, 'timeout_seconds': 1},
             'targets': {'arm:cortex-m0': {'max_flash_bytes': 2}}},
        ):
            with self.subTest(limits=limits):
                task = TaskConfig.from_dict({'id': 'external', 'limits': limits}, Path('external'))
                self.assertEqual(task.limits.max_flash_bytes, 1)
                self.assertEqual(task.limits.timeout_seconds, 1)
                if 'targets' in limits:
                    self.assertEqual(task.target_limits['arm:cortex-m0'].max_flash_bytes, 2)
