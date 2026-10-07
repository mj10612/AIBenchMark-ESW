/* AIBENCHMARK_ESW_CANARY_V1_tier3_spi_flash */
#include "unity.h"
#include "spi_flash.h"
#include <string.h>
static spi_flash_t d;static int calls, fail_at, busy, status_calls, programs, erases, enables;static uint32_t addresses[4];static size_t sizes[4];static uint8_t payloads[4][256];static int wel;
static int transaction(void *ctx,const uint8_t *tx,size_t n,uint8_t *rx,size_t rn){
 (void)ctx;++calls;if(calls==fail_at)return -1;TEST_ASSERT_TRUE(n>0);
 if(tx[0]==0x9F){TEST_ASSERT_EQUAL_UINT(1,n);TEST_ASSERT_EQUAL_UINT(3,rn);rx[0]=0xEF;rx[1]=0x40;rx[2]=0x16;}
 else if(tx[0]==0x05){TEST_ASSERT_EQUAL_UINT(1,n);TEST_ASSERT_EQUAL_UINT(1,rn);++status_calls;rx[0]=busy>0?1:0;if(busy>0)--busy;}
 else if(tx[0]==0x06){TEST_ASSERT_EQUAL_UINT(1,n);TEST_ASSERT_EQUAL_UINT(0,rn);wel=1;++enables;}
 else if(tx[0]==0x02){TEST_ASSERT_TRUE(wel);wel=0;TEST_ASSERT_TRUE(n>4&&n<=260);TEST_ASSERT_TRUE(programs<4);addresses[programs]=((uint32_t)tx[1]<<16)|((uint32_t)tx[2]<<8)|tx[3];sizes[programs]=n-4;memcpy(payloads[programs],tx+4,n-4);++programs;}
 else if(tx[0]==0x20){TEST_ASSERT_TRUE(wel);wel=0;TEST_ASSERT_EQUAL_UINT(4,n);addresses[0]=((uint32_t)tx[1]<<16)|((uint32_t)tx[2]<<8)|tx[3];++erases;}
 else TEST_FAIL_MESSAGE("Unknown opcode");return 0;
}
static spi_hal_t hal={NULL,transaction};
void setUp(void){memset(&d,0,sizeof(d));calls=busy=status_calls=programs=erases=enables=wel=0;fail_at=-1;}
void tearDown(void){}
static void init(void){uint8_t id[3]={0};TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_init(&d,&hal,3,id));TEST_ASSERT_EQUAL_HEX8(0xEF,id[0]);calls=0;}
void test_jedec_and_validation(void){uint8_t id[3]={0xAA,0xBB,0xCC};TEST_ASSERT_EQUAL(FLASH_ARGUMENT,spi_flash_init(&d,&hal,0,id));TEST_ASSERT_EQUAL(0,calls);fail_at=1;TEST_ASSERT_EQUAL(FLASH_IO,spi_flash_init(&d,&hal,3,id));TEST_ASSERT_EQUAL_HEX8(0xAA,id[0]);TEST_ASSERT_FALSE(d.initialized);fail_at=-1;TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_init(&d,&hal,3,id));TEST_ASSERT_EQUAL_HEX8(0x16,id[2]);}
void test_page_split_big_endian_and_payload(void){uint8_t data[260];for(size_t i=0;i<260;++i)data[i]=(uint8_t)i;init();TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_program(&d,0x12FFFE,data,260));TEST_ASSERT_EQUAL(3,programs);TEST_ASSERT_EQUAL(3,enables);TEST_ASSERT_EQUAL_HEX32(0x12FFFE,addresses[0]);TEST_ASSERT_EQUAL_HEX32(0x130000,addresses[1]);TEST_ASSERT_EQUAL_HEX32(0x130100,addresses[2]);TEST_ASSERT_EQUAL_UINT(2,sizes[0]);TEST_ASSERT_EQUAL_UINT(256,sizes[1]);TEST_ASSERT_EQUAL_UINT(2,sizes[2]);TEST_ASSERT_EQUAL(0,memcmp(data,payloads[0],2));TEST_ASSERT_EQUAL(0,memcmp(data+2,payloads[1],256));TEST_ASSERT_EQUAL(0,memcmp(data+258,payloads[2],2));}
void test_busy_timeout_and_retry(void){uint8_t data=42;init();busy=3;TEST_ASSERT_EQUAL(FLASH_TIMEOUT,spi_flash_program(&d,0,&data,1));TEST_ASSERT_EQUAL(3,status_calls);TEST_ASSERT_EQUAL(0,programs);busy=2;status_calls=0;TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_program(&d,0,&data,1));TEST_ASSERT_EQUAL(1,programs);}
void test_erase_alignment_and_address_range(void){uint8_t data[2]={1,2};init();TEST_ASSERT_EQUAL(FLASH_ARGUMENT,spi_flash_erase(&d,1));TEST_ASSERT_EQUAL(FLASH_ARGUMENT,spi_flash_program(&d,0xFFFFFF,data,2));TEST_ASSERT_EQUAL(FLASH_ARGUMENT,spi_flash_program(&d,0x1000000,data,0));TEST_ASSERT_EQUAL(0,calls);TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_erase(&d,0xABC000));TEST_ASSERT_EQUAL_HEX32(0xABC000,addresses[0]);TEST_ASSERT_EQUAL(1,erases);TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_program(&d,0xFFFFFF,data,1));}
void test_each_hal_error_is_propagated(void){uint8_t data=1;for(int failure=1;failure<=4;++failure){init();fail_at=failure;TEST_ASSERT_EQUAL(FLASH_IO,spi_flash_program(&d,0,&data,1));TEST_ASSERT_EQUAL(failure,calls);fail_at=-1;}init();fail_at=3;TEST_ASSERT_EQUAL(FLASH_IO,spi_flash_erase(&d,0));}
void test_noop_and_invalid_pointers(void){init();TEST_ASSERT_EQUAL(FLASH_OK,spi_flash_program(&d,0,NULL,0));TEST_ASSERT_EQUAL(0,calls);TEST_ASSERT_EQUAL(FLASH_ARGUMENT,spi_flash_program(&d,0,NULL,1));TEST_ASSERT_EQUAL(FLASH_ARGUMENT,spi_flash_erase(NULL,0));TEST_ASSERT_EQUAL(0,calls);}
int main(void){UNITY_BEGIN();RUN_TEST(test_jedec_and_validation);RUN_TEST(test_page_split_big_endian_and_payload);RUN_TEST(test_busy_timeout_and_retry);RUN_TEST(test_erase_alignment_and_address_range);RUN_TEST(test_each_hal_error_is_propagated);RUN_TEST(test_noop_and_invalid_pointers);return UNITY_END();}
