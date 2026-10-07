"""Actual bounded child execution; no provider calls or persistent helpers."""

import os
import subprocess
import sys
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.models import CompilationResult
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.process_runner import run_bounded, OutputLimitExceeded, ExecutionCancelled, _stop_posix_group
from compiler_tools import find_clang


def child_alive(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return api.WaitForSingleObject(handle, 200) == 258
        finally:
            api.CloseHandle(handle)
    # SIGKILL delivery is asynchronous, like Windows Job termination above.
    deadline = time.monotonic() + 0.2
    while True:
        try:
            os.kill(pid, 0)
            status = Path(f"/proc/{pid}/stat")
            if status.exists() and status.read_text().split(")", 1)[1].strip().startswith("Z"):
                return False
        except (ProcessLookupError, FileNotFoundError):
            return False
        if time.monotonic() >= deadline:
            return True
        time.sleep(0.005)


class TestRuntimeControls(unittest.TestCase):
    @patch("aibenchmark_esw.sandbox.process_runner.signal.SIGKILL", 9, create=True)
    def test_zombie_group_permission_error_reaps_and_retries_descendant_cleanup(self):
        process = Mock(pid=123, poll=Mock(return_value=0))
        for final_result in (None, ProcessLookupError()):
            with self.subTest(final_result=final_result), patch(
                    "aibenchmark_esw.sandbox.process_runner.os.killpg", create=True,
                    side_effect=[PermissionError(), final_result]) as kill:
                _stop_posix_group(process)
                self.assertEqual(kill.call_count, 2)
                process.poll.assert_called()

    @patch("aibenchmark_esw.sandbox.process_runner.signal.SIGKILL", 9, create=True)
    def test_live_or_persistently_denied_process_group_reports_permission_error(self):
        for returncode in (None, 0):
            with self.subTest(returncode=returncode), patch(
                    "aibenchmark_esw.sandbox.process_runner.os.killpg", create=True,
                    side_effect=PermissionError()):
                with self.assertRaises(PermissionError):
                    _stop_posix_group(Mock(pid=123, poll=Mock(return_value=returncode)))

    def test_unity_hex_widths_and_bit_masks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/test_widths.c").write_text('''#include "unity.h"
void setUp(void){}
void tearDown(void){}
void test_hex_widths(void){
    TEST_ASSERT_EQUAL_HEX8(0xFF, (int8_t)-1);
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, (int16_t)-1);
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xFFFFFFFF), (int32_t)-1);
    TEST_ASSERT_EQUAL_HEX8(0x1FF, 0xFF);
}
void test_bits_pass(void){
    TEST_ASSERT_BITS(0xF0,0xA0,0xA5);
    TEST_ASSERT_BITS_HIGH(0x30,0x73);
    TEST_ASSERT_BITS_LOW(0x80,0x7F);
    UnityAssertBits(0,0xFF,0,0,__LINE__);
}
void test_bits_fail(void){TEST_ASSERT_BITS(0xF0,0x20,0x30);}
int main(void){
    UNITY_BEGIN(); RUN_TEST(test_hex_widths); RUN_TEST(test_bits_pass);
    RUN_TEST(test_bits_fail); return UNITY_END();
}
''')
            task = replace(DatasetLoader().get_task("tier1_crc16"), task_dir=root)
            compiled, result = ExecutionSandbox().compile_and_test(task, "void implementation(void){}")
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(result.completed, result.output)
            self.assertEqual((result.total_tests, result.passed_tests, result.failed_tests), (3, 2, 1))
            self.assertIn("Expected 0x00000020 Was 0x00000030", result.output)

    def test_disabled_runner_and_preprocessor_prose_do_not_hide_real_runner(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/test_runner.c").write_text('''#include "unity.h"
