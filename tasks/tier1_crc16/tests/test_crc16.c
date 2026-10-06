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
    TEST_ASSERT_EQUAL_HEX16(0x84C0, crc_zero);

    uint8_t ones[4] = {0xFF, 0xFF, 0xFF, 0xFF};
    uint16_t crc_ones = crc16_ccitt(ones, sizeof(ones));
    TEST_ASSERT_EQUAL_HEX16(0x1D0F, crc_ones);
}

/* Polynomial long division consumes one input bit at a time, independently of
 * the reference's byte injection implementation. */
static uint16_t oracle_update(uint16_t initial, uint8_t byte) {
    uint32_t state = initial;
    for (uint8_t bit = 0; bit < 8; ++bit) {
        uint32_t feedback = ((state >> 15) ^ ((uint32_t)byte >> (7U - bit))) & 1U;
        state = (state * 2U) & UINT32_C(0xFFFF);
        if (feedback != 0U) state ^= UINT32_C(0x1021);
    }
    return (uint16_t)state;
}

void test_every_binary_byte_and_streaming_state(void) {
    const uint16_t initials[] = {0, 1, 0x8000, 0xFFFF, 0xA55A};
    uint8_t all_bytes[256];
    uint16_t expected = 0xFFFF;
    uint16_t streamed = 0xFFFF;
    for (uint16_t value = 0; value < 256; ++value) {
        uint8_t byte = (uint8_t)value;
        all_bytes[value] = byte;
        TEST_ASSERT_EQUAL_HEX16(oracle_update(0xFFFF, byte), crc16_ccitt(&byte, 1));
        for (size_t i = 0; i < sizeof(initials) / sizeof(initials[0]); ++i) {
            TEST_ASSERT_EQUAL_HEX16(oracle_update(initials[i], byte), crc16_update(initials[i], byte));
        }
        expected = oracle_update(expected, byte);
        streamed = crc16_update(streamed, byte);
        TEST_ASSERT_EQUAL_HEX16(expected, streamed);
    }
    TEST_ASSERT_EQUAL_HEX16(expected, crc16_ccitt(all_bytes, sizeof(all_bytes)));
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, crc16_ccitt(NULL, 0));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_standard_test_vector);
    RUN_TEST(test_empty_buffer);
    RUN_TEST(test_null_buffer);
    RUN_TEST(test_single_byte_and_stepwise_update);
    RUN_TEST(test_all_zeros_and_ones);
    RUN_TEST(test_every_binary_byte_and_streaming_state);
    return UNITY_END();
}
