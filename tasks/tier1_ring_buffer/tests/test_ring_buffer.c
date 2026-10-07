/* AIBENCHMARK_ESW_CANARY_V1_tier1_ring_buffer */
#include "unity.h"
#include "ring_buffer.h"

#define BUFFER_SIZE 8
static uint8_t raw_buffer[BUFFER_SIZE];
static ring_buffer_t rb;

void setUp(void) {
    ring_buffer_init(&rb, raw_buffer, BUFFER_SIZE);
}

void tearDown(void) {
}

void test_init_and_empty(void) {
    TEST_ASSERT_TRUE(ring_buffer_is_empty(&rb));
    TEST_ASSERT_FALSE(ring_buffer_is_full(&rb));
    TEST_ASSERT_EQUAL_UINT(0, ring_buffer_count(&rb));
}

void test_push_and_pop_single(void) {
    uint8_t out_byte = 0;
    TEST_ASSERT_TRUE(ring_buffer_push(&rb, 0x42));
    TEST_ASSERT_FALSE(ring_buffer_is_empty(&rb));
    TEST_ASSERT_EQUAL_UINT(1, ring_buffer_count(&rb));

    TEST_ASSERT_TRUE(ring_buffer_pop(&rb, &out_byte));
    TEST_ASSERT_EQUAL_HEX8(0x42, out_byte);
    TEST_ASSERT_TRUE(ring_buffer_is_empty(&rb));
    TEST_ASSERT_EQUAL_UINT(0, ring_buffer_count(&rb));
}

void test_fill_to_capacity_and_is_full(void) {
    for (uint8_t i = 0; i < BUFFER_SIZE; i++) {
        TEST_ASSERT_TRUE(ring_buffer_push(&rb, i));
    }
    TEST_ASSERT_TRUE(ring_buffer_is_full(&rb));
    TEST_ASSERT_EQUAL_UINT(BUFFER_SIZE, ring_buffer_count(&rb));

    /* Push when full must fail without modifying data */
    TEST_ASSERT_FALSE(ring_buffer_push(&rb, 0xFF));
    TEST_ASSERT_EQUAL_UINT(BUFFER_SIZE, ring_buffer_count(&rb));
}

void test_fifo_ordering(void) {
    for (uint8_t i = 0; i < BUFFER_SIZE; i++) {
        ring_buffer_push(&rb, i * 10);
    }
    for (uint8_t i = 0; i < BUFFER_SIZE; i++) {
        uint8_t val = 0;
        TEST_ASSERT_TRUE(ring_buffer_pop(&rb, &val));
        TEST_ASSERT_EQUAL_UINT(i * 10, val);
    }
    TEST_ASSERT_TRUE(ring_buffer_is_empty(&rb));
}

void test_wrap_around_continuous(void) {
    /* Push 5, pop 3, push 4... repeatedly to test circular index wrap */
    for (int cycle = 0; cycle < 10; cycle++) {
        for (uint8_t i = 0; i < 4; i++) {
            TEST_ASSERT_TRUE(ring_buffer_push(&rb, (uint8_t)(cycle * 10 + i)));
        }
        for (uint8_t i = 0; i < 4; i++) {
            uint8_t val = 0;
            TEST_ASSERT_TRUE(ring_buffer_pop(&rb, &val));
            TEST_ASSERT_EQUAL_UINT(cycle * 10 + i, val);
        }
    }
    TEST_ASSERT_TRUE(ring_buffer_is_empty(&rb));
}

void test_null_pointer_safety(void) {
    uint8_t byte = 0;
    TEST_ASSERT_FALSE(ring_buffer_push(NULL, 0x11));
    TEST_ASSERT_FALSE(ring_buffer_pop(NULL, &byte));
    TEST_ASSERT_FALSE(ring_buffer_pop(&rb, NULL));
    TEST_ASSERT_TRUE(ring_buffer_is_empty(NULL));
    TEST_ASSERT_FALSE(ring_buffer_is_full(NULL));
    TEST_ASSERT_EQUAL_UINT(0, ring_buffer_count(NULL));
}

void test_non_power_of_two_capacity_rollover(void) {
    uint8_t storage[3] = {0};
    ring_buffer_t local;
    ring_buffer_init(&local, storage, 3);
    /* Many fill/drain cycles cross the implementation's counter rollover. */
    for (uint16_t cycle = 0; cycle < 300; cycle++) {
        for (uint8_t i = 0; i < 3; i++) {
            TEST_ASSERT_TRUE(ring_buffer_push(&local, (uint8_t)(cycle + i)));
        }
        TEST_ASSERT_TRUE(ring_buffer_is_full(&local));
        TEST_ASSERT_FALSE(ring_buffer_push(&local, 0xFF));
        for (uint8_t i = 0; i < 3; i++) {
            uint8_t value = 0;
            TEST_ASSERT_TRUE(ring_buffer_pop(&local, &value));
            TEST_ASSERT_EQUAL_HEX8((uint8_t)(cycle + i), value);
            TEST_ASSERT_EQUAL_UINT(2U - i, ring_buffer_count(&local));
        }
    }
}

