/* AIBENCHMARK_ESW_CANARY_V1_tier1_q15_math */
#ifndef Q15_MATH_H
#define Q15_MATH_H

#include <stdint.h>

/* Raw signed Q1.15 values: -32768 represents -1, 32767 represents 1 - 2^-15.
 * Add/subtract clamp the exact raw result to [-32768, 32767].
 * Multiply divides the exact raw product by 32768, truncates toward zero,
 * then clamps. In particular, -32768 * -32768 returns 32767.
 */
int16_t q15_add_sat(int16_t a, int16_t b);
int16_t q15_sub_sat(int16_t a, int16_t b);
int16_t q15_mul_sat(int16_t a, int16_t b);

#endif
