/* ==========================================
    Unity Project - A Test Framework for C
    Copyright (c) 2007-21 Mike Karlesky, Mark VanderVoord, Greg Williams
    [Released under MIT License. Please refer to license.txt for details]
========================================== */

#ifndef UNITY_INTERNALS_H
#define UNITY_INTERNALS_H

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdio.h>
#include <setjmp.h>
#include <stdint.h>
#include <stddef.h>

#define UNITY_DISPLAY_STYLE_INT 0
#define UNITY_DISPLAY_STYLE_UINT 1
#define UNITY_DISPLAY_STYLE_HEX8 2
#define UNITY_DISPLAY_STYLE_HEX16 3
#define UNITY_DISPLAY_STYLE_HEX32 4

typedef struct {
    const char* TestFile;
    const char* CurrentTestName;
    uint32_t CurrentTestLineNumber;
    uint32_t NumberOfTests;
    uint32_t TestFailures;
    uint32_t TestIgnores;
    uint32_t CurrentTestFailed;
    uint32_t CurrentTestIgnored;
    jmp_buf AbortFrame;
} UNITY_STORAGE_T;

extern UNITY_STORAGE_T Unity;

void UnityBegin(const char* filename);
int UnityEnd(void);
void UnityDefaultTestRun(void (*func)(void), const char* name, int line_num);
void UnityAssertEqualNumber(int64_t expected, int64_t actual, const char* msg, uint32_t line, int style);
void UnityAssertBits(uint32_t mask, uint32_t expected, uint32_t actual, const char* msg, uint32_t line);
void UnityFail(const char* message, uint32_t line);
void UnityIgnore(const char* message, uint32_t line);

#ifdef __cplusplus
}
#endif

#endif /* UNITY_INTERNALS_H */
