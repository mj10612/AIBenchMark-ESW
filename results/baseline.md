# AIBenchMark-ESW Benchmark Report: `baseline`

### Summary Overview
- **Total Tasks**: 8
- **Compilation Rate**: 8/8 (100.0%)
- **Pass@1 (All Tests Passed)**: 8/8 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-06T14:26:20.761351+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `7560070a1f197ce704b41ad2114ce060af0bf89a932ea7349606bb56b8c8f765`
- **Evaluator SHA-256**: `93dc27935477c4e15f8637b0753d251103eb358605d6acb2c888d970266fa74e`
- **Source revision**: `Unavailable in installed distribution`
- **Source had local changes**: None

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
| 1 | `tier1_crc16` | c99 | 60%/20%/20% | PASS | 6/6 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.20s |
| 1 | `tier1_q15_math` | c99 | 60%/20%/20% | PASS | 16/16 | 270 / 0 | Err:0, Warn:0 | **100.0** | 0.26s |
| 1 | `tier1_ring_buffer` | c99 | 60%/20%/20% | PASS | 9/9 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 2 | `tier2_cobs_codec` | c99 | 60%/20%/20% | PASS | 9/9 | 1186 / 0 | Err:0, Warn:0 | **100.0** | 0.22s |
| 2 | `tier2_debounce_fsm` | c99 | 60%/20%/20% | PASS | 5/5 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.30s |
| 2 | `tier2_tick_timer` | c99 | 60%/20%/20% | PASS | 16/16 | 636 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 3 | `tier3_i2c_sensor` | c99 | 60%/20%/20% | PASS | 11/11 | 830 / 0 | Err:0, Warn:0 | **100.0** | 0.24s |
| 4 | `tier4_bitmask_fix` | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.26s |
