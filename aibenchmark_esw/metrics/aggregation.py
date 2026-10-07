"""Offline descriptive statistics; one saved complete run is one sample."""

import csv
import hashlib
import io
import json
from collections import defaultdict

from aibenchmark_esw.metrics.comparison import compare_runs, generation_conditions
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.metrics.measurements import generation_sequence, measurement_summary, coverage_text
from aibenchmark_esw.metrics.statistics import score_statistics, interval_text


def _stats(values):
    return score_statistics(values)


def aggregate_runs(reports):
    """Group complete, identified runs by requested/resolved model and settings.

    Legacy reports without run identity or core provenance are rejected: copies
    cannot be distinguished from independent samples. Missing usage is allowed.
    """
    if not reports:
        raise ValueError("Aggregation requires at least one report")
    expanded = []
    for report in reports:
        if "samples" in report:
            BenchmarkReporter.from_json_dict(report)
            if (report.get("metadata") or {}).get("run_status") != "completed":
                raise ValueError("Aggregation requires completed sampling collections")
            expanded.extend(report["samples"])
        else:
            expanded.append(report)
    reports = expanded
    if not reports:
        raise ValueError("Aggregation requires at least one completed sample")
    run_ids, contents = set(), set()
    for report in reports:
        BenchmarkReporter.from_json_dict(report)
        metadata = report.get("metadata") or {}
        if metadata.get("run_mode") == "replay":
            raise ValueError("Offline replay is not an independent generation sample; use compare or trend")
        run_id = metadata.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("Aggregation requires a recorded run_id; legacy independence is unknown")
        if run_id in run_ids:
            raise ValueError(f"Duplicate run_id: {run_id}")
        run_ids.add(run_id)
        fingerprint = hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
        if fingerprint in contents:
            raise ValueError("Duplicate report content")
        contents.add(fingerprint)
        if metadata.get("run_status") != "completed":
            raise ValueError("Aggregation requires explicitly completed runs")
    checked = compare_runs(reports, _allow_repeated_models=True, _check_generation=False)
    if any(row["provenance"] != "Recorded" for row in checked["models"]):
        raise ValueError("Aggregation requires evaluator, dataset, toolchain, host and analyzer provenance")
    warnings = list(dict.fromkeys(checked["warnings"]))
    prepared = []
    known_identities = defaultdict(set)
    for report in reports:
        results = BenchmarkReporter.from_json_dict(report)
        settings = generation_conditions(report["metadata"])
        settings_key = json.dumps(settings, sort_keys=True)
        identities = set()
        for result in results:
            value = generation_sequence(result.generation or {})
            if value:
                identities.add(value)
        if len(identities) > 1:
            raise ValueError("A single run contains different resolved model identities")
        identity = next(iter(identities), None)
        requested = report["model_name"]
        key = (requested, settings_key)
        if identity is not None:
            known_identities[key].add(identity)
        prepared.append((report, results, key, identity))
    groups = defaultdict(list)
    for report, results, key, identity in prepared:
        # A failed generation still belongs in the denominator when every known
        # response for this requested model/config identifies the same model.
        known = known_identities[key]
        if identity is None and len(known) == 1:
            identity = next(iter(known))
            warnings.append(f"{key[0]}: a run without a resolved model is included with {identity}; "
                            "its identity is inferred from the other runs.")
        elif identity is None and json.loads(key[1]) is not None:
            warnings.append(f"{key[0]}: resolved model identity is unknown; such runs form a separate group.")
        groups[(key[0], key[1], identity)].append((report, results))
    rows = []
    for (requested, settings_key, identity), samples in groups.items():
        dimensions: dict = {key: [] for key in ("score", "functional", "memory", "safety", "pass_at_1_pct")}
        task_passes = {task_id: 0 for task_id in checked["task_ids"]}
        tokens, durations = [], []
        for report, results in samples:
            summary = BenchmarkReporter.to_json_dict(results, requested)
            dimensions["score"].append(summary["overall_score"])
            dimensions["pass_at_1_pct"].append(summary["pass_at_1_pct"])
            for dimension in ("functional", "memory", "safety"):
                dimensions[dimension].append(sum(getattr(result.scores, dimension + "_score") for result in results) / len(results))
            for result in results:
                task_passes[result.task_id] += int(BenchmarkReporter._all_tests_passed(result))
                generation = result.generation or {}
                total = (generation.get("usage") or {}).get("total_tokens")
                latency = generation.get("latency_seconds")
                if total is not None:
                    tokens.append(total)  # compare_runs already validated usage and latency.
                if latency is not None:
                    durations.append(latency)
        count = len(samples)
        rows.append({
            "model": requested,
            "resolved_model": (identity[0] if identity and len(set(identity)) == 1 else "Mixed pipeline" if identity else None),
            "resolved_model_sequence": list(identity) if identity else [],
            "generation_settings": json.loads(settings_key), "runs": count,
            "run_ids": [report["metadata"]["run_id"] for report, _ in samples],
            "statistics": {key: _stats(values) for key, values in dimensions.items()},
            "task_success": [{"task_id": task_id, "passed_runs": passed, "runs": count,
                              "pass_rate_pct": round(passed / count * 100, 6)}
                             for task_id, passed in sorted(task_passes.items())],
            "total_tokens": sum(tokens) if tokens else None, "usage_tasks": len(tokens),
            "generation_seconds": round(sum(durations), 6) if durations else None,
            "duration_tasks": len(durations), "task_attempts": count * len(task_passes),
        })
        rows[-1].update(measurement_summary([result for _, results in samples for result in results]))
    return {"schema_version": 1, "sampling_unit": "complete independent run",
            "task_ids": checked["task_ids"], "warnings": list(dict.fromkeys(warnings)),
            "groups": sorted(rows, key=lambda row: (row["model"], row["resolved_model"] or "",
                                                    json.dumps(row["generation_settings"], sort_keys=True),
                                                    json.dumps(row["resolved_model_sequence"])))}


