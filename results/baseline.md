# AIBenchMark-ESW Benchmark Report: baseline

### Summary Overview
- **Total Tasks**: 15
- **Compilation Rate**: 15/15 (100.0%)
- **Pass@1 (All Tests Passed)**: 15/15 (100.0%)
- **Overall AIBenchMark-ESW Score**: **100.00 / 100.0**

- **Tier-weighted score**: **100.00 / 100.0** (weights proportional to tier)

### Tier and category breakdown

| Model | Group type | Group | Tasks | Attempts | Mean | Pass@1 (%) | Delta vs baseline |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| baseline | by_tier | 1 | 3 | 3 | 100.0 | 100.0 | Unavailable |
| baseline | by_tier | 2 | 6 | 6 | 100.0 | 100.0 | Unavailable |
| baseline | by_tier | 3 | 3 | 3 | 100.0 | 100.0 | Unavailable |
| baseline | by_tier | 4 | 3 | 3 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | bug_fix_and_safety | 2 | 2 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | concurrency | 1 | 1 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | core_fundamentals | 3 | 3 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | device_drivers | 2 | 2 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | fixed_point_control | 1 | 1 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | flash_management | 1 | 1 | 100.0 | 100.0 | Unavailable |
| baseline | by_category | fsm_and_protocols | 5 | 5 | 100.0 | 100.0 | Unavailable |
### Reproducibility
- **Run (UTC)**: 2026-10-12T00:15:43.856860+00:00
- **Run status**: completed
- **Benchmark / Python**: 0.1.0 / 3.14.3
- **Compiler**: clang / clang version 19.1.5 (-Os)
- **Static analysis**: builtin / No cppcheck version recorded
- **Dataset SHA-256**: `f2312a9944c5296fd55354f9f27cafafa920da443579e32581d6e4287124da97`
- **Evaluator SHA-256**: `30b852bc11f446af70b9a1d0799e8fc0ee8d49e725ec03474f665fb13591f2db`
- **Source revision**: `c5405138704d53fc6f4fcf0b8fe01b7e5a8ab1ee`
- **Source had local changes**: False

### Dimensional Scores
| Dimension | Average Score | Weight |
| :--- | :--- | :--- |
| **Functional Correctness** | 100.00 / 100 | 60% |
| **Memory Efficiency** | 100.00 / 100 | 20% |
| **Safety & Code Rules** | 100.00 / 100 | 20% |
Measured dimensions: memory 15/15, safety 15/15 task attempts.

| **Composite Score** | **100.00 / 100** | 100% |

### Detailed Task Breakdown
Weights below are functional/memory/safety. Memory and safety contributions are scaled by the functional pass fraction.

| Tier | Task ID | Standard | Weights | Compile | Tests Passed | Flash/RAM (B) | Safety | Score | Time |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | tier1_crc16 | c99 | 60%/20%/20% | PASS | 7/7 | 130 / 0 | Err:0, Warn:0 | **100.0** | 0.92s |
| 1 | tier1_q15_math | c99 | 60%/20%/20% | PASS | 16/16 | 70 / 0 | Err:0, Warn:0 | **100.0** | 0.90s |
| 1 | tier1_ring_buffer | c99 | 60%/20%/20% | PASS | 11/11 | 384 / 0 | Err:0, Warn:0 | **100.0** | 0.95s |
| 2 | tier2_can_frame | c99 | 60%/20%/20% | PASS | 14/14 | 1130 / 0 | Err:0, Warn:0 | **100.0** | 0.94s |
| 2 | tier2_cobs_codec | c99 | 60%/20%/20% | PASS | 9/9 | 609 / 0 | Err:0, Warn:0 | **100.0** | 0.96s |
| 2 | tier2_debounce_fsm | c99 | 60%/20%/20% | PASS | 7/7 | 292 / 0 | Err:0, Warn:0 | **100.0** | 0.91s |
| 2 | tier2_fixed_control | c99 | 60%/20%/20% | PASS | 7/7 | 327 / 0 | Err:0, Warn:0 | **100.0** | 0.90s |
| 2 | tier2_tick_timer | c99 | 60%/20%/20% | PASS | 16/16 | 139 / 0 | Err:0, Warn:0 | **100.0** | 0.90s |
| 2 | tier2_windowed_watchdog | c99 | 60%/20%/20% | PASS | 13/13 | 413 / 0 | Err:0, Warn:0 | **100.0** | 0.91s |
| 3 | tier3_flash_update | c99 | 60%/20%/20% | PASS | 7/7 | 779 / 0 | Err:0, Warn:0 | **100.0** | 0.93s |
| 3 | tier3_i2c_sensor | c99 | 60%/20%/20% | PASS | 11/11 | 444 / 0 | Err:0, Warn:0 | **100.0** | 0.90s |
| 3 | tier3_spi_flash | c99 | 60%/20%/20% | PASS | 8/8 | 1018 / 0 | Err:0, Warn:0 | **100.0** | 0.93s |
| 4 | tier4_bitmask_fix | c99 | 60%/20%/20% | PASS | 5/5 | 141 / 0 | Err:0, Warn:0 | **100.0** | 0.92s |
| 4 | tier4_dma_buffer | c11 | 60%/20%/20% | PASS | 8/8 | 545 / 0 | Err:0, Warn:0 | **100.0** | 0.94s |
| 4 | tier4_uart_frame_fix | c99 | 60%/20%/20% | PASS | 8/8 | 406 / 0 | Err:0, Warn:0 | **100.0** | 0.92s |