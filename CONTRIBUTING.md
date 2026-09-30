# Contributing to AIBenchMark-ESW

Thank you for your interest in contributing to **AIBenchMark-ESW**! We aim to make this benchmark the industry standard for evaluating AI coding assistants in embedded systems and firmware development.

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
  "entry_file": "src/my_task.c"
}
```

### 3. Guidelines for Task Design

1. **Embedded Relevance**: Focus on challenges unique to microcontrollers:
   - Fixed resource limits (stack, flash, RAM).
   - Peripheral register sequences and timing loops.
   - Non-blocking state machines and ISR-safe algorithms.
   - Zero dynamic allocation (`malloc`/`free`).
2. **Deterministic Mocking**: If hardware interaction is required, provide clean mock interfaces (function pointers or mock register arrays) in `include/mock_<peripheral>.h`.
3. **Comprehensive Tests**: Include boundary conditions, null pointer checks, and wrap-around logic in `tests/test_<module>.c`.
4. **Golden Reference**: Ensure `reference/<module>.c` passes all test cases. Verify its measured Flash/RAM fit the budgets with the compiler used for comparisons; a reference exceeding a budget does not receive full memory points:
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
3. Commit your changes with clear messages:
   ```bash
   git commit -m "feat(tasks): add tier2 modbus parser task"
   ```
4. Push to your branch and open a Pull Request.
