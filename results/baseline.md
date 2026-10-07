# AIBenchMark-ESW Benchmark Report: `baseline`

### Summary Overview
- **Total Tasks**: 13
- **Compilation Rate**: 13/13 (100.0%)
- **Pass@1 (All Tests Passed)**: 13/13 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-07T13:13:08.412447+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `4bf4901e0db7d114619431a8f2ed815f0069d6c89fc6baa5acf6d8a8e587d9e9`
- **Evaluator SHA-256**: `5f3a5a8f71588afc5d166238325fe8b6f8b2368c0e4def4ec8a78f94d9f034df`
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
| 1 | `tier1_crc16` | c99 | 60%/20%/20% | PASS | 7/7 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.89s |
| 1 | `tier1_q15_math` | c99 | 60%/20%/20% | PASS | 16/16 | 270 / 0 | Err:0, Warn:0 | **100.0** | 0.84s |
| 1 | `tier1_ring_buffer` | c99 | 60%/20%/20% | PASS | 11/11 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.81s |
| 2 | `tier2_cobs_codec` | c99 | 60%/20%/20% | PASS | 9/9 | 1186 / 0 | Err:0, Warn:0 | **100.0** | 0.86s |
| 2 | `tier2_debounce_fsm` | c99 | 60%/20%/20% | PASS | 7/7 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.78s |
| 2 | `tier2_fixed_control` | c99 | 60%/20%/20% | PASS | 7/7 | 941 / 0 | Err:0, Warn:0 | **100.0** | 0.74s |
| 2 | `tier2_tick_timer` | c99 | 60%/20%/20% | PASS | 16/16 | 636 / 0 | Err:0, Warn:0 | **100.0** | 0.63s |
| 3 | `tier3_flash_update` | c99 | 60%/20%/20% | PASS | 6/6 | 1980 / 0 | Err:0, Warn:0 | **100.0** | 0.69s |
| 3 | `tier3_i2c_sensor` | c99 | 60%/20%/20% | PASS | 11/11 | 830 / 0 | Err:0, Warn:0 | **100.0** | 0.79s |
| 3 | `tier3_spi_flash` | c99 | 60%/20%/20% | PASS | 6/6 | 1913 / 0 | Err:0, Warn:0 | **100.0** | 0.62s |
| 4 | `tier4_bitmask_fix` | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.73s |
| 4 | `tier4_dma_buffer` | c11 | 60%/20%/20% | PASS | 5/5 | 1590 / 0 | Err:0, Warn:0 | **100.0** | 0.73s |
| 4 | `tier4_uart_frame_fix` | c99 | 60%/20%/20% | PASS | 7/7 | 760 / 0 | Err:0, Warn:0 | **100.0** | 0.61s |