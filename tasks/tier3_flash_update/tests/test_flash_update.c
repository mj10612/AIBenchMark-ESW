/* AIBENCHMARK_ESW_CANARY_V1_tier3_flash_update */
#include "unity.h"
#include "flash_update.h"
#include <string.h>
static uint8_t slots[2][256],image[256];static uint8_t active;static int calls,fail_at,commits,corrupt;static flash_update_t u;
static size_t writes,reads,written_bytes,read_bytes,last_write,last_read,committed_length;
static uint16_t committed_crc;
static int erased(void *c,uint8_t s){(void)c;TEST_ASSERT_TRUE(s!=active);++calls;if(calls==fail_at)return -1;memset(slots[s],0xFF,256);return 0;}
static int written(void *c,uint8_t s,size_t o,const uint8_t *p,size_t n){(void)c;TEST_ASSERT_TRUE(s!=active);TEST_ASSERT_TRUE(n>0&&n<=64);TEST_ASSERT_TRUE(o+n<=256);++calls;if(calls==fail_at)return -1;memcpy(slots[s]+o,p,n);++writes;written_bytes+=n;last_write=n;return 0;}
static int readback(void *c,uint8_t s,size_t o,uint8_t *p,size_t n){(void)c;TEST_ASSERT_TRUE(s!=active);TEST_ASSERT_TRUE(n>0&&n<=64);TEST_ASSERT_TRUE(o+n<=256);++calls;if(calls==fail_at)return -1;memcpy(p,slots[s]+o,n);++reads;read_bytes+=n;last_read=n;if(corrupt)p[0]^=1;return 0;}
static int committed(void *c,uint8_t s,uint16_t crc,size_t n){(void)c;++calls;if(calls==fail_at)return -1;TEST_ASSERT_TRUE(n<=sizeof(image));TEST_ASSERT_EQUAL_HEX16(flash_update_crc(image,n),crc);TEST_ASSERT_EQUAL(0,memcmp(image,slots[s],n));committed_length=n;committed_crc=crc;active=s;++commits;return 0;}
static update_hal_t hal={NULL,erased,written,readback,committed};
void setUp(void){memset(slots,0xA5,sizeof(slots));for(size_t i=0;i<sizeof(image);++i)image[i]=(uint8_t)(i*17U);active=0;calls=commits=corrupt=0;writes=reads=written_bytes=read_bytes=last_write=last_read=committed_length=0;committed_crc=0;fail_at=-1;memset(&u,0,sizeof(u));}
void tearDown(void){}
static void finish(void){for(int i=0;i<20&&u.state!=UPDATE_DONE&&u.state!=UPDATE_ERROR;++i)TEST_ASSERT_EQUAL(UPDATE_OK,flash_update_step(&u));TEST_ASSERT_EQUAL(UPDATE_DONE,u.state);}
void test_crc_known_vector_and_null(void){const uint8_t v[]="123456789";TEST_ASSERT_EQUAL_HEX16(0x29B1,flash_update_crc(v,9));TEST_ASSERT_EQUAL_HEX16(0xFFFF,flash_update_crc(NULL,0));TEST_ASSERT_EQUAL_HEX16(0,flash_update_crc(NULL,1));}
void test_full_update_order_and_active_preservation(void){TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,0,image,130));TEST_ASSERT_EQUAL(UPDATE_ERASE,u.state);finish();TEST_ASSERT_EQUAL(1,active);TEST_ASSERT_EQUAL(1,commits);TEST_ASSERT_EQUAL(8,calls);for(size_t i=0;i<256;++i)TEST_ASSERT_EQUAL_HEX8(0xA5,slots[0][i]);TEST_ASSERT_EQUAL(UPDATE_OK,flash_update_step(&u));TEST_ASSERT_EQUAL(8,calls);}
void test_power_cut_after_every_phase_keeps_old_image(void){for(int cut=0;cut<8;++cut){setUp();TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,0,image,130));for(int i=0;i<cut;++i)TEST_ASSERT_EQUAL(UPDATE_OK,flash_update_step(&u));TEST_ASSERT_EQUAL(0,active);for(size_t i=0;i<256;++i)TEST_ASSERT_EQUAL_HEX8(0xA5,slots[0][i]);/* Lose all RAM; reboot derives active from durable HAL record. */memset(&u,0,sizeof(u));calls=0;TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,active,image,130));finish();TEST_ASSERT_EQUAL(1,active);}}
void test_corruption_never_commits(void){TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,0,image,130));corrupt=1;int rc=0;for(int i=0;i<20&&u.state!=UPDATE_ERROR;++i)rc=flash_update_step(&u);TEST_ASSERT_EQUAL(UPDATE_CRC,rc);TEST_ASSERT_EQUAL(0,active);TEST_ASSERT_EQUAL(0,commits);int before=calls;TEST_ASSERT_EQUAL(UPDATE_IO,flash_update_step(&u));TEST_ASSERT_EQUAL(before,calls);}
void test_error_at_every_hal_operation(void){for(int failure=1;failure<=8;++failure){setUp();TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,0,image,130));fail_at=failure;int rc=0;for(int i=0;i<20&&u.state!=UPDATE_ERROR;++i)rc=flash_update_step(&u);TEST_ASSERT_EQUAL(UPDATE_IO,rc);TEST_ASSERT_EQUAL(failure,calls);TEST_ASSERT_EQUAL(0,active);TEST_ASSERT_EQUAL(0,commits);}}
void test_bounds_reinit_and_second_slot(void){TEST_ASSERT_FALSE(flash_update_begin(&u,&hal,2,image,1));TEST_ASSERT_FALSE(flash_update_begin(&u,&hal,0,NULL,1));TEST_ASSERT_FALSE(flash_update_begin(&u,&hal,0,image,0));TEST_ASSERT_FALSE(flash_update_begin(&u,&hal,0,image,257));update_hal_t bad=hal;bad.commit=NULL;TEST_ASSERT_FALSE(flash_update_begin(&u,&bad,0,image,1));TEST_ASSERT_EQUAL(0,calls);active=1;TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,1,image,1));finish();TEST_ASSERT_EQUAL(0,active);TEST_ASSERT_FALSE(flash_update_begin(&u,&hal,0,image,0));TEST_ASSERT_EQUAL(UPDATE_ARGUMENT,flash_update_step(&u));}
void test_valid_lengths_cover_chunk_boundaries_and_maximum(void) {
    const size_t lengths[] = {63,64,65,127,128,129,131,255,256};
    for (size_t index = 0; index < sizeof(lengths)/sizeof(lengths[0]); ++index) {
        size_t length = lengths[index];
        size_t chunks = (length+63U)/64U;
        size_t final_chunk = (length-1U)%64U+1U;
        setUp();
        TEST_ASSERT_TRUE(flash_update_begin(&u,&hal,0,image,length));
        TEST_ASSERT_EQUAL(0,calls);
        finish();
        TEST_ASSERT_EQUAL(1,active);
        TEST_ASSERT_EQUAL(1,commits);
        TEST_ASSERT_EQUAL(chunks,writes);
        TEST_ASSERT_EQUAL(chunks,reads);
        TEST_ASSERT_EQUAL(2U+2U*chunks,calls);
        TEST_ASSERT_EQUAL(length,written_bytes);
        TEST_ASSERT_EQUAL(length,read_bytes);
        TEST_ASSERT_EQUAL(final_chunk,last_write);
        TEST_ASSERT_EQUAL(final_chunk,last_read);
        TEST_ASSERT_EQUAL(length,committed_length);
        TEST_ASSERT_EQUAL_HEX16(flash_update_crc(image,length),committed_crc);
        TEST_ASSERT_EQUAL(0,memcmp(image,slots[1],length));
        for (size_t i = 0; i < sizeof(slots[0]); ++i) TEST_ASSERT_EQUAL_HEX8(0xA5,slots[0][i]);
        TEST_ASSERT_EQUAL(UPDATE_OK,flash_update_step(&u));
        TEST_ASSERT_EQUAL(2U+2U*chunks,calls);
    }
}
int main(void){UNITY_BEGIN();RUN_TEST(test_crc_known_vector_and_null);RUN_TEST(test_full_update_order_and_active_preservation);RUN_TEST(test_power_cut_after_every_phase_keeps_old_image);RUN_TEST(test_corruption_never_commits);RUN_TEST(test_error_at_every_hal_operation);RUN_TEST(test_bounds_reinit_and_second_slot);RUN_TEST(test_valid_lengths_cover_chunk_boundaries_and_maximum);return UNITY_END();}
