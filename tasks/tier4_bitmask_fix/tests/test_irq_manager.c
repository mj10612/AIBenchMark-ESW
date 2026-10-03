#include "unity.h"
#include "irq_manager.h"

static irq_controller_t ctrl;

void setUp(void) {
    irq_init(&ctrl);
}

void tearDown(void) {}

void test_w1c_clears_only_target_bit(void) {
    /* In a W1C register, the firmware must write (1 << irq_num)
       and NOT invert/read-modify-write other bits. */
    ctrl.status_reg = 0x00;
    TEST_ASSERT_TRUE(irq_clear_pending(&ctrl, 3));
    TEST_ASSERT_EQUAL_HEX32((1U << 3), ctrl.status_reg);

    TEST_ASSERT_TRUE(irq_clear_pending(&ctrl, 0));
    TEST_ASSERT_EQUAL_HEX32((1U << 0), ctrl.status_reg);

    TEST_ASSERT_TRUE(irq_clear_pending(&ctrl, 7));
    TEST_ASSERT_EQUAL_HEX32((1U << 7), ctrl.status_reg);
}

void test_priority_overwrite_no_corruption(void) {
    /* Set IRQ 2 to priority 7 (0b111) */
    TEST_ASSERT_TRUE(irq_set_priority(&ctrl, 2, 7));
    TEST_ASSERT_EQUAL_UINT(7, irq_get_priority(&ctrl, 2));

    /* Overwrite IRQ 2 to priority 2 (0b010).
       If old bits are not cleared first, (7 | 2) would remain 7. */
    TEST_ASSERT_TRUE(irq_set_priority(&ctrl, 2, 2));
    TEST_ASSERT_EQUAL_UINT(2, irq_get_priority(&ctrl, 2));

    /* Overwrite to priority 0 */
    TEST_ASSERT_TRUE(irq_set_priority(&ctrl, 2, 0));
    TEST_ASSERT_EQUAL_UINT(0, irq_get_priority(&ctrl, 2));
}

void test_multiple_irq_priorities_independent(void) {
    /* Setting a low IRQ must preserve upper priorities and every reserved bit. */
    ctrl.priority_reg = UINT32_C(0xE8888888);
    TEST_ASSERT_TRUE(irq_set_priority(&ctrl, 0, 5));
    TEST_ASSERT_EQUAL_HEX32(UINT32_C(0xE888888D), ctrl.priority_reg);
    TEST_ASSERT_TRUE(irq_set_priority(&ctrl, 1, 3));
    TEST_ASSERT_TRUE(irq_set_priority(&ctrl, 7, 6));

    TEST_ASSERT_EQUAL_UINT(5, irq_get_priority(&ctrl, 0));
    TEST_ASSERT_EQUAL_UINT(3, irq_get_priority(&ctrl, 1));
    TEST_ASSERT_EQUAL_UINT(6, irq_get_priority(&ctrl, 7));

    /* Exercise all shifts, including IRQs 4-7 (16-28 bits). */
    for (uint8_t irq = 0; irq < MAX_IRQS; irq++) {
        uint32_t before = ctrl.priority_reg;
        uint32_t mask = (uint32_t)PRIORITY_MASK << ((uint32_t)irq * 4U);
        TEST_ASSERT_TRUE(irq_set_priority(&ctrl, irq, 7));
        TEST_ASSERT_EQUAL_UINT(7, irq_get_priority(&ctrl, irq));
        TEST_ASSERT_EQUAL_HEX32(before & ~mask, ctrl.priority_reg & ~mask);
        TEST_ASSERT_TRUE(irq_set_priority(&ctrl, irq, 0));
        TEST_ASSERT_EQUAL_HEX32(before & ~mask, ctrl.priority_reg);
    }
}

void test_out_of_bounds_handling(void) {
    TEST_ASSERT_FALSE(irq_clear_pending(&ctrl, MAX_IRQS));
    TEST_ASSERT_FALSE(irq_clear_pending(&ctrl, 100));

    TEST_ASSERT_FALSE(irq_set_priority(&ctrl, MAX_IRQS, 1));
    TEST_ASSERT_FALSE(irq_set_priority(&ctrl, 0, 8)); /* Priority > 7 */

    TEST_ASSERT_EQUAL_UINT(0, irq_get_priority(&ctrl, MAX_IRQS));
}

void test_null_pointer_safety(void) {
    TEST_ASSERT_FALSE(irq_clear_pending(NULL, 0));
    TEST_ASSERT_FALSE(irq_set_priority(NULL, 0, 1));
    TEST_ASSERT_EQUAL_UINT(0, irq_get_priority(NULL, 0));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_w1c_clears_only_target_bit);
    RUN_TEST(test_priority_overwrite_no_corruption);
    RUN_TEST(test_multiple_irq_priorities_independent);
    RUN_TEST(test_out_of_bounds_handling);
    RUN_TEST(test_null_pointer_safety);
    return UNITY_END();
}