def render_aggregation(summary, format_name="markdown"):
    if format_name == "html":
        from aibenchmark_esw.metrics.exports import summary_html
        return summary_html("Repeated-run benchmark statistics", summary["groups"], summary)
    if format_name == "json":
        return json.dumps(summary, indent=2, allow_nan=False) + "\n"
    if format_name == "csv":
        stream = io.StringIO(newline="")
        fields = ["model", "resolved_model", "generation_settings", "runs", "score_mean", "score_sample_stddev",
                  "functional_mean", "functional_sample_stddev", "memory_mean", "memory_sample_stddev",
                  "safety_mean", "safety_sample_stddev", "pass_at_1_pct_mean", "pass_at_1_pct_sample_stddev",
                  "total_tokens", "known_total_tokens", "usage_tasks", "usage_partial_tasks", "total_cost_usd", "known_cost_usd",
                  "usage_known_attempts", "usage_total_attempts", "usage_attempt_coverage_tasks", "usage_known_turns", "usage_total_turns", "usage_turn_coverage_tasks",
                  "cost_tasks", "cost_partial_tasks", "cost_per_passed_task", "resolved_model_sequence", "generation_seconds", "duration_tasks", "task_attempts"]
        fields += [dimension + '_mean_ci95_' + bound for dimension in ('score','functional','memory','safety','pass_at_1_pct') for bound in ('lower','upper')]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for group in summary["groups"]:
            row = {key: group[key] for key in fields if key in group}
            row["generation_settings"] = json.dumps(group["generation_settings"], sort_keys=True)
            for key, stats in group["statistics"].items():
                row[key + "_mean"] = stats["mean"]
                row[key + "_sample_stddev"] = stats["sample_stddev"]
                interval = stats['mean_ci95_approx']
                for bound in ('lower','upper'):
                    row[key + '_mean_ci95_' + bound] = interval[bound] if interval else None
            writer.writerow(row)
        return stream.getvalue()
    if format_name not in ("markdown", "cli"):
        raise ValueError(f"Unknown aggregation format: {format_name}")
    heading = "# Repeated-run benchmark statistics" if format_name == "markdown" else "Repeated-run benchmark statistics"
    lines = [heading, "",
             "Each complete run is one sample. Failed attempts remain in the denominator.",
             "Success rates describe single attempts, not Pass@k. Variability is sample standard deviation.", ""]
    lines += ["Warning: " + warning for warning in summary["warnings"]]
    for group in summary["groups"]:
        label = group["model"].replace("\n", " ").replace("\r", " ")
        score = group["statistics"]["score"]
        deviation = "Unavailable (one run)" if score["sample_stddev"] is None else f"{score['sample_stddev']:.2f}"
        resolved = (group["resolved_model"] or "Unknown resolved model").replace("\n", " ").replace("\r", " ")
        group_heading = f"{label} / {resolved}"
        lines += ["", ("## " if format_name == "markdown" else "") + group_heading,
                  f"Runs: {group['runs']}; mean score: {score['mean']:.2f}; sample SD: {deviation}",
                  interval_text(score['mean_ci95_approx']),
                  "Generation settings: " + json.dumps(group["generation_settings"], sort_keys=True),
                  "Contributing model sequence: " + json.dumps(group["resolved_model_sequence"]),
                  coverage_text(group),
                  f"Cost USD: {group['total_cost_usd']}; known subtotal {group['known_cost_usd']}; complete "
                  f"{group['cost_tasks']}/{group['task_attempts']} attempts; cost per passing task {group['cost_per_passed_task']}",
                  "Dimension means (F/M/S): " + "/".join(f"{group['statistics'][key]['mean']:.2f}"
                                                           for key in ("functional", "memory", "safety")),
                  "Dimension sample SD (F/M/S): " + "/".join(
                      "Unavailable" if group["statistics"][key]["sample_stddev"] is None else
                      f"{group['statistics'][key]['sample_stddev']:.2f}" for key in ("functional", "memory", "safety")),
                  f"Tokens: {group['total_tokens'] if group['total_tokens'] is not None else 'Unknown'} "
                  f"(known subtotal {group['known_total_tokens']}; {group['usage_tasks']}/{group['task_attempts']} complete attempts); generation seconds: "
                  f"{group['generation_seconds'] if group['generation_seconds'] is not None else 'Unknown'} "
                  f"({group['duration_tasks']}/{group['task_attempts']} attempts)", "",
                  "| Task | Full passes | Success (%) |", "| :--- | ---: | ---: |"]
        for task in group["task_success"]:
            label = task["task_id"].replace("|", "\\|").replace("\r", " ").replace("\n", " ")
            lines.append(f"| {label} | {task['passed_runs']}/{task['runs']} | {task['pass_rate_pct']:.2f} |")
    return "\n".join(lines)
