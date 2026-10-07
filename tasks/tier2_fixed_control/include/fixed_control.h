/* AIBENCHMARK_ESW_CANARY_V1_tier2_fixed_control */
#ifndef FIXED_CONTROL_H
#define FIXED_CONTROL_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {int16_t kp,ki,kd,minimum,maximum,previous;int32_t integral;bool ready;} fixed_pid_t;
bool fixed_pid_init(fixed_pid_t *,int16_t kp,int16_t ki,int16_t kd,int16_t minimum,int16_t maximum);
int16_t fixed_pid_step(fixed_pid_t *,int16_t error);
int16_t fixed_filter_step(int16_t previous,int16_t sample,uint16_t alpha);
#endif
