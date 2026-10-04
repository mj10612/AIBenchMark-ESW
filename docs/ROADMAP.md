# Roadmap and project status

AIBenchMark-ESW is an early-stage, Apache-2.0 embedded C benchmark. The current
dataset contains seven tasks and 65 C test cases. Public baseline results are
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

## Next community priorities

1. Add reviewed tasks for packet framing and DMA ownership,
   with boundary tests and resource budgets calibrated per toolchain.
2. Publish authorized, reproducible provider runs using exact model IDs and
   matching evaluation settings. Keep failed generations and missing usage visible.
3. Add repeated-sampling statistics before making model-ranking claims.
4. Expand MCU cross-compilation and target-specific footprint calibration;
   host footprints and LLVM width checks remain limited proxies.
5. Explore opt-in process/container isolation for untrusted candidates. Current
   native execution has no OS security boundary.

These are planned work, not implemented guarantees. Contributors can open a
feature request with an API contract, test cases, and validation plan. Documentation
and reproducibility fixes are useful starting points. Report real downstream
usage through GitHub issues so project impact can be documented with evidence.
