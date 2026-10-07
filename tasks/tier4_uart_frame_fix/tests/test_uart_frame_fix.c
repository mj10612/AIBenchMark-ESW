/* AIBENCHMARK_ESW_CANARY_V1_tier4_uart_frame_fix */
#include "unity.h"
#include "uart_frame_fix.h"
#include <string.h>
static uint8_t stream[80];static size_t size,at;static int calls,waits,fail_at,resets;static uint8_t out[32];static size_t length;
static int read_byte(void *c,uint8_t *p){(void)c;++calls;if(calls==fail_at)return -1;if(waits>0){--waits;return 0;}if(at==size)return 0;*p=stream[at++];return 1;}
static void reset(void *c){(void)c;++resets;}
static uart_hal_t hal={NULL,read_byte,reset};
static void frame(size_t n){stream[0]=0xA5;stream[1]=(uint8_t)n;uint8_t crc=(uint8_t)n;for(size_t i=0;i<n;++i){stream[2+i]=(uint8_t)(i*13U+5U);crc^=stream[2+i];}stream[2+n]=crc;size=3+n;}
void setUp(void){memset(out,0xCC,sizeof(out));at=size=calls=waits=resets=0;fail_at=-1;length=99;}
void tearDown(void){}
void test_valid_frame_and_exact_budget(void){frame(3);TEST_ASSERT_EQUAL(UART_OK,uart_receive(&hal,out,32,&length,6));TEST_ASSERT_EQUAL_UINT(3,length);TEST_ASSERT_EQUAL(0,memcmp(stream+2,out,3));TEST_ASSERT_EQUAL(0,resets);TEST_ASSERT_EQUAL(6,calls);}
void test_timeout_budget_is_for_whole_frame(void){frame(3);waits=2;TEST_ASSERT_EQUAL(UART_TIMEOUT,uart_receive(&hal,out,32,&length,7));TEST_ASSERT_EQUAL(7,calls);TEST_ASSERT_EQUAL(1,resets);TEST_ASSERT_EQUAL_UINT(99,length);for(size_t i=0;i<32;++i)TEST_ASSERT_EQUAL_HEX8(0xCC,out[i]);}
void test_bad_checksum_preserves_output(void){frame(4);stream[size-1]^=1;TEST_ASSERT_EQUAL(UART_FRAME,uart_receive(&hal,out,32,&length,20));TEST_ASSERT_EQUAL(1,resets);TEST_ASSERT_EQUAL_UINT(99,length);TEST_ASSERT_EQUAL_HEX8(0xCC,out[0]);}
void test_io_error_then_recovery(void){frame(2);fail_at=4;TEST_ASSERT_EQUAL(UART_IO,uart_receive(&hal,out,32,&length,20));TEST_ASSERT_EQUAL(1,resets);TEST_ASSERT_EQUAL_UINT(99,length);fail_at=-1;at=0;calls=0;TEST_ASSERT_EQUAL(UART_OK,uart_receive(&hal,out,32,&length,5));TEST_ASSERT_EQUAL_UINT(2,length);}
void test_frame_length_and_capacity(void){frame(0);TEST_ASSERT_EQUAL(UART_FRAME,uart_receive(&hal,out,32,&length,10));TEST_ASSERT_EQUAL(1,resets);at=0;resets=0;frame(33);TEST_ASSERT_EQUAL(UART_FRAME,uart_receive(&hal,out,32,&length,40));TEST_ASSERT_EQUAL(1,resets);at=0;frame(4);TEST_ASSERT_EQUAL(UART_SPACE,uart_receive(&hal,out,3,&length,10));TEST_ASSERT_EQUAL_UINT(99,length);}
void test_sync_noise_and_max_frame(void){frame(32);memmove(stream+2,stream,size);stream[0]=0;stream[1]=0xFE;size+=2;TEST_ASSERT_EQUAL(UART_OK,uart_receive(&hal,out,32,&length,37));TEST_ASSERT_EQUAL_UINT(32,length);TEST_ASSERT_EQUAL(0,memcmp(stream+4,out,32));}
void test_invalid_arguments_do_not_touch_hal(void){TEST_ASSERT_EQUAL(UART_ARGUMENT,uart_receive(&hal,out,32,&length,0));TEST_ASSERT_EQUAL(UART_ARGUMENT,uart_receive(NULL,out,32,&length,10));TEST_ASSERT_EQUAL(UART_ARGUMENT,uart_receive(&hal,NULL,32,&length,10));uart_hal_t bad=hal;bad.reset=NULL;TEST_ASSERT_EQUAL(UART_ARGUMENT,uart_receive(&bad,out,32,&length,10));TEST_ASSERT_EQUAL(0,calls);TEST_ASSERT_EQUAL(0,resets);TEST_ASSERT_EQUAL_UINT(99,length);}
int main(void){UNITY_BEGIN();RUN_TEST(test_valid_frame_and_exact_budget);RUN_TEST(test_timeout_budget_is_for_whole_frame);RUN_TEST(test_bad_checksum_preserves_output);RUN_TEST(test_io_error_then_recovery);RUN_TEST(test_frame_length_and_capacity);RUN_TEST(test_sync_noise_and_max_frame);RUN_TEST(test_invalid_arguments_do_not_touch_hal);return UNITY_END();}
