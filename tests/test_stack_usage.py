import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compiler_tools import find_clang

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestStackUsage(unittest.TestCase):
    def stack_module(self):
        self.assertIsNotNone(importlib.util.find_spec('aibenchmark_esw.sandbox.stack_usage'))
        from aibenchmark_esw.sandbox import stack_usage
        return stack_usage

    def test_records_distinguish_static_bounded_and_unbounded(self):
        module = self.stack_module()
        evidence = module.parse_stack_usage('candidate.c:1:2:buffer\t288\tstatic\ncandidate.c:2:1:bounded\t40\tdynamic,bounded\ncandidate.c:3:1:vla\t16\tdynamic\n')
        self.assertEqual([row['classification'] for row in evidence['functions']], ['static', 'dynamic-bounded', 'unknown'])
        self.assertEqual(evidence['functions'][2]['bytes'], None)
        self.assertEqual(evidence['functions'][2]['reported_bytes'], 16)
        self.assertEqual(evidence['max_per_function_bytes'], 288)
        self.assertEqual(evidence['whole_program_peak_bytes'], None)
        self.assertEqual(evidence['bounded_functions'], 2)

    def test_missing_malformed_oversized_records_are_unavailable(self):
        module = self.stack_module()
        for text in ('', 'bad record', 'x\t-1\tstatic', 'x\t0\tunsupported'):
            evidence = module.parse_stack_usage(text)
            self.assertEqual(evidence['status'], 'unavailable')
            self.assertIsNone(evidence['max_per_function_bytes'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.su'
            self.assertEqual(module.read_stack_usage(path, 10)['status'], 'unavailable')
            path.write_text('x' * 11)
            self.assertEqual(module.read_stack_usage(path, 10)['status'], 'unavailable')

    def test_real_spi_object_has_stack_evidence_without_static_ram_change(self):
        compiler = find_clang()
        if not compiler:
            self.skipTest('Clang unavailable')
        self.stack_module()
        task = DatasetLoader().get_task('tier3_spi_flash')
        executor = ExecutionSandbox(compiler_path=compiler, stack_usage=True)
        code = task.reference_path.read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            result = executor.compile_object(task, code, Path(directory))
            self.assertTrue(result.success, result.output)
            self.assertGreater(result.stack_usage['max_per_function_bytes'], 0)
            self.assertEqual(result.stack_usage['provenance']['target'], 'host')
            self.assertIn('-fstack-usage', result.stack_usage['provenance']['flags'])
            self.assertIsNotNone(result.stack_usage['provenance']['compiler']['version'])

    def test_unsupported_compiler_is_explicit_without_stack_flag(self):
        self.assertIn('stack_usage', ExecutionSandbox.__init__.__code__.co_varnames)
        executor = ExecutionSandbox(compiler_path='tcc', stack_usage=True)
        self.assertEqual(executor.stack_usage_flags(), [])
        from aibenchmark_esw.models import CompilationResult
        evidence = executor.collect_stack_usage(CompilationResult(True, ''), Path('missing.o'), ['-Os'])
        self.assertEqual(evidence['status'], 'unavailable')
        self.assertIn('Unsupported', evidence['reason'])

    def test_evidence_roundtrip_markdown_html_and_schema(self):
        from test_aggregation import fixture_report

        from aibenchmark_esw.metrics.exports import report_html
        from aibenchmark_esw.metrics.reporter import BenchmarkReporter
        from aibenchmark_esw.report_schema import report_schema
        module = self.stack_module()
        report = fixture_report()
        evidence = module.parse_stack_usage('candidate.c:1:fn\t32\tstatic', {'target': 'host'})
        report['tasks'][0]['stack_usage'] = dict(candidate=evidence, reference=evidence)
        results = BenchmarkReporter.from_json_dict(report)
        self.assertEqual(results[0].stack_usage, report['tasks'][0]['stack_usage'])
        saved = BenchmarkReporter.to_json_dict(results, report['model_name'], report['metadata'])
        self.assertEqual(saved['tasks'][0]['stack_usage'], report['tasks'][0]['stack_usage'])
        self.assertIn('stack per-function maximum 32 B', BenchmarkReporter.generate_markdown(results, report['model_name']))
        self.assertIn('stack per-function maximum 32 B', report_html(results, report['model_name']))
        self.assertIn('stack_usage', report_schema()['properties']['tasks']['items']['properties'])
        self.assertEqual(saved['overall_score'], report['overall_score'])
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pass
        else:
            Draft202012Validator(report_schema()).validate(saved)

    def test_invalid_unknown_frame_cannot_be_loaded_as_zero(self):
        from test_aggregation import fixture_report

        from aibenchmark_esw.metrics.reporter import BenchmarkReporter
        module = self.stack_module()
        evidence = module.parse_stack_usage('candidate.c:1:fn\t16\tdynamic')
        evidence['functions'][0]['bytes'] = 0
        report = fixture_report()
        report['tasks'][0]['stack_usage'] = dict(candidate=evidence, reference=evidence)
        with self.assertRaisesRegex(ValueError, 'stack'):
            BenchmarkReporter.from_json_dict(report)

    def test_rejected_stack_flag_does_not_break_object_measurement(self):
        from aibenchmark_esw.models import CompilationResult
        task = DatasetLoader().get_task('tier1_crc16')
        executor = ExecutionSandbox(compiler_path='gcc', stack_usage=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'candidate.o'
            failure = CompilationResult(False, 'unrecognized command-line option -fstack-usage')
            success = CompilationResult(True, '', binary_path=output)
            with patch.object(executor, '_compile', side_effect=[failure, success]) as compile_object:
                result = executor.compile_object(task, 'void foo(void) {}', Path(directory))
            self.assertTrue(result.success)
            self.assertEqual(compile_object.call_count, 2)
            self.assertEqual(result.stack_usage['status'], 'unavailable')

    def test_compiler_warning_source_identity_preserves_headers(self):
        executor = ExecutionSandbox(compiler_path='gcc', warnings=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate.c'
            header = root / 'include' / 'candidate.c'
            log = f'{candidate}:1:2: warning: candidate [-Wconversion]\n{header}:2:1: warning: header [-Wshadow]\ncandidate.c:3:1: warning: ambiguous [-Wunused-variable]\nunity.c:4:2: warning: harness [-Wconversion]\n{root / "aibenchmark_tests_0.c"}:4:2: warning: harness [-Wconversion]'
            findings = executor._warning_findings(log, [str(candidate)])
            self.assertEqual([row.get('source_origin') for row in findings], ['candidate', 'unknown'])
            self.assertEqual(findings[1]['file'], 'candidate.c')

    def test_real_candidate_reference_scores_match_default_and_cross_target_is_separate(self):
        from aibenchmark_esw.evaluation import evaluate_task
        from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer
        compiler = find_clang()
        if not compiler:
            self.skipTest('Clang unavailable')
        task = DatasetLoader().get_task('tier1_crc16')
        code = task.reference_path.read_text(encoding='utf-8')
        default = evaluate_task(task, code, code, 'reference', ExecutionSandbox(compiler_path=compiler), StaticAnalyzer(cppcheck_cmd='off'))
        measured = evaluate_task(task, code, code, 'reference', ExecutionSandbox(compiler_path=compiler, stack_usage=True), StaticAnalyzer(cppcheck_cmd='off'))
        self.assertTrue(default.compiled, default.error_log)
        self.assertEqual(default.scores, measured.scores)
        self.assertNotIn('stack_usage', default.to_dict())
        self.assertEqual(measured.stack_usage['candidate']['status'], 'measured')
        self.assertEqual(measured.stack_usage['candidate'], measured.stack_usage['reference'])
        executor = ExecutionSandbox(compiler_path=compiler, stack_usage=True, target='arm:cortex-m0', cross_compiler=compiler)
        with tempfile.TemporaryDirectory() as directory:
            result = executor.compile_object(task, code, Path(directory))
        self.assertTrue(result.success, result.output)
        self.assertEqual(result.stack_usage['provenance']['target'], 'arm:cortex-m0')
        self.assertIn('-mcpu=cortex-m0', result.stack_usage['provenance']['flags'])

    def test_invalid_source_is_not_retried_as_evidence_flag_failure(self):
        from aibenchmark_esw.models import CompilationResult
        task = DatasetLoader().get_task('tier1_crc16')
        executor = ExecutionSandbox(compiler_path='gcc', stack_usage=True)
        with tempfile.TemporaryDirectory() as directory, patch.object(executor, '_compile', return_value=CompilationResult(False, 'expected semicolon')) as compile_object:
            result = executor.compile_object(task, 'invalid source', Path(directory))
            self.assertFalse(result.success)
            self.assertEqual(compile_object.call_count, 1)
            self.assertIsNone(result.stack_usage['max_per_function_bytes'])

    def test_boolean_coverage_or_maximum_is_not_numeric_stack_evidence(self):
        module = self.stack_module()
        evidence = module.parse_stack_usage('candidate.c:1:fn\t0\tstatic')
        for field in ('bounded_functions', 'total_functions', 'max_per_function_bytes'):
            invalid = copy.deepcopy(evidence)
            invalid[field] = field != 'max_per_function_bytes'
            with self.assertRaisesRegex(ValueError, 'stack'):
                module.validate_stack_usage(dict(candidate=invalid, reference=evidence))

