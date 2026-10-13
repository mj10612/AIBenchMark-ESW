import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.task_variants import prepare_task_variants


class TestI2CVariants(unittest.TestCase):
    def test_seeded_contract_assets_and_parameters_are_reproducible(self):
        task = DatasetLoader().get_task('tier3_i2c_sensor')
        original = {str(p.relative_to(task.task_dir)): p.read_bytes() for p in task.task_dir.rglob('*') if p.is_file()}
        snapshots = []
        parameters = []
        for seed in (42, 42, 43):
            with prepare_task_variants([task], variant_seed=seed) as (prepared, evidence):
                current = prepared[0]
                params = evidence['variant_parameters'][task.id]
                parameters.append(params)
                self.assertEqual(evidence['variant_task_versions'][task.id], 'i2c-registers-v1')
                self.assertEqual(params['SENSOR_REG_TEMP_LSB'], params['SENSOR_REG_TEMP_MSB'] + 1)
                registers = [value for name, value in params.items() if name.startswith('SENSOR_REG_')]
                self.assertEqual(len(set(registers)), 4)
                self.assertIn(f"0x{params['SENSOR_EXPECTED_CHIP_ID']:02X}", current.prompt)
                metadata = json.loads((current.task_dir / 'task.json').read_text())
                self.assertEqual(metadata['variant']['parameters'], params)
                snapshots.append({str(p.relative_to(current.task_dir)): p.read_bytes() for p in current.task_dir.rglob('*') if p.is_file()})
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertNotEqual(parameters[0], parameters[2])
        self.assertEqual(original, {str(p.relative_to(task.task_dir)): p.read_bytes() for p in task.task_dir.rglob('*') if p.is_file()})

    def test_i2c_private_suite_with_seed_is_rejected(self):
        task = DatasetLoader().get_task('tier3_i2c_sensor')
        with TemporaryDirectory() as directory:
            shutil.copytree(task.task_dir / 'tests', Path(directory) / task.id / 'tests')
            with self.assertRaisesRegex(ValueError, 'tier3_i2c_sensor'), prepare_task_variants([task], variant_seed=42, heldout_tests=directory):
                pass

    def test_unvaried_tasks_are_explicit(self):
        task = DatasetLoader().get_task('tier1_ring_buffer')
        with prepare_task_variants([task], variant_seed=42) as (_, evidence):
            self.assertEqual(evidence['unvaried_tasks'], [task.id])

    def test_variant_reference_and_reviewed_faults_compile_and_complete(self):
        from aibenchmark_esw.mutations import MUTATIONS
        from aibenchmark_esw.sandbox.executor import ExecutionSandbox
        task = DatasetLoader().get_task('tier3_i2c_sensor')
        executor = ExecutionSandbox()
        for seed in (42, 43):
            with prepare_task_variants([task], variant_seed=seed) as (prepared, _):
                current = prepared[0]
                reference = current.reference_path.read_text()
                hardcoded = reference.replace('SENSOR_REG_WHO_AM_I', '0x0F').replace('SENSOR_REG_CONFIG', '0x02').replace('SENSOR_REG_TEMP_MSB', '0x00').replace('SENSOR_EXPECTED_CHIP_ID', '0xA5')
                candidates = [('reference', reference), ('original-parameters', hardcoded)]
                candidates += [(mutation.name, mutation.apply(reference)) for mutation in MUTATIONS[task.id]]
                for name, source in candidates:
                    with self.subTest(seed=seed, candidate=name):
                        compiled, result = executor.compile_and_test(current, source)
                        try:
                            self.assertTrue(compiled.success, compiled.output)
                            self.assertTrue(result.completed, result.output)
                            self.assertEqual(result.passed, name == 'reference', result.output)
                        finally:
                            compiled.cleanup()

    def test_task_fingerprints_distinguish_parameters(self):
        from aibenchmark_esw.provenance import task_sha256
        from aibenchmark_esw.resources import data_root
        task = DatasetLoader().get_task('tier3_i2c_sensor')
        fingerprints = []
        for seed in (42, 42, 43):
            with prepare_task_variants([task], variant_seed=seed) as (prepared, _):
                fingerprints.append(task_sha256(prepared[0], data_root() / 'third_party/unity'))
        self.assertEqual(fingerprints[0], fingerprints[1])
        self.assertNotEqual(fingerprints[0], fingerprints[2])

    def test_no_seed_preserves_original_objects_and_contract(self):
        task = DatasetLoader().get_task('tier3_i2c_sensor')
        with prepare_task_variants([task]) as (prepared, evidence):
            self.assertIs(prepared[0], task)
            self.assertEqual(evidence['variant_parameters'], {})
            self.assertEqual(evidence['variant_task_versions'], {})
            self.assertEqual(evidence['unvaried_tasks'], [task.id])
