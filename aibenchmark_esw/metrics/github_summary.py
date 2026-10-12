"""Compact, credential-free GitHub Actions summaries from saved evidence."""

from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.metrics.text import markdown_text


def github_summary(report):
    results = BenchmarkReporter.from_json_dict(report)
    model = markdown_text(report.get('model_name', 'unknown'))
    state = (report.get('sampling') or report.get('metadata') or {}).get('run_status', 'unknown')
    lines = [f'## AIBenchMark-ESW: {model}', '', f'Run status: {markdown_text(state)}', '',
             '| Task | Tier | Functional | Flash | RAM | Safety | Score |',
             '| --- | ---: | --- | ---: | ---: | --- | ---: |']
    for result in results:
        passed = BenchmarkReporter._all_tests_passed(result)
        status = 'PASS' if passed and not result.error_log else 'FAIL' if result.test_result.completed else 'INCOMPLETE'
        measured = result.size_metrics.measured
        safety = result.safety_metrics.cppcheck_status in ('completed', 'disabled')
        lines.append(f'| {markdown_text(result.task_id)} | {result.tier} | {status} | '
                     f'{result.size_metrics.flash_bytes if measured else "Unavailable"} | '
                     f'{result.size_metrics.ram_bytes if measured else "Unavailable"} | '
                     f'{result.scores.safety_score if safety else "Unavailable"} | {result.scores.total_score:.2f} |')
    lines.extend(['', 'Functional results and evaluation success are distinct; unmeasured dimensions are unavailable.'])
    return '\n'.join(lines) + '\n'
