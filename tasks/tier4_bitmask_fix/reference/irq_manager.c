/* AIBENCHMARK_ESW_CANARY_V1_tier4_bitmask_fix */
#include "irq_manager.h"
#include <stddef.h>

void irq_init(irq_controller_t* ctrl) {
    if (ctrl != NULL) {
        ctrl->status_reg = 0;
        ctrl->priority_reg = 0;
    }
}

bool irq_clear_pending(irq_controller_t* ctrl, uint8_t irq_num) {
    if (ctrl == NULL || irq_num >= MAX_IRQS) {
        return false;
    }
    /* W1C register: Write 1 to only the target bit to clear it */
    ctrl->status_reg = (1U << irq_num);
    return true;
}

bool irq_set_priority(irq_controller_t* ctrl, uint8_t irq_num, uint8_t priority) {
    if (ctrl == NULL || irq_num >= MAX_IRQS || priority > PRIORITY_MASK) {
        return false;
    }
    uint32_t shift = (uint32_t)irq_num * 4U;
    uint32_t mask = (uint32_t)PRIORITY_MASK << shift;
    /* Clear old priority bits first */
    ctrl->priority_reg &= ~mask;
    /* Set new priority bits */
    ctrl->priority_reg |= ((uint32_t)priority << shift);
    return true;
}

uint8_t irq_get_priority(const irq_controller_t* ctrl, uint8_t irq_num) {
    if (ctrl == NULL || irq_num >= MAX_IRQS) {
        return 0;
    }
    uint32_t shift = (uint32_t)irq_num * 4U;
    return (uint8_t)((ctrl->priority_reg >> shift) & PRIORITY_MASK);
}
