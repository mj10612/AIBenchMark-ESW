# Task authoring, held-out suites, and contamination controls

The bundled dataset has 15 tasks, 150 Unity cases, and 66 mandatory reviewed
mutants. Its prompts, APIs, tests, starters, and references are public. A passing
result can reflect recall; these controls provide audit evidence, not a proof
that training contamination was absent.

Every bundled asset contains the task-specific string
`AIBENCHMARK_ESW_CANARY_V1_<task_id>`. Search training corpora for those exact
strings when auditing inclusion. The canary is public and deterministic; it
does not prevent retrieval, copying, or memorization. Task fingerprints include
the assets containing it.

Use an external `--tasks-root` for an independently authored dataset. Author each
task with a prompt, immutable API header, compiling starter, golden reference,
Unity suite, CMake fixture, and task.json. State invalid-argument behavior,
ownership, integer rounding, timing origin, callback failure semantics, and
resource measurement scope explicitly. Do not treat a host mock as device or
concurrency certification.

For example, the DMA task uses C11 `_Static_assert`, volatile ownership fields,
and HAL critical sections/cache hooks. TCC 0.9.27 accepts the C11 flag but lacks
the assertion syntax, so the reference uses a documented `__TINYC__` typedef
assertion fallback. HAL must prevent writes to application-owned halves and
provide platform memory barriers. Tests simulate serialized interrupt
interleavings, not arbitrary C threads. The flash-update task relies on an
atomic durable commit HAL; physical boot-record validity remains a deployment
requirement. SPI's maximum stack staging buffer is 260 bytes. Object RAM budgets
measure static data, not caller buffers or peak stack; MCU final linking must
account for runtime helpers, stack and alignment separately.

## Reproducible variants

`run --variant-seed INTEGER` prepares temporary assets without changing
original public files. The `task-parameters-v2` dispatcher records per-task
versions and exact parameters. Supported transforms are:

| Task | Task version | Valid domain and hooks |
| --- | --- | --- |
| `tier1_crc16` | `crc-polynomial-v1` | Odd 16-bit polynomial with bit 15 set; SHA-256 mapping and original CRC seed outputs are preserved. Implementation, oracle, vectors, header and prompt are updated. |
| `tier3_i2c_sensor` | `i2c-registers-v1` | Address `0x20..0x3F`; even temperature MSB register `0x10..0x2E`, adjacent LSB; CONFIG register `0x40..0x5F`; WHO_AM_I register `0x60..0x7F`; expected chip ID `0x80..0xFF`. |

I2C maps SHA-256 of `i2c-registers-v1:SEED:tier3_i2c_sensor`:
address is `0x20 + digest[0] % 32`, temperature MSB is
`0x10 + 2*(digest[1] % 16)`, CONFIG is `0x40 + digest[2] % 32`,
WHO_AM_I is `0x60 + digest[3] % 32`, and chip ID is
`0x80 + digest[4] % 128`. All register slots are distinct and the two-byte
read cannot wrap. Named header definitions and prompt hooks are checked
before rendering. The starter, reference and suite already consume those
header macros, so no unconstrained replacements of their source are needed.
Temperature conversion and CONFIG enable bit retain their original meaning.

Seeds 42 and 43 produce distinct contracts for both supported tasks. Repeat
`run --model baseline --tasks tier3_i2c_sensor --variant-seed 42` to reproduce
I2C parameters and effective task fingerprints; replacing 42 with 43 changes
them. Matching references pass and original hardcoded I2C register/chip-ID
values fail completed assertions. Relevant reviewed I2C faults remain killed.

Reports record `variant_version`, `variant_seed`, `variant_parameters`,
`variant_task_versions`, `unvaried_tasks`, and transformed task hashes.
Copied task.json records its per-task version, parameters and whether it was
varied. Unsupported tasks retain their functional contracts, are listed in
`unvaried_tasks`, and record seed identity only. With no seed or overlay,
original task objects/assets are used directly. Temporary copies live until
the authoring context exits; compile and replay within that context.

Different seeds or effective fingerprints are distinct evaluation conditions
and comparison/resume must reject incompatible inputs. The finite domains can
produce parameter collisions between seeds, so use recorded parameters and
fingerprints to identify the effective contract. Seeds do not make a task
private or prove absence of training contamination; retain or publish them
for reproduction. CRC variants are not CCITT-FALSE and must be described by
the recorded polynomial. UART, watchdog and other tasks remain unvaried.

The Python authoring API is:

```python
from aibenchmark_esw.task_variants import prepare_task_variants
with prepare_task_variants(tasks, variant_seed=42) as (prepared, evidence):
    # Evaluate prepared TaskConfig objects while their temporary paths exist.
    ...
```

## Private held-out suites

Keep private tests outside the published dataset and pass
`--heldout-tests PRIVATE_DIRECTORY`. Arrange overlays as
`PRIVATE_DIRECTORY/<selected_task_id>/tests/test_*.c`. A present task directory
replaces that task's entire tests directory, so each suite should own its main
and avoid duplicate entry points. Omitted selected tasks retain public tests;
unknown task IDs, empty suites and symlinks are rejected. Include any additional
test fixtures under that tests directory.

The overlay preserves public prompt and API headers, so private test bytes are
not sent as generation inputs. Reports record whether overlays were used and
the length-prefixed SHA-256 digest of private relative paths and bytes, plus
effective task fingerprints. Reports do not store those private test contents.
Retain the private assets securely to reproduce the digest; a hash alone cannot
reconstruct them. Candidate native execution has filesystem access, so this
workflow separates provider inputs but does not claim hostile-candidate secrecy
or isolation. Use an appropriate external containment boundary where needed.

Combining a seed with an overlay for either supported task (`tier1_crc16`
or `tier3_i2c_sensor`) is rejected: private expectations cannot be assumed to
match generated parameters. No user-owned suite is silently rewritten.
Overlays for unvaried tasks can still be combined with a seed.
`reference_similarity(candidate,
reference)` detects exact token equality ignoring comments/spacing while keeping
literals. Its warning is an audit signal, not a penalty or contamination proof.

## Mutation adequacy

`aibenchmark-esw mutations` validates the golden first and requires every
registered reviewed fault to fail a completed assertion suite. A compile
failure, timeout, crash, stale anchor or incomplete verdict is **invalid**, never
a kill. Public task additions need reviewed mutants and measured budgets before
being used for comparisons.

```bash
aibenchmark-esw mutations --auto --max-mutants 20 --jobs 2 --min-score 0.8
```

The optional `c-operators-v1` lexical generator changes one relational or
arithmetic token, increments/decrements an integer constant, swaps a named
boundary constant, drops a NULL comparison, or removes a guarded return. It masks comments, literals,
literal inactive branches and preprocessor directives. Sources with phase-2
line splices are skipped to avoid wrong byte offsets. Generation order is
deterministic; each task is capped and execution uses at most `--jobs` workers.
External tasks may opt into automatic probes without a reviewed registry.

Automatic score is killed/(killed+survived); invalid probes are counted separately
and excluded. `--min-score` is a fraction in [0,1]. A positive threshold fails
when no valid probes exist. Automatic invalid probes do not satisfy a reviewed
gate, and a reviewed invalid/surviving mutant always fails the command. Survivors
are not assumed equivalent: `equivalent_suspect` stays zero until an independent
equivalence review exists. The generator version and effective cap, parallelism
and threshold are recorded. This bounded lexical experiment is not a C AST
mutation engine or evidence that untested fault classes are covered.
