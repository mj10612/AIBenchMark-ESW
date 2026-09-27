# EmbEval: An Open-Source Embedded AI Coding Benchmark

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![C Standard](https://img.shields.io/badge/standard-C99%2FC11-orange)](https://en.wikipedia.org/wiki/C99)
[![Test Harness](https://img.shields.io/badge/harness-Unity%20TDD-brightgreen)](https://github.com/ThrowTheSwitch/Unity)

> **The first comprehensive, multi-dimensional AI coding benchmark specifically designed for embedded systems and firmware engineering.**

---

## 📌 Why EmbEval?

Existing AI coding benchmarks (like *HumanEval*, *MBPP*, and *SWE-bench*) are almost exclusively built around Python, JavaScript, or enterprise applications. They evaluate models purely on boolean unit test pass rates ($Pass@k$).

However, **embedded systems software (firmware)** operates under fundamentally different constraints:
1. **Strict Resource Budgets**: Firmware runs on microcontrollers with tens of kilobytes of Flash and RAM. Code size and memory layout directly dictate whether code can run.
2. **Hardware & Peripheral Abstraction**: Embedded code directly controls registers, timers, interrupts, and communication buses (I2C, SPI, UART).
3. **Safety & Reliability Standards**: Dynamic memory allocation (`malloc`/`free`) is forbidden in automotive and medical standards (MISRA-C, ISO 26262, IEC 62304). Race conditions on interrupt flags or bitmask errors lead to hard faults and system deadlocks.

**EmbEval fills this gap** by providing an automated, host-based testbed that evaluates AI-generated embedded C code across **functional correctness**, **memory footprint**, and **static code safety**.

---

## 🚀 Key Features

* **Deterministic Host-Based Testing**: Validates code using mocked hardware abstraction layers (Mock HAL) and [Unity TDD](https://github.com/ThrowTheSwitch/Unity). No physical development boards required; runs seamlessly in any CI/CD pipeline or Docker container.
* **Multi-Dimensional Scoring**:
  $$\text{Total Score} = 0.6 \times S_{\text{func}} + 0.2 \times S_{\text{mem}} + 0.2 \times S_{\text{safety}}$$
  Combines test pass rate, Flash/RAM footprint consumption, and MISRA-C/static analysis warnings.
* **4-Tier Problem Progression**: Tasks range from core embedded data structures to asynchronous protocol state machines, register-level device drivers, and real-world race condition bug fixes.
* **Broad LLM Ecosystem Support**: Integrates with [LiteLLM](https://github.com/BerriAI/litellm) to evaluate OpenAI (GPT-4o), Anthropic (Claude 3.5), DeepSeek, and local models via Ollama or vLLM.

---

## 📊 Benchmark Tiers & Tasks

| Tier | Category | Task ID | Description | Key Embedded Focus |
| :---: | :--- | :--- | :--- | :--- |
| **1** | Core Fundamentals | `tier1_ring_buffer` | Lock-free Single-Producer Single-Consumer (SPSC) Ring Buffer | Boundary wrap-around, zero allocation, pointer safety |
| **1** | Core Fundamentals | `tier1_crc16` | Standard CRC-16/CCITT-FALSE Checksum Engine | Fixed polynomial (0x1021), bitwise manipulation, lookup logic |
| **2** | FSM & Protocols | `tier2_debounce_fsm` | Noise-Immune Button Input Debounce FSM | Glitch rejection, multi-event emission (Click, Hold, Release) |
| **3** | Device Drivers | `tier3_i2c_sensor` | I2C Temperature Sensor Driver with Mock HAL | Register verification, error/timeout propagation, fixed-point math |
| **4** | Bug Fix & Safety | `tier4_bitmask_fix` | W1C Interrupt Status Register & Priority Bitmask Fix | Write-1-to-Clear race condition, bitfield isolation |

---

## 🛠️ Quickstart Guide

### 1. Installation

Clone the repository and install the Python package in development mode:

```bash
git clone https://github.com/sentimentalmija-lgtm/AIBenchMark-ESW.git
cd AIBenchMark-ESW

# Install minimal core
pip install -e .

# Or install with full LLM and UI dependencies
pip install -e ".[full]"
```

*Prerequisites*: A C compiler in your PATH (`gcc`, `clang`, `tcc`, or `cl`).

---

### 2. Basic CLI Usage

#### List Available Tasks
```bash
embeval list
```

#### Evaluate Local Solution or Reference
Test a specific task against the built-in golden reference:
```bash
embeval eval --task tier1_ring_buffer --reference
```
Or test your own local C solution:
```bash
embeval eval --task tier1_ring_buffer --solution ./my_ring_buffer.c
```

#### Run Benchmark with LLM Models
Run the benchmark across all tasks using any LLM:
```bash
# Evaluate OpenAI GPT-4o
export OPENAI_API_KEY="your-api-key"
embeval run --model gpt-4o --output results/gpt4o_results.json

# Evaluate Anthropic Claude 3.5 Sonnet
export ANTHROPIC_API_KEY="your-api-key"
embeval run --model claude-3-5-sonnet-20241022 --output results/claude_results.json

# Evaluate a local Ollama model (no API key needed)
embeval run --model ollama/qwen2.5-coder:7b --output results/ollama_results.json

# Run reference baseline
embeval run --model baseline --output results/baseline.json
```

#### View Results
```bash
embeval report --results results/baseline.json
```

---

## 📐 Scoring Methodology

Each task is evaluated across three weighted dimensions:

### 1. Functional Correctness ($S_{\text{func}}$, 60%)
Evaluates whether the candidate implementation compiles without errors and passes all test cases in the Unity suite.
$$S_{\text{func}} = \frac{\text{Passed Test Cases}}{\text{Total Test Cases}} \times 100$$
*(Note: If compilation fails, $S_{\text{func}} = 0$ and the overall task score is 0).*

### 2. Memory Footprint Efficiency ($S_{\text{mem}}$, 20%)
Measures the compiled code and data size ($\text{Flash} + \text{RAM}$) compared to the reference implementation ($M_{\text{ref}}$) and the maximum budget limit ($M_{\text{max}}$).
* If $M_{\text{actual}} \le M_{\text{ref}}$: $S_{\text{mem}} = 100$
* If $M_{\text{ref}} < M_{\text{actual}} \le M_{\text{max}}$: Linear decay toward 0.
* If $M_{\text{actual}} > M_{\text{max}}$: $S_{\text{mem}} = 0$

### 3. Static Code Safety ($S_{\text{safety}}$, 20%)
Checks compliance with MISRA-C and embedded safety rules (using `cppcheck` or built-in static analyzers). Penalizes:
* Dynamic memory allocation (`malloc`, `free`) — **Fatal error in safety profiles**
* Unrestricted `goto` jumps (MISRA Rule 15.1)
* Non-fixed-width standard types (MISRA Rule 4.6)
* Buffer overflows and uninitialized variables

---

## 📁 Repository Layout

```text
AIBenchMark-ESW/
├── pyproject.toml              # Python packaging & dependencies
├── README.md                   # Project documentation & quickstart
├── CONTRIBUTING.md             # Guide for contributing new tasks
├── embeval/                    # Python benchmark orchestrator
│   ├── cli.py                  # CLI command entry point
│   ├── dataset.py              # Task discovery & loader
│   ├── models.py               # Data models and evaluation types
│   ├── llm/                    # LLM API adapter (LiteLLM)
│   ├── sandbox/                # Compiler execution, size analysis, static analysis
│   └── metrics/                # Multi-dimensional scoring & reporting
├── tasks/                      # Benchmark task dataset
│   ├── tier1_ring_buffer/      # Tier 1: SPSC Ring Buffer
│   ├── tier1_crc16/            # Tier 1: CRC16 Checksum Engine
│   ├── tier2_debounce_fsm/     # Tier 2: Button Debounce FSM
│   ├── tier3_i2c_sensor/       # Tier 3: I2C Sensor Driver (Mock HAL)
│   └── tier4_bitmask_fix/      # Tier 4: Interrupt W1C Bug Fix
├── third_party/
│   └── unity/                  # Unity C unit test framework
└── tests/                      # Orchestrator test suite
```

---

## 🤝 Contributing

We welcome contributions from embedded systems engineers, AI researchers, and open-source developers!
To contribute new benchmark tasks, hardware mock abstractions, or evaluation metrics, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📜 License

This project is licensed under the [Apache License 2.0](LICENSE).
Third-party components:
* [Unity](https://github.com/ThrowTheSwitch/Unity) is licensed under the MIT License by Mike Karlesky, Mark VanderVoord, and Greg Williams.