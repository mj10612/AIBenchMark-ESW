import sys
import json
import argparse
import math
from pathlib import Path
from typing import List

from aibenchmark_esw.models import TaskEvaluationResult
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.llm.client import LLMClient
from aibenchmark_esw.evaluation import evaluate_task, failed_evaluation
from aibenchmark_esw.provenance import collect_run_metadata, text_sha256
from aibenchmark_esw.metrics.comparison import compare_runs, render_comparison
from aibenchmark_esw.report_io import atomic_write_json
from aibenchmark_esw.output_paths import validate_output_paths
from aibenchmark_esw.resources import data_root


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def _temperature(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 2:
        raise argparse.ArgumentTypeError("must be a finite number between 0 and 2")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aibenchmark-esw",
        description="AIBenchMark-ESW: Open-Source Embedded AI Coding Benchmark Framework",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: list
    list_p = subparsers.add_parser("list", help="List available benchmark tasks")
    list_p.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Filter tasks by tier")

    # Command: eval (local solution evaluation)
    eval_p = subparsers.add_parser("eval", help="Evaluate a local solution or reference implementation")
    eval_p.add_argument("--task", type=str, required=True, help="Task ID (e.g. tier1_ring_buffer)")
    input_group = eval_p.add_mutually_exclusive_group()
    input_group.add_argument("--solution", type=str, help="Path to C solution file")
    input_group.add_argument("--reference", action="store_true", help="Evaluate the built-in reference solution")
    eval_p.add_argument("--output", type=Path, help="Save evaluation JSON with reproducibility metadata")
    eval_p.add_argument("--compiler", type=str, help="Custom C compiler executable path")
    eval_p.add_argument("--allow-standard-fallback", action="store_true",
                        help="Allow MSVC to evaluate C99 tasks as C11; recorded in results")

    # Command: run (LLM or baseline benchmark)
    run_p = subparsers.add_parser("run", help="Run benchmark across tasks using an LLM or reference baseline")
    run_p.add_argument("--model", type=str, default="baseline", help="Provider/model ID available to your account, or 'baseline'")
    run_p.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run only tasks in this tier")
    run_p.add_argument("--tasks", type=str, help="Comma-separated task IDs to evaluate")
    run_p.add_argument("--output", type=str, help="Save JSON progress after every task and on interruption")
    run_p.add_argument("--compiler", type=str, help="Custom C compiler executable path")
    run_p.add_argument("--temperature", type=_temperature,
                       help="Optional provider-supported temperature; omitted by default")
    run_p.add_argument("--max-tokens", type=_positive_int, help="Maximum generation tokens per task")
    run_p.add_argument("--request-timeout", type=_positive_float, default=60.0,
                       help="Provider request timeout in seconds (default: 60)")
    run_p.add_argument("--save-solutions", type=Path,
                       help="Directory for extracted candidate C files, for local replay")
    run_p.add_argument("--allow-standard-fallback", action="store_true",
                       help="Allow MSVC to evaluate C99 tasks as C11; recorded in results")

    # Command: report
    report_p = subparsers.add_parser("report", help="Generate report from evaluation JSON")
    report_p.add_argument("--results", type=str, required=True, help="Path to results JSON file")
    report_p.add_argument("--format", choices=["cli", "markdown"], default="cli", help="Output format")

    compare_p = subparsers.add_parser("compare", help="Compare saved model runs without API calls")
    compare_p.add_argument("--results", nargs="+", type=Path, required=True, help="Two or more saved JSON reports")
    compare_p.add_argument("--format", choices=["cli", "markdown", "csv"], default="markdown")
    compare_p.add_argument("--output", type=Path, help="Save the comparison to a file")

    return parser


def cmd_list(args: argparse.Namespace) -> int:
    loader = DatasetLoader()
    tasks = loader.list_tasks(tier=args.tier)
    print("=" * 80)
    print(f" AIBenchMark-ESW Tasks (Total: {len(tasks)})")
    print("=" * 80)
    print(f"{'Tier':<6} {'Task ID':<24} {'Category':<20} {'Standard':<10} {'Name'}")
    print("-" * 80)
    for t in tasks:
        print(f"Tier {t.tier:<2} {t.id:<24} {t.category:<20} {t.target_standard:<10} {t.name}")
    print("=" * 80)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    loader = DatasetLoader()
    task = loader.get_task(args.task)
    if not task:
        print(f"Error: Task '{args.task}' not found.", file=sys.stderr)
        return 1

    output = getattr(args, "output", None)
    validate_output_paths([output], protected_files=[args.solution] if args.solution else [],
                          protected_roots=_input_roots(loader))
    solution_code = None
    model_name = "local_solution"
    if args.reference:
        solution_code = loader.get_reference_solution(args.task)
        model_name = "golden_reference"
        if not solution_code:
            print(f"Error: Reference solution for '{args.task}' not found.", file=sys.stderr)
            return 1
    elif args.solution:
        sol_path = Path(args.solution)
        if not sol_path.is_file():
            print(f"Error: Solution file '{args.solution}' not found.", file=sys.stderr)
            return 1
        with open(sol_path, "r", encoding="utf-8") as f:
            solution_code = f.read()
    else:
        # Default to starter code
        solution_code = loader.get_starter_code(args.task)
        model_name = "starter_stub"

    if not solution_code:
        print(f"Error: No solution available for '{args.task}'.", file=sys.stderr)
        return 1

    executor = ExecutionSandbox(compiler_path=args.compiler,
                                allow_standard_fallback=getattr(args, "allow_standard_fallback", False))
    analyzer = StaticAnalyzer()
    metadata = collect_run_metadata([task], executor, static_analyzer=analyzer) if output else None
    if metadata is not None:
        metadata.update(run_status="running", pending_tasks=[task.id])
        pending = failed_evaluation(task, model_name, "Not evaluated: evaluation has not finished")
        _attach_provenance(pending, metadata, task.id, solution_code)
        _save_checkpoint(output, [pending], model_name, metadata)
    interrupted = False
    try:
        result = evaluate_task(task, solution_code, loader.get_reference_solution(task.id),
                               model_name, executor, analyzer)
    except KeyboardInterrupt:
        result = failed_evaluation(task, model_name, "Evaluation interrupted by user")
        interrupted = True
    except Exception as error:
        result = failed_evaluation(task, model_name, str(error))
    if metadata is not None:
        metadata.update(run_status="interrupted" if interrupted else "completed",
                        pending_tasks=[task.id] if interrupted else [])
        _attach_provenance(result, metadata, task.id, solution_code)
        _save_checkpoint(output, [result], model_name, metadata)
    print(BenchmarkReporter.generate_cli_table([result], model_name=model_name, metadata=metadata))
    if result.error_log:
        print("\n[Evaluation Error Details]")
        print(result.error_log)
    if output:
        print(f"\nResults successfully saved to: {output}")
    return 130 if interrupted else 0 if result.test_result.passed and not result.error_log else 1


def _attach_provenance(result, metadata, task_id, solution_code=None, messages=None):
    result.provenance = {
        "task_sha256": metadata["task_fingerprints"][task_id],
        "candidate_sha256": text_sha256(solution_code) if solution_code else None,
        "prompt_sha256": text_sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False)) if messages else None,
    }


