/* AIBENCHMARK_ESW_CANARY_V1_tier4_dma_buffer */
#include "unity.h"
#include "dma_buffer.h"
#include <string.h>
static union { uint32_t align; uint8_t bytes[16]; } mem;
static dma_buffer_t b;
static int depth, enters, invalidates, cleans;
static uint8_t *last; static size_t last_n;
static void enter(void *c){(void)c;TEST_ASSERT_EQUAL(0,depth);++depth;++enters;}
static void leave(void *c){(void)c;TEST_ASSERT_EQUAL(1,depth);--depth;}
static void invalidate(void *c,uint8_t *p,size_t n){(void)c;TEST_ASSERT_EQUAL(1,depth);++invalidates;last=p;last_n=n;}
static void clean(void *c,uint8_t *p,size_t n){(void)c;TEST_ASSERT_EQUAL(1,depth);++cleans;last=p;last_n=n;}
static dma_hal_t hal={NULL,enter,leave,invalidate,clean};
void setUp(void){memset(&b,0,sizeof(b));depth=enters=invalidates=cleans=0;}
void tearDown(void){TEST_ASSERT_EQUAL(0,depth);}
void test_init_validation(void){
 TEST_ASSERT_FALSE(dma_buffer_init(NULL,mem.bytes,16,&hal));
 TEST_ASSERT_FALSE(dma_buffer_init(&b,mem.bytes+1,8,&hal));
 TEST_ASSERT_FALSE(dma_buffer_init(&b,mem.bytes,6,&hal));
 TEST_ASSERT_FALSE(dma_buffer_init(&b,mem.bytes,0,&hal));
 TEST_ASSERT_FALSE(dma_buffer_init(&b,NULL,16,&hal));
 dma_hal_t bad=hal;bad.leave=NULL;TEST_ASSERT_FALSE(dma_buffer_init(&b,mem.bytes,16,&bad));
 TEST_ASSERT_TRUE(dma_buffer_init(&b,mem.bytes,16,&hal));TEST_ASSERT_EQUAL_UINT(8,b.half_size);
}
void test_half_transfer_and_cache_order(void){
 const uint8_t *p=NULL;size_t n=0;TEST_ASSERT_TRUE(dma_buffer_init(&b,mem.bytes,16,&hal));
 TEST_ASSERT_FALSE(dma_buffer_acquire(&b,0,&p,&n));
 TEST_ASSERT_TRUE(dma_buffer_complete(&b,0));TEST_ASSERT_EQUAL(1,invalidates);TEST_ASSERT_TRUE(last==mem.bytes);TEST_ASSERT_EQUAL_UINT(8,last_n);
 TEST_ASSERT_TRUE(dma_buffer_acquire(&b,0,&p,&n));TEST_ASSERT_TRUE(p==mem.bytes);TEST_ASSERT_EQUAL_UINT(8,n);TEST_ASSERT_EQUAL(DMA_READING,b.owner[0]);
 TEST_ASSERT_TRUE(dma_buffer_complete(&b,1));TEST_ASSERT_EQUAL(DMA_READY,b.owner[1]);
 TEST_ASSERT_TRUE(dma_buffer_release(&b,0));TEST_ASSERT_EQUAL(1,cleans);TEST_ASSERT_EQUAL(DMA_OWNED,b.owner[0]);TEST_ASSERT_TRUE(last==mem.bytes);
 TEST_ASSERT_TRUE(dma_buffer_acquire(&b,1,&p,&n));TEST_ASSERT_TRUE(p==mem.bytes+8);TEST_ASSERT_TRUE(dma_buffer_release(&b,1));
}
void test_overrun_does_not_steal_reader(void){
 const uint8_t *p=NULL;size_t n=0;TEST_ASSERT_TRUE(dma_buffer_init(&b,mem.bytes,16,&hal));
 TEST_ASSERT_TRUE(dma_buffer_complete(&b,0));TEST_ASSERT_FALSE(dma_buffer_complete(&b,0));TEST_ASSERT_EQUAL_UINT(1,b.overruns);
 TEST_ASSERT_TRUE(dma_buffer_acquire(&b,0,&p,&n));TEST_ASSERT_FALSE(dma_buffer_complete(&b,0));TEST_ASSERT_EQUAL(DMA_READING,b.owner[0]);TEST_ASSERT_EQUAL_UINT(2,b.overruns);TEST_ASSERT_EQUAL(1,invalidates);
 TEST_ASSERT_FALSE(dma_buffer_acquire(&b,0,&p,&n));TEST_ASSERT_TRUE(dma_buffer_release(&b,0));TEST_ASSERT_FALSE(dma_buffer_release(&b,0));
}
void test_invalid_calls_preserve_outputs(void){
 const uint8_t *p=mem.bytes+3;size_t n=99;TEST_ASSERT_TRUE(dma_buffer_init(&b,mem.bytes,16,&hal));
 TEST_ASSERT_FALSE(dma_buffer_complete(&b,2));TEST_ASSERT_FALSE(dma_buffer_acquire(&b,2,&p,&n));TEST_ASSERT_FALSE(dma_buffer_release(&b,2));
 TEST_ASSERT_FALSE(dma_buffer_acquire(&b,0,NULL,&n));TEST_ASSERT_FALSE(dma_buffer_acquire(NULL,0,&p,&n));
 TEST_ASSERT_TRUE(p==mem.bytes+3);TEST_ASSERT_EQUAL_UINT(99,n);TEST_ASSERT_EQUAL(0,enters);
}
void test_reinitialization_invalidates_stale_state(void){
 TEST_ASSERT_TRUE(dma_buffer_init(&b,mem.bytes,16,&hal));TEST_ASSERT_TRUE(dma_buffer_complete(&b,0));
 TEST_ASSERT_FALSE(dma_buffer_init(&b,mem.bytes+1,8,&hal));TEST_ASSERT_FALSE(dma_buffer_complete(&b,0));
}
int main(void){UNITY_BEGIN();RUN_TEST(test_init_validation);RUN_TEST(test_half_transfer_and_cache_order);RUN_TEST(test_overrun_does_not_steal_reader);RUN_TEST(test_invalid_calls_preserve_outputs);RUN_TEST(test_reinitialization_invalidates_stale_state);return UNITY_END();}
