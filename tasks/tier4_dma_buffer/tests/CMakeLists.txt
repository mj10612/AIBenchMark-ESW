# AIBENCHMARK_ESW_CANARY_V1_tier4_dma_buffer
cmake_minimum_required(VERSION 3.12)
project(test_tier4_dma_buffer C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(TARGET_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../src/dma_buffer.c" CACHE FILEPATH "Source file to test")

add_executable(test_runner
    test_dma_buffer.c
    ${TARGET_SRC}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity/unity.c
)
target_include_directories(test_runner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity
)
enable_testing()
add_test(NAME dma_buffer_test COMMAND test_runner)
