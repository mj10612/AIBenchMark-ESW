cmake_minimum_required(VERSION 3.12)
project(test_tier2_debounce_fsm C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(TARGET_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../src/debounce_fsm.c" CACHE FILEPATH "Source file to test")

add_executable(test_runner
    test_debounce_fsm.c
    ${TARGET_SRC}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/unity/unity.c
)

target_include_directories(test_runner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/unity
)

enable_testing()
add_test(NAME debounce_fsm_test COMMAND test_runner)
