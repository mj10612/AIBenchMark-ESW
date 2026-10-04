# AIBenchMark-ESW Benchmark Report: `baseline`

### Summary Overview
- **Total Tasks**: 7
- **Compilation Rate**: 7/7 (100.0%)
- **Pass@1 (All Tests Passed)**: 7/7 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-04T13:54:59.310666+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `51666cee03a28722f5be778949910b330eef6eac0dee0e708a20c47119232e56`
- **Evaluator SHA-256**: `ea7a79bbdc025515361af1b7ec90089c8a5e668ef4626470359b24a157af5009`
- **Source revision**: `5724b561f3a0791c0ba20a311de84ffd70082544`
- **Source had local changes**: False

### Dimensional Scores
| Dimension | Average Score | Weight |
| :--- | :--- | :--- |
| **Functional Correctness** | 100.00 / 100 | 60% |
| **Memory Efficiency** | 100.00 / 100 | 20% |
| **Safety & Code Rules** | 100.00 / 100 | 20% |
| **Composite Score** | **100.00 / 100** | 100% |

### Detailed Task Breakdown
Weights below are functional/memory/safety. Memory and safety contributions are scaled by the functional pass fraction.

| Tier | Task ID | Standard | Weights | Compile | Tests Passed | Flash/RAM (B) | Safety | Score | Time |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `tier1_crc16` | c99 | 60%/20%/20% | PASS | 5/5 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.15s |
| 1 | `tier1_q15_math` | c99 | 60%/20%/20% | PASS | 16/16 | 270 / 0 | Err:0, Warn:0 | **100.0** | 0.14s |
| 1 | `tier1_ring_buffer` | c99 | 60%/20%/20% | PASS | 9/9 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.14s |
| 2 | `tier2_debounce_fsm` | c99 | 60%/20%/20% | PASS | 5/5 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.14s |
| 2 | `tier2_tick_timer` | c99 | 60%/20%/20% | PASS | 16/16 | 636 / 0 | Err:0, Warn:0 | **100.0** | 0.16s |
| 3 | `tier3_i2c_sensor` | c99 | 60%/20%/20% | PASS | 9/9 | 790 / 0 | Err:0, Warn:0 | **100.0** | 0.16s |
| 4 | `tier4_bitmask_fix` | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.15s |
