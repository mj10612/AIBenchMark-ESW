/* AIBENCHMARK_ESW_CANARY_V1_tier2_cobs_codec */
#include "unity.h"
#include "cobs_codec.h"
#include <string.h>

void setUp(void) {}
void tearDown(void) {}

static void equal_bytes(const uint8_t *expected, const uint8_t *actual, size_t length) {
    for (size_t i = 0; i < length; ++i) TEST_ASSERT_EQUAL_HEX8(expected[i], actual[i]);
}

static void vector(const uint8_t *raw, size_t raw_length,
                   const uint8_t *encoded, size_t encoded_length) {
    uint8_t output[600];
    size_t written = 123;
    memset(output, 0xA5, sizeof(output));
    TEST_ASSERT_EQUAL(COBS_OK, cobs_encode(raw, raw_length, output, encoded_length, &written));
    TEST_ASSERT_EQUAL_UINT(encoded_length, written);
    equal_bytes(encoded, output, encoded_length);
    TEST_ASSERT_EQUAL_HEX8(0xA5, output[encoded_length]);
    memset(output, 0xA5, sizeof(output));
    TEST_ASSERT_EQUAL(COBS_OK, cobs_decode(encoded, encoded_length, output, raw_length, &written));
    TEST_ASSERT_EQUAL_UINT(raw_length, written);
    equal_bytes(raw, output, raw_length);
    TEST_ASSERT_EQUAL_HEX8(0xA5, output[raw_length]);
    memset(output, 0xA5, sizeof(output));
    written = 123;
    TEST_ASSERT_EQUAL(COBS_NO_SPACE, cobs_encode(raw, raw_length, output, encoded_length - 1, &written));
    TEST_ASSERT_EQUAL_UINT(0, written);
    TEST_ASSERT_EQUAL_HEX8(0xA5, output[encoded_length - 1]);
    if (raw_length != 0) {
        memset(output, 0xA5, sizeof(output));
        written = 123;
        TEST_ASSERT_EQUAL(COBS_NO_SPACE, cobs_decode(encoded, encoded_length, output, raw_length - 1, &written));
        TEST_ASSERT_EQUAL_UINT(0, written);
        TEST_ASSERT_EQUAL_HEX8(0xA5, output[raw_length - 1]);
    }
}

void test_empty_and_single_byte_vectors(void) {
    const uint8_t empty[] = {1}, zero[] = {0}, zero_encoded[] = {1, 1};
    const uint8_t byte[] = {0xFF}, byte_encoded[] = {2, 0xFF};
    vector(NULL, 0, empty, sizeof(empty));
    vector(zero, sizeof(zero), zero_encoded, sizeof(zero_encoded));
    vector(byte, sizeof(byte), byte_encoded, sizeof(byte_encoded));
}

void test_zero_positions_and_mixed_vectors(void) {
    const uint8_t raw[] = {0, 17, 0, 0, 34, 0xFF, 0};
    const uint8_t encoded[] = {1, 2, 17, 1, 3, 34, 0xFF, 1};
    vector(raw, sizeof(raw), encoded, sizeof(encoded));
    const uint8_t zeros[] = {0, 0, 0, 0};
    const uint8_t ones[] = {1, 1, 1, 1, 1};
    vector(zeros, sizeof(zeros), ones, sizeof(ones));
}

void test_all_byte_values_known_answer(void) {
    uint8_t raw[256], encoded[258];
    for (size_t i = 0; i < 256; ++i) raw[i] = (uint8_t)i;
    encoded[0] = 1;
    encoded[1] = 255;
    for (size_t i = 1; i <= 254; ++i) encoded[i + 1] = (uint8_t)i;
    encoded[256] = 2;
    encoded[257] = 255;
    vector(raw, sizeof(raw), encoded, sizeof(encoded));
}

void test_full_block_boundaries_and_canonical_ending(void) {
    const size_t lengths[] = {253, 254, 255, 508};
    uint8_t raw[509], encoded[512];
    memset(raw, 0x42, sizeof(raw));
    for (size_t i = 0; i < sizeof(lengths) / sizeof(lengths[0]); ++i) {
        size_t length = lengths[i], output = 0, remaining = length;
        while (remaining >= 254) {
            encoded[output++] = 255;
            memset(encoded + output, 0x42, 254);
            output += 254;
            remaining -= 254;
        }
        if (remaining != 0) {
            encoded[output++] = (uint8_t)(remaining + 1);
            memset(encoded + output, 0x42, remaining);
            output += remaining;
        }
        vector(raw, length, encoded, output);
    }
    raw[254] = 0;
    encoded[0] = 255;
    memset(encoded + 1, 0x42, 254);
    encoded[255] = 1;
    encoded[256] = 1;
    vector(raw, 255, encoded, 257);
}

void test_decoder_accepts_full_block_with_optional_empty_group(void) {
    uint8_t encoded[256], output[255];
    size_t written = 99;
    encoded[0] = 255;
    memset(encoded + 1, 0x55, 254);
    encoded[255] = 1;
    memset(output, 0xA5, sizeof(output));
    TEST_ASSERT_EQUAL(COBS_OK, cobs_decode(encoded, sizeof(encoded), output, 254, &written));
    TEST_ASSERT_EQUAL_UINT(254, written);
    for (size_t i = 0; i < 254; ++i) TEST_ASSERT_EQUAL_HEX8(0x55, output[i]);
    TEST_ASSERT_EQUAL_HEX8(0xA5, output[254]);
}

