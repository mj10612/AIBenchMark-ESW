import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import Mock, patch

from aibenchmark_esw import cli
from aibenchmark_esw.llm.client import LLMClient, is_fatal_provider_error
from aibenchmark_esw.output_paths import validate_output_paths
from aibenchmark_esw.provenance import _digest_records
from aibenchmark_esw.resume import _equivalent
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestBacklogCoordinator(unittest.TestCase):
    def test_task_scoped_context_error_is_not_fatal(self):
        class ContextWindowExceededError(Exception):
            status_code = 400
        self.assertFalse(is_fatal_provider_error(ContextWindowExceededError()))

    def test_missing_turn_usage_stays_unknown(self):
        client = LLMClient('mock', prompt_strategy='plan')
        provider = Mock()
        provider.completion.side_effect = [
            N(model='snapshot', usage=N(prompt_tokens=2, completion_tokens=3, total_tokens=5),
              choices=[N(finish_reason='stop', message=N(content='Plan'))]),
            N(model='snapshot', usage=None,
              choices=[N(finish_reason='stop', message=N(content='int f(void){return 1;}'))]),
        ]
        with patch.dict('sys.modules', {'litellm': provider}):
            client.generate_solution([{'role': 'user', 'content': 'Task'}])
        self.assertIsNone(client.last_generation['usage']['total_tokens'])
        self.assertEqual(client.last_generation['known_usage']['total_tokens'], 5)

    def test_compiler_spellings_resolve_to_same_binary(self):
        executor = ExecutionSandbox()
        name = Path(executor.compiler_path).name
        self.assertTrue(_equivalent('compiler', name, executor.compiler_path))

    def test_opaque_utf8_binary_newline_bytes_change_fingerprint(self):
        before = _digest_records([('task/fixture.bin', b'ABC\r\nDEF')])
        after = _digest_records([('task/fixture.bin', b'ABC\nDEF')])
        self.assertNotEqual(before, after)
        self.assertEqual(_digest_records([('task/header.h', b'ABC\r\nDEF')]),
                         _digest_records([('task/header.h', b'ABC\nDEF')]))

    def test_new_output_file_cannot_also_be_an_output_directory(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'run.json'
            for paths in ([output, output / 'junit.xml'], [output / 'junit.xml', output]):
                with self.subTest(paths=paths), self.assertRaises(ValueError):
                    validate_output_paths(paths)
            self.assertFalse(output.exists())

    def test_explicit_abbreviated_options_are_rejected(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(['run', '--temp', '1'])

    def test_dry_run_does_not_generate_or_evaluate(self):
        try:
            args = cli.build_parser().parse_args(['run', '--model', 'mock', '--tasks', 'tier1_crc16', '--dry-run'])
        except SystemExit:
            self.fail('dry-run is unavailable')
        with patch.object(cli.LLMClient, 'generate_solution', side_effect=AssertionError('provider called')), \
                patch.object(cli, 'evaluate_task', side_effect=AssertionError('candidate evaluated')), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.cmd_run(args), 0)
        self.assertIn('tier1_crc16', output.getvalue())

    def test_directory_symlink_cycle_does_not_hide_protected_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'inputs'; root.mkdir()
            source = root / 'source.c'; source.write_text('keep')
            try:
                (root / 'cycle').symlink_to(root, target_is_directory=True)
            except OSError:
                self.skipTest('directory symlinks unavailable')
            alias = Path(d) / 'output.json'; os.link(source, alias)
            with self.assertRaises(ValueError):
                validate_output_paths([alias], protected_roots=[root])
            self.assertEqual(source.read_text(), 'keep')
