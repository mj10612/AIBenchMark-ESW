/* ==========================================
    Unity Project - A Test Framework for C
    Copyright (c) 2007-21 Mike Karlesky, Mark VanderVoord, Greg Williams
    [Released under MIT License. Please refer to license.txt for details]
========================================== */

#ifndef UNITY_FRAMEWORK_H
#define UNITY_FRAMEWORK_H

#include "unity_internals.h"

#ifdef __cplusplus
extern "C"
{
#endif

void setUp(void);
void tearDown(void);

#define UNITY_BEGIN() UnityBegin(__FILE__)
#define UNITY_END() UnityEnd()
#define RUN_TEST(func) UnityDefaultTestRun(func, #func, __LINE__)

#define TEST_ASSERT(condition) do { if (!(condition)) { UnityFail("Condition evaluated FALSE", __LINE__); } } while (0)
#define TEST_ASSERT_TRUE(condition) TEST_ASSERT(condition)
#define TEST_ASSERT_FALSE(condition) TEST_ASSERT(!(condition))
#define TEST_ASSERT_NULL(pointer) TEST_ASSERT((pointer) == NULL)
#define TEST_ASSERT_NOT_NULL(pointer) TEST_ASSERT((pointer) != NULL)

#define TEST_ASSERT_EQUAL_INT(expected, actual) \
    UnityAssertEqualNumber((int64_t)(expected), (int64_t)(actual), NULL, __LINE__, UNITY_DISPLAY_STYLE_INT)
#define TEST_ASSERT_EQUAL_UINT(expected, actual) \
    UnityAssertEqualNumber((int64_t)(expected), (int64_t)(actual), NULL, __LINE__, UNITY_DISPLAY_STYLE_UINT)
#define TEST_ASSERT_EQUAL_HEX8(expected, actual) \
    UnityAssertEqualNumber((int64_t)(expected), (int64_t)(actual), NULL, __LINE__, UNITY_DISPLAY_STYLE_HEX8)
#define TEST_ASSERT_EQUAL_HEX16(expected, actual) \
    UnityAssertEqualNumber((int64_t)(expected), (int64_t)(actual), NULL, __LINE__, UNITY_DISPLAY_STYLE_HEX16)
#define TEST_ASSERT_EQUAL_HEX32(expected, actual) \
    UnityAssertEqualNumber((int64_t)(expected), (int64_t)(actual), NULL, __LINE__, UNITY_DISPLAY_STYLE_HEX32)

#define TEST_ASSERT_EQUAL(expected, actual) TEST_ASSERT_EQUAL_INT(expected, actual)
#define TEST_ASSERT_BITS(mask, expected, actual) \
    UnityAssertBits((uint32_t)(mask), (uint32_t)(expected), (uint32_t)(actual), NULL, __LINE__)
#define TEST_ASSERT_BITS_HIGH(mask, actual) TEST_ASSERT_BITS(mask, mask, actual)
#define TEST_ASSERT_BITS_LOW(mask, actual) TEST_ASSERT_BITS(mask, 0, actual)
#define TEST_FAIL_MESSAGE(msg) UnityFail(msg, __LINE__)
#define TEST_IGNORE_MESSAGE(msg) UnityIgnore(msg, __LINE__)

#ifdef __cplusplus
}
#endif

#endif /* UNITY_FRAMEWORK_H */
