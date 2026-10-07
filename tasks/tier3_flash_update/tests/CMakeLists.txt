# AIBENCHMARK_ESW_CANARY_V1_tier3_flash_update
cmake_minimum_required(VERSION 3.12)
project(test_tier3_flash_update C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(TARGET_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../src/flash_update.c" CACHE FILEPATH "Source file to test")

add_executable(test_runner
    test_flash_update.c
    ${TARGET_SRC}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity/unity.c
)
target_include_directories(test_runner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity
)
enable_testing()
add_test(NAME flash_update_test COMMAND test_runner)
