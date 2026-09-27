import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import List, Optional

from aibenchmark_esw.models import TaskEvaluationResult
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer
from aibenchmark_esw.metrics.scorer import BenchmarkScorer
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.llm.client import LLMClient


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
    eval_p.add_argument("--solution", type=str, help="Path to C solution file")
    eval_p.add_argument("--reference", action="store_true", help="Evaluate the built-in reference solution")
    eval_p.add_argument("--compiler", type=str, help="Custom C compiler executable path")

    # Command: run (LLM or baseline benchmark)
    run_p = subparsers.add_parser("run", help="Run benchmark across tasks using an LLM or reference baseline")
    run_p.add_argument("--model", type=str, default="baseline", help="Model name (e.g. gpt-4o, claude-3-5-sonnet, ollama/codellama) or 'baseline'")
    run_p.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run only tasks in this tier")
    run_p.add_argument("--tasks", type=str, help="Comma-separated task IDs to evaluate")
    run_p.add_argument("--output", type=str, help="Path to save output JSON report")
    run_p.add_argument("--compiler", type=str, help="Custom C compiler executable path")

    # Command: report
    report_p = subparsers.add_parser("report", help="Generate report from evaluation JSON")
    report_p.add_argument("--results", type=str, required=True, help="Path to results JSON file")
    report_p.add_argument("--format", choices=["cli", "markdown"], default="cli", help="Output format")

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

    executor = ExecutionSandbox(compiler_path=args.compiler)
    size_analyzer = SizeAnalyzer()
    static_analyzer = StaticAnalyzer()

    start_time = time.time()
    comp_res, test_res = executor.compile_and_test(task, solution_code)
    exec_time = time.time() - start_time

    # Size analysis
    size_metrics = size_analyzer.analyze(
        comp_res.binary_path if comp_res.binary_path else Path("dummy"),
    )

    # Static analysis (save code to temp file for inspection)
    temp_c = task.task_dir / f"_temp_eval_{task.id}.c"
    try:
        with open(temp_c, "w", encoding="utf-8") as f:
            f.write(solution_code)
        safety_metrics = static_analyzer.analyze(temp_c)
    finally:
        if temp_c.exists():
            temp_c.unlink(missing_ok=True)

    scores = BenchmarkScorer.calculate_scores(
        task, comp_res, test_res, size_metrics, safety_metrics
    )

    result = TaskEvaluationResult(
        task_id=task.id,
        tier=task.tier,
        model_name=model_name,
        compiled=comp_res.success,
        test_result=test_res,
        size_metrics=size_metrics,
        safety_metrics=safety_metrics,
        scores=scores,
        execution_time_sec=exec_time,
        error_log=comp_res.output if not comp_res.success else None,
    )

    print(BenchmarkReporter.generate_cli_table([result], model_name=model_name))
    if not comp_res.success:
        print("\n[Compilation Error Details]")
        print(comp_res.output)
    return 0 if test_res.passed else 1


def cmd_run(args: argparse.Namespace) -> int:
    loader = DatasetLoader()
    tasks = loader.list_tasks(tier=args.tier)
    if args.tasks:
        selected_ids = [s.strip() for s in args.tasks.split(",")]
        tasks = [t for t in tasks if t.id in selected_ids]

    if not tasks:
        print("No matching tasks found.", file=sys.stderr)
        return 1

    print(f"Starting AIBenchMark-ESW run on {len(tasks)} tasks using model '{args.model}'...")
    executor = ExecutionSandbox(compiler_path=args.compiler)
    size_analyzer = SizeAnalyzer()
    static_analyzer = StaticAnalyzer()
    llm_client = None
    if args.model != "baseline":
        llm_client = LLMClient(model_name=args.model)

    results: List[TaskEvaluationResult] = []

    for task in tasks:
        print(f" -> Running [{task.id}] (Tier {task.tier})...", end="", flush=True)
        if args.model == "baseline":
            solution_code = loader.get_reference_solution(task.id)
            if not solution_code:
                print(" [ERROR: Missing reference]")
                continue
        else:
            # Query LLM
            include_dir = task.task_dir / "include"
            headers_text = ""
            for h in include_dir.glob("*.h"):
                with open(h, "r", encoding="utf-8") as hf:
                    headers_text += f"// --- {h.name} ---\n" + hf.read() + "\n"
            starter_code = loader.get_starter_code(task.id) or ""
            messages = llm_client.build_prompt(task.prompt, headers_text, starter_code)
            try:
                solution_code = llm_client.generate_solution(messages)
            except Exception as e:
                print(f" [LLM ERROR: {e}]")
                continue

        start_time = time.time()
        comp_res, test_res = executor.compile_and_test(task, solution_code)
        exec_time = time.time() - start_time

        size_metrics = size_analyzer.analyze(
            comp_res.binary_path if comp_res.binary_path else Path("dummy"),
        )

        temp_c = task.task_dir / f"_temp_run_{task.id}.c"
        try:
            with open(temp_c, "w", encoding="utf-8") as f:
                f.write(solution_code)
            safety_metrics = static_analyzer.analyze(temp_c)
        finally:
            if temp_c.exists():
                temp_c.unlink(missing_ok=True)

        scores = BenchmarkScorer.calculate_scores(
            task, comp_res, test_res, size_metrics, safety_metrics
        )

        res = TaskEvaluationResult(
            task_id=task.id,
            tier=task.tier,
            model_name=args.model,
            compiled=comp_res.success,
            test_result=test_res,
            size_metrics=size_metrics,
            safety_metrics=safety_metrics,
            scores=scores,
            execution_time_sec=exec_time,
            error_log=comp_res.output if not comp_res.success else None,
        )
        results.append(res)
        status_sym = "PASS" if test_res.passed else ("FAIL" if comp_res.success else "NO_COMPILE")
        print(f" [{status_sym} - Score: {scores.total_score:.1f}]")

    print("\n" + BenchmarkReporter.generate_cli_table(results, model_name=args.model))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(BenchmarkReporter.to_json_dict(results, args.model), f, indent=2)
        print(f"\nResults successfully saved to: {out_path}")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    report_file = Path(args.results)
    if not report_file.is_file():
        print(f"Error: File not found: {args.results}", file=sys.stderr)
        return 1

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Simple pretty dump
    print(json.dumps(data, indent=2))
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
    }

    exit_code = dispatch[args.command](args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
