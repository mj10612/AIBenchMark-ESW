import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def runner():
    path=Path('.github/scripts/action_runner.py')
    spec=importlib.util.spec_from_file_location('action_runner',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConsumerActionTests(unittest.TestCase):
    def test_default_run_is_offline_baseline_with_json_junit(self):
        command,outputs=runner().build_command({})
        self.assertIn('run',command)
        self.assertEqual(command[command.index('--model')+1],'baseline')
        self.assertEqual(command[command.index('--tasks')+1],'tier1_crc16')
        self.assertIn('--junit-output',command)
        self.assertEqual(set(outputs),{'json','junit'})

    def test_eval_solution_arguments_are_separate_tokens(self):
        command,_=runner().build_command({'INPUT_COMMAND':'eval','INPUT_SOLUTION':'my source;echo bad.c','INPUT_TASKS':'tier1_crc16','INPUT_EXTRA_ARGUMENTS':'["--compile-timeout", "12"]'})
        self.assertEqual(command[command.index('--solution')+1],'my source;echo bad.c')
        self.assertNotIn('--reference',command)
        self.assertIn('--compile-timeout',command)

    def test_invalid_versions_commands_and_output_overrides_rejected(self):
        module=runner()
        for value in ('a>=1','--index-url secret',''):
            if value:
                with self.assertRaises(ValueError):
                    module.install_spec(value,'run')
        for env in ({'INPUT_COMMAND':'shell'},{'INPUT_EXTRA_ARGUMENTS':'["--output=source.c"]'},{'INPUT_EXTRA_ARGUMENTS':'["--junit-output", "source.c"]'},{'INPUT_EXTRA_ARGUMENTS':'"--reference"'}):
            with self.assertRaises(ValueError):
                module.build_command(env)

    def test_real_offline_baseline_helper_writes_artifacts_and_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            outputs=root/'outputs.txt'
            environment=dict(os.environ,INPUT_OUTPUT_DIRECTORY=str(root/'artifacts'),GITHUB_OUTPUT=str(outputs),AIBENCHMARK_ESW_CPPCHECK='off')
            process=subprocess.run([sys.executable,'.github/scripts/action_runner.py','benchmark'],env=environment,capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            report=json.loads((root/'artifacts'/'benchmark.json').read_text())
            self.assertEqual(report['model_name'],'baseline')
            self.assertEqual(report['pass_at_1_pct'],100)
            self.assertTrue((root/'artifacts'/'benchmark.junit.xml').is_file())
            self.assertIn('exit-code=0',outputs.read_text())

    def test_action_uploads_even_when_benchmark_fails_and_smoke_is_offline(self):
        action=Path('action.yml').read_text()
        self.assertIn('using: composite',action)
        self.assertIn('if: always()',action)
        self.assertIn('actions/upload-artifact@',action)
        self.assertIn('continue-on-error: true',action)
        workflow=Path('.github/workflows/action-smoke.yml').read_text()
        self.assertIn('uses: ./',workflow)
        self.assertIn('model: baseline',workflow)
