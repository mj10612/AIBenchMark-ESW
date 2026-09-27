# Embedded AI Coding Benchmark (AIBenchMark-ESW) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and release `AIBenchMark-ESW`, an open-source AI coding benchmark framework specialized for embedded systems, evaluating functional correctness, memory footprint, and static safety across 4 problem tiers with automated host-based Unity/CMake verification.

**Architecture:** Python-based CLI orchestrator (`aibenchmark_esw`) manages task loading, LLM interaction via LiteLLM, and execution within an isolated sandbox. The sandbox compiles C99 code, runs Unity unit test suites, extracts ELF Flash/RAM sizes, runs static analysis, and computes a composite multi-dimensional score.

**Tech Stack:** Python 3.10+, Click/Typer, Pydantic, LiteLLM, Rich, C99, CMake, Unity Test Framework, GCC/Clang/MSVC, size/readelf.

## Global Constraints
- Target standard: Pure C (C99/C11 compatible).
- Execution: Host-based testing with mocked HAL/registers (deterministic, zero hardware dependency).
- Multi-dimensional scoring weights: 60% Functional (Unity tests), 20% Memory Footprint (Flash/RAM), 20% Safety/MISRA.
- Output artifacts: JSON results, Markdown summaries, and CLI leaderboard tables.

---

### Task 1: Third-Party Unity Test Harness Setup

**Files:**
- Create: `third_party/unity/unity.h`
- Create: `third_party/unity/unity.c`
- Create: `third_party/unity/unity_internals.h`
- Create: `third_party/unity/CMakeLists.txt`

- [ ] **Step 1: Download or vendor Unity C testing framework**
- [ ] **Step 2: Add CMake target for unity library**
- [ ] **Step 3: Verify Unity compiles into static library**
- [ ] **Step 4: Commit third_party/unity**

---

### Task 2: Core Benchmark Tasks Dataset (Tiers 1 ~ 4)

**Files:**
- Create: `tasks/tier1_ring_buffer/task.json`, `prompt.md`, `include/ring_buffer.h`, `src/ring_buffer.c`, `tests/test_ring_buffer.c`, `tests/CMakeLists.txt`, `reference/ring_buffer.c`
- Create: `tasks/tier1_crc16/task.json`, `prompt.md`, `include/crc16.h`, `src/crc16.c`, `tests/test_crc16.c`, `tests/CMakeLists.txt`, `reference/crc16.c`
- Create: `tasks/tier2_debounce_fsm/task.json`, `prompt.md`, `include/debounce_fsm.h`, `src/debounce_fsm.c`, `tests/test_debounce_fsm.c`, `tests/CMakeLists.txt`, `reference/debounce_fsm.c`
- Create: `tasks/tier3_i2c_sensor/task.json`, `prompt.md`, `include/mock_i2c.h`, `include/i2c_sensor.h`, `src/i2c_sensor.c`, `tests/test_i2c_sensor.c`, `tests/CMakeLists.txt`, `reference/i2c_sensor.c`
- Create: `tasks/tier4_bitmask_fix/task.json`, `prompt.md`, `include/irq_manager.h`, `src/irq_manager.c`, `tests/test_irq_manager.c`, `tests/CMakeLists.txt`, `reference/irq_manager.c`

- [ ] **Step 1: Implement Tier 1 `ring_buffer` task and tests**
- [ ] **Step 2: Implement Tier 1 `crc16` task and tests**
- [ ] **Step 3: Implement Tier 2 `debounce_fsm` task and tests**
- [ ] **Step 4: Implement Tier 3 `i2c_sensor` driver task with Mock HAL and tests**
- [ ] **Step 5: Implement Tier 4 `bitmask_fix` bug patch task and tests**
- [ ] **Step 6: Verify reference implementations pass all unit tests**
- [ ] **Step 7: Commit tasks dataset**

---

### Task 3: Python Orchestrator Core Implementation

**Files:**
- Create: `pyproject.toml`
- Create: `aibenchmark_esw/__init__.py`
- Create: `aibenchmark_esw/models.py`
- Create: `aibenchmark_esw/dataset.py`
- Create: `aibenchmark_esw/sandbox/executor.py`
- Create: `aibenchmark_esw/sandbox/size_analyzer.py`
- Create: `aibenchmark_esw/sandbox/static_analyzer.py`
- Create: `aibenchmark_esw/metrics/scorer.py`
- Create: `aibenchmark_esw/metrics/reporter.py`
- Create: `aibenchmark_esw/llm/client.py`
- Create: `aibenchmark_esw/cli.py`

- [ ] **Step 1: Define data models (TaskConfig, EvaluationResult, DimensionScores)**
- [ ] **Step 2: Implement DatasetLoader for discovering and parsing task directories**
- [ ] **Step 3: Implement Execution Sandbox (CMake/compiler execution, timeout control, test log parsing)**
- [ ] **Step 4: Implement Size Analyzer (binary footprint extraction with fallback heuristics)**
- [ ] **Step 5: Implement Static Analyzer (cppcheck / clang-tidy integration)**
- [ ] **Step 6: Implement Multi-Dimensional Scorer & Reporter (Markdown/Rich table/JSON)**
- [ ] **Step 7: Implement LLM Client (LiteLLM wrapper with prompt construction and code block extraction)**
- [ ] **Step 8: Implement CLI commands (`list`, `eval`, `run`, `report`)**
- [ ] **Step 9: Commit orchestrator core**

---

### Task 4: Framework Unit Tests & Verification

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_dataset.py`
- Create: `tests/test_scorer.py`
- Create: `tests/test_executor.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write and run tests for dataset loading**
- [ ] **Step 2: Write and run tests for scoring algorithm**
- [ ] **Step 3: Write and run tests for evaluation sandbox against reference implementations**
- [ ] **Step 4: Write and run CLI integration tests**
- [ ] **Step 5: Commit tests and verification results**

---

### Task 5: Documentation, README.md, Commit & Push

**Files:**
- Modify: `README.md`
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Write comprehensive, developer-ready `README.md` (Overview, Quickstart, Benchmark Tiers, Evaluation Methodology, CLI Guide, Custom Tasks)**
- [ ] **Step 2: Write `CONTRIBUTING.md` for adding new tasks**
- [ ] **Step 3: Verify working tree clean and all tests passing**
- [ ] **Step 4: Commit all changes**
- [ ] **Step 5: Push to remote repository (`origin/main`)**
