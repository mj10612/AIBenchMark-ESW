# Task authoring, held-out suites, and contamination controls

The bundled dataset has 13 tasks, 113 Unity cases, and 47 mandatory reviewed
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
the public source tree. The `crc-polynomial-v1` authoring transform chooses a
deterministic odd 16-bit CRC polynomial from SHA-256 of version, seed, and task
ID; it updates the CRC implementation, independent bit oracle, fixed vectors,
header text and prompt. Only `tier1_crc16` changes algorithm parameters. Other
selected tasks retain their contracts and record the seed in task.json.

Reports record `variant_version`, `variant_seed`, `variant_parameters`, and the
actual transformed task hashes. Different seeds are distinct evaluation
conditions and must not be combined silently. Seeds do not make a task private;
publish or retain them for reproduction. CRC variants are not CCITT-FALSE and
must be described by their recorded polynomial.

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

When combining overlays with a seed, author the private CRC oracle for the
recorded polynomial; the user-owned overlay is applied after the public variant
transform and is never silently rewritten. `reference_similarity(candidate,
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
