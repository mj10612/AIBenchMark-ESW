cmake_minimum_required(VERSION 3.12)
project(test_tier1_ring_buffer C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(TARGET_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../src/ring_buffer.c" CACHE FILEPATH "Source file to test")

add_executable(test_runner
    test_ring_buffer.c
    ${TARGET_SRC}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity/unity.c
)

target_include_directories(test_runner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity
)

enable_testing()
add_test(NAME ring_buffer_test COMMAND test_runner)
