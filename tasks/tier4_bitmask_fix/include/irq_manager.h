/* AIBENCHMARK_ESW_CANARY_V1_tier4_bitmask_fix */
#ifndef IRQ_MANAGER_H
#define IRQ_MANAGER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_IRQS 8
#define PRIORITY_MASK 0x07U

typedef struct {
    /* Hardware register: Write-1-to-Clear (W1C).
       Writing a 1 clears that specific IRQ pending bit.
       Writing a 0 has no effect. */
    volatile uint32_t status_reg;

    /* Hardware register: Each IRQ has 4 bits of priority configuration
       (bits [2:0] store priority 0-7, bit [3] is reserved). */
    volatile uint32_t priority_reg;
} irq_controller_t;

void irq_init(irq_controller_t* ctrl);
bool irq_clear_pending(irq_controller_t* ctrl, uint8_t irq_num);
bool irq_set_priority(irq_controller_t* ctrl, uint8_t irq_num, uint8_t priority);
uint8_t irq_get_priority(const irq_controller_t* ctrl, uint8_t irq_num);

#ifdef __cplusplus
}
#endif

#endif /* IRQ_MANAGER_H */
