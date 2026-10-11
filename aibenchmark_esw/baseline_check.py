"""Credential-free published-evidence drift check, independent of compilers."""

import json
import sys
from pathlib import Path

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.provenance import _digest_records, task_sha256
from aibenchmark_esw.resources import data_root


def current_fingerprints(package_dir=None, loader=None, task_ids=None):
    package = Path(package_dir) if package_dir is not None else Path(__file__).resolve().parent
    dataset = loader if loader is not None else DatasetLoader()
    selected = dataset.list_tasks()
    if task_ids is not None:
        unknown = set(task_ids) - {task.id for task in selected}
        if unknown:
            raise ValueError('Baseline names unavailable tasks: ' + ', '.join(sorted(unknown)))
        selected = [task for task in selected if task.id in task_ids]
    tasks = {task.id: task_sha256(task, data_root() / "third_party" / "unity") for task in selected}
    return {"evaluator_sha256": _digest_records([
        (path.relative_to(package).as_posix(), path.read_bytes())
        for path in package.rglob("*.py") if "_data" not in path.relative_to(package).parts]),
        "dataset_sha256": _digest_records([(name, value.encode("ascii")) for name, value in tasks.items()])}


def verify_baseline(report, fingerprints=None, *, allow_dirty=False, reference=None):
    metadata = report.get("metadata") or {}
    selected = metadata.get('selected_tasks')
    if not isinstance(selected, list) or not selected:
        raise ValueError('Baseline requires explicit nonempty selected_tasks')
    fresh = current_fingerprints(task_ids=selected) if fingerprints is None else fingerprints
    for key, value in fresh.items():
        if metadata.get(key) != value:
            raise ValueError(f"Published baseline has stale {key}; regenerate results/baseline.json and .md")
    results = BenchmarkReporter.from_json_dict(report)
    if set(selected) != {result.task_id for result in results}:
        raise ValueError('Baseline task selection disagrees with contributing results')
    if metadata.get('run_status') != 'completed' or metadata.get('pending_tasks'):
        raise ValueError('Baseline must be a completed run with no pending tasks')
    if metadata.get('source_dirty') is True and not allow_dirty:
        raise ValueError('Published baseline was generated from dirty evaluator/assets; regenerate after committing source changes')
    for result in results:
        if (not BenchmarkReporter._all_tests_passed(result) or result.error_log
                or not result.size_metrics.measured or result.scores.total_score != 100):
            raise ValueError(f'Reference baseline score regression: {result.task_id} must pass all tests and score 100')
    if reference is not None:
        expected = {result.task_id: result for result in BenchmarkReporter.from_json_dict(reference)}
        for result in results:
            previous = expected.get(result.task_id)
            if previous is None or result.scores.total_score < previous.scores.total_score:
                raise ValueError('Reference baseline differs or regressed: ' + result.task_id)


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "results/baseline.json")
    try:
        reference = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8')) if len(sys.argv) > 2 else None
        verify_baseline(json.loads(path.read_text(encoding="utf-8")), reference=reference)
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Reference fingerprints, completion and per-task 100-point score gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
