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

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_and_empty);
    RUN_TEST(test_push_and_pop_single);
    RUN_TEST(test_fill_to_capacity_and_is_full);
    RUN_TEST(test_fifo_ordering);
    RUN_TEST(test_wrap_around_continuous);
    RUN_TEST(test_null_pointer_safety);
    return UNITY_END();
}
