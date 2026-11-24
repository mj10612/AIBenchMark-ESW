/* AIBENCHMARK_ESW_CANARY_V1_tier3_flash_update */
#include "unity.h"
#include "flash_update.h"
#include <string.h>

static uint8_t slots[2][256], image[256];
static uint8_t active;
static size_t image_length, written_bytes, read_bytes;
static int calls, fail_at, commits;
static bool slot_erased, corrupt;
static flash_update_t u;

static int erased(void *ctx, uint8_t slot) {
    (void)ctx;
    TEST_ASSERT_EQUAL_UINT(1U - active, slot);
    TEST_ASSERT_FALSE(slot_erased);
    if (++calls == fail_at) return -1;
    memset(slots[slot], 0xFF, sizeof(slots[slot]));
    slot_erased = true;
    return 0;
}

static int written(void *ctx, uint8_t slot, size_t offset, const uint8_t *data, size_t length) {
    (void)ctx;
    TEST_ASSERT_EQUAL_UINT(1U - active, slot);
    TEST_ASSERT_TRUE(slot_erased);
    TEST_ASSERT_EQUAL_UINT(0, read_bytes);
    TEST_ASSERT_TRUE(offset == written_bytes);
    TEST_ASSERT_TRUE(length > 0 && length <= 64U && length <= image_length - written_bytes);
    if (++calls == fail_at) return -1;
    memcpy(slots[slot] + offset, data, length);
    written_bytes += length;
    return 0;
}

static int readback(void *ctx, uint8_t slot, size_t offset, uint8_t *data, size_t length) {
    (void)ctx;
    TEST_ASSERT_EQUAL_UINT(1U - active, slot);
    TEST_ASSERT_EQUAL_UINT(image_length, written_bytes);
    TEST_ASSERT_TRUE(offset == read_bytes);
    TEST_ASSERT_TRUE(length > 0 && length <= 64U && length <= image_length - read_bytes);
    if (++calls == fail_at) return -1;
    memcpy(data, slots[slot] + offset, length);
    if (corrupt && offset == 0) data[0] ^= 1;
    read_bytes += length;
    return 0;
}

static int committed(void *ctx, uint8_t slot, uint16_t crc, size_t length) {
    (void)ctx;
    TEST_ASSERT_EQUAL_UINT(1U - active, slot);
    TEST_ASSERT_EQUAL_UINT(0, commits);
    TEST_ASSERT_EQUAL_UINT(image_length, written_bytes);
    TEST_ASSERT_EQUAL_UINT(image_length, read_bytes);
    TEST_ASSERT_TRUE(length == image_length);
    TEST_ASSERT_EQUAL_HEX16(flash_update_crc(image, length), crc);
    TEST_ASSERT_EQUAL(0, memcmp(image, slots[slot], length));
    if (++calls == fail_at) return -1;
    active = slot;
    ++commits;
    return 0;
}

static const update_hal_t hal = {NULL, erased, written, readback, committed};

void setUp(void) {
    memset(slots, 0xA5, sizeof(slots));
    for (size_t i = 0; i < sizeof(image); ++i) image[i] = (uint8_t)(i * 17U);
    active = 0;
    image_length = written_bytes = read_bytes = 0;
    calls = commits = 0;
    fail_at = -1;
    slot_erased = corrupt = false;
    memset(&u, 0, sizeof(u));
}

void tearDown(void) {}

static void begin_update(size_t length) {
    image_length = length;
    calls = 0;
    written_bytes = read_bytes = 0;
    slot_erased = false;
    TEST_ASSERT_TRUE(flash_update_begin(&u, &hal, active, image, length));
    TEST_ASSERT_EQUAL(UPDATE_ERASE, u.state);
    TEST_ASSERT_EQUAL(0, calls);
}

static int step(void) {
    int before = calls;
    int rc = flash_update_step(&u);
    TEST_ASSERT_TRUE(calls - before <= 1);
    return rc;
}

static size_t step_limit(void) {
    /* Allow one-byte writes and reads plus steps that only change state. */
    return 4U * image_length + 8U;
}

static size_t finish(void) {
    size_t steps = 0;
    while (steps < step_limit() && u.state != UPDATE_DONE) {
        TEST_ASSERT_EQUAL(UPDATE_OK, step());
        ++steps;
    }
    TEST_ASSERT_EQUAL(UPDATE_DONE, u.state);
    TEST_ASSERT_EQUAL(1, commits);
    return steps;
}

static void assert_old_image_preserved(void) {
    for (size_t i = 0; i < sizeof(slots[0]); ++i) TEST_ASSERT_EQUAL_HEX8(0xA5, slots[0][i]);
}

static void assert_terminal_step(int expected) {
    int before = calls;
    TEST_ASSERT_EQUAL(expected, step());
    TEST_ASSERT_EQUAL(before, calls);
}

