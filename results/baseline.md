# AIBenchMark-ESW Benchmark Report: baseline

### Summary Overview
- **Total Tasks**: 13
- **Compilation Rate**: 13/13 (100.0%)
- **Pass@1 (All Tests Passed)**: 13/13 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

### Reproducibility
- **Run (UTC)**: 2026-10-11T04:05:25.051154+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.11.15
- **Compiler**: tcc / tcc version 0.9.27 (x86_64 Windows) (native)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `c78302d1d093e5cbbb0809253575de209662f96db73dc7d56d492f51338a93ac`
- **Evaluator SHA-256**: `78d86f33d6fca7f79d66286afa04634931901aa88a07e026e9cd14f14ca21408`
- **Source revision**: `c6b0fc86e8c741ab4f659614f692da5974232656`
- **Source had local changes**: False

### Dimensional Scores
| Dimension | Average Score | Weight |
| :--- | :--- | :--- |
| **Functional Correctness** | 100.00 / 100 | 60% |
| **Memory Efficiency** | 100.00 / 100 | 20% |
| **Safety & Code Rules** | 100.00 / 100 | 20% |
Measured dimensions: memory 13/13, safety 13/13 task attempts.

| **Composite Score** | **100.00 / 100** | 100% |

### Detailed Task Breakdown
Weights below are functional/memory/safety. Memory and safety contributions are scaled by the functional pass fraction.

| Tier | Task ID | Standard | Weights | Compile | Tests Passed | Flash/RAM (B) | Safety | Score | Time |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | tier1_crc16 | c99 | 60%/20%/20% | PASS | 7/7 | 361 / 0 | Err:0, Warn:0 | **100.0** | 0.29s |
| 1 | tier1_q15_math | c99 | 60%/20%/20% | PASS | 16/16 | 270 / 0 | Err:0, Warn:0 | **100.0** | 0.26s |
| 1 | tier1_ring_buffer | c99 | 60%/20%/20% | PASS | 11/11 | 1474 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 2 | tier2_cobs_codec | c99 | 60%/20%/20% | PASS | 9/9 | 1186 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 2 | tier2_debounce_fsm | c99 | 60%/20%/20% | PASS | 7/7 | 1134 / 0 | Err:0, Warn:0 | **100.0** | 0.26s |
| 2 | tier2_fixed_control | c99 | 60%/20%/20% | PASS | 7/7 | 941 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 2 | tier2_tick_timer | c99 | 60%/20%/20% | PASS | 16/16 | 636 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 3 | tier3_flash_update | c99 | 60%/20%/20% | PASS | 7/7 | 1980 / 0 | Err:0, Warn:0 | **100.0** | 0.28s |
| 3 | tier3_i2c_sensor | c99 | 60%/20%/20% | PASS | 11/11 | 830 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 3 | tier3_spi_flash | c99 | 60%/20%/20% | PASS | 6/6 | 1913 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 4 | tier4_bitmask_fix | c99 | 60%/20%/20% | PASS | 5/5 | 462 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 4 | tier4_dma_buffer | c11 | 60%/20%/20% | PASS | 5/5 | 1590 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |
| 4 | tier4_uart_frame_fix | c99 | 60%/20%/20% | PASS | 7/7 | 760 / 0 | Err:0, Warn:0 | **100.0** | 0.27s |