import csv
import os
import struct
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import test_containment
from compiler_tools import find_clang

from aibenchmark_esw.cli import build_parser, cmd_doctor
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.doctor import run_doctor
from aibenchmark_esw.sandbox.cross_compiler import CrossCompiler
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.process_runner import OutputLimitExceeded
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestAnalyzerContainmentIssues(unittest.TestCase):
    def test_analyzer_is_contained_and_output_and_findings_are_bounded(self):
        executor = Mock(containment=True, cancel_event=None)
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'candidate.c'
            source.write_text('void f(void){}')
            executor._run_contained.return_value = subprocess.CompletedProcess(
                [], 0, b'warning:many:candidate.c:1:message\n' * 201, b'')
            analyzer = StaticAnalyzer('cppcheck', max_output_bytes=2048)
            result = analyzer.analyze(source, executor=executor)
            self.assertEqual(result.cppcheck_status, 'failed')
            self.assertIn('finding limit', result.cppcheck_diagnostic)
            self.assertLessEqual(len(result.findings), 200)
            options = executor._run_contained.call_args.kwargs
            self.assertEqual(options['max_output_bytes'], 2048)
            self.assertEqual(options['memory_limit_bytes'], 536870912)
            executor._run_contained.side_effect = OutputLimitExceeded(b'prefix', 2048)
            result = analyzer.analyze(source, executor=executor)
            self.assertEqual(result.cppcheck_status, 'failed')
            self.assertIn('truncated', result.cppcheck_diagnostic)

    def test_doctor_runs_fixture_when_only_container_has_compiler(self):
        loader = DatasetLoader()
        # The fake container executes the local compiler, so retain its host
        # linker policy rather than pretending macOS uses a Linux linker.
        executor = ExecutionSandbox(hardening='off')
        executor.containment = Mock()
        with patch('aibenchmark_esw.doctor.shutil.which', return_value=None), patch.object(
                executor, 'compiler_identity', return_value={'version': 'container GCC'}), patch.object(
                executor, '_run_contained', wraps=__import__(
                    'aibenchmark_esw.sandbox.process_runner', fromlist=['run_bounded']).run_bounded):
            report = run_doctor([loader.get_task('tier1_crc16')], loader, executor,
                                analyzer=StaticAnalyzer('off'))
        self.assertTrue(report['passed'], report)
        checks = {item['name']: item for item in report['checks']}
        self.assertTrue(checks['compile_run:c99']['passed'])
        self.assertTrue(checks['object_size:c99']['passed'])

    def test_cli_doctor_applies_analyzer_options_and_mutations_reject_noops(self):
        import io
        from contextlib import redirect_stdout
        output = io.StringIO()
        args = build_parser().parse_args(['doctor', '--tasks', 'tier1_crc16',
            '--static-analysis-timeout', '0.25', '--extended-safety-rules', '--max-output-bytes', '4096'])
        with redirect_stdout(output), patch.dict(os.environ, {'AIBENCHMARK_ESW_CPPCHECK': 'off'}), patch(
                'aibenchmark_esw.doctor.run_doctor', return_value={'passed': True, 'checks': []}) as invoke:
            code = cmd_doctor(args)
        self.assertEqual(code, 0)
        configuration = invoke.call_args.kwargs['analyzer'].configuration()
        self.assertEqual(configuration['timeout_seconds'], .25)
        self.assertTrue(configuration['extended_rules'])
        self.assertEqual(configuration['max_output_bytes'], 4096)
        with self.assertRaises(SystemExit), patch('sys.stderr', io.StringIO()):
            build_parser().parse_args(['mutations', '--extended-safety-rules'])

    def test_fused_paths_and_csv_mounts(self):
        backend = test_containment.TestContainment().backend()
        with TemporaryDirectory(prefix='comma,space ') as directory, TemporaryDirectory() as external:
            root, include = Path(directory), Path(external)
            (include / 'api.h').write_text('int f(void);')
            for flag in ('-I', '-L', '-B', '--sysroot=', '/I', '/FI'):
                input_path = include / 'api.h' if flag == '/FI' else include
                _, _, command = backend._workspace_command(['gcc', flag + str(input_path)], root)
                self.assertTrue(command[1].startswith(flag + '/workspace/'), command)
            for flag in ('/Fo', '/Fe'):
                _, _, command = backend._workspace_command(['cl', '/nologo', flag + str(root / 'out')], root)
                self.assertIn(flag + '/workspace/out', command)
            with self.assertRaisesRegex(ValueError, 'Unrecognized containment path flag'):
                backend._workspace_command(['gcc', '--unknown=' + str(include)], root)
            with patch('aibenchmark_esw.sandbox.containment.run_bounded',
                       return_value=subprocess.CompletedProcess([], 0, b'', b'')) as runner:
                backend.run(['gcc', '--version'], cwd=root, timeout=1, max_output_bytes=1024)
            command = runner.call_args_list[0].args[0]
            fields = next(csv.reader([command[command.index('--mount') + 1]]))
            self.assertIn('source=' + str(root.resolve()), fields)
            if os.name != 'nt':
                self.assertEqual(root.stat().st_mode & 0o077, 0)
                self.assertTrue(all(path.stat().st_mode & 0o022 == 0 for path in root.rglob('*')))

    def test_rv64_selection_prefers_matching_toolchain_and_rejects_mismatch(self):
        with patch('aibenchmark_esw.sandbox.cross_compiler.shutil.which', side_effect=lambda name: name), patch(
                'aibenchmark_esw.sandbox.cross_compiler.run_bounded',
                return_value=subprocess.CompletedProcess([], 0, b'GCC', b'')):
            self.assertEqual(CrossCompiler('riscv:rv64gc').compiler, 'riscv64-unknown-elf-gcc')
            with self.assertRaisesRegex(ValueError, 'RV64-capable'):
                CrossCompiler('riscv:rv64gc', 'riscv32-unknown-elf-gcc')

    def test_modern_arm_targets_and_cross_warnings(self):
        with patch('aibenchmark_esw.sandbox.cross_compiler.run_bounded',
                   return_value=subprocess.CompletedProcess([], 0, b'clang', b'')):
            for cpu in ('cortex-m23', 'cortex-m33', 'cortex-m55', 'cortex-m85'):
                cross = CrossCompiler('arm:' + cpu, 'clang')
                self.assertIn('-mcpu=' + cpu, cross.flags)
        executor = ExecutionSandbox(warnings=True)
        cross = CrossCompiler('arm:cortex-m33', 'clang', warnings=True,
                              finding_parser=executor._warning_findings,
                              runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, b'clang', b''))
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / 'candidate.c', Path(directory) / 'candidate.o'
            source.write_text('int f(void){int unused;return 0;}')
            def compile_mock(command, **options):
                self.assertIn('-Wall', command)
                output.write_bytes(b'object')
                return subprocess.CompletedProcess(command, 0,
                    b'candidate.c:1: warning: unused variable [-Wunused-variable]\n', b'')
            cross.runner = compile_mock
            result = cross.compile(DatasetLoader().get_task('tier1_crc16'), source, output)
        self.assertTrue(result.success)
        self.assertEqual(result.findings[0]['rule_id'], 'compiler.-Wunused-variable')
        self.assertEqual(result.warning_flags, cross.settings()['warning_flags'])

    def test_coff_uninitialized_virtual_size_is_ram(self):
        data = bytearray(60)
        struct.pack_into('<HH', data, 0, 0x8664, 1)
        struct.pack_into('<I', data, 28, 548)
        struct.pack_into('<I', data, 56, 0xC0000080)
        self.assertEqual(SizeAnalyzer()._parse_coff(bytes(data), 0), (0, 548))

    def test_real_coff_bss_and_modern_arm_objects(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest('Clang unavailable')
        with TemporaryDirectory() as directory:
            source, output = Path(directory) / 'memory.c', Path(directory) / 'memory.o'
            source.write_text('int buffer[137]; int read_buffer(int i){return buffer[i];}')
            for target, flags in [('x86_64-pc-windows-msvc', []), ('arm-none-eabi', ['-mcpu=cortex-m33', '-mthumb'])]:
                with self.subTest(target=target):
                    result = subprocess.run([compiler, '--target=' + target, '-fno-common', *flags,
                        '-c', str(source), '-o', str(output)], capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(SizeAnalyzer().analyze(output).ram_bytes, 548)


if __name__ == '__main__':
    unittest.main()
