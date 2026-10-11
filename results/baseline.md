# AIBenchMark-ESW Benchmark Report: `baseline`

### Summary Overview
- **Total Tasks**: 13
- **Compilation Rate**: 13/13 (100.0%)
- **Pass@1 (All Tests Passed)**: 13/13 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-11T03:16:44.808656+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `33924d0c6c9af95325974ac45aed9d4d07c6ed07541f2db7dc86699c1b9d67d3`
- **Evaluator SHA-256**: `336ec2b9b2169e2bde81112311e3448dce386dde4c28d8ddd6a01e79aa453d15`
- **Source revision**: `f3f970b0ec81b944d89524e404681c1d7c14acf3`
- **Source had local changes**: True

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
| 1 | `tier1_crc16` | c99 | 60%/20%/20% | PASS | 7/7 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.33s |
| 1 | `tier1_q15_math` | c99 | 60%/20%/20% | PASS | 16/16 | 270 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 1 | `tier1_ring_buffer` | c99 | 60%/20%/20% | PASS | 11/11 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 2 | `tier2_cobs_codec` | c99 | 60%/20%/20% | PASS | 9/9 | 1186 / 0 | Err:0, Warn:0 | **100.0** | 0.30s |
| 2 | `tier2_debounce_fsm` | c99 | 60%/20%/20% | PASS | 7/7 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 2 | `tier2_fixed_control` | c99 | 60%/20%/20% | PASS | 7/7 | 941 / 0 | Err:0, Warn:0 | **100.0** | 0.29s |
| 2 | `tier2_tick_timer` | c99 | 60%/20%/20% | PASS | 16/16 | 636 / 0 | Err:0, Warn:0 | **100.0** | 0.29s |
| 3 | `tier3_flash_update` | c99 | 60%/20%/20% | PASS | 7/7 | 1980 / 0 | Err:0, Warn:0 | **100.0** | 0.30s |
| 3 | `tier3_i2c_sensor` | c99 | 60%/20%/20% | PASS | 11/11 | 830 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 3 | `tier3_spi_flash` | c99 | 60%/20%/20% | PASS | 6/6 | 1913 / 0 | Err:0, Warn:0 | **100.0** | 0.30s |
| 4 | `tier4_bitmask_fix` | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 4 | `tier4_dma_buffer` | c11 | 60%/20%/20% | PASS | 5/5 | 1590 / 0 | Err:0, Warn:0 | **100.0** | 0.29s |
| 4 | `tier4_uart_frame_fix` | c99 | 60%/20%/20% | PASS | 7/7 | 760 / 0 | Err:0, Warn:0 | **100.0** | 0.29s |