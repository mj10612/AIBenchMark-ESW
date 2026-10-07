<!-- AIBENCHMARK_ESW_CANARY_V1_tier4_bitmask_fix -->
# Task: Fix W1C Register & Priority Masking Bugs in Interrupt Controller

You are debugging firmware in an embedded system. The interrupt manager in `src/irq_manager.c` contains three critical bugs reported by the hardware team:

## Bug Reports:
1. **Accidental Clearing of Pending Interrupts**:
   - `ctrl->status_reg` is a hardware **Write-1-to-Clear (W1C)** register.
   - When an interrupt is acknowledged, only that IRQ's bit should be cleared.
   - The current implementation reads `status_reg`, inverts the target bit, and writes back (`ctrl->status_reg &= ~(1U << irq_num)`). Because writing `1` clears bits, this inadvertently writes `1` to all other currently active IRQ flags, clearing them before they can be handled!
2. **Priority Bit Corruption**:
   - In `irq_set_priority`, when changing the priority of an IRQ that already had a non-zero priority, the old priority bits are not cleared before the new bits are set. This corrupts the priority value.
3. **Missing Bounds Checks**:
   - `irq_num` must be strictly `< MAX_IRQS` (`8`). If `irq_num >= MAX_IRQS`, operations must return `false` without touching registers.
   - `priority` must be `<= PRIORITY_MASK` (`7`).

Fix these bugs in `src/irq_manager.c` while preserving all function signatures.
