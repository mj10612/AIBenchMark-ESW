import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from compiler_tools import find_clang


class TestTickTimerTask(unittest.TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.task = self.loader.get_task("tier2_tick_timer")
        self.reference = self.loader.get_reference_solution(self.task.id)
        self.executor = ExecutionSandbox()

    def test_reference_passes_and_starter_fails_a_completed_suite(self):
        for source, expected in ((self.reference, True), (self.loader.get_starter_code(self.task.id), False)):
            compiled, result = self.executor.compile_and_test(self.task, source)
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(result.completed, result.output)
            self.assertEqual(result.total_tests, 16)
            self.assertEqual(result.passed, expected, result.output)

    def test_rollover_phase_count_and_boundary_mutations_are_rejected(self):
        mutations = {
            "naive deadline comparison": self.reference.replace("elapsed < timer->interval",
                "now < timer->started_at + timer->interval"),
            "phase drift": self.reference.replace("timer->started_at += count * timer->interval;",
                "timer->started_at = now;"),
            "dropped expirations": self.reference.replace("count = elapsed / timer->interval;", "count = 1;"),
            "repeated one-shot": self.reference.replace("if (!timer->periodic) {\n        timer->active = false;",
                "if (!timer->periodic) {"),
            "exclusive deadline": self.reference.replace("elapsed < timer->interval", "elapsed <= timer->interval"),
            "unnecessary half-range restriction": self.reference.replace("timer == NULL || interval == 0",
                "timer == NULL || interval == 0 || interval > INT32_MAX"),
            "narrow count": self.reference.replace("return count;", "return (uint16_t)count;"),
            "zero interval accepted": self.reference.replace("timer == NULL || interval == 0", "timer == NULL"),
        }
        for name, source in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(source, self.reference)
                compiled, result = self.executor.compile_and_test(self.task, source)
                self.addCleanup(compiled.cleanup)
                self.assertTrue(compiled.success, compiled.output)
                self.assertTrue(result.completed, result.output)
                self.assertFalse(result.passed)

    def test_remainder_based_phase_update_also_passes(self):
        candidate = self.reference.replace("timer->started_at += count * timer->interval;",
                                           "timer->started_at = now - elapsed % timer->interval;")
        self.assertNotEqual(candidate, self.reference)
        compiled, result = self.executor.compile_and_test(self.task, candidate)
        self.addCleanup(compiled.cleanup)
        self.assertTrue(compiled.success, compiled.output)
        self.assertTrue(result.passed, result.output)

    def test_reference_uses_unsigned_32_bit_arithmetic_on_avr(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest("Clang is required for AVR cross-compilation validation")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "tick_timer.ll"
            compiled = subprocess.run([compiler, "--target=avr", "-mmcu=atmega328p", "-ffreestanding",
                "-std=c99", "-S", "-emit-llvm", "-O0", "-I", str(self.task.task_dir / "include"),
                str(self.task.task_dir / "reference/tick_timer.c"), "-o", str(output)],
                capture_output=True, text=True, errors="backslashreplace", timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ir = output.read_text(encoding="utf-8")
        for operation in ("sub", "udiv", "mul", "add"):
            self.assertRegex(ir, rf"\b{operation} i32 ")
            self.assertNotRegex(ir, rf"\b{operation} i16 ")
