# AIBENCHMARK_ESW_CANARY_V1_tier2_windowed_watchdog
cmake_minimum_required(VERSION 3.16)
project(windowed_watchdog_tests C)
set(CMAKE_C_STANDARD 99)
add_executable(test_runner test_windowed_watchdog.c ../reference/windowed_watchdog.c ../../../third_party/unity/unity.c)
target_include_directories(test_runner PRIVATE ../include ../../../third_party/unity)
