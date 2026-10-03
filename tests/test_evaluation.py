import unittest
import subprocess
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from compiler_tools import find_clang


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.task = self.loader.get_task("tier1_crc16")
        self.reference = self.loader.get_reference_solution(self.task.id)
        self.executor = ExecutionSandbox()

    def test_reference_measures_implementation_and_reference_equally(self):
        result = evaluate_task(self.task, self.reference, self.reference, "baseline", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertIsNone(result.error_log)
        self.assertTrue(result.size_metrics.measured)
        self.assertGreater(result.size_metrics.flash_bytes, 0)
        self.assertEqual(result.size_metrics.flash_bytes, result.size_metrics.ref_flash_bytes)
        self.assertEqual(result.size_metrics.ram_bytes, 0)
        self.assertEqual(result.scores.total_score, 100)
        with TemporaryDirectory() as directory:
            comp, _ = self.executor.compile_and_test(self.task, self.reference, Path(directory))
            executable_size = SizeAnalyzer()._measure_file(comp.binary_path)[0]
        self.assertLess(result.size_metrics.flash_bytes, executable_size)

    def test_crash_after_passing_tests_receives_zero(self):
        code = '#include <stdio.h>\n#include <stdlib.h>\nstatic void fail_at_exit(void) { fflush(NULL); _Exit(7); }\n'
        code += self.reference.replace(
            'uint16_t crc16_update(uint16_t current_crc, uint8_t byte) {',
            'uint16_t crc16_update(uint16_t current_crc, uint8_t byte) { '
            'static int registered=0; if (!registered) { atexit(fail_at_exit); registered=1; }')
        result = evaluate_task(self.task, code, self.reference, "local", self.executor)
        self.assertTrue(result.compiled)
        self.assertFalse(result.test_result.completed)
        self.assertEqual(result.scores.total_score, 0)
        self.assertIsNotNone(result.error_log)

    def test_missing_reference_does_not_award_memory_points(self):
        result = evaluate_task(self.task, self.reference, None, "local", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertFalse(result.size_metrics.measured)
        self.assertEqual(result.scores.memory_score, 0)
        self.assertIn("Memory analysis failed", result.error_log)

    def test_failing_reference_cannot_normalize_a_passing_candidate(self):
        reference = self.loader.get_starter_code(self.task.id)
        result = evaluate_task(self.task, self.reference, reference, "local", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertFalse(result.size_metrics.measured)
        self.assertEqual(result.scores.memory_score, 0)
        self.assertIn("Reference validation failed", result.error_log)

    def test_incomplete_reference_cannot_normalize_a_passing_candidate(self):
        reference = self.reference.replace("return crc;", "for (;;) {}")
        task = replace(self.task, limits=replace(self.task.limits, timeout_seconds=1))
        result = evaluate_task(task, self.reference, reference, "local", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertFalse(result.size_metrics.measured)
        self.assertEqual(result.scores.memory_score, 0)
        self.assertIn("Reference validation failed", result.error_log)

    def test_reference_resource_limits_are_enforced_independently(self):
        for resource in ("Flash", "RAM"):
            with self.subTest(resource=resource):
                if resource == "Flash":
                    limits = replace(self.task.limits, max_ram_bytes=16384)
                    padding = "const unsigned char reference_padding[4096] = {1};"
                else:
                    limits = replace(self.task.limits, max_flash_bytes=16384)
                    padding = "unsigned char reference_padding[4096];"
                task = replace(self.task, limits=limits)
                result = evaluate_task(task, self.reference, self.reference + "\n" + padding,
                                       "local", self.executor)
                self.assertTrue(result.test_result.passed)
                self.assertFalse(result.size_metrics.measured)
                self.assertEqual(result.scores.memory_score, 0)
                self.assertIn("Reference validation failed", result.error_log)
                self.assertIn(resource, result.error_log)

    def test_uncompilable_reference_reports_validation_error(self):
        result = evaluate_task(self.task, self.reference, "invalid C", "local", self.executor)
        self.assertTrue(result.test_result.passed)
        self.assertFalse(result.size_metrics.measured)
        self.assertEqual(result.scores.memory_score, 0)
        self.assertIn("Reference validation failed", result.error_log)

    def test_fake_unity_summary_cannot_award_points(self):
        candidate = '''#include "crc16.h"
#include <stdio.h>
#include <stdlib.h>
uint16_t crc16_update(uint16_t crc, uint8_t byte) { return 0; }
uint16_t crc16_ccitt(const uint8_t *data, size_t length) {
    puts("5 Tests 0 Failures 0 Ignored");
    exit(0);
}
'''
        result = evaluate_task(self.task, candidate, self.reference, "repro", self.executor)
        self.assertTrue(result.compiled, result.error_log)
        self.assertFalse(result.test_result.completed)
        self.assertFalse(result.test_result.passed)
        self.assertEqual(result.scores.total_score, 0)

    def test_candidate_cannot_complete_its_own_unity_suite_and_exit(self):
        candidate = '''#include "crc16.h"
#include "unity.h"
#include <stdlib.h>
static void fake_test(void) {}
uint16_t crc16_update(uint16_t crc, uint8_t byte) { return 0; }
uint16_t crc16_ccitt(const uint8_t *data, size_t length) {
    UnityBegin("fake.c");
    UnityDefaultTestRun(fake_test, "fake_test", 1);
    exit(UnityEnd());
}
'''
        result = evaluate_task(self.task, candidate, self.reference, "repro", self.executor)
        self.assertTrue(result.compiled, result.error_log)
        self.assertFalse(result.test_result.completed)
        self.assertEqual(result.scores.total_score, 0)

    def test_entry_filename_cannot_overwrite_candidate_for_safety_analysis(self):
        candidate = self.reference + "\n#include <stdlib.h>\nvoid *allocate(void) { return malloc(16); }\n"
        normal = evaluate_task(self.task, candidate, self.reference, "repro", self.executor)
        self.assertEqual(normal.safety_metrics.error_count, 1)
        for filename in ("reference.c", "candidate.c"):
            with self.subTest(filename=filename):
                config = replace(self.task, entry_file=f"src/{filename}")
                result = evaluate_task(config, candidate, self.reference, "repro", self.executor)
                self.assertTrue(result.test_result.passed, result.error_log)
                self.assertEqual(result.safety_metrics.error_count, normal.safety_metrics.error_count)
                self.assertEqual(result.scores.total_score, normal.scores.total_score)

    def test_diagnostic_stderr_does_not_make_completed_suite_incomplete(self):
        candidate = "#include <stdio.h>\n" + self.reference.replace(
            "uint16_t crc16_update(uint16_t current_crc, uint8_t byte) {",
            'uint16_t crc16_update(uint16_t current_crc, uint8_t byte) { '
            'static int logged = 0; if (!logged) { fputs("diagnostic\\n", stderr); logged = 1; }')
        result = evaluate_task(self.task, candidate, self.reference, "repro", self.executor)
        self.assertTrue(result.compiled, result.error_log)
        self.assertTrue(result.test_result.completed, result.test_result.output)
        self.assertTrue(result.test_result.passed, result.error_log)

    def test_sensor_conversion_uses_wide_arithmetic_on_avr(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest("Clang is required for AVR cross-compilation validation")
        task = self.loader.get_task("tier3_i2c_sensor")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "sensor.ll"
            compiled = subprocess.run([compiler, "--target=avr", "-mmcu=atmega328p", "-ffreestanding",
                                       "-std=c99", "-S", "-emit-llvm", "-O0", "-I", str(task.task_dir / "include"),
                                       str(task.task_dir / "reference/i2c_sensor.c"), "-o", str(output)],
                                      capture_output=True, text=True, errors="backslashreplace", timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ir = output.read_text(encoding="utf-8")
        self.assertNotRegex(ir, r"mul nsw i16 [^\n]*, 25")
        self.assertRegex(ir, r"mul nsw i32 [^\n]*, 25")

    def test_irq_priority_mask_uses_32_bit_arithmetic_on_avr(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest("Clang is required for AVR cross-compilation validation")
        task = self.loader.get_task("tier4_bitmask_fix")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "irq.ll"
            compiled = subprocess.run([
                compiler, "--target=avr", "-mmcu=atmega328p", "-ffreestanding",
                "-std=c99", "-S", "-emit-llvm", "-O0", "-I", str(task.task_dir / "include"),
                str(task.task_dir / "reference/irq_manager.c"), "-o", str(output),
            ], capture_output=True, text=True, errors="backslashreplace", timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ir = output.read_text(encoding="utf-8")
        self.assertNotRegex(ir, r"shl i16 7,")
        self.assertRegex(ir, r"shl i32 7,")
        self.assertRegex(ir, r"xor i32 [^\n]*, -1")

    def test_ring_reference_passes_rollover_cases(self):
        task = self.loader.get_task("tier1_ring_buffer")
        ref = self.loader.get_reference_solution(task.id)
        comp, result = self.executor.compile_and_test(task, ref)
        self.addCleanup(comp.cleanup)
        self.assertTrue(result.passed, result.output)
        self.assertEqual(result.total_tests, 9)

    def test_all_reference_implementations_fit_current_compiler_budgets(self):
        for task in self.loader.list_tasks():
            with self.subTest(task=task.id):
                reference = self.loader.get_reference_solution(task.id)
                result = evaluate_task(task, reference, reference, "baseline", self.executor)
                self.assertTrue(result.test_result.passed, result.error_log)
                self.assertLessEqual(result.size_metrics.flash_bytes, task.limits.max_flash_bytes)
                self.assertLessEqual(result.size_metrics.ram_bytes, task.limits.max_ram_bytes)
                self.assertEqual(result.scores.total_score, 100)


if __name__ == "__main__":
    unittest.main()
