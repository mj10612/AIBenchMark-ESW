import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from compiler_tools import find_clang

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.evaluation import evaluate_task
from aibenchmark_esw.models import (
    CompilationResult,
    SizeMetrics,
    StaticSafetyMetrics,
    TestResult,
)
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestClangClWarnings(unittest.TestCase):
    def test_parenthesized_locations_keep_rules_lines_and_distinct_messages(self):
        executor = ExecutionSandbox(compiler_path='clang-cl', warnings=True)
        with TemporaryDirectory() as directory:
            source = Path(directory).resolve() / 'candidate (copy).c'
            log = (f"{source}(7,13): warning: unused variable 'first' [-Wunused-variable]\n"
                   f"{source}(7): warning: unused variable 'second' [-Wunused-variable]\n"
                   f'{source}(9,3): warning: diagnostic without a warning flag\n')
            findings = executor._warning_findings(log, [str(source)])
            self.assertEqual([row['rule_id'] for row in findings],
                             ['compiler.-Wunused-variable', 'compiler.-Wunused-variable', 'compiler.warning'])
            self.assertEqual([row['line'] for row in findings], [7, 7, 9])
            self.assertIn("'first'", findings[0]['message'])
            self.assertIn("'second'", findings[1]['message'])
            for finding in findings:
                self.assertEqual(finding['engine'], 'compiler')
                self.assertEqual(finding['severity'], 'warning')
                self.assertEqual(finding['file'], str(source))
                self.assertEqual(finding['source_origin'], 'candidate')

    def test_headers_harness_and_locationless_warnings_are_not_candidate_findings(self):
        executor = ExecutionSandbox(compiler_path='clang-cl', warnings=True)
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'candidate.c'
            unity, harness = root / 'unity.c', root / 'aibenchmark_tests_0.c'
            log = '\n'.join(f'{path}(2,1): warning: unused variable [-Wunused-variable]'
                            for path in (source, root / 'include' / 'candidate.c', unity, harness))
            log += ('\ninclude/candidate.c(2): warning: header [-Wshadow]\n'
                    'clang-cl: warning: argument unused [-Wunused-command-line-argument]\n'
                    'warning: no source location [-Wunknown-warning-option]\n1 warning generated.')
            findings = executor._warning_findings(log, list(map(str, (source, unity, harness))))
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]['file'], str(source))
            self.assertEqual(findings[0]['source_origin'], 'candidate')

    def test_existing_gnu_and_msvc_locations_are_preserved(self):
        executor = ExecutionSandbox(compiler_path='clang-cl', warnings=True)
        with TemporaryDirectory() as directory:
            source = Path(directory).resolve() / 'candidate.c'
            log = (f'{source}:3:4: warning: conversion [-Wconversion]\n'
                   f"{source}(5): warning C4101: 'unused': unreferenced local variable\n")
            findings = executor._warning_findings(log, [str(source)])
            self.assertEqual([row['rule_id'] for row in findings], ['compiler.-Wconversion', 'compiler.C4101'])
            self.assertEqual([row['line'] for row in findings], [3, 5])

    def test_object_warning_contributes_to_evaluated_safety_score(self):
        task = DatasetLoader().get_task('tier1_crc16')
        executor = ExecutionSandbox(compiler_path='clang-cl', warnings=True)
        with TemporaryDirectory() as directory:
            source = Path(directory).resolve() / 'candidate.c'
            findings = executor._warning_findings(
                f"{source}(1,17): warning: unused variable 'unused' [-Wunused-variable]", [str(source)])
            binary = source.with_suffix('.o')
            binary.write_bytes(b'object fixture')
            compiled = CompilationResult(True, '', effective_standard='c99')
            tests = TestResult(total_tests=1, passed_tests=1, passed=True, completed=True, returncode=0)
            object_result = CompilationResult(True, '', binary_path=binary, findings=findings)
            cache = Mock()
            cache.validate.return_value = (SimpleNamespace(error=None, flash_bytes=100, ram_bytes=0), False)
            analyzer = Mock()
            analyzer.analyze.return_value = StaticSafetyMetrics(cppcheck_status='disabled')
            with patch.object(executor, 'compile_and_test', return_value=(compiled, tests)), \
                    patch.object(executor, 'compile_object', return_value=object_result), \
                    patch('aibenchmark_esw.evaluation.SizeAnalyzer.analyze', return_value=SizeMetrics(flash_bytes=100)):
                result = evaluate_task(task, 'candidate', 'reference', 'fixture', executor, analyzer, cache)
            self.assertTrue(result.test_result.passed)
            self.assertIsNone(result.error_log)
            self.assertEqual(result.safety_metrics.warning_count, 1)
            self.assertEqual(result.safety_metrics.findings, findings)
            self.assertEqual(result.scores.safety_score, 97)
            self.assertEqual(result.scores.total_score, 99.4)

    def test_real_clang_cl_object_warning_retains_rule_location_and_ownership(self):
        clang = find_clang()
        if not clang or not Path(clang).with_name('clang-cl.exe').is_file():
            self.skipTest('Windows clang-cl unavailable')
        compiler = Path(clang).with_name('clang-cl.exe')
        executor = ExecutionSandbox(compiler_path=str(compiler), warnings=True)
        task = DatasetLoader().get_task('tier1_crc16')
        with TemporaryDirectory() as directory:
            result = executor.compile_object(task, 'int f(void){int unused; return 0;}', Path(directory))
            self.assertTrue(result.success, result.output)
            self.assertIn("unused variable 'unused'", result.output)
            self.assertEqual(len(result.findings), 1)
            finding = result.findings[0]
            self.assertEqual(finding['rule_id'], 'compiler.-Wunused-variable')
            self.assertEqual(finding['line'], 1)
            self.assertEqual(Path(finding['file']).resolve(), Path(directory).resolve() / 'candidate.c')
            self.assertEqual(finding['source_origin'], 'candidate')