void test_capacity_failures_preserve_bounds_and_written(void) {
    const uint8_t raw[] = {1, 0, 2}, encoded[] = {2, 1, 2, 2};
    uint8_t output[600];
    for (size_t capacity = 0; capacity < sizeof(encoded); ++capacity) {
        size_t written = 99;
        memset(output, 0xA5, sizeof(output));
        TEST_ASSERT_EQUAL(COBS_NO_SPACE, cobs_encode(raw, sizeof(raw), output, capacity, &written));
        TEST_ASSERT_EQUAL_UINT(0, written);
        for (size_t i = capacity; i < sizeof(output); ++i) TEST_ASSERT_EQUAL_HEX8(0xA5, output[i]);
    }
    for (size_t capacity = 0; capacity < sizeof(raw); ++capacity) {
        size_t written = 99;
        memset(output, 0xA5, sizeof(output));
        TEST_ASSERT_EQUAL(COBS_NO_SPACE, cobs_decode(encoded, sizeof(encoded), output, capacity, &written));
        TEST_ASSERT_EQUAL_UINT(0, written);
        for (size_t i = capacity; i < sizeof(output); ++i) TEST_ASSERT_EQUAL_HEX8(0xA5, output[i]);
    }
}

void test_null_pointer_contract(void) {
    const uint8_t empty[] = {1};
    uint8_t output[8];
    size_t written = 99;
    TEST_ASSERT_EQUAL(COBS_INVALID_ARGUMENT, cobs_encode(empty, 1, output, 8, NULL));
    TEST_ASSERT_EQUAL(COBS_INVALID_ARGUMENT, cobs_decode(empty, 1, output, 8, NULL));
    TEST_ASSERT_EQUAL(COBS_INVALID_ARGUMENT, cobs_encode(NULL, 1, output, 8, &written));
    TEST_ASSERT_EQUAL_UINT(0, written);
    written = 99;
    TEST_ASSERT_EQUAL(COBS_INVALID_ARGUMENT, cobs_decode(NULL, 1, output, 8, &written));
    TEST_ASSERT_EQUAL_UINT(0, written);
    TEST_ASSERT_EQUAL(COBS_INVALID_ARGUMENT, cobs_encode(NULL, 0, NULL, 1, &written));
    TEST_ASSERT_EQUAL(COBS_INVALID_ARGUMENT, cobs_decode(empty, 1, NULL, 1, &written));
    TEST_ASSERT_EQUAL(COBS_NO_SPACE, cobs_encode(NULL, 0, NULL, 0, &written));
    TEST_ASSERT_EQUAL(COBS_OK, cobs_decode(empty, 1, NULL, 0, &written));
    TEST_ASSERT_EQUAL_UINT(0, written);
}

void test_malformed_encodings(void) {
    const uint8_t invalid[][5] = {{0}, {2}, {3, 17}, {255, 17, 34}, {2, 0}, {1, 0}, {2, 17, 0}};
    const size_t lengths[] = {1, 1, 2, 3, 2, 2, 3};
    uint8_t output[600];
    size_t written = 99;
    TEST_ASSERT_EQUAL(COBS_MALFORMED, cobs_decode(NULL, 0, output, sizeof(output), &written));
    TEST_ASSERT_EQUAL_UINT(0, written);
    for (size_t i = 0; i < sizeof(lengths) / sizeof(lengths[0]); ++i) {
        written = 99;
        TEST_ASSERT_EQUAL(COBS_MALFORMED, cobs_decode(invalid[i], lengths[i], output, sizeof(output), &written));
        TEST_ASSERT_EQUAL_UINT(0, written);
    }
}

void test_fixed_seed_roundtrip_and_source_preservation(void) {
    uint32_t state = UINT32_C(0xC0B51234);
    uint8_t raw[513], original[513], encoded[520], encoded_original[520], decoded[513];
    for (size_t length = 0; length <= sizeof(raw); ++length) {
        size_t encoded_length = 0, decoded_length = 0;
        for (size_t i = 0; i < length; ++i) {
            state = state * UINT32_C(1664525) + UINT32_C(1013904223);
            raw[i] = (uint8_t)(state >> 24);
        }
        memcpy(original, raw, length);
        TEST_ASSERT_EQUAL(COBS_OK, cobs_encode(raw, length, encoded, sizeof(encoded), &encoded_length));
        equal_bytes(original, raw, length);
        TEST_ASSERT_TRUE(encoded_length <= sizeof(encoded));
        for (size_t i = 0; i < encoded_length; ++i) TEST_ASSERT_TRUE(encoded[i] != 0);
        memcpy(encoded_original, encoded, encoded_length);
        TEST_ASSERT_EQUAL(COBS_OK, cobs_decode(encoded, encoded_length, decoded, sizeof(decoded), &decoded_length));
        equal_bytes(encoded_original, encoded, encoded_length);
        TEST_ASSERT_EQUAL_UINT(length, decoded_length);
        equal_bytes(raw, decoded, length);
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_empty_and_single_byte_vectors);
    RUN_TEST(test_zero_positions_and_mixed_vectors);
    RUN_TEST(test_all_byte_values_known_answer);
    RUN_TEST(test_full_block_boundaries_and_canonical_ending);
    RUN_TEST(test_decoder_accepts_full_block_with_optional_empty_group);
    RUN_TEST(test_capacity_failures_preserve_bounds_and_written);
    RUN_TEST(test_null_pointer_contract);
    RUN_TEST(test_malformed_encodings);
    RUN_TEST(test_fixed_seed_roundtrip_and_source_preservation);
    return UNITY_END();
}
