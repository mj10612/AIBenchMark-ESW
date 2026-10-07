/* AIBENCHMARK_ESW_CANARY_V1_tier1_q15_math */
#include "unity.h"
#include "q15_math.h"

void setUp(void) {}
void tearDown(void) {}

void test_add_ordinary(void) {
    TEST_ASSERT_EQUAL_INT(20000, q15_add_sat(12000, 8000));
    TEST_ASSERT_EQUAL_INT(-7000, q15_add_sat(-12000, 5000));
}

void test_add_positive_saturation(void) {
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_add_sat(INT16_MAX, 0));
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_add_sat(INT16_MAX, 1));
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_add_sat(INT16_MAX, INT16_MAX));
}

void test_add_negative_saturation(void) {
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_add_sat(INT16_MIN, 0));
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_add_sat(INT16_MIN, -1));
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_add_sat(INT16_MIN, INT16_MIN));
}

void test_add_mixed_extremes(void) {
    TEST_ASSERT_EQUAL_INT(-1, q15_add_sat(INT16_MIN, INT16_MAX));
    TEST_ASSERT_EQUAL_INT(-1, q15_add_sat(INT16_MAX, INT16_MIN));
    TEST_ASSERT_EQUAL_INT(0, q15_add_sat(16384, -16384));
}

void test_sub_ordinary(void) {
    TEST_ASSERT_EQUAL_INT(4000, q15_sub_sat(12000, 8000));
    TEST_ASSERT_EQUAL_INT(-17000, q15_sub_sat(-12000, 5000));
    TEST_ASSERT_EQUAL_INT(-7000, q15_sub_sat(-12000, -5000));
}

void test_sub_positive_saturation(void) {
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_sub_sat(INT16_MAX, -1));
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_sub_sat(INT16_MAX, INT16_MIN));
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_sub_sat(0, INT16_MIN));
}

void test_sub_negative_saturation(void) {
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_sub_sat(INT16_MIN, 1));
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_sub_sat(INT16_MIN, INT16_MAX));
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_sub_sat(-30000, 30000));
}

void test_sub_equal_extremes(void) {
    TEST_ASSERT_EQUAL_INT(0, q15_sub_sat(INT16_MIN, INT16_MIN));
    TEST_ASSERT_EQUAL_INT(0, q15_sub_sat(INT16_MAX, INT16_MAX));
    TEST_ASSERT_EQUAL_INT(INT16_MIN, q15_sub_sat(INT16_MIN, 0));
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_sub_sat(INT16_MAX, 0));
}

void test_mul_zero(void) {
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(0, INT16_MIN));
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(INT16_MAX, 0));
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(0, 0));
}

void test_mul_positive_fractions(void) {
    TEST_ASSERT_EQUAL_INT(8192, q15_mul_sat(16384, 16384));
    TEST_ASSERT_EQUAL_INT(4096, q15_mul_sat(16384, 8192));
    TEST_ASSERT_EQUAL_INT(27465, q15_mul_sat(30000, 30000));
}

void test_mul_signs(void) {
    TEST_ASSERT_EQUAL_INT(-8192, q15_mul_sat(16384, -16384));
    TEST_ASSERT_EQUAL_INT(8192, q15_mul_sat(-16384, -16384));
    TEST_ASSERT_EQUAL_INT(-16384, q15_mul_sat(INT16_MIN, 16384));
}

void test_mul_negative_one_squared_saturates(void) {
    TEST_ASSERT_EQUAL_INT(INT16_MAX, q15_mul_sat(INT16_MIN, INT16_MIN));
}

void test_mul_extreme_products(void) {
    TEST_ASSERT_EQUAL_INT(32766, q15_mul_sat(INT16_MAX, INT16_MAX));
    TEST_ASSERT_EQUAL_INT(-32767, q15_mul_sat(INT16_MIN, INT16_MAX));
    TEST_ASSERT_EQUAL_INT(-32767, q15_mul_sat(INT16_MAX, INT16_MIN));
}

void test_mul_truncates_toward_zero(void) {
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(-1, 1));
    TEST_ASSERT_EQUAL_INT(-1, q15_mul_sat(-3, 16384));
    TEST_ASSERT_EQUAL_INT(-1, q15_mul_sat(3, -16384));
    TEST_ASSERT_EQUAL_INT(1, q15_mul_sat(3, 16384));
    TEST_ASSERT_EQUAL_INT(1, q15_mul_sat(-3, -16384));
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(-32767, 1));
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(32767, -1));
}

void test_mul_one_raw_unit_boundaries(void) {
    TEST_ASSERT_EQUAL_INT(-1, q15_mul_sat(INT16_MIN, 1));
    TEST_ASSERT_EQUAL_INT(0, q15_mul_sat(INT16_MAX, 1));
    TEST_ASSERT_EQUAL_INT(1, q15_mul_sat(INT16_MIN, -1));
    TEST_ASSERT_EQUAL_INT(-1, q15_mul_sat(INT16_MAX, -2));
}

void test_all_raw_values_obey_identity_and_scaling(void) {
    int32_t value;
    /* Exhaust all 65536 raw values for these identities, not all input pairs. */
    for (value = INT16_MIN; value <= INT16_MAX; ++value) {
        int16_t raw = (int16_t)value;
        int16_t negated = value == INT16_MIN ? INT16_MAX : (int16_t)(-value);
        TEST_ASSERT_EQUAL_INT(raw, q15_add_sat(raw, 0));
        TEST_ASSERT_EQUAL_INT(0, q15_sub_sat(raw, raw));
        TEST_ASSERT_EQUAL_INT(negated, q15_sub_sat(0, raw));
        TEST_ASSERT_EQUAL_INT(negated, q15_mul_sat(raw, INT16_MIN));
        TEST_ASSERT_EQUAL_INT(negated, q15_mul_sat(INT16_MIN, raw));
        TEST_ASSERT_EQUAL_INT(value / 2, q15_mul_sat(raw, 16384));
        TEST_ASSERT_EQUAL_INT(value / 2, q15_mul_sat(16384, raw));
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_add_ordinary);
    RUN_TEST(test_add_positive_saturation);
    RUN_TEST(test_add_negative_saturation);
    RUN_TEST(test_add_mixed_extremes);
    RUN_TEST(test_sub_ordinary);
    RUN_TEST(test_sub_positive_saturation);
    RUN_TEST(test_sub_negative_saturation);
    RUN_TEST(test_sub_equal_extremes);
    RUN_TEST(test_mul_zero);
    RUN_TEST(test_mul_positive_fractions);
    RUN_TEST(test_mul_signs);
    RUN_TEST(test_mul_negative_one_squared_saturates);
    RUN_TEST(test_mul_extreme_products);
    RUN_TEST(test_mul_truncates_toward_zero);
    RUN_TEST(test_mul_one_raw_unit_boundaries);
    RUN_TEST(test_all_raw_values_obey_identity_and_scaling);
    return UNITY_END();
}