def _save_checkpoint(output, results, model_name, metadata):
    if output:
        atomic_write_json(output, BenchmarkReporter.to_json_dict(results, model_name, metadata))


def _input_roots(loader):
    return [loader.tasks_root, data_root() / "third_party" / "unity", Path(__file__).resolve().parent]


def cmd_run(args: argparse.Namespace) -> int:
    loader = DatasetLoader()
    tasks = loader.list_tasks(tier=args.tier)
    if args.tasks:
        selected_ids = [item.strip() for item in args.tasks.split(",") if item.strip()]
        unknown = [item for item in selected_ids if loader.get_task(item) is None]
        if unknown:
            print(f"Error: Unknown task IDs: {', '.join(unknown)}", file=sys.stderr)
            return 1
        tasks = [task for task in tasks if task.id in selected_ids]
    if not tasks:
        print("No matching tasks found.", file=sys.stderr)
        return 1

    solution_directory = getattr(args, "save_solutions", None)
    solution_paths = [] if solution_directory is None else [
        Path(solution_directory) / f"{task.id}.c" for task in tasks]
    validate_output_paths([args.output, *solution_paths], protected_roots=_input_roots(loader))
    if solution_directory is not None:
        Path(solution_directory).mkdir(parents=True, exist_ok=True)

    print(f"Starting AIBenchMark-ESW run on {len(tasks)} tasks using model '{args.model}'...")
    executor = ExecutionSandbox(compiler_path=args.compiler,
                                allow_standard_fallback=getattr(args, "allow_standard_fallback", False))
    llm_client = LLMClient(model_name=args.model,
                           temperature=getattr(args, "temperature", None),
                           max_tokens=getattr(args, "max_tokens", None),
                           request_timeout=getattr(args, "request_timeout", 60.0)) if args.model != "baseline" else None
    settings = None if llm_client is None else {
        "temperature": llm_client.temperature, "max_tokens": llm_client.max_tokens,
        "request_timeout_seconds": llm_client.request_timeout,
    }
    analyzer = StaticAnalyzer()
    metadata = collect_run_metadata(tasks, executor, settings, analyzer)
    metadata.update(run_status="running", pending_tasks=[task.id for task in tasks])
    results: List[TaskEvaluationResult] = [failed_evaluation(
        task, args.model, "Not evaluated: run has not reached this task") for task in tasks]
    for task, result in zip(tasks, results):
        _attach_provenance(result, metadata, task.id)
    # Establish a usable checkpoint and catch output path errors before any API calls.
    _save_checkpoint(args.output, results, args.model, metadata)
    interrupted = False
    for index, task in enumerate(tasks):
        print(f" -> Running [{task.id}] (Tier {task.tier})...", end="", flush=True)
        if llm_client is not None:
            llm_client.last_generation = None
        solution_code = messages = None
        try:
            reference_code = loader.get_reference_solution(task.id)
            if args.model == "baseline":
                if not reference_code:
                    raise ValueError("Missing reference implementation")
                solution_code = reference_code
            else:
                headers_text = "\n".join(
                    f"// --- {header.name} ---\n{header.read_text(encoding='utf-8')}"
                    for header in sorted((task.task_dir / "include").glob("*.h"))
                )
                messages = llm_client.build_prompt(task.prompt, headers_text,
                                                    loader.get_starter_code(task.id) or "",
                                                    target_standard=task.target_standard)
                solution_code = llm_client.generate_solution(messages)
                if not solution_code:
                    raise ValueError("Model returned an empty implementation")
            if solution_directory is not None:
                solution_paths[index].write_text(solution_code, encoding="utf-8")
            result = evaluate_task(task, solution_code, reference_code, args.model, executor, analyzer)
        except KeyboardInterrupt:
            result = failed_evaluation(task, args.model, "Evaluation interrupted by user")
            interrupted = True
        except Exception as error:
            result = failed_evaluation(task, args.model, str(error))
        if llm_client is not None:
            result.generation = llm_client.last_generation
        _attach_provenance(result, metadata, task.id, solution_code, messages)
        results[index] = result
        metadata["pending_tasks"] = [pending.id for pending in tasks[index if interrupted else index + 1:]]
        metadata["run_status"] = "interrupted" if interrupted else "running" if metadata["pending_tasks"] else "completed"
        _save_checkpoint(args.output, results, args.model, metadata)
        status = "PASS" if result.test_result.passed and not result.error_log else "FAIL"
        print(f" [{status} - Score: {result.scores.total_score:.1f}]")
        if result.error_log:
            print(f"    {result.error_log}")
        if interrupted:
            break

    print("\n" + BenchmarkReporter.generate_cli_table(results, model_name=args.model, metadata=metadata))
    if args.output:
        print(f"\nResults successfully saved to: {args.output}")
    return 130 if interrupted else 0 if all(result.test_result.passed and not result.error_log for result in results) else 1


