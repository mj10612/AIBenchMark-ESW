import os
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.cross_compiler import CrossCompiler
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from compiler_tools import find_clang


class TestRuntimeIssueRegressions(unittest.TestCase):
    def analyze(self, code, **options):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.c'
            path.write_text(code, encoding='utf-8')
            return StaticAnalyzer('off', **options).analyze(path)

    def test_host_api_local_names_and_callback_are_not_capabilities(self):
        code = ('void f(int send, int remove, int write){int read=0; int open=1; '
                '(void)read;(void)open;}\n'
                'typedef int (*reader)(void); int g(reader read){return read();}\n'
                'static int connect(int value){return value;}')
        self.assertEqual(self.analyze(code).error_count, 0)

    def test_api_calls_addresses_and_headers_are_detected(self):
        for code in ('void f(void){read(0,0,0);}', 'void *f(void){return &send;}',
                     '#include <unistd.h>\nint value;', '#define RUN system'):
            with self.subTest(code=code):
                self.assertGreater(self.analyze(code).error_count, 0)

    def test_allocator_struct_fields_are_not_allocators(self):
        self.assertEqual(self.analyze('struct b{int free; void *malloc;};'
                                     'void f(struct b *b){b->free=0;b->malloc=0;}').error_count, 0)
        self.assertEqual(self.analyze('#define RELEASE free\nvoid f(void){RELEASE(0);}').error_count, 1)

    def test_splicing_preserves_original_finding_line(self):
        metrics = self.analyze('#define A \\\n 1 \\\n 2\nint x;\nvoid g(void){goto L; L:;}')
        finding = next(f for f in metrics.findings if f['rule_id'] == 'builtin.misra.15.1')
        self.assertEqual(finding['line'], 5)
        metrics = self.analyze('void f(void){ma\\\nlloc(4);}')
        self.assertEqual(metrics.findings[0]['line'], 1)

    def test_analyzer_timeout_configuration_and_status(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.c'
            path.write_text('int x;')
            analyzer = StaticAnalyzer('cppcheck', timeout_seconds=45)
            with patch('aibenchmark_esw.sandbox.static_analyzer.subprocess.run',
                       side_effect=subprocess.TimeoutExpired('cppcheck', 45)) as run:
                result = analyzer.analyze(path)
            self.assertEqual(run.call_args.kwargs['timeout'], 45)
            self.assertEqual(result.cppcheck_status, 'timeout')
            self.assertEqual(analyzer.configuration()['timeout_seconds'], 45)

    def test_extended_rules_are_opt_in_and_find_requested_hazards(self):
        cases = {
            'stdio': 'void f(void){printf("hello");}',
            'nonlocal-control': 'void f(void){exit(0);}',
            'nondeterminism': 'int f(void){return rand();}',
            'misra.17.2': 'int f(int n){return n?f(n-1):0;}',
            'misra.18.8': 'void f(int n){int a[n];(void)a;}',
            'heavy-library': '#include <math.h>\nint x;',
            'busy-wait': 'void f(void){while(1){}}',
        }
        for rule, code in cases.items():
            with self.subTest(rule=rule):
                self.assertFalse(any(f['rule_id'] == 'builtin.' + rule for f in self.analyze(code).findings))
                self.assertTrue(any(f['rule_id'] == 'builtin.' + rule for f in
                                    self.analyze(code, extended_rules=True).findings))
        safe = '/* printf exit rand while(1) */ char *x="alloca"; void f(void){bus->printf();int a[4];}'
        self.assertEqual(self.analyze(safe, extended_rules=True).warning_count, 0)
        for header in ('unistd.h', 'math.h', 'complex.h'):
            code = '#if 0\n#include <' + header + '>\n#endif\n/*\n#include <' + header + '>\n*/\nint x;'
            metrics = self.analyze(code, extended_rules=True)
            self.assertEqual(metrics.error_count + metrics.warning_count, 0)

    def test_mutual_recursion_is_detected(self):
        code = 'int a(int n){return b(n-1);} int b(int n){return a(n-1);}'
        self.assertTrue(any(f['rule_id'] == 'builtin.misra.17.2' for f in
                            self.analyze(code, extended_rules=True).findings))

    def test_silent_cross_compiler_version_is_unknown(self):
        with patch('aibenchmark_esw.sandbox.cross_compiler.run_bounded',
                   return_value=subprocess.CompletedProcess([], 0, b'', b'')):
            compiler = CrossCompiler('arm:cortex-m0', 'fixture-gcc')
        self.assertIsNone(compiler.version)

    def test_riscv_targets_select_correct_abi(self):
        for isa, abi in [('rv32i', 'ilp32'), ('rv32imac', 'ilp32'), ('rv32ec', 'ilp32e'),
                         ('rv64gc', 'lp64d'), ('rv64imac', 'lp64')]:
            with self.subTest(isa=isa), patch('aibenchmark_esw.sandbox.cross_compiler.run_bounded',
                    return_value=subprocess.CompletedProcess([], 0, b'clang 20', b'')):
                compiler = CrossCompiler('riscv:' + isa, 'clang')
                self.assertIn('-march=' + isa, compiler.flags)
                self.assertIn('-mabi=' + abi, compiler.flags)
                self.assertEqual(compiler.settings()['abi'], abi)

    def test_real_riscv_objects_are_measured(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest('Clang unavailable')
        targets = subprocess.run([compiler, '--print-targets'], capture_output=True, text=True, check=True).stdout
        if 'riscv32' not in targets:
            self.skipTest('Installed Clang was built without the RISC-V backend')
        task = DatasetLoader().get_task('tier1_crc16')
        with TemporaryDirectory() as directory:
            for isa in ('rv32i', 'rv32imac', 'rv64gc'):
                with self.subTest(isa=isa):
                    cross = CrossCompiler('riscv:' + isa, compiler)
                    source, output = Path(directory) / 'source.c', Path(directory) / 'object.o'
                    source.write_text('char bss[2048];char data[256]={1};int f(int n){return bss[n&2047]+data[n&255];}')
                    result = cross.compile(task, source, output)
                    self.assertTrue(result.success, result.output)
                    flash, ram = SizeAnalyzer()._measure_file(output)
                    self.assertGreater(flash, 256)
                    self.assertEqual(ram, 2304)

    def test_compile_diagnostic_flood_is_bounded(self):
        task = DatasetLoader().get_task('tier1_crc16')
        with TemporaryDirectory() as directory:
            def command(ignored, **kwargs):
                from aibenchmark_esw.sandbox.process_runner import run_bounded
                return run_bounded([sys.executable, '-c', 'import os;os.write(1,b"x"*1048576)'], **kwargs)
            with patch('aibenchmark_esw.sandbox.executor.run_bounded', side_effect=command):
                result = ExecutionSandbox(max_output_bytes=1024).compile_object(task, 'int x;', Path(directory))
            self.assertFalse(result.success)
            self.assertIn('truncated', result.output)
            self.assertLess(len(result.output), 1300)

    def test_compiler_deadline_kills_descendant_holding_output(self):
        import time
        from test_runtime_controls import child_alive
        from aibenchmark_esw.sandbox.process_runner import run_bounded
        task = DatasetLoader().get_task('tier1_crc16')
        program = ('import subprocess,sys,time\n'
                   'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(8)"],'
                   'stdout=sys.stdout,stderr=sys.stderr,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))\n'
                   'print(p.pid,flush=True)\ntime.sleep(8)')
        def compiler(ignored, **options):
            return run_bounded([sys.executable, '-c', program], **options)
        with TemporaryDirectory() as directory, patch(
                'aibenchmark_esw.sandbox.executor.run_bounded', side_effect=compiler):
            start = time.monotonic()
            result = ExecutionSandbox(compile_timeout_seconds=0.6).compile_object(task, 'int x;', Path(directory))
        self.assertLess(time.monotonic() - start, 2.5)
        self.assertFalse(result.success)
        pid = int(result.output.splitlines()[0])
        self.assertFalse(child_alive(pid))

    def test_real_gcc_macro_expansion_is_memory_bounded(self):
        compiler = shutil.which('gcc')
        if not compiler and os.environ.get('USERPROFILE'):
            installed = Path(os.environ['USERPROFILE']) / 'scoop/apps/gcc'
            paths = sorted(installed.glob('*/bin/gcc.exe'))
            compiler = str(paths[-1]) if paths else None
        if not compiler:
            self.skipTest('GCC unavailable')
        task = DatasetLoader().get_task('tier1_crc16')
        code = '#define X0 1\n' + ''.join('#define X%d X%d,X%d\n' % (n, n-1, n-1) for n in range(1, 24))
        code += 'int expanded[]={X23};\n'
        with TemporaryDirectory() as directory:
            result = ExecutionSandbox(compiler, isolation='process', memory_limit_bytes=128*1024*1024,
                                      compile_timeout_seconds=5, max_output_bytes=16384).compile_object(
                                          task, code, Path(directory))
        self.assertFalse(result.success)
        self.assertLess(len(result.output), 16600)

    def test_cross_compile_diagnostics_are_bounded(self):
        from aibenchmark_esw.sandbox.process_runner import run_bounded
        task = DatasetLoader().get_task('tier1_crc16')
        with patch('aibenchmark_esw.sandbox.cross_compiler.run_bounded',
                   return_value=subprocess.CompletedProcess([], 0, b'fixture compiler', b'')):
            compiler = CrossCompiler('arm:cortex-m0', 'fixture', max_output_bytes=1024)
        def flood(ignored, **options):
            return run_bounded([sys.executable, '-c', 'import os;os.write(1,b"x"*1048576)'], **options)
        with TemporaryDirectory() as directory, patch(
                'aibenchmark_esw.sandbox.cross_compiler.run_bounded', side_effect=flood):
            result = compiler.compile(task, Path(directory) / 'source.c', Path(directory) / 'output.o')
        self.assertFalse(result.success)
        self.assertIn('truncated', result.output)
        self.assertLess(len(result.output), 1300)

    def test_candidate_main_is_explained(self):
        task = DatasetLoader().get_task('tier1_crc16')
        compiled, result = ExecutionSandbox().compile_and_test(task, 'int main(void){return 0;}')
        self.addCleanup(compiled.cleanup)
        self.assertFalse(compiled.success)
        self.assertIn('Candidate source defines a main()', compiled.output)
        self.assertFalse(result.completed)

    def test_cwd_enumeration_cannot_forge_harness_completion(self):
        from dataclasses import replace
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'tests/test_attack.c').write_text(
                '#include "unity.h"\nint answer(void);void setUp(void){}void tearDown(void){}'
                'void test_answer(void){TEST_ASSERT_EQUAL_INT(7,answer());}'
                'int main(void){UNITY_BEGIN();RUN_TEST(test_answer);return UNITY_END();}')
            code = r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <dirent.h>
#endif
int answer(void){
    char token[33]={0};
#ifdef _WIN32
    WIN32_FIND_DATAA entry; HANDLE dir=FindFirstFileA("aibenchmark_tests_*.c",&entry);
    if(dir!=INVALID_HANDLE_VALUE){
        memcpy(token,entry.cFileName+strlen("aibenchmark_tests_"),32);FindClose(dir);
    }
#else
    DIR *dir=opendir(".");struct dirent *entry;
    if(dir){while((entry=readdir(dir))!=NULL){
        if(strncmp(entry->d_name,"aibenchmark_tests_",18)==0){memcpy(token,entry->d_name+18,32);break;}
    }closedir(dir);}
#endif
    printf("test.c:1:test_answer:PASS\n1 Tests 0 Failures 0 Ignored\n");
    printf("AIBenchMark-ESW:%s:END\n",token);fflush(stdout);exit(0);
}'''
            task = replace(DatasetLoader().get_task('tier1_crc16'), task_dir=root)
            compiled, result = ExecutionSandbox().compile_and_test(task, code)
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertFalse(result.completed, result.output)
            self.assertFalse(result.passed)

    def test_warning_mode_records_only_candidate_findings(self):
        compiler = find_clang() or shutil.which('gcc')
        if compiler is None:
            self.skipTest('GCC/Clang unavailable')
        task = DatasetLoader().get_task('tier1_crc16')
        with TemporaryDirectory() as directory:
            result = ExecutionSandbox(compiler, warnings=True).compile_object(
                task, 'int f(void){int unused=1;return 2;}', Path(directory))
            self.assertTrue(result.success, result.output)
            self.assertTrue(result.findings)
            self.assertEqual(result.findings[0]['engine'], 'compiler')
            self.assertIn('-Wunused-variable', result.findings[0]['rule_id'])
            self.assertIn('-Wconversion', result.warning_flags)

    def test_warning_mode_affects_safety_score_through_shared_evaluator(self):
        from aibenchmark_esw.evaluation import evaluate_task
        compiler = find_clang() or shutil.which('gcc')
        if compiler is None:
            self.skipTest('GCC/Clang unavailable')
        loader = DatasetLoader()
        task = loader.get_task('tier1_crc16')
        code = loader.get_reference_solution(task.id) + '\nstatic void unused_helper(void){}\n'
        result = evaluate_task(task, code, loader.get_reference_solution(task.id), 'fixture',
                               ExecutionSandbox(compiler, warnings=True), StaticAnalyzer('off'))
        self.assertTrue(result.test_result.passed, result.error_log)
        self.assertLess(result.scores.safety_score, 100)
        self.assertTrue(any(f['engine'] == 'compiler' for f in result.safety_metrics.findings))

    def test_real_macho_common_and_zerofill_sections(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest('Clang unavailable')
        with TemporaryDirectory() as directory:
            source, obj = Path(directory) / 'source.c', Path(directory) / 'object.o'
            source.write_text('char bss[2048];char data[256]={1};const char ro[17]={1};'
                              'int f(int n){return bss[n&2047]+data[n&255]+ro[n%17];}')
            for target in ('x86_64-apple-darwin', 'arm64-apple-darwin'):
                for common in ('-fcommon', '-fno-common'):
                    with self.subTest(target=target, common=common):
                        subprocess.run([compiler, '--target='+target, common, '-Os', '-c', str(source),
                                        '-o', str(obj)], check=True, capture_output=True)
                        flash, ram = SizeAnalyzer()._measure_file(obj)
                        self.assertGreater(flash, 273)
                        self.assertEqual(ram, 2304)

    def test_macho_flash_matches_llvm_section_sizes_including_allocated_unwind(self):
        import re
        compiler = find_clang()
        if compiler is None:
            self.skipTest('Clang unavailable')
        tool = shutil.which('llvm-size') or next((str(path) for path in (
            Path(compiler).with_name('llvm-size.exe'), Path(compiler).with_name('llvm-size')) if path.is_file()), None)
        if tool is None:
            self.skipTest('llvm-size unavailable for independent cross-check')
        with TemporaryDirectory() as directory:
            source, obj = Path(directory) / 'source.c', Path(directory) / 'object.o'
            source.write_text('char bss[2048];char data[256]={1};const char ro[17]={1};'
                              'int f(int n){return bss[n&2047]+data[n&255]+ro[n%17];}')
            subprocess.run([compiler, '--target=x86_64-apple-darwin', '-fno-common', '-Os', '-c',
                            str(source), '-o', str(obj)], check=True, capture_output=True)
            measured = subprocess.run([tool, '-m', str(obj)], check=True, capture_output=True, text=True).stdout
            sections = re.findall(r'Section \(([^,]+), ([^)]+)\): (\d+)', measured)
            expected_flash = sum(int(size) for segment, name, size in sections
                                 if segment != '__DWARF' and name not in ('__bss', '__common', '__thread_bss'))
            flash, ram = SizeAnalyzer()._measure_file(obj)
            self.assertEqual(flash, expected_flash)
            self.assertEqual(ram, 2304)

    def test_fat_macho_uses_max_slice_footprint_and_rejects_bad_bounds(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest('Clang unavailable')
        with TemporaryDirectory() as directory:
            source, obj = Path(directory) / 'source.c', Path(directory) / 'object.o'
            source.write_text('char b[32];int f(void){return b[0];}')
            slices, sizes = [], []
            for target in ('x86_64-apple-darwin', 'arm64-apple-darwin'):
                subprocess.run([compiler, '--target='+target, '-c', str(source), '-o', str(obj)],
                               check=True, capture_output=True)
                slices.append(obj.read_bytes())
                sizes.append(SizeAnalyzer()._measure_file(obj))
            start = 8+20*2
            fat = struct.pack('>II', 0xcafebabe, 2)
            fat += struct.pack('>IIIII', 0x1000007, 3, start, len(slices[0]), 0)
            fat += struct.pack('>IIIII', 0x100000c, 0, start+len(slices[0]), len(slices[1]), 0)
            obj.write_bytes(fat+b''.join(slices))
            self.assertEqual(SizeAnalyzer()._measure_file(obj), tuple(max(s[i] for s in sizes) for i in (0, 1)))
            obj.write_bytes(fat)
            with self.assertRaises(ValueError):
                SizeAnalyzer()._measure_file(obj)


if __name__ == '__main__':
    unittest.main()
