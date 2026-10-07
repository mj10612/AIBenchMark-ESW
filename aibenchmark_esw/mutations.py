"""Reviewed, deterministic task faults; all compilation uses disposable workspaces.

These mutations check suite adequacy, not model quality. A compilation error or
an incomplete execution is an invalid fixture, never evidence of a killed fault.
"""

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import math
import re
from typing import List, Optional, Tuple

from aibenchmark_esw.provenance import collect_run_metadata
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.c_source import mask_noncode

GENERATOR_VERSION = "c-operators-v1"


@dataclass(frozen=True)
class Mutation:
    name: str
    description: str
    replacements: Tuple[Tuple[str, str], ...]
    offset: Optional[int] = None

    def apply(self, source):
        if self.offset is not None:
            before, after = self.replacements[0]
            if source[self.offset:self.offset + len(before)] != before:
                raise ValueError(f"Mutation {self.name}: source offset no longer matches")
            return source[:self.offset] + after + source[self.offset + len(before):]
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
        _mutation("narrow-length", "Lengths 65535, 65536 and 65537 cannot narrow to uint16_t.",
                  "i < length", "i < (uint16_t)length"),
    ),
    "tier1_ring_buffer": (
        _mutation("overwrite-full", "A full buffer rejects a push and preserves unread data.",
                  "count >= rb->capacity", "count > rb->capacity"),
        _mutation("early-head-wrap", "Head rollover must preserve FIFO and distinguish full from empty.",
                  "head == (2U * rb->capacity) - 1U", "head == rb->capacity - 1U"),
        _mutation("invalid-upper-capacity", "Every capacity above SIZE_MAX/2 disables the buffer.",
                  "capacity <= SIZE_MAX / 2U", "capacity != SIZE_MAX"),
        _mutation("narrow-index", "Capacity 300 requires indices wider than eight bits.",
                  "size_t head = rb->head;", "uint8_t head = (uint8_t)rb->head;"),
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
        _mutation("late-hold", "HOLD fires exactly at the documented confirmed-press duration.",
                  "fsm->press_duration >= fsm->hold_threshold", "fsm->press_duration > fsm->hold_threshold"),
        _mutation("only-one-is-pressed", "All nonzero raw input levels are active.",
                  "raw_pin_level != 0U", "raw_pin_level == 1U"),
        _mutation("zero-hold-enabled", "A zero HOLD threshold permanently disables HOLD.",
                  "(fsm->hold_threshold > 0U) &&", ""),
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
        _mutation("invalid-side-effects", "Rejected setters preserve both register sentinels.",
                  "if (ctrl == NULL || irq_num >= MAX_IRQS || priority > PRIORITY_MASK) {",
                  "if (ctrl == NULL || irq_num >= MAX_IRQS || priority > PRIORITY_MASK) { if (ctrl) { ctrl->status_reg = 0; ctrl->priority_reg = 0; }"),
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
    "tier4_dma_buffer": (
        _mutation("steal-reader", "A DMA completion cannot steal an application-owned half.",
                  "bool ok = b->owner[half] == DMA_OWNED;", "bool ok = true;"),
        _mutation("skip-invalidation", "DMA writes require cache invalidation before publication.",
                  "b->hal.invalidate(b->hal.ctx, b->storage + half * b->half_size, b->half_size);", ""),
        _mutation("skip-guard", "ISR transitions and cache operations require critical sections.",
                  "b->hal.enter(b->hal.ctx);", ""),
        _mutation("misaligned-storage", "The DMA base must be four-byte aligned.",
                  "(uintptr_t)storage % 4U != 0", "false"),
    ),
    "tier3_spi_flash": (
        _mutation("cross-page", "Programs split at actual 256-byte page boundaries.",
                  "256U - (address & 255U)", "256U"),
        _mutation("little-endian-address", "NOR commands serialize 24-bit addresses most-significant byte first.",
                  "tx[1] = (uint8_t)(address >> 16);", "tx[1] = (uint8_t)address;"),
        _mutation("ignore-busy", "Busy status must consume the bounded poll budget.",
                  "if ((status & 1U) == 0) return FLASH_OK;", "return FLASH_OK;"),
        _mutation("ignore-wren-error", "WREN failures stop the transaction sequence.",
                  "if (status != FLASH_OK) return status;\n        uint8_t tx[260];", "uint8_t tx[260];"),
    ),
    "tier4_uart_frame_fix": (
        _mutation("skip-checksum", "Only verified frames publish caller output.",
                  "if (byte != checksum)", "if (0)"),
        _mutation("skip-reset", "Errors invoke peripheral recovery exactly once.",
                  "hal->reset(hal->ctx);", ""),
        _mutation("reset-time-budget", "One poll budget covers the whole frame.",
                  "if (rc == 0) continue;", "if (rc == 0) { poll = 0; continue; }"),
    ),
    "tier2_fixed_control": (
        _mutation("integral-windup", "Saturated output must reject outward integral growth.",
                  "if (!windup) p->integral", "if (true) p->integral"),
        _mutation("narrow-pid-product", "PID gain times integral requires signed 64-bit arithmetic.",
                  "(int64_t)p->ki * accumulated", "(int16_t)(p->ki * accumulated)"),
        _mutation("negative-filter-rounding", "Filter fractions truncate toward zero.",
                  "numerator / 256);", "numerator >> 8);"),
    ),
    "tier3_flash_update": (
        _mutation("erase-active-slot", "Update operations only touch the inactive slot.",
                  "(uint8_t)(1U - active_slot)", "active_slot"),
        _mutation("skip-crc-verification", "Corrupt read-back cannot reach commit.",
                  "if (u->verified != u->crc)", "if (false)"),
        _mutation("early-commit", "Commit occurs only after all read-back chunks verify.",
                  "u->state = UPDATE_VERIFY;", "u->state = UPDATE_COMMIT;"),
        _mutation("ignore-hal-errors", "Every failed HAL operation transitions to ERROR.",
                  "if (rc != 0) { u->state = UPDATE_ERROR; return UPDATE_IO; }", ""),
    ),
}


