"""Credential-free published-evidence drift check, independent of compilers."""

import json
import sys
from pathlib import Path

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.provenance import _digest_records, task_sha256
from aibenchmark_esw.resources import data_root


def current_fingerprints(package_dir=None, loader=None):
    package = Path(package_dir) if package_dir is not None else Path(__file__).resolve().parent
    dataset = loader if loader is not None else DatasetLoader()
    tasks = {task.id: task_sha256(task, data_root() / "third_party" / "unity") for task in dataset.list_tasks()}
    return {"evaluator_sha256": _digest_records([
        (path.relative_to(package).as_posix(), path.read_bytes())
        for path in package.rglob("*.py") if "_data" not in path.relative_to(package).parts]),
        "dataset_sha256": _digest_records([(name, value.encode("ascii")) for name, value in tasks.items()])}


def verify_baseline(report, fingerprints=None):
    fresh = current_fingerprints() if fingerprints is None else fingerprints
    metadata = report.get("metadata") or {}
    for key, value in fresh.items():
        if metadata.get(key) != value:
            raise ValueError(f"Published baseline has stale {key}; regenerate results/baseline.json and .md")


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "results/baseline.json")
    try:
        verify_baseline(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Published evaluator/dataset fingerprints: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
