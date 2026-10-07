/* AIBENCHMARK_ESW_CANARY_V1_tier2_fixed_control */
#include "unity.h"
#include "fixed_control.h"
#include <limits.h>
static fixed_pid_t p;
void setUp(void){}
void tearDown(void){}
void test_init_and_reset_validation(void){TEST_ASSERT_FALSE(fixed_pid_init(NULL,1,2,3,-1,1));TEST_ASSERT_TRUE(fixed_pid_init(&p,256,128,64,-100,100));TEST_ASSERT_EQUAL(0,p.integral);TEST_ASSERT_EQUAL(0,p.previous);TEST_ASSERT_FALSE(fixed_pid_init(&p,1,2,3,2,1));TEST_ASSERT_EQUAL(0,fixed_pid_step(&p,10));}
void test_q8_proportional_and_signed_truncation(void){TEST_ASSERT_TRUE(fixed_pid_init(&p,128,0,0,-32768,32767));TEST_ASSERT_EQUAL(1,fixed_pid_step(&p,3));TEST_ASSERT_EQUAL(-1,fixed_pid_step(&p,-3));}
void test_integral_antiwindup_and_recovery(void){TEST_ASSERT_TRUE(fixed_pid_init(&p,0,256,0,-10,10));TEST_ASSERT_EQUAL(6,fixed_pid_step(&p,6));TEST_ASSERT_EQUAL(10,fixed_pid_step(&p,6));TEST_ASSERT_EQUAL(6,p.integral);TEST_ASSERT_EQUAL(2,fixed_pid_step(&p,-4));TEST_ASSERT_EQUAL(2,p.integral);}
void test_derivative_and_wide_arithmetic(void){TEST_ASSERT_TRUE(fixed_pid_init(&p,32767,32767,32767,-100,100));TEST_ASSERT_EQUAL(100,fixed_pid_step(&p,32767));TEST_ASSERT_EQUAL(-100,fixed_pid_step(&p,-32768));TEST_ASSERT_EQUAL(-32768,p.previous);TEST_ASSERT_TRUE(fixed_pid_init(&p,0,0,128,-32768,32767));TEST_ASSERT_EQUAL(5,fixed_pid_step(&p,10));TEST_ASSERT_EQUAL(-7,fixed_pid_step(&p,-5));}
void test_integral_limits(void){TEST_ASSERT_TRUE(fixed_pid_init(&p,0,0,0,-32768,32767));p.integral=INT32_MAX-2;TEST_ASSERT_EQUAL(0,fixed_pid_step(&p,32767));TEST_ASSERT_EQUAL(INT32_MAX,p.integral);p.integral=INT32_MIN+2;TEST_ASSERT_EQUAL(0,fixed_pid_step(&p,-32768));TEST_ASSERT_EQUAL(INT32_MIN,p.integral);
 TEST_ASSERT_TRUE(fixed_pid_init(&p,0,32767,0,-100,100));TEST_ASSERT_EQUAL(100,fixed_pid_step(&p,32767));TEST_ASSERT_EQUAL(0,p.integral);TEST_ASSERT_EQUAL(-100,fixed_pid_step(&p,-32768));
 p.integral=INT32_MAX;TEST_ASSERT_EQUAL(100,fixed_pid_step(&p,-1));TEST_ASSERT_EQUAL(INT32_MAX-1,p.integral);
}
void test_filter_endpoints_and_extremes(void){TEST_ASSERT_EQUAL(-32768,fixed_filter_step(-32768,32767,0));TEST_ASSERT_EQUAL(32767,fixed_filter_step(-32768,32767,256));TEST_ASSERT_EQUAL(32767,fixed_filter_step(-32768,32767,300));TEST_ASSERT_EQUAL(0,fixed_filter_step(-32768,32767,128));TEST_ASSERT_EQUAL(1,fixed_filter_step(3,0,128));TEST_ASSERT_EQUAL(-1,fixed_filter_step(-3,0,128));}
void test_filter_independent_integer_oracle(void){const int16_t values[]={INT16_MIN,-1000,-3,0,3,1000,INT16_MAX};const uint16_t alphas[]={0,1,127,128,255,256,257};for(size_t i=0;i<7;++i)for(size_t j=0;j<7;++j)for(size_t k=0;k<7;++k){int32_t a=alphas[k]>256?256:alphas[k];int32_t numerator=(int32_t)values[i]*(256-a)+(int32_t)values[j]*a;TEST_ASSERT_EQUAL(numerator/256,fixed_filter_step(values[i],values[j],alphas[k]));}}
int main(void){UNITY_BEGIN();RUN_TEST(test_init_and_reset_validation);RUN_TEST(test_q8_proportional_and_signed_truncation);RUN_TEST(test_integral_antiwindup_and_recovery);RUN_TEST(test_derivative_and_wide_arithmetic);RUN_TEST(test_integral_limits);RUN_TEST(test_filter_endpoints_and_extremes);RUN_TEST(test_filter_independent_integer_oracle);return UNITY_END();}