void test_invalid_storage_and_capacity(void) {
    uint8_t value = 0;
    ring_buffer_init(&rb, NULL, BUFFER_SIZE);
    TEST_ASSERT_FALSE(ring_buffer_push(&rb, 1));
    TEST_ASSERT_FALSE(ring_buffer_pop(&rb, &value));
    TEST_ASSERT_TRUE(ring_buffer_is_empty(&rb));
    TEST_ASSERT_EQUAL_UINT(0, ring_buffer_count(&rb));
    ring_buffer_init(&rb, raw_buffer, 0);
    TEST_ASSERT_FALSE(ring_buffer_push(&rb, 1));
    ring_buffer_init(&rb, raw_buffer, SIZE_MAX);
    TEST_ASSERT_FALSE(ring_buffer_push(&rb, 1));
}

void test_capacity_one(void) {
    uint8_t storage[1];
    ring_buffer_t local;
    ring_buffer_init(&local, storage, 1);
    for (uint8_t i = 0; i < 20; i++) {
        uint8_t value = 0;
        TEST_ASSERT_TRUE(ring_buffer_push(&local, i));
        TEST_ASSERT_FALSE(ring_buffer_push(&local, 0xFF));
        TEST_ASSERT_TRUE(ring_buffer_pop(&local, &value));
        TEST_ASSERT_EQUAL_HEX8(i, value);
    }
}

void test_forbidden_upper_capacities_preserve_storage(void) {
    const size_t capacities[] = {SIZE_MAX / 2U + 1U, SIZE_MAX / 2U + 2U, SIZE_MAX - 1U};
    uint8_t storage[1] = {0xA5};
    uint8_t output = 0xC3;
    for (size_t i = 0; i < sizeof(capacities) / sizeof(capacities[0]); ++i) {
        ring_buffer_init(&rb, storage, capacities[i]);
        TEST_ASSERT_FALSE(ring_buffer_push(&rb, 42));
        TEST_ASSERT_FALSE(ring_buffer_pop(&rb, &output));
        TEST_ASSERT_EQUAL_HEX8(0xC3, output);
        TEST_ASSERT_EQUAL_HEX8(0xA5, storage[0]);
        TEST_ASSERT_EQUAL_UINT(0, ring_buffer_count(&rb));
        TEST_ASSERT_TRUE(ring_buffer_is_empty(&rb));
        TEST_ASSERT_FALSE(ring_buffer_is_full(&rb));
    }
}

void test_capacity_300_fill_drain_and_wrap(void) {
    uint8_t storage[300];
    ring_buffer_t local;
    ring_buffer_init(&local, storage, sizeof(storage));
    for (size_t cycle = 0; cycle < 4; ++cycle) {
        for (size_t i = 0; i < sizeof(storage); ++i) {
            TEST_ASSERT_TRUE(ring_buffer_push(&local, (uint8_t)(i + cycle * 31U)));
            TEST_ASSERT_EQUAL_UINT(i + 1U, ring_buffer_count(&local));
        }
        TEST_ASSERT_TRUE(ring_buffer_is_full(&local));
        TEST_ASSERT_FALSE(ring_buffer_push(&local, 0xFF));
        for (size_t i = 0; i < sizeof(storage); ++i) {
            uint8_t output = 0;
            TEST_ASSERT_TRUE(ring_buffer_pop(&local, &output));
            TEST_ASSERT_EQUAL_HEX8((uint8_t)(i + cycle * 31U), output);
            TEST_ASSERT_EQUAL_UINT(sizeof(storage) - i - 1U, ring_buffer_count(&local));
        }
        TEST_ASSERT_TRUE(ring_buffer_is_empty(&local));
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_and_empty);
    RUN_TEST(test_push_and_pop_single);
    RUN_TEST(test_fill_to_capacity_and_is_full);
    RUN_TEST(test_fifo_ordering);
    RUN_TEST(test_wrap_around_continuous);
    RUN_TEST(test_null_pointer_safety);
    RUN_TEST(test_non_power_of_two_capacity_rollover);
    RUN_TEST(test_invalid_storage_and_capacity);
    RUN_TEST(test_capacity_one);
    RUN_TEST(test_forbidden_upper_capacities_preserve_storage);
    RUN_TEST(test_capacity_300_fill_drain_and_wrap);
    return UNITY_END();
}
