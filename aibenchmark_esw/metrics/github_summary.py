"""Compact, credential-free GitHub Actions summaries from saved evidence."""

from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.metrics.text import markdown_text


def _collection_summary(report, model, state):
    from aibenchmark_esw.metrics.junit import collection_results
    from aibenchmark_esw.sampling import pass_at_k
    sampling = report['sampling']
    groups: dict[str, list] = {task['task_id']: [] for task in report['tasks']}
    for result in collection_results(report):
        groups.setdefault(result.task_id, []).append(result)
    ks = sampling.get('pass_k', [1])
    lines = [f'## AIBenchMark-ESW: {model}', '', f'Run status: {markdown_text(state)}', '',
             f'Samples: requested {sampling["requested"]}; completed {sampling["completed"]}; pending {len(sampling["pending"])}.', '',
             '| Task | Passed/attempted | Pending | Evaluation errors | Mean score | ' +
             ' | '.join(f'Pass@{k}' for k in ks) + ' |',
             '| --- | ---: | ---: | ---: | ---: | ' + ' | '.join('---:' for _ in ks) + ' |']
    for task_id, values in groups.items():
        attempts = [value for value in values if not value.provenance['sample_pending']]
        n = len(attempts)
        passed = sum(BenchmarkReporter._all_tests_passed(value) for value in attempts)
        errors = sum(bool(value.error_log) or not value.compiled or not value.test_result.completed for value in attempts)
        pending = sampling['requested'] - n
        mean = f'{sum(value.scores.total_score for value in attempts) / n:.2f}' if n else 'Unavailable'
        estimates = [f'{100 * pass_at_k(n, passed, k):.2f}%' if k <= n else 'Unavailable' for k in ks]
        lines.append(f'| {markdown_text(task_id)} | {passed}/{n} | {pending} | {errors} | {mean} | ' + ' | '.join(estimates) + ' |')
    lines.extend(['', 'Functional results and evaluation success are distinct; pending attempts are excluded from means and Pass@k.'])
    return '\n'.join(lines) + '\n'


def github_summary(report):
    results = BenchmarkReporter.from_json_dict(report)
    model = markdown_text(report.get('model_name', 'unknown'))
    state = (report.get('metadata') or {}).get('run_status', 'unknown')
    if 'samples' in report:
        return _collection_summary(report, model, state)
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
