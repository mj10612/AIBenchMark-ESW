#include "unity.h"
#include "crc16.h"
#include <string.h>

void setUp(void) {}
void tearDown(void) {}

void test_standard_test_vector(void) {
    const uint8_t test_vec[] = "123456789";
    uint16_t crc = crc16_ccitt(test_vec, 9);
    TEST_ASSERT_EQUAL_HEX16(0x29B1, crc);
}

void test_empty_buffer(void) {
    uint16_t crc = crc16_ccitt((const uint8_t*)"", 0);
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, crc);
}

void test_null_buffer(void) {
    uint16_t crc = crc16_ccitt(NULL, 10);
    TEST_ASSERT_EQUAL_HEX16(0x0000, crc);
}

void test_single_byte_and_stepwise_update(void) {
    const uint8_t test_vec[] = "123456789";
    uint16_t step_crc = 0xFFFF;
    for (size_t i = 0; i < 9; i++) {
        step_crc = crc16_update(step_crc, test_vec[i]);
    }
    TEST_ASSERT_EQUAL_HEX16(0x29B1, step_crc);
}

void test_all_zeros_and_ones(void) {
    uint8_t zeros[4] = {0, 0, 0, 0};
    uint16_t crc_zero = crc16_ccitt(zeros, sizeof(zeros));
    TEST_ASSERT_TRUE(crc_zero != 0xFFFF);

    uint8_t ones[4] = {0xFF, 0xFF, 0xFF, 0xFF};
    uint16_t crc_ones = crc16_ccitt(ones, sizeof(ones));
    TEST_ASSERT_TRUE(crc_ones != 0x0000);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_standard_test_vector);
    RUN_TEST(test_empty_buffer);
    RUN_TEST(test_null_buffer);
    RUN_TEST(test_single_byte_and_stepwise_update);
    RUN_TEST(test_all_zeros_and_ones);
    return UNITY_END();
}
