# AIBenchMark-ESW Benchmark Report: `baseline`

### Summary Overview
- **Total Tasks**: 5
- **Compilation Rate**: 5/5 (100.0%)
- **Pass@1 (All Tests Passed)**: 5/5 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-04T02:38:33.695026+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `23604719d8a64f99729efa8f68db46f031d2ce26636f3e9437769eaa978bb88e`
- **Evaluator SHA-256**: `4aff1a50f81a007bc484f85bd026f232c88235372c711bc7f6363eb0db776707`
- **Source revision**: `27dfda7d00754d70819518aa4219d4ea5be0f6c4`
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
| 1 | `tier1_crc16` | c99 | 60%/20%/20% | PASS | 5/5 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.39s |
| 1 | `tier1_ring_buffer` | c99 | 60%/20%/20% | PASS | 9/9 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.45s |
| 2 | `tier2_debounce_fsm` | c99 | 60%/20%/20% | PASS | 5/5 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.35s |
| 3 | `tier3_i2c_sensor` | c99 | 60%/20%/20% | PASS | 9/9 | 790 / 0 | Err:0, Warn:0 | **100.0** | 0.33s |
| 4 | `tier4_bitmask_fix` | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.36s |
