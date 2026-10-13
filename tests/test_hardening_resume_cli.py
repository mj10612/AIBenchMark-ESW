"""Native CLI checkpoints restore their saved hardening policy before resuming."""

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from compiler_tools import find_clang

from aibenchmark_esw.cli import build_parser, cmd_run
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestHardeningResumeCLI(unittest.TestCase):
    def setUp(self):
        self.compiler = find_clang() or ExecutionSandbox().compiler_path

    def _command(self, arguments):
        args = build_parser().parse_args(['run', *arguments])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = cmd_run(args)
        return status, args

    def _exercise_policy(self, policy):
        if policy == 'required' and Path(self.compiler).stem.lower() == 'tcc':
            self.skipTest('TCC cannot provide required hardening')
        with patch.dict(os.environ, {'AIBENCHMARK_ESW_CPPCHECK': 'off'}):
            for samples in (1, 2):
                with self.subTest(policy=policy, samples=samples), TemporaryDirectory() as directory:
                    checkpoint = Path(directory) / 'checkpoint.json'
                    status, _ = self._command([
                        '--model', 'baseline', '--tasks', 'tier1_crc16', '--compiler', self.compiler,
                        '--hardening', policy, '--samples', str(samples), '--quiet', '--output', str(checkpoint)])
                    self.assertEqual(status, 0)
                    original = json.loads(checkpoint.read_text(encoding='utf-8'))
                    self.assertEqual(original['metadata']['run_options']['hardening'], policy)
                    self.assertEqual(original['metadata']['execution_settings']['hardening']['policy'], policy)
                    self.assertEqual(original['tasks'][0]['scores']['total'], 100)
                    if samples > 1:
                        self.assertEqual(original['sampling']['completed'], samples)
                        self.assertEqual(len(original['samples']), samples)

                    # Ordinary resume omits the original policy and compiler flags.
                    status, restored = self._command(['--resume', str(checkpoint), '--quiet'])
                    self.assertEqual(status, 0)
                    self.assertEqual(restored.hardening, policy)
                    resumed = json.loads(checkpoint.read_text(encoding='utf-8'))
                    self.assertEqual(resumed['metadata']['run_id'], original['metadata']['run_id'])
                    self.assertEqual(resumed['metadata']['run_status'], 'completed')
                    self.assertEqual(resumed['metadata']['execution_settings'], original['metadata']['execution_settings'])
                    if samples > 1:
                        self.assertEqual(resumed['sampling']['pending'], [])
                        self.assertEqual(resumed['samples'], original['samples'])

                    status, _ = self._command(['--resume', str(checkpoint), '--hardening', policy, '--quiet'])
                    self.assertEqual(status, 0)
                    before_conflict = checkpoint.read_bytes()
                    conflict = 'auto' if policy == 'off' else 'off'
                    with patch('aibenchmark_esw.cli._new_client', side_effect=AssertionError('provider client created')) as client, patch(
                            'aibenchmark_esw.cli._new_executor', side_effect=AssertionError('compiler executor created')) as executor:
                        with self.assertRaisesRegex(ValueError, '--hardening conflicts'):
                            self._command(['--resume', str(checkpoint), '--hardening', conflict, '--quiet'])
                        client.assert_not_called()
                        executor.assert_not_called()
                    self.assertEqual(checkpoint.read_bytes(), before_conflict)

    def test_off_policy_single_and_collection_resume(self):
        self._exercise_policy('off')

    def test_auto_policy_single_and_collection_resume(self):
        self._exercise_policy('auto')

    def test_required_policy_single_and_collection_resume(self):
        self._exercise_policy('required')
