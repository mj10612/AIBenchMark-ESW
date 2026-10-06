import unittest
import xml.etree.ElementTree as ET

from aibenchmark_esw.metrics.junit import render_junit
from aibenchmark_esw.models import (
    DimensionScores, SizeMetrics, StaticSafetyMetrics, TaskEvaluationResult, TestResult,
)


class TestJUnitReport(unittest.TestCase):
    def result(self, name):
        return TaskEvaluationResult(name, 1, "model<&>", True,
            TestResult(total_tests=1, passed_tests=1, completed=True, passed=True),
            SizeMetrics(), StaticSafetyMetrics(), DimensionScores(100, 0, 100, 80), 1.2)

    def test_ci_distinguishes_success_failure_error_and_pending_without_inventing_unity_cases(self):
        passed, failed, compile_error, timeout, pending = [self.result(name) for name in
                                                         ("pass", "fail", "compile", "timeout", "pending")]
        failed.test_result.passed = False
        failed.test_result.passed_tests = 0
        failed.test_result.failed_tests = 1
        failed.error_log = "assertion <failed> & detail\x00"
        compile_error.compiled = False
        compile_error.error_log = "syntax error"
        timeout.test_result.completed = False
        timeout.error_log = "timed out"
        document = render_junit([passed, failed, compile_error, timeout, pending], "model<&>",
                                {"run_status": "interrupted", "pending_tasks": ["pending"]})
        suite = ET.fromstring(document)
        self.assertEqual(suite.get("tests"), "5")
        self.assertEqual(suite.get("failures"), "1")
        self.assertEqual(suite.get("errors"), "2")
        self.assertEqual(suite.get("skipped"), "1")
        cases = suite.findall("testcase")
        self.assertIsNone(cases[0].find("failure"))
        self.assertEqual(cases[1].find("failure").text, "assertion <failed> & detail")
        self.assertEqual(cases[3].find("error").get("type"), "incomplete")
        self.assertIsNotNone(cases[4].find("skipped"))
        self.assertEqual(cases[0].get("classname"), "model<&>")

    def test_evaluation_errors_and_candidate_timing_are_preserved(self):
        result = self.result("memory")
        result.error_log = "Reference validation failed"
        result.candidate_time_sec = 0.25
        suite = ET.fromstring(render_junit([result], "model"))
        self.assertEqual(suite.get("time"), "0.250000")
        self.assertEqual(suite.find("testcase/error").get("type"), "evaluation")
        self.assertEqual(ET.fromstring(render_junit([], "empty")).get("tests"), "0")
