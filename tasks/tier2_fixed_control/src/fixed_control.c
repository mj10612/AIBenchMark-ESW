/* AIBENCHMARK_ESW_CANARY_V1_tier2_fixed_control */
#include "fixed_control.h"
bool fixed_pid_init(fixed_pid_t *p,int16_t a,int16_t b,int16_t c,int16_t lo,int16_t hi){(void)p;(void)a;(void)b;(void)c;(void)lo;(void)hi;return true;}
int16_t fixed_pid_step(fixed_pid_t *p,int16_t e){(void)p;return e;}
int16_t fixed_filter_step(int16_t p,int16_t s,uint16_t a){(void)s;(void)a;return p;}
