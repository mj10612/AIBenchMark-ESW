/* AIBENCHMARK_ESW_CANARY_V1_tier1_q15_math */
#include "q15_math.h"

static int16_t clamp_q15(int32_t value) {
    if (value > INT16_MAX) {
        return INT16_MAX;
    }
    if (value < INT16_MIN) {
        return INT16_MIN;
    }
    return (int16_t)value;
}

int16_t q15_add_sat(int16_t a, int16_t b) {
    return clamp_q15((int32_t)a + (int32_t)b);
}

int16_t q15_sub_sat(int16_t a, int16_t b) {
    return clamp_q15((int32_t)a - (int32_t)b);
}

int16_t q15_mul_sat(int16_t a, int16_t b) {
    /* Widen before multiplying, including on targets with 16-bit int.
     * C99 signed division truncates toward zero, unlike a negative shift.
     */
    int32_t product = (int32_t)a * (int32_t)b;
    return clamp_q15(product / INT32_C(32768));
}
