"""Reviewed, deterministic task faults; all compilation uses disposable workspaces.

These mutations check suite adequacy, not model quality. A compilation error or
an incomplete execution is an invalid fixture, never evidence of a killed fault.
"""

from dataclasses import dataclass
from typing import Tuple

from aibenchmark_esw.provenance import collect_run_metadata
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


@dataclass(frozen=True)
class Mutation:
    name: str
    description: str
    replacements: Tuple[Tuple[str, str], ...]

    def apply(self, source):
        for before, after in self.replacements:
            if before not in source:
                raise ValueError(f"Mutation {self.name}: source anchor no longer exists")
            source = source.replace(before, after)
        return source


def _mutation(name, description, before, after):
    return Mutation(name, description, ((before, after),))


MUTATIONS = {
    "tier1_crc16": (
        _mutation("discard-high-bit", "Bytes >= 128 must retain their high bit in the CRC.",
                  "(uint16_t)byte << 8", "(uint16_t)(byte & 0x7FU) << 8"),
        _mutation("wrong-polynomial", "The CCITT-FALSE polynomial is exactly 0x1021.",
                  "^ 0x1021U", "^ 0x1020U"),
    ),
    "tier1_ring_buffer": (
        _mutation("overwrite-full", "A full buffer rejects a push and preserves unread data.",
                  "count >= rb->capacity", "count > rb->capacity"),
        _mutation("early-head-wrap", "Head rollover must preserve FIFO and distinguish full from empty.",
                  "head == (2U * rb->capacity) - 1U", "head == rb->capacity - 1U"),
    ),
    "tier1_q15_math": (
        _mutation("positive-wrap", "Positive saturation cannot narrow an out-of-range value.",
                  "return INT16_MAX;", "return (int16_t)value;"),
        _mutation("negative-rounding", "Negative fractional products truncate toward zero.",
                  "product / INT32_C(32768)", "product >> 15"),
        _mutation("narrow-product", "The product must remain wide until scaling and saturation.",
                  "int32_t product = (int32_t)a * (int32_t)b;",
                  "int32_t product = (int16_t)((int32_t)a * (int32_t)b);"),
    ),
    "tier2_debounce_fsm": (
        _mutation("repeated-hold", "One continuous press emits HOLD exactly once.",
                  "(fsm->press_duration >= fsm->hold_threshold) && \n                    (!fsm->hold_emitted)",
                  "(fsm->press_duration >= fsm->hold_threshold)"),
        _mutation("premature-press", "Press confirmation needs the complete debounce interval.",
                  "fsm->debounce_counter = 1;", "fsm->debounce_counter = fsm->debounce_threshold;"),
    ),
    "tier2_tick_timer": (
        _mutation("naive-deadline", "Deadline comparisons must work across uint32 rollover.",
                  "elapsed < timer->interval", "now < timer->started_at + timer->interval"),
        _mutation("phase-drift", "Periodic timers preserve phase after delayed polling.",
                  "timer->started_at += count * timer->interval;", "timer->started_at = now;"),
        _mutation("dropped-expirations", "A delayed poll returns every complete interval.",
                  "count = elapsed / timer->interval;", "count = 1;"),
    ),
    "tier3_i2c_sensor": (
        _mutation("ignored-config-error", "Initialization propagates CONFIG write failures.",
                  "if (bus->write(bus->dev_addr, SENSOR_REG_CONFIG, &cfg_val, 1) != I2C_STATUS_OK) {\n        return SENSOR_ERR_COMM_FAIL;\n    }",
                  "bus->write(bus->dev_addr, SENSOR_REG_CONFIG, &cfg_val, 1);"),
        _mutation("ignored-read-error", "Temperature reads propagate non-OK bus statuses.",
                  "if (dev->bus->read(dev->bus->dev_addr, SENSOR_REG_TEMP_MSB, raw_data, 2) != I2C_STATUS_OK) {\n        return SENSOR_ERR_COMM_FAIL;\n    }",
                  "dev->bus->read(dev->bus->dev_addr, SENSOR_REG_TEMP_MSB, raw_data, 2);"),
        _mutation("stale-ready-state", "Failed re-initialization invalidates the old ready device.",
                  "    dev->is_initialized = false;\n    dev->bus = NULL;\n", ""),
    ),
    "tier4_bitmask_fix": (
        _mutation("w1c-read-modify-write", "Acknowledging one IRQ writes only its W1C bit.",
                  "ctrl->status_reg = (1U << irq_num);", "ctrl->status_reg &= ~(1U << irq_num);"),
        _mutation("uncleared-priority", "Changing a priority must clear the previous value.",
                  "ctrl->priority_reg &= ~mask;", "(void)mask;"),
    ),
    "tier2_cobs_codec": (
        _mutation("block-length-off-by-one", "Code bytes include themselves in each block length.",
                  "dst[output++] = (uint8_t)(block + 1);", "dst[output++] = (uint8_t)block;"),
        _mutation("full-block-zero", "A 255-code block never inserts an implicit zero.",
                  "code != 255 && input < src_len", "input < src_len"),
        _mutation("trailing-zero", "A final short block does not add a decoded zero.",
                  "code != 255 && input < src_len", "code != 255"),
        _mutation("ignored-encode-capacity", "A nonempty destination can still be too small for encoding.",
                  "if (block + 1 > dst_capacity - output) return COBS_NO_SPACE;",
                  "if (dst_capacity == 0) return COBS_NO_SPACE;"),
        _mutation("ignored-decode-capacity", "Decoding respects payload and inserted-zero capacity.",
                  "if (count > dst_capacity - output) return COBS_NO_SPACE;", ""),
    ),
}


def run_mutations(tasks, loader, executor=None):
    """Return a JSON-serializable adequacy report; ``passed`` controls CLI/CI exit.

    Only fully executed assertion failures kill a reviewed mutant. Surviving,
    stale, noncompiling, or crashing fixtures fail the check. External tasks
    without reviewed mutations are explicitly reported as unsupported.
    """
    tasks = list(tasks)
    executor = executor or ExecutionSandbox()
    metadata = collect_run_metadata(tasks, executor)
    report = {key: metadata.get(key) for key in ("compiler", "evaluator_sha256", "source_revision")}
    report.update(tasks=[], passed=bool(tasks))
    for task in tasks:
        row = {"task_id": task.id, "reference_passed": False,
               "killed": 0, "survived": 0, "invalid": 0, "mutants": []}
        report["tasks"].append(row)
        try:
            reference = loader.get_reference_solution(task.id)
            if not reference:
                raise ValueError("Reference implementation is missing")
            compiled, result = executor.compile_and_test(task, reference)
            try:
                row["reference_passed"] = bool(compiled.success and result.completed and result.passed)
                if not row["reference_passed"]:
                    raise ValueError("Reference validation failed: " + (result.output or compiled.output))
            finally:
                compiled.cleanup()
            cases = MUTATIONS.get(task.id, ())
            if not cases:
                raise ValueError("No reviewed mutations are registered for this task")
            for mutation in cases:
                record = {"name": mutation.name, "description": mutation.description,
                          "status": "invalid", "diagnostic": None}
                row["mutants"].append(record)
                try:
                    candidate = mutation.apply(reference)
                    if candidate == reference:
                        raise ValueError("Mutation did not change the reference")
                    compiled, result = executor.compile_and_test(task, candidate)
                    try:
                        if not compiled.success or not result.completed:
                            record["diagnostic"] = result.output or compiled.output
                        elif result.passed:
                            record["status"] = "survived"
                        elif result.failed_tests > 0:
                            record["status"] = "killed"
                        else:
                            record["diagnostic"] = "Suite did not report an assertion failure"
                    finally:
                        compiled.cleanup()
                except (OSError, ValueError) as error:
                    record["diagnostic"] = str(error)
                row[record["status"]] += 1
        except (OSError, ValueError) as error:
            row["invalid"] += 1
            row["diagnostic"] = str(error)
        if not row["reference_passed"] or row["survived"] or row["invalid"]:
            report["passed"] = False
    return report