void test_crc_known_vector_and_null(void) {
    const uint8_t vector[] = "123456789";
    TEST_ASSERT_EQUAL_HEX16(0x29B1, flash_update_crc(vector, 9));
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, flash_update_crc(NULL, 0));
    TEST_ASSERT_EQUAL_HEX16(0, flash_update_crc(NULL, 1));
}

void test_full_update_order_and_active_preservation(void) {
    begin_update(130);
    finish();
    TEST_ASSERT_EQUAL(1, active);
    assert_old_image_preserved();
    assert_terminal_step(UPDATE_OK);
}

void test_power_cut_after_every_phase_keeps_old_image(void) {
    size_t steps_before_commit = 0;
    begin_update(130);
    while (steps_before_commit < step_limit() && commits == 0) {
        TEST_ASSERT_EQUAL(UPDATE_OK, step());
        if (commits == 0) ++steps_before_commit;
    }
    TEST_ASSERT_EQUAL(1, commits);

    for (size_t cut = 0; cut <= steps_before_commit; ++cut) {
        setUp();
        begin_update(130);
        for (size_t i = 0; i < cut; ++i) TEST_ASSERT_EQUAL(UPDATE_OK, step());
        TEST_ASSERT_EQUAL(0, active);
        TEST_ASSERT_EQUAL(0, commits);
        assert_old_image_preserved();
        /* Lose all RAM; reboot derives active from the durable HAL record. */
        memset(&u, 0, sizeof(u));
        begin_update(130);
        finish();
        TEST_ASSERT_EQUAL(1, active);
        assert_old_image_preserved();
    }
}

void test_corruption_never_commits(void) {
    begin_update(130);
    corrupt = true;
    int rc = UPDATE_OK;
    for (size_t i = 0; i < step_limit() && rc == UPDATE_OK; ++i) rc = step();
    TEST_ASSERT_EQUAL(UPDATE_CRC, rc);
    TEST_ASSERT_EQUAL(UPDATE_ERROR, u.state);
    TEST_ASSERT_EQUAL(0, active);
    TEST_ASSERT_EQUAL(0, commits);
    assert_terminal_step(UPDATE_IO);
}

void test_error_at_every_hal_operation(void) {
    begin_update(130);
    finish();
    int operations = calls;
    for (int failure = 1; failure <= operations; ++failure) {
        setUp();
        begin_update(130);
        fail_at = failure;
        int rc = UPDATE_OK;
        for (size_t i = 0; i < step_limit() && rc == UPDATE_OK; ++i) rc = step();
        TEST_ASSERT_EQUAL(UPDATE_IO, rc);
        TEST_ASSERT_EQUAL(UPDATE_ERROR, u.state);
        TEST_ASSERT_EQUAL(failure, calls);
        TEST_ASSERT_EQUAL(0, active);
        TEST_ASSERT_EQUAL(0, commits);
        assert_old_image_preserved();
        assert_terminal_step(UPDATE_IO);
    }
}

void test_bounds_reinit_and_second_slot(void) {
    TEST_ASSERT_FALSE(flash_update_begin(&u, &hal, 2, image, 1));
    TEST_ASSERT_FALSE(flash_update_begin(&u, &hal, 0, NULL, 1));
    TEST_ASSERT_FALSE(flash_update_begin(&u, &hal, 0, image, 0));
    TEST_ASSERT_FALSE(flash_update_begin(&u, &hal, 0, image, 257));
    update_hal_t bad = hal;
    bad.commit = NULL;
    TEST_ASSERT_FALSE(flash_update_begin(&u, &bad, 0, image, 1));
    TEST_ASSERT_EQUAL(0, calls);
    active = 1;
    begin_update(1);
    finish();
    TEST_ASSERT_EQUAL(0, active);
    TEST_ASSERT_FALSE(flash_update_begin(&u, &hal, 0, image, 0));
    TEST_ASSERT_EQUAL(UPDATE_ARGUMENT, step());
}

void test_valid_lengths_cover_chunk_boundaries_and_maximum(void) {
    const size_t lengths[] = {63, 64, 65, 127, 128, 129, 131, 255, 256};
    for (size_t index = 0; index < sizeof(lengths) / sizeof(lengths[0]); ++index) {
        setUp();
        begin_update(lengths[index]);
        finish();
        TEST_ASSERT_EQUAL(1, active);
        assert_old_image_preserved();
        assert_terminal_step(UPDATE_OK);
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_crc_known_vector_and_null);
    RUN_TEST(test_full_update_order_and_active_preservation);
    RUN_TEST(test_power_cut_after_every_phase_keeps_old_image);
    RUN_TEST(test_corruption_never_commits);
    RUN_TEST(test_error_at_every_hal_operation);
    RUN_TEST(test_bounds_reinit_and_second_slot);
    RUN_TEST(test_valid_lengths_cover_chunk_boundaries_and_maximum);
    return UNITY_END();
}
