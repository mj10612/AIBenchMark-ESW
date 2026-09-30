cmake_minimum_required(VERSION 3.12)
project(test_tier3_i2c_sensor C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(TARGET_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../src/i2c_sensor.c" CACHE FILEPATH "Source file to test")

add_executable(test_runner
    test_i2c_sensor.c
    ${TARGET_SRC}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity/unity.c
)

target_include_directories(test_runner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../../third_party/unity
)

enable_testing()
add_test(NAME i2c_sensor_test COMMAND test_runner)
