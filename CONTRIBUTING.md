# Contributing to AIBenchMark-ESW

Thank you for your interest in contributing to **AIBenchMark-ESW**. The project is an early-stage embedded C benchmark. Contributions that improve test validity, reproducibility, and coverage are particularly useful; see the [roadmap](docs/ROADMAP.md).

---

## How to Add a New Benchmark Task

Every task in AIBenchMark-ESW lives in its own directory under `tasks/<task_id>/` and must be fully self-contained.

### 1. Task Directory Layout

```text
tasks/<task_id>/
├── task.json               # Required: Task metadata and resource limits
├── prompt.md               # Required: Human-readable task prompt for LLMs
├── include/                # Required: Public C headers to implement/use
│   └── <module>.h
├── src/                    # Required: Starter code or buggy code to patch
│   └── <module>.c
├── reference/              # Required: Verified golden solution (passes 100%)
│   └── <module>.c
└── tests/                  # Required: Unity unit test suite
    ├── test_<module>.c
    └── CMakeLists.txt
```

### 2. `task.json` Specification

Create `task.json` with the following schema:

```json
{
  "id": "tier1_my_task",
  "name": "Human-Readable Task Name",
  "tier": 1,
  "category": "core_fundamentals",
  "target_standard": "c99",
  "description": "Short description of what the task tests.",
  "limits": {
    "max_flash_bytes": 1024,
    "max_ram_bytes": 128,
    "timeout_seconds": 5
  },
  "weights": {
    "functional": 0.6,
    "memory": 0.2,
    "safety": 0.2
  },
  "entry_file": "src/my_task.c",
  "reference_file": "reference/my_task.c"
}
```

`entry_file` and `reference_file` must be relative paths within the task directory. `reference_file` is optional for older datasets and defaults to `reference/<entry_file basename>`. Task IDs use ASCII letters, digits, underscores or hyphens, cannot start with a hyphen, and cannot be reserved Windows names such as `CON`; these IDs become saved candidate filenames. Weights must be finite, nonnegative, and sum to 1. Flash and timeout limits must be positive integers; the RAM limit may be zero. Invalid metadata or duplicate IDs abort dataset loading so tasks cannot silently disappear from a benchmark.

You can develop a dataset outside the checkout or with an installed wheel. Pass the parent directory containing your task folders to each command:

```bash
aibenchmark-esw list --tasks-root ./my_tasks
aibenchmark-esw validate --tasks-root ./my_tasks
aibenchmark-esw eval --tasks-root ./my_tasks --task tier1_my_task --reference --output results/custom.json
aibenchmark-esw run --tasks-root ./my_tasks --model baseline --output results/custom-baseline.json
```

The external root replaces the bundled task set for that invocation; reports fingerprint the selected external task contents. Python evaluation uses the installed Unity harness. Keep output reports and saved sources outside the task root. With `--tasks` and `--tier` together, every explicit task must belong to that tier; empty, duplicate, unknown, and conflicting IDs are rejected before provider calls.

`validate` checks that the prompt, declared starter/reference, at least one public header, and at least one `tests/test_*.c` are readable, nonempty UTF-8 files. It needs neither a compiler nor provider access and accepts `--tasks` and `--tier`. It checks file structure only; run the reference baseline to verify C correctness and resource budgets. `run` also performs the asset check for each task before generation: invalid tasks retain an explicit zero-score result without spending a provider request, while valid tasks continue.

### 3. Guidelines for Task Design

1. **Embedded Relevance**: Focus on challenges unique to microcontrollers:
   - Fixed resource limits (stack, flash, RAM).
   - Peripheral register sequences and timing loops.
   - Non-blocking state machines and ISR-safe algorithms.
   - Zero dynamic allocation (`malloc`/`free`).
2. **Deterministic Mocking**: If hardware interaction is required, provide clean mock interfaces (function pointers or mock register arrays) in `include/mock_<peripheral>.h`.
3. **Comprehensive Tests**: Include boundary conditions, null pointer checks, and wrap-around logic in `tests/test_<module>.c`. Define one runner `main(void)` or `main(int argc, char **argv)` and return `UNITY_END()` after the tests. Helpers may include headers from the task's `tests/` directory. Include integer-width boundaries for code intended to run on 16-bit-int targets.
4. **Golden Reference**: Ensure the declared reference passes all test cases and its measured Flash/RAM fit the budgets with the compiler used for comparisons. Calibrate host object budgets using that compiler and record it when sharing results; a reference exceeding a budget does not receive full memory points:
   ```bash
   aibenchmark-esw eval --task <task_id> --reference
   ```

---

## Submitting a Pull Request

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feat/add-task-name
   ```
2. Verify all existing tests pass:
   ```bash
   python -m unittest discover tests
   ```
   Install `pip install -e ".[dev]"` to include the sdist/wheel packaging integration test. It builds a wheel from the sdist and executes the bundled baseline outside the checkout.
   Task distributions include JSON metadata, Markdown prompts, C sources/headers, and CMakeLists.txt. Generated build directories, binaries, object files, and caches are excluded.
3. Commit your changes with clear messages:
   ```bash
   git commit -m "feat(tasks): add tier2 modbus parser task"
   ```
4. Push to your branch and open a Pull Request.

## Reproducibility and AI-assisted contributions

Record the compiler and use the same task selection, generation limits, and standards for model comparisons. See [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for the reporting and replay workflow. `AIBENCHMARK_ESW_COMPILER` selects the compiler used by the test suite; CI validates GCC, Clang, and TCC.

AI-assisted patches are welcome. Review every generated change, describe the concrete problem, and include relevant regression evidence. Do not submit fabricated results or describe mocked provider tests as live model measurements. Avoid committing API keys, account identifiers, or private response content. Use the issue and pull-request templates to provide a reproducible example and validation details.

For vulnerabilities, follow [SECURITY.md](SECURITY.md).