def generate_mutations(source, max_mutants=20):
    """Deterministic single-location probes; comments/literals/inactive C are skipped.

    This intentionally small lexical generator does not prove equivalence or C
    validity. Compilation failures, crashes and timeouts remain invalid probes.
    """
    if isinstance(max_mutants, bool) or not isinstance(max_mutants, int) or max_mutants < 1:
        raise ValueError("max_mutants must be a positive integer")
    # Phase-2 splices can change lexer offsets. Reject those sources until a
    # preprocessor-aware generator is used rather than mutating the wrong byte.
    if re.search(r"\\\r?\n", source):
        return ()
    masked = mask_noncode(source)
    masked = re.sub(r"(?m)^\s*#[^\r\n]*", lambda m: " " * len(m.group()), masked)
    operators = {"<=": "<", ">=": ">", "==": "!=", "!=": "==", "<": "<=", ">": ">=", "+": "-", "-": "+"}
    pattern = r"<=|>=|==|!=|(?<![+\-<>])(?:[<>+\-])(?![+\->=])|\b(?:0[xX][0-9A-Fa-f]+|[0-9]+)[uUlL]*\b"
    locations = []
    for match in re.finditer(pattern, masked):
        before = source[match.start():match.end()]
        if before in operators:
            after = operators[before]
            kind = "operator"
        else:
            number_match = re.match(r"(?:0[xX][0-9A-Fa-f]+|[0-9]+)", before)
            assert number_match is not None
            number = number_match.group()
            value = int(number, 16 if number.lower().startswith("0x") else 10)
            after = str(value + 1) + before[len(number):]
            kind = "increment"
            locations.append((match.start(), before, str(value - 1) + before[len(number):], "decrement"))
        locations.append((match.start(), before, after, kind))
    for match in re.finditer(r"\b[A-Za-z_]\w*(?:\s*->\s*\w+)*\s*(==|!=)\s*NULL\b", masked):
        locations.append((match.start(), source[match.start():match.end()], "0" if match.group(1) == "==" else "1", "null"))
    for match in re.finditer(r"\bif\s*\([^{};]*?\)\s*return\b[^;{}]*;", masked):
        locations.append((match.start(), source[match.start():match.end()], ";", "return"))
    boundaries = {"INT16_MIN": "INT16_MAX", "INT16_MAX": "INT16_MIN", "INT32_MIN": "INT32_MAX",
                  "INT32_MAX": "INT32_MIN", "UINT16_MAX": "UINT8_MAX", "UINT32_MAX": "UINT16_MAX", "SIZE_MAX": "0U"}
    for match in re.finditer(r"\b(?:" + "|".join(boundaries) + r")\b", masked):
        locations.append((match.start(), match.group(), boundaries[match.group()], "boundary"))
    probes: List[Mutation] = []
    for offset, before, after, kind in sorted(locations, key=lambda item: (item[0], item[3])):
        probes.append(Mutation(f"auto-{len(probes) + 1:04d}-{kind}",
                               f"{kind} at offset {offset}: {before} -> {after}",
                               ((before, after),), offset))
        if len(probes) >= max_mutants:
            break
    return tuple(probes)


