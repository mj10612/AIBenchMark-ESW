# AIBenchMark-ESW Benchmark Report: `baseline`

### Summary Overview
- **Total Tasks**: 6
- **Compilation Rate**: 6/6 (100.0%)
- **Pass@1 (All Tests Passed)**: 6/6 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-04T08:38:41.726037+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `e67c6c170f8c8e3ff65324db04344c94e31da1a2b809a87a85bca1b9e0345e6c`
- **Evaluator SHA-256**: `91c721177e04b18a63af1856555187b9917f57d78122f21863248b6fa8c1217d`
- **Source revision**: `2d5c67cdc5848bf2eb22b7ec2788b9376878b133`
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
| 1 | `tier1_crc16` | c99 | 60%/20%/20% | PASS | 5/5 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.25s |
| 1 | `tier1_q15_math` | c99 | 60%/20%/20% | PASS | 16/16 | 270 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 1 | `tier1_ring_buffer` | c99 | 60%/20%/20% | PASS | 9/9 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.29s |
| 2 | `tier2_debounce_fsm` | c99 | 60%/20%/20% | PASS | 5/5 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.25s |
| 3 | `tier3_i2c_sensor` | c99 | 60%/20%/20% | PASS | 9/9 | 790 / 0 | Err:0, Warn:0 | **100.0** | 0.26s |
| 4 | `tier4_bitmask_fix` | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.25s |
