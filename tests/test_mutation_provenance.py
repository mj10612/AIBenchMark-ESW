import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.models import CompilationResult, TestResult
from aibenchmark_esw.mutations import run_mutations
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestMutationProvenance(unittest.TestCase):
    def test_external_asset_identity_and_execution_settings_survive_serialization(self):
        bundled = DatasetLoader().get_task('tier1_crc16')
        executor = ExecutionSandbox(compiler_path='tcc')
        with TemporaryDirectory() as directory:
            task_dir = Path(directory) / 'crc'
            shutil.copytree(bundled.task_dir, task_dir)
            reports = []
            for changed in (False, True):
                if changed:
                    header = next((task_dir / 'include').glob('*.h'))
                    header.write_text(header.read_text(encoding='utf-8') + '\n/* audit variant */\n', encoding='utf-8')
                loader = DatasetLoader(Path(directory))
                with patch.object(executor, 'compiler_identity', return_value={'name': 'tcc', 'version': 'test'}), \
                        patch.object(executor, 'compile_and_test', return_value=(CompilationResult(False, 'fixture'), TestResult())):
                    report = run_mutations(loader.list_tasks(), loader, executor)
                reports.append(json.loads(json.dumps(report)))
            first, second = reports
            self.assertNotEqual(first['dataset_sha256'], second['dataset_sha256'])
            self.assertNotEqual(first['tasks'][0]['task_sha256'], second['tasks'][0]['task_sha256'])
            self.assertEqual(first['tasks'][0]['task_sha256'], first['task_fingerprints'][bundled.id])
            self.assertEqual(first['execution_settings'], executor.execution_settings())
            self.assertEqual(first['schema_version'], 1)
            self.assertEqual(first['mutation_policy_version'], 'reviewed-v1')