def cmd_report(args: argparse.Namespace) -> int:
    report_file = Path(args.results)
    if not report_file.is_file():
        print(f"Error: File not found: {args.results}", file=sys.stderr)
        return 1

    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
        results = BenchmarkReporter.from_json_dict(data)
        model_name = data.get("model_name", "unknown")
        rendered = (BenchmarkReporter.generate_markdown(results, model_name, data.get("metadata")) if args.format == "markdown"
                    else BenchmarkReporter.generate_cli_table(results, model_name, data.get("metadata")))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Error: Invalid results file: {error}", file=sys.stderr)
        return 1
    print(rendered)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        validate_output_paths([args.output], protected_files=args.results)
        reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.results]
        comparison = compare_runs(reports)
        rendered = render_comparison(comparison, args.format)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(f"Error: Cannot compare reports: {error}", file=sys.stderr)
        return 1
    # CSV exports keep a regular schema; provenance warnings still go to stderr.
    if args.format == "csv":
        for warning in comparison["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
    print(rendered)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "list": cmd_list,
        "eval": cmd_eval,
        "run": cmd_run,
        "report": cmd_report,
        "compare": cmd_compare,
    }

    try:
        exit_code = dispatch[args.command](args)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        exit_code = 1
    except KeyboardInterrupt:
        print("Interrupted. Any completed JSON checkpoint remains available.", file=sys.stderr)
        exit_code = 130
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
