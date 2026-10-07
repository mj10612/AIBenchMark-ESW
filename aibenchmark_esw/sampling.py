"""Independent checkpointed samples with unbiased pass@k estimates."""
import copy
import json
import tempfile
import uuid
import sys
import statistics
import math
from datetime import datetime, timezone
from pathlib import Path

from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.output_paths import validate_output_paths
from aibenchmark_esw.report_io import atomic_write_json, atomic_write_text
from aibenchmark_esw.metrics.junit import render_junit


def pass_at_k(n, c, k):
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (n, c, k)) or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("pass@k requires 0 <= passed <= attempts and 1 <= k <= attempts")
    if n - c < k:
        return 1.0
    miss = 1.0
    for index in range(k):
        miss *= (n - c - index) / (n - index)
    return 1 - miss


def sampling_statistics(reports, ks):
    groups: dict[str, list] = {}
    for report in reports:
        for result in BenchmarkReporter.from_json_dict(report):
            groups.setdefault(result.task_id, []).append(result)
    summary = {}
    for task_id, values in groups.items():
        n = len(values)
        c = sum(BenchmarkReporter._all_tests_passed(value) for value in values)
        summary[task_id] = {"attempts": n, "passed": c,
            "mean_score": round(sum(value.scores.total_score for value in values) / n, 6),
            "pass_at_k": {str(k): pass_at_k(n, c, k) if k <= n else None for k in ks}}
        scores = [value.scores.total_score for value in values]
        deviation = statistics.stdev(scores) if n > 1 else None
        margin = 1.96 * deviation / math.sqrt(n) if deviation is not None else None
        mean = statistics.mean(scores)
        summary[task_id].update(sample_stddev=deviation,
            approximate_95pct_mean_interval=[max(0, mean - margin), min(100, mean + margin)] if margin is not None else None,
            interval_method="normal approximation; descriptive, especially unreliable for small N")
    return summary


def run_samples(args, saved, run_once, protected_roots):
    if saved and "sampling" not in saved:
        raise ValueError("A single-run checkpoint cannot be resumed as multiple samples")
    n = args.samples
    if getattr(args, "temperature", None) == 0:
        print("Warning: multiple samples at temperature 0 may be redundant; independence depends on provider sampling.", file=sys.stderr)
    ks = [int(item.strip()) for item in args.pass_k.split(",")] if args.pass_k else list(range(1, n + 1))
    if not ks or len(set(ks)) != len(ks) or any(not 1 <= k <= n for k in ks):
        raise ValueError("--pass-k must contain distinct positive integers <= --samples")
    if saved and ks != saved["sampling"]["pass_k"]:
        if "--pass-k" in args._explicit_options:
            raise ValueError("Resume --pass-k conflicts with the saved collection")
        ks = saved["sampling"]["pass_k"]
    with tempfile.TemporaryDirectory(prefix="aibench-samples-") as temporary:
        root = Path(str(args.output) + ".samples") if args.output else Path(temporary)
        sample_paths = [root / f"sample-{index + 1:04d}.json" for index in range(n)]
        resume_root = Path(str(args.resume) + ".samples") if saved else root
        resume_paths = [resume_root / f"sample-{index + 1:04d}.json" for index in range(n)]
        sources = [Path(args.save_solutions) / f"sample-{index + 1:04d}" / (task + suffix)
            for index in range(n) for task in args._sampling_task_ids
            for suffix in (".c", ".truncated.c")] if args.save_solutions else []
        validate_output_paths([args.output, args.junit_output, *sample_paths, *sources],
            protected_files=[args.system_prompt_file] if args.system_prompt_file else [], protected_roots=protected_roots)
        root.mkdir(parents=True, exist_ok=True)
        samples = copy.deepcopy(saved.get("samples", [])) if saved else []
        pending = list(saved["sampling"]["pending"]) if saved else list(range(n))
        active_sample = saved["sampling"].get("active_sample") if saved else None
        wrapper = copy.deepcopy(saved) if saved else None
        identifier = saved["metadata"]["run_id"] if saved else uuid.uuid4().hex
        started = saved["metadata"]["created_at_utc"] if saved else datetime.now(timezone.utc).isoformat()

        def checkpoint(child, status):
            nonlocal wrapper
            wrapper = copy.deepcopy(samples[0] if samples else child)
            wrapper["metadata"].update(run_id=identifier, created_at_utc=started, run_status=status)
            options = wrapper["metadata"].setdefault("run_options", {})
            options["save_solutions"] = str(Path(args.save_solutions).resolve()) if args.save_solutions else None
            # Wrapper task dimensions display the first sample; collection-wide
            # estimates live explicitly in sampling.statistics.
            if samples:
                wrapper["metadata"]["pending_tasks"] = []
            if getattr(args, "_budget_guard", None) is not None:
                wrapper["metadata"]["cost_budget"] = args._budget_guard.snapshot()
            wrapper["samples"] = samples
            from aibenchmark_esw.metrics.measurements import measurement_summary
            measured_reports = samples + ([child] if child["metadata"]["run_status"] != "completed" else [])
            wrapper["generation_summary"] = measurement_summary(
                [result for sample in measured_reports for result in BenchmarkReporter.from_json_dict(sample)])
            wrapper["sampling"] = {"requested": n, "completed": len(samples), "pending": pending,
                                   "pass_k": ks, "statistics": sampling_statistics(samples, ks), "active_sample": active_sample}
            BenchmarkReporter.from_json_dict(wrapper)
            if args.output:
                atomic_write_json(args.output, wrapper)

        interrupted = aborted = False
        for index in list(pending):
            child_args = copy.copy(args)
            child_args.samples, child_args.pass_k = 1, None
            child_args.output, child_args.junit_output = sample_paths[index], None
            if saved and active_sample == index and not resume_paths[index].is_file():
                raise ValueError(f"Pending sample checkpoint missing: {resume_paths[index]}; restore the .samples directory before resuming")
            child_args.resume = resume_paths[index] if saved and resume_paths[index].is_file() else None
            child_args._explicit_options = set(args._explicit_options) - {"--output", "--resume", "--samples", "--pass-k"}
            child_args._explicit_options.add("--output")
            child_args._sample_checkpoint_callback = lambda child: checkpoint(child,
                child["metadata"]["run_status"] if child["metadata"]["run_status"] != "completed" else "running")
            if args.save_solutions:
                child_args.save_solutions = Path(args.save_solutions) / f"sample-{index + 1:04d}"
            active_sample = index
            code = run_once(child_args)
            if not sample_paths[index].is_file():
                raise ValueError("Sample did not produce a checkpoint")
            child = json.loads(sample_paths[index].read_text(encoding="utf-8"))
            status = child["metadata"]["run_status"]
            if status == "completed":
                samples.append(child)
                pending.remove(index)
                active_sample = None
            interrupted = code == 130 or status == "interrupted"
            aborted = status == "aborted"
            checkpoint(child, "interrupted" if interrupted else "aborted" if aborted else "running" if pending else "completed")
            if interrupted or aborted:
                break
        if wrapper is None:
            wrapper = saved
            if args.output and wrapper is not None:
                atomic_write_json(args.output, wrapper)
        if args.junit_output:
            atomic_write_text(args.junit_output, render_junit(
                [result for sample in samples for result in BenchmarkReporter.from_json_dict(sample)], args.model, wrapper["metadata"]))
        print(json.dumps(wrapper["sampling"], indent=2))
        return 130 if interrupted else 1 if pending or any(
            not BenchmarkReporter._all_tests_passed(result) for sample in samples
            for result in BenchmarkReporter.from_json_dict(sample)) else 0
