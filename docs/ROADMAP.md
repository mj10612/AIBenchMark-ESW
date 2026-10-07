# Roadmap and project status

AIBenchMark-ESW is an early-stage, Apache-2.0 embedded C benchmark. The current
dataset contains 13 tasks and 113 C test cases. Public baseline results are
golden-reference validation; no live OpenAI or Claude measurements have been
published in this repository yet.

## Implemented foundations

- Functional, host object Flash/RAM, and heuristic safety scoring.
- Reference correctness/budget validation, completed-suite checks, and preserved timeout diagnostics.
- Provider generation controls, usage records, and saved source replay.
- Versioned environment/dataset/source provenance and offline model comparisons.
- Static-analysis backend/coverage records and validated report inputs.
- Atomic progress checkpoints, interruption handling, and local evaluation JSON exports.
- Input/output collision checks and external dataset CLI workflows.
- Offline task-asset validation and pre-generation checks that retain invalid tasks as failures.
- Q1.15 saturation and truncation tests, faulty-implementation checks, and AVR arithmetic-width validation.
- Rollover-safe tick timers with periodic phase retention, missed-expiration counts, and boundary/mutation tests.
- CI across GCC/Clang/TCC, distribution installation checks, and baseline artifacts.
- Compatible checkpoint resume, bounded parallel jobs, transient retries and public plan/review turns.
- Offline doctor/preflight, cached reference validation, JUnit exports and repeated-run statistics.
- Bounded COBS packet framing, 47 reviewed mutation probes and strengthened CRC/I2C/button contracts.
- Structured safety findings, portable report schema and versioned scoring-policy validation.
- Per-task comparison matrices, target-scoped AVR/ARM object evidence and process resource caps.
- Ruff/type/coverage gates and a published-evidence fingerprint drift check.
- C11 DMA ownership, SPI NOR page/busy contracts, fixed-point PID/filter saturation,
  power-safe dual-slot flash updates and a second framed-UART bugfix task.
- Conservative shared request-cost budgets, dry-run bounds, independent samples
  with Pass@k and approximate mean intervals, and offline hash-checked batch replay.
- HTML/SARIF exports, comparison regression JUnit, fingerprint-grouped trend histories
  and a reusable consumer GitHub Action.
- Optional compiler warnings and extended safety heuristics, bounded analyzer coverage,
  Mach-O footprint parsing, RISC-V objects and container/bubblewrap execution.
- Private test overlays, reproducible task variants, public canary audit markers
  and normalized-reference similarity warnings.
- Scheduled compiler/sanitizer/container CI and automated dependency update proposals.

## Next community priorities

1. Expand reviewed peripheral contracts and calibrate resource budgets against
   actual MCU toolchains and hardware beyond host/object proxies.
2. Publish authorized, reproducible provider runs using exact model IDs and
   matching evaluation settings. Keep failed generations and missing usage visible.
3. Expand reviewed mutation coverage and publish larger independent sample sets
   before making model-ranking claims.
4. Expand MCU cross-compilation and target-specific footprint calibration;
   object footprints exclude startup/linker/stack/heap and remain limited proxies.
5. Review VM isolation and adversarial grading beyond the optional container
   backend. Native/process execution has no filesystem/network security boundary.

These are planned work, not implemented guarantees. Contributors can open a
feature request with an API contract, test cases, and validation plan. Documentation
and reproducibility fixes are useful starting points. Report real downstream
usage through GitHub issues so project impact can be documented with evidence.