def _evaluate_mutation(task, reference, mutation, executor):
    record = {"name": mutation.name, "description": mutation.description,
              "status": "invalid", "diagnostic": None}
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
    return record


def run_mutations(tasks, loader, executor=None, *, auto=False, max_mutants=20, jobs=1, min_score=0.0):
    """Return a JSON-serializable adequacy report; ``passed`` controls CLI/CI exit.

    Only fully executed assertion failures kill a reviewed mutant. Surviving,
    stale, noncompiling, or crashing fixtures fail the check. External tasks
    without reviewed mutations are explicitly reported as unsupported.
    """
    for name, value in (("jobs", jobs), ("max_mutants", max_mutants)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if isinstance(min_score, bool) or not isinstance(min_score, (float, int)) or not math.isfinite(min_score) or not 0 <= min_score <= 1:
        raise ValueError("min_score must be in [0, 1]")
    tasks = list(tasks)
    executor = executor or ExecutionSandbox()
    metadata = collect_run_metadata(tasks, executor)
    report = {key: metadata.get(key) for key in ("compiler", "evaluator_sha256", "source_revision")}
    report.update(tasks=[], passed=bool(tasks))
    if auto:
        report.update(generator_version=GENERATOR_VERSION,
                      automatic_settings={"max_mutants": max_mutants, "jobs": jobs, "min_score": min_score})
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
            if not cases and not auto:
                raise ValueError("No reviewed mutations are registered for this task")
            for mutation in cases:
                record = _evaluate_mutation(task, reference, mutation, executor)
                row["mutants"].append(record)
                row[record["status"]] += 1
            if auto:
                generated = generate_mutations(reference, max_mutants)
                with ThreadPoolExecutor(max_workers=jobs) as pool:
                    records = list(pool.map(lambda mutation: _evaluate_mutation(task, reference, mutation, executor), generated))
                counts = {status: sum(record["status"] == status for record in records)
                          for status in ("killed", "survived", "invalid")}
                valid = counts["killed"] + counts["survived"]
                score = counts["killed"] / valid if valid else None
                row["reviewed_supported"] = bool(cases)
                row["automatic"] = {**counts, "equivalent_suspect": 0, "score": score,
                                    "valid_mutants": valid, "mutants": records,
                                    "equivalence_policy": "Survivors remain survivors; equivalence is not inferred."}
                if min_score > 0 and (score is None or score < min_score):
                    report["passed"] = False
        except (OSError, ValueError) as error:
            row["invalid"] += 1
            row["diagnostic"] = str(error)
        if not row["reference_passed"] or row["survived"] or row["invalid"]:
            report["passed"] = False
    return report
