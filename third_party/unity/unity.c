/* ==========================================
    Unity Project - A Test Framework for C
    Copyright (c) 2007-21 Mike Karlesky, Mark VanderVoord, Greg Williams
    [Released under MIT License. Please refer to license.txt for details]
========================================== */

#include "unity.h"
#include <string.h>
#include <inttypes.h>

UNITY_STORAGE_T Unity;

void UnityBegin(const char* filename)
{
    Unity.TestFile = filename;
    Unity.CurrentTestName = NULL;
    Unity.CurrentTestLineNumber = 0;
    Unity.NumberOfTests = 0;
    Unity.TestFailures = 0;
    Unity.TestIgnores = 0;
    Unity.CurrentTestFailed = 0;
    Unity.CurrentTestIgnored = 0;
}

int UnityEnd(void)
{
    printf("-----------------------\n");
    printf("%u Tests %u Failures %u Ignored\n",
           Unity.NumberOfTests, Unity.TestFailures, Unity.TestIgnores);
    if (Unity.TestFailures == 0U)
    {
        printf("OK\n");
        return 0;
    }
    else
    {
        printf("FAIL\n");
        return (int)Unity.TestFailures;
    }
}

void UnityDefaultTestRun(void (*func)(void), const char* name, int line_num)
{
    Unity.CurrentTestName = name;
    Unity.CurrentTestLineNumber = (uint32_t)line_num;
    Unity.NumberOfTests++;
    Unity.CurrentTestFailed = 0;
    Unity.CurrentTestIgnored = 0;

    if (setjmp(Unity.AbortFrame) == 0)
    {
        setUp();
        func();
    }
    /* Cleanup needs its own abort frame so an assertion cannot retry it. */
    if (setjmp(Unity.AbortFrame) == 0)
    {
        tearDown();
    }

    /* Count each test once, even if both the body and cleanup abort. */
    if (Unity.CurrentTestFailed)
    {
        Unity.TestFailures++;
        printf("%s:%d:%s:FAIL\n", Unity.TestFile, line_num, name);
    }
    else if (Unity.CurrentTestIgnored)
    {
        Unity.TestIgnores++;
        printf("%s:%d:%s:IGNORE\n", Unity.TestFile, line_num, name);
    }
    else
    {
        printf("%s:%d:%s:PASS\n", Unity.TestFile, line_num, name);
    }
}

void UnityFail(const char* message, uint32_t line)
{
    Unity.CurrentTestFailed = 1;
    printf("%s:%u:FAIL: %s\n", Unity.TestFile, line, message ? message : "Assertion Failed");
    longjmp(Unity.AbortFrame, 1);
}

void UnityIgnore(const char* message, uint32_t line)
{
    Unity.CurrentTestIgnored = 1;
    printf("%s:%u:IGNORE: %s\n", Unity.TestFile, line, message ? message : "Test Ignored");
    longjmp(Unity.AbortFrame, 1);
}

void UnityAssertEqualNumber(int64_t expected, int64_t actual, const char* msg, uint32_t line, int style)
{
    uint64_t mask = UINT64_MAX;
    if (style == UNITY_DISPLAY_STYLE_HEX8) mask = UINT64_C(0xFF);
    else if (style == UNITY_DISPLAY_STYLE_HEX16) mask = UINT64_C(0xFFFF);
    else if (style == UNITY_DISPLAY_STYLE_HEX32) mask = UINT64_C(0xFFFFFFFF);
    if (style == UNITY_DISPLAY_STYLE_HEX8 || style == UNITY_DISPLAY_STYLE_HEX16 || style == UNITY_DISPLAY_STYLE_HEX32) {
        expected = (int64_t)((uint64_t)expected & mask);
        actual = (int64_t)((uint64_t)actual & mask);
    }
    if (expected != actual)
    {
        char buf[128];
        if (style == UNITY_DISPLAY_STYLE_HEX8)
        {
            snprintf(buf, sizeof(buf), "Expected 0x%02X Was 0x%02X", (unsigned int)(expected & 0xFF), (unsigned int)(actual & 0xFF));
        }
        else if (style == UNITY_DISPLAY_STYLE_HEX16)
        {
            snprintf(buf, sizeof(buf), "Expected 0x%04X Was 0x%04X", (unsigned int)(expected & 0xFFFF), (unsigned int)(actual & 0xFFFF));
        }
        else if (style == UNITY_DISPLAY_STYLE_HEX32)
        {
            snprintf(buf, sizeof(buf), "Expected 0x%08X Was 0x%08X", (unsigned int)(expected & 0xFFFFFFFF), (unsigned int)(actual & 0xFFFFFFFF));
        }
        else
        {
            snprintf(buf, sizeof(buf), "Expected %lld Was %lld", (long long)expected, (long long)actual);
        }
        UnityFail(msg ? msg : buf, line);
    }
}

void UnityAssertBits(uint32_t mask, uint32_t expected, uint32_t actual, const char* msg, uint32_t line)
{
    UnityAssertEqualNumber((int64_t)(expected & mask), (int64_t)(actual & mask),
                           msg, line, UNITY_DISPLAY_STYLE_HEX32);
}
