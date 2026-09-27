#include "irq_manager.h"

void irq_init(irq_controller_t* ctrl) {
    if (ctrl != 0) {
        ctrl->status_reg = 0;
        ctrl->priority_reg = 0;
    }
}

bool irq_clear_pending(irq_controller_t* ctrl, uint8_t irq_num) {
    /* BUG 1: Read-modify-write on W1C register clears other interrupts!
       BUG 2: Missing bounds check for irq_num >= MAX_IRQS */
    ctrl->status_reg &= ~(1U << irq_num);
    return true;
}

bool irq_set_priority(irq_controller_t* ctrl, uint8_t irq_num, uint8_t priority) {
    /* BUG 3: Does not clear old priority bits before setting new ones!
       BUG 4: Missing bounds check on irq_num and priority */
    uint32_t shift = (uint32_t)irq_num * 4U;
    ctrl->priority_reg |= ((uint32_t)priority << shift);
    return true;
}

uint8_t irq_get_priority(const irq_controller_t* ctrl, uint8_t irq_num) {
    if (ctrl == 0 || irq_num >= MAX_IRQS) {
        return 0;
    }
    uint32_t shift = (uint32_t)irq_num * 4U;
    return (uint8_t)((ctrl->priority_reg >> shift) & PRIORITY_MASK);
}
