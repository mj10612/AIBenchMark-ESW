import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from compiler_tools import find_clang


class TestQ15Task(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.task = self.loader.get_task("tier1_q15_math")
        self.reference = self.loader.get_reference_solution(self.task.id)
        self.executor = ExecutionSandbox()

    def test_reference_passes_and_starter_fails_the_complete_suite(self):
        for source, expected in ((self.reference, True), (self.loader.get_starter_code(self.task.id), False)):
            compiled, result = self.executor.compile_and_test(self.task, source)
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(result.completed, result.output)
            self.assertEqual(result.total_tests, 16)
            self.assertEqual(result.passed, expected, result.output)

    def test_suite_rejects_saturation_rounding_scaling_and_narrowing_bugs(self):
        mutations = {
            "positive saturation": self.reference.replace("return INT16_MAX;", "return (int16_t)value;"),
            "negative saturation": self.reference.replace("return INT16_MIN;", "return (int16_t)value;"),
            "negative rounding": self.reference.replace("product / INT32_C(32768)", "product >> 15"),
            "wrong scale": self.reference.replace("product / INT32_C(32768)", "product / INT32_C(32767)"),
            "narrow product": self.reference.replace("int32_t product = (int32_t)a * (int32_t)b;",
                                                      "int32_t product = (int16_t)((int32_t)a * (int32_t)b);"),
            "narrow sum": self.reference.replace("clamp_q15((int32_t)a + (int32_t)b)",
                                                 "clamp_q15((int16_t)((int32_t)a + (int32_t)b))"),
            "narrow difference": self.reference.replace("clamp_q15((int32_t)a - (int32_t)b)",
                                                        "clamp_q15((int16_t)((int32_t)a - (int32_t)b))"),
        }
        for name, source in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(source, self.reference)
                compiled, result = self.executor.compile_and_test(self.task, source)
                self.addCleanup(compiled.cleanup)
                self.assertTrue(compiled.success, compiled.output)
                self.assertTrue(result.completed, result.output)
                self.assertFalse(result.passed)

    def test_unsigned_magnitude_implementation_also_satisfies_contract(self):
        candidate = '''#include "q15_math.h"
int16_t q15_add_sat(int16_t a, int16_t b) {
    if (b > 0 && (int32_t)a > (int32_t)INT16_MAX - b) return INT16_MAX;
    if (b < 0 && (int32_t)a < (int32_t)INT16_MIN - b) return INT16_MIN;
    return (int16_t)((int32_t)a + b);
}
int16_t q15_sub_sat(int16_t a, int16_t b) {
    if (b < 0 && (int32_t)a > (int32_t)INT16_MAX + b) return INT16_MAX;
    if (b > 0 && (int32_t)a < (int32_t)INT16_MIN + b) return INT16_MIN;
    return (int16_t)((int32_t)a - b);
}
int16_t q15_mul_sat(int16_t a, int16_t b) {
    uint32_t left = a < 0 ? (uint32_t)(-(int32_t)a) : (uint32_t)a;
    uint32_t right = b < 0 ? (uint32_t)(-(int32_t)b) : (uint32_t)b;
    uint32_t magnitude = (left * right) >> 15;
    if ((a < 0) != (b < 0)) return (int16_t)(-(int32_t)magnitude);
    return magnitude > INT16_MAX ? INT16_MAX : (int16_t)magnitude;
}
'''
        compiled, result = self.executor.compile_and_test(self.task, candidate)
        self.addCleanup(compiled.cleanup)
        self.assertTrue(compiled.success, compiled.output)
        self.assertTrue(result.passed, result.output)

    def test_reference_widens_before_arithmetic_on_16_bit_int_avr(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest("Clang is required for AVR cross-compilation validation")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "q15.ll"
            compiled = subprocess.run([compiler, "--target=avr", "-mmcu=atmega328p", "-ffreestanding",
                "-std=c99", "-S", "-emit-llvm", "-O0", "-I", str(self.task.task_dir / "include"),
                str(self.task.task_dir / "reference/q15_math.c"), "-o", str(output)],
                capture_output=True, text=True, errors="backslashreplace", timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ir = output.read_text(encoding="utf-8")
        for operation in ("add", "sub", "mul"):
            self.assertRegex(ir, rf"\b{operation}(?: nsw)? i32 ")
            self.assertNotRegex(ir, rf"\b{operation}(?: nsw)? i16 ")