#if 0
#error don't mistake this for a multi-line C character literal
int main(int bad, int arguments, int here){return 0;}
#endif
void setUp(void){}
void tearDown(void){}
void test_ok(void){TEST_ASSERT_TRUE(1);}
int main(void){UNITY_BEGIN();RUN_TEST(test_ok);return UNITY_END();}
''')
            task = replace(DatasetLoader().get_task("tier1_crc16"), task_dir=root)
            compiled, result = ExecutionSandbox().compile_and_test(task, "void implementation(void){}")
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(result.passed, result.output)

    def test_deadline_kills_inherited_output_descendant(self):
        source = ("import subprocess,sys,time,os\n"
                  "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(4)'],"
                  "stdout=sys.stdout,stderr=sys.stderr,"
                  "creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))\n"
                  "print(child.pid,flush=True)\ntime.sleep(4)\n")
        for mode in ("native", "process"):
            with self.subTest(mode=mode):
                started = time.monotonic()
                with self.assertRaises(subprocess.TimeoutExpired) as caught:
                    run_bounded([sys.executable, "-c", source], timeout=0.6,
                                max_output_bytes=1024, isolation=mode)
                self.assertLess(time.monotonic() - started, 2.5)
                pid = int(caught.exception.stdout.strip())
                self.assertFalse(child_alive(pid), f"Descendant {pid} survived cleanup")

    def test_completed_parent_also_releases_owned_children(self):
        source = ("import subprocess,sys\n"
                  "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(4)'],"
                  "stdout=sys.stdout,stderr=sys.stderr,"
                  "creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))\n"
                  "print(p.pid,flush=True)\n")
        result = run_bounded([sys.executable, "-c", source], timeout=2, max_output_bytes=1024)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(child_alive(int(result.stdout.strip())))

    def test_output_limit_retains_only_bounded_prefix_and_stops_writer(self):
        source = "import os\nwhile True: os.write(1,b'x'*65536)\n"
        with self.assertRaises(OutputLimitExceeded) as caught:
            run_bounded([sys.executable, "-c", source], timeout=3, max_output_bytes=4096)
        self.assertEqual(caught.exception.output, b"x" * 4096)
        self.assertIn("truncated", str(caught.exception))

    def test_cancellation_event_stops_execution(self):
        cancelled = threading.Event()
        cancelled.set()
        started = time.monotonic()
        with self.assertRaises(ExecutionCancelled):
            run_bounded([sys.executable, "-c", "import time;time.sleep(4)"],
                        timeout=4, max_output_bytes=1024, cancel_event=cancelled)
        self.assertLess(time.monotonic() - started, 2)

    def test_process_memory_limit_is_applied(self):
        # This allocation is comfortably above the cap on both supported hosts.
        source = "a=bytearray(256*1024*1024);print('allocation succeeded')"
        result = run_bounded([sys.executable, "-c", source], timeout=5, max_output_bytes=4096,
                             isolation="process", memory_limit_bytes=128*1024*1024)
        self.assertNotEqual(result.returncode, 0)
        # Python 3.13 traceback source echoes the string literal on failure.
        self.assertNotIn(b"allocation succeeded", result.stdout.splitlines())

    def test_compile_timeout_is_configurable_independently(self):
        task = DatasetLoader().get_task("tier1_crc16")
        executor = ExecutionSandbox(compile_timeout_seconds=0.125)
        with TemporaryDirectory() as directory, patch(
                "aibenchmark_esw.sandbox.executor.run_bounded",
                side_effect=subprocess.TimeoutExpired("compiler", 0.125, output=b"partial")) as run:
            result = executor.compile_object(task, "int answer(void){return 1;}", Path(directory))
        self.assertEqual(run.call_args.kwargs["timeout"], 0.125)
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Compilation timed out")
        self.assertIn("partial", result.output)
        self.assertEqual(executor.execution_settings()["compile_timeout_seconds"], 0.125)

    def test_invalid_controls_are_rejected(self):
        for settings in ({"compile_timeout_seconds": 0}, {"compile_timeout_seconds": float("nan")},
                         {"max_output_bytes": True}, {"max_output_bytes": 0}, {"isolation": "unknown"},
                         {"memory_limit_bytes": 1}, {"sanitizers": ["unknown"]}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                ExecutionSandbox(**settings)

    def test_test_output_overflow_is_incomplete(self):
        loader = DatasetLoader()
        task = loader.get_task("tier1_crc16")
        source = '#include <stdio.h>\n' + loader.get_reference_solution(task.id)
        source = source.replace("return crc;", 'puts("' + "x" * 3000 + '"); return crc;', 1)
        compiled, result = ExecutionSandbox(max_output_bytes=1024).compile_and_test(task, source)
        self.addCleanup(compiled.cleanup)
        self.assertTrue(compiled.success, compiled.output)
        self.assertFalse(result.completed)
        self.assertIn("output truncated", result.output)
        self.assertLess(len(result.output), 1200)

    def test_unsupported_sanitizer_toolchain_fails_explicitly(self):
        task = DatasetLoader().get_task("tier1_crc16")
        compiled, result = ExecutionSandbox("tcc", sanitizers=("address",)).compile_and_test(task, "int x;")
        self.assertFalse(compiled.success)
        self.assertIn("Sanitizers require", compiled.output)
        self.assertFalse(result.completed)

    def test_sanitizer_flags_do_not_pollute_object_measurement(self):
        task = DatasetLoader().get_task("tier1_crc16")
        executor = ExecutionSandbox("clang", sanitizers=("address", "undefined"))
        commands = []
        def compile_fixture(command, **kwargs):
            commands.append(command)
            Path(command[command.index("-o") + 1]).write_bytes(b"object")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with TemporaryDirectory() as directory, patch(
                "aibenchmark_esw.sandbox.executor.run_bounded", side_effect=compile_fixture):
            source = Path(directory) / "source.c"
            source.write_text("int value;")
            executor._compile(task, [source], Path(directory) / "test.exe")
            executor.compile_object(task, "int value;", Path(directory))
        self.assertIn("-fsanitize=address,undefined", commands[0])
        self.assertIn("-fno-sanitize-recover=all", commands[0])
        self.assertFalse(any(flag.startswith("-fsanitize") for flag in commands[1]))

    def test_sanitizer_diagnostic_invalidates_an_otherwise_passing_summary(self):
        task = DatasetLoader().get_task("tier1_crc16")
        executor = ExecutionSandbox("clang", sanitizers=("undefined",))
        def compile_fixture(task, sources, output, **kwargs):
            output.write_bytes(b"fixture")
            return CompilationResult(True, "", binary_path=output, effective_standard="c99")
        def execute_fixture(command, **kwargs):
            wrapper = next(Path(command[0]).parent.glob("aibenchmark_tests_*.c")).read_text()
            token = wrapper.split("AIBenchMark-ESW:", 1)[1].split(":END", 1)[0]
            output = ("file.c:1:test:PASS\n1 Tests 0 Failures 0 Ignored\n"
                      "file.c:2: runtime error: overflow\n")
            Path(command[1]).write_text(f"AIBenchMark-ESW:{token}:END\n")
            return subprocess.CompletedProcess(command, 0, output.encode(), b"")
        with patch.object(executor, "_compile", side_effect=compile_fixture), patch(
                "aibenchmark_esw.sandbox.executor.run_bounded", side_effect=execute_fixture):
            compiled, result = executor.compile_and_test(task, "int answer(void){return 1;}")
        self.addCleanup(compiled.cleanup)
        self.assertEqual(result.passed_tests, 1)
        self.assertFalse(result.completed)
        self.assertFalse(result.passed)
        self.assertIn("runtime error:", result.output)

    @unittest.skipIf(os.name == "nt", "Real sanitizer runtime test runs in POSIX GCC/Clang CI")
    def test_real_sanitizers_accept_clean_code_and_stop_unsafe_candidates(self):
        compiler = find_clang()
        if compiler is None:
            import shutil
            compiler = shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC/Clang sanitizer runtime is unavailable")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/test_ub.c").write_text(
                '#include "unity.h"\nint answer(void);\nvoid setUp(void){}\nvoid tearDown(void){}\n'
                'void test_answer(void){TEST_ASSERT_TRUE(answer()!=0);}\n'
                'int main(void){UNITY_BEGIN();RUN_TEST(test_answer);return UNITY_END();}\n')
            task = replace(DatasetLoader().get_task("tier1_crc16"), task_dir=root)
            for sanitizer, source, diagnostic in (
                    ("undefined", "int answer(void){volatile int a=2147483647;return a+1;}", "runtime error:"),
                    # Runtime allocation size prevents scalar replacement from
                    # deleting the out-of-bounds access before ASan runs.
                    ("address", "#include <stdlib.h>\nint answer(void){volatile unsigned count=1;"
                     "volatile unsigned index=2;int *a=malloc(count*sizeof *a);if(!a)return 1;"
                     "a[0]=1;int value=a[index];free(a);return value;}", "AddressSanitizer")):
                with self.subTest(sanitizer=sanitizer):
                    executor = ExecutionSandbox(compiler, sanitizers=(sanitizer,))
                    compiled, result = executor.compile_and_test(task, "int answer(void){return 1;}")
                    self.addCleanup(compiled.cleanup)
                    self.assertTrue(compiled.success, compiled.output)
                    self.assertTrue(result.passed, result.output)
                    compiled, result = executor.compile_and_test(task, source)
                    self.addCleanup(compiled.cleanup)
                    self.assertTrue(compiled.success, compiled.output)
                    self.assertFalse(result.completed, result.output)
                    self.assertIn(diagnostic, result.output)


if __name__ == "__main__":
    unittest.main()
