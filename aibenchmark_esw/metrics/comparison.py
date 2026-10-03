"""Compare saved runs without making model API requests."""

import csv
import io
import math
from dataclasses import asdict

from aibenchmark_esw.metrics.reporter import BenchmarkReporter


def compare_runs(reports):
    if len(reports) < 2:
        raise ValueError("Comparison requires at least two reports")
    runs, models, warnings = [], set(), []
    for report in reports:
        results = BenchmarkReporter.from_json_dict(report)
        model = report.get("model_name")
        if not isinstance(model, str) or not model or model in models:
            raise ValueError("Reports must have distinct, nonempty model names")
        models.add(model)
        if not results:
            raise ValueError("Cannot compare an empty run")
        tasks = {result.task_id: result for result in results}
        if len(tasks) != len(results):
            raise ValueError("Duplicate task IDs in a run")
        if any(result.model_name != model for result in results):
            raise ValueError("Task model names must match the run model")
        metadata = report.get("metadata") or {}
        compiler = metadata.get("compiler") or {}
        complete_provenance = bool(metadata.get("dataset_sha256") and compiler.get("name") and compiler.get("version"))
        if not complete_provenance:
            warnings.append(f"{model}: missing dataset/toolchain provenance; compatibility cannot be fully checked.")
        runs.append((report, results, tasks, metadata, complete_provenance))

    expected = set(runs[0][2])
    for _, _, tasks, _, _ in runs[1:]:
        if set(tasks) != expected:
            raise ValueError("Reports must contain identical task sets, including failures")
    for task_id in expected:
        entries = [run[2][task_id] for run in runs]
        weights = {tuple(asdict(entry.weights).values()) for entry in entries if entry.weights is not None}
        standards = {entry.target_standard for entry in entries if entry.target_standard is not None}
        effective = {entry.effective_standard for entry in entries if entry.effective_standard is not None}
        if len(weights) > 1 or len(standards) > 1 or len(effective) > 1:
            raise ValueError(f"Incompatible weights or C standards for {task_id}")
        if any(entry.weights is None or entry.target_standard is None for entry in entries):
            warnings.append(f"{task_id}: legacy weights or C standard are unknown.")
        fingerprints = {(entry.provenance or {}).get("task_sha256") for entry in entries}
        fingerprints.discard(None)
        if len(fingerprints) > 1:
            raise ValueError(f"Incompatible task fingerprints for {task_id}")

    for key in ("dataset_sha256", "compiler"):
        available = [metadata[key] for _, _, _, metadata, _ in runs if metadata.get(key)]
        if any(value != available[0] for value in available[1:]):
            raise ValueError(f"Incompatible {key} across reports")
    hosts = [(metadata["platform"].get("system"), metadata["platform"].get("machine"))
             for _, _, _, metadata, _ in runs if metadata.get("platform")]
    if any(value != hosts[0] for value in hosts[1:]):
        raise ValueError("Incompatible host platform/architecture across reports")
    settings = [(metadata["generation_settings"].get("temperature"), metadata["generation_settings"].get("max_tokens"))
                for _, _, _, metadata, _ in runs if metadata.get("generation_settings") is not None]
    if any(value != settings[0] for value in settings[1:]):
        raise ValueError("Incompatible temperature or generation token limits across reports")

    rows = []
    for report, results, _, _, provenance in runs:
        tokens, durations = [], []
        for result in results:
            generation = result.generation or {}
            usage = generation.get("usage") or {}
            total = usage.get("total_tokens")
            duration = generation.get("latency_seconds")
            if total is not None:
                if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                    raise ValueError("Invalid token usage in report")
                tokens.append(total)
            if duration is not None:
                if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                    raise ValueError("Invalid generation duration in report")
                durations.append(duration)
        summary = BenchmarkReporter.to_json_dict(results, report["model_name"])
        rows.append({
            "model": report["model_name"], "tasks": len(results),
            "score": summary["overall_score"], "pass_at_1_pct": summary["pass_at_1_pct"],
            "functional": round(sum(r.scores.functional_score for r in results) / len(results), 2),
            "memory": round(sum(r.scores.memory_score for r in results) / len(results), 2),
            "safety": round(sum(r.scores.safety_score for r in results) / len(results), 2),
            "total_tokens": sum(tokens) if tokens else None, "usage_tasks": len(tokens),
            "generation_seconds": round(sum(durations), 3) if durations else None,
            "duration_tasks": len(durations), "provenance": "Recorded" if provenance else "Unknown",
        })
    return {"task_ids": sorted(expected), "warnings": warnings,
            "models": sorted(rows, key=lambda row: (-row["score"], row["model"]))}


def render_comparison(comparison, format_name="markdown"):
    if format_name == "csv":
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(comparison["models"][0]))
        writer.writeheader()
        writer.writerows(comparison["models"])
        return stream.getvalue()
    if format_name == "cli":
        lines = ["AIBenchMark-ESW Model Comparison", "=" * 94,
                 f"{'Model':<32} {'Score':>8} {'Pass@1':>8} {'F/M/S':>20} {'Provenance':>12}"]
        for row in comparison["models"]:
            model = row["model"].replace("\r", " ").replace("\n", " ")
            dimensions = f"{row['functional']:.1f}/{row['memory']:.1f}/{row['safety']:.1f}"
            lines.append(f"{model:<32} {row['score']:>8.2f} {row['pass_at_1_pct']:>7.2f}% {dimensions:>20} {row['provenance']:>12}")
        lines += ["", "Failed tasks remain in the denominator."]
        lines += [f"Warning: {warning}" for warning in comparison["warnings"]]
        return "\n".join(lines)
    lines = ["# AIBenchMark-ESW Model Comparison", "",
             "Identical task sets; scores include failed tasks. Pass@1 measures fully passing suites.", ""]
    for warning in comparison["warnings"]:
        lines.append(f"- Warning: {warning}")
    if comparison["warnings"]:
        lines.append("")
    lines += ["| Model | Score | Pass@1 (%) | Functional | Memory | Safety | Tokens | Generation (s) | Provenance |",
              "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |"]
    for row in comparison["models"]:
        model = row["model"].replace("|", "\\|").replace("\r", " ").replace("\n", " ")
        tokens = "Unknown" if row["total_tokens"] is None else str(row["total_tokens"])
        duration = "Unknown" if row["generation_seconds"] is None else str(row["generation_seconds"])
        if row["total_tokens"] is not None and row["usage_tasks"] < row["tasks"]:
            tokens += f" ({row['usage_tasks']}/{row['tasks']} tasks)"
        if row["generation_seconds"] is not None and row["duration_tasks"] < row["tasks"]:
            duration += f" ({row['duration_tasks']}/{row['tasks']} tasks)"
        lines.append(f"| {model} | {row['score']:.2f} | {row['pass_at_1_pct']:.2f} | {row['functional']:.2f} | {row['memory']:.2f} | {row['safety']:.2f} | {tokens} | {duration} | {row['provenance']} |")
    return "\n".join(lines)
