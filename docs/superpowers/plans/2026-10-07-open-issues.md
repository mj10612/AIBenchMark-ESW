# Open GitHub Issues Implementation Plan

> **For agentic workers:** Implement independent work packages in parallel; use test-driven-development and systematic-debugging for behavioral changes. The coordinator owns shared CLI/model/provenance integration and final verification.

**Goal:** Resolve every open issue in the captured #92–#150 backlog, publish reviewed code, then comment and close each issue using concrete validation evidence.

**Architecture:** Preserve the dependency-free Python 3.9 core, shared C evaluation pipeline and portable schema-v2 reports. Separate runtime containment, report/export services, dataset tasks and CLI orchestration; new execution modes are opt-in and recorded in provenance.

**Tech Stack:** Python stdlib/argparse/unittest, optional LiteLLM/jsonschema, C99/C11 Unity fixtures, GCC/Clang/TCC/MSVC, GitHub Actions.

**Spec:** GitHub issues #92–#150, snapshot at `.git/resolve-open-20261007/issues.json`; subsequent arriving issues are audited before completion.

## Global Constraints

- Python >=3.9; core dependencies remain empty.
- Never make paid provider calls for verification; provider tests use explicit offline responses.
- Preserve unknown usage/cost measurements, pending denominators and source identities.
- Keep default host footprints and native execution; containment/cross compilation/warning scores are opt-in.
- Preserve the existing untracked `uv.lock`; stage only task-owned changes.
- User explicitly authorized implementation, commits, push and issue comments/closures; proceed continuously without repeating approval.

## Review Focus

- Reordered, malformed and locally uncorroboratable report inputs must fail cleanly or remain portable without losing completed results.
- Interrupted multi-sample runs, mixed resolved identities and missing measurement turns must preserve independent samples and honest coverage.
- Compiler/runtime descendants, large diagnostics and file-parent output collisions must not bypass bounds or destroy inputs.
- MCU object accounting, warning policy and platform differences must remain reproducible and distinguish final deployment evidence.
- New task boundary tests must kill reviewed mutants and golden references must fit measured budgets.

## Work Package 1: Runtime and safety

**Files:** sandbox modules, runtime tests, containment documentation. **Issues:** #92–95, #97–98, #110–112, #114, #117–119, #133–134, #137.

- [ ] Write/reproduce focused failing tests before fixes.
- [ ] Bound host/cross compilation through the owned process runner, retain capped diagnostics and cancellation.
- [ ] Fix lexer location mapping and API reference classification; add opt-in compiler warnings and requested additional safety rules with configuration provenance.
- [ ] Measure Mach-O objects, support RISC-V target objects, handle silent versions and normalize portable toolchain identity at consumers.
- [ ] Add explicit external containment backends and document/test actual boundaries; remove discoverable completion tokens from candidate working-directory names and strengthen harness ownership without claiming native security isolation.
- [ ] Run runtime/static/size/target tests and record exact validation and limitations.

**Interfaces:** ExecutionSandbox retains current methods; additional constructor options are additive. Notify coordinator of exact `warnings`, isolation and container options before CLI integration. StaticAnalyzer adds configurable timeout and records its effective configuration.

## Work Package 2: Report integrity and offline workflows

**Files:** metrics modules, report_schema/schema, new replay/trend/export services, report tests. **Issues:** #103, #105–106, #109, #116–117, #123, #126, #128–130, #132, #135, #146–149.

- [ ] Prove and fix schema/reader/finding/counter validation, platform exit codes, optional corroboration and model identity sequence handling.
- [ ] Preserve full usage/cost completeness and retry policies in comparison/aggregation; coordinate generation metadata with coordinator.
- [ ] Add escaped, self-contained interactive HTML and SARIF exports; add thresholded comparison JUnit and compatible history/trend groups.
- [ ] Add verified batch replay through the shared evaluator; create fresh grading identity and preserve source origin without charging origin generation twice.
- [ ] Provide tested command helper APIs for coordinator CLI plumbing; do not edit shared cli.py/provenance.py/resume.py/models.py without coordination.

**Interfaces:** New service modules expose explicit functions and report renderers retain existing signatures. Report additions remain optional and structural schema plus Python cross-field validation agree.

## Work Package 3: Dataset and adequacy

**Files:** tasks, mutations.py, C-task tests, authoring/contamination documentation. **Issues:** #101, #108, #113, #120–121, #124–125, #131, #140–142.

- [ ] Add failing mutants for invalid ring capacities, wide indices, CRC lengths, IRQ side effects and exact debounce timing/threshold contracts.
- [ ] Implement reviewed DMA/ISR ownership, UART/SPI/NOR, fixed-point PID/filter, power-safe flash update and another bug-fix/C11 task with golden references and independent boundary oracles.
- [ ] Add deterministic operator mutation generation and report invalid/surviving mutants honestly.
- [ ] Add canary/variant authoring controls without treating public tests as hidden; record evaluation variant evidence.
- [ ] Verify every reference with real compilers, every mandatory mutant kill, and resource budgets; report resulting task/case/mutant counts.

**Interfaces:** Existing TaskConfig fields unchanged unless coordinator approves an additive metadata field. Host tests remain portable; metadata and standard/resource requirements are explicit per task.

## Work Package 4: Coordinator integration

**Files:** cli.py, llm/client.py, resume.py, provenance.py, output_paths.py, report_io.py, CI/composite action/docs and integration tests. **Issues:** #96, #99–100, #102, #104, #107, #115, #122–123, #127, #136, #138–139, #143–145, #150; integrate all other CLI options.

- [ ] Fix task-scoped provider errors, systematic-outage pending slots, canonical explicit options, ID-based resume and equivalent compiler spellings.
- [ ] Preserve opaque binary asset bytes, reject parent/file output collisions with a cycle-safe input walk and fsync POSIX directory renames.
- [ ] Add request/cost accounting and guarded optional spend budget; dry-run must not call providers or compile candidates.
- [ ] Add independent samples and unbiased Pass@k with sample-level checkpoints and explicit report structure/validation.
- [ ] Wire offline replay/trend/HTML/SARIF/JUnit features and CLI-level wrapper tests.
- [ ] Expand compiler/macOS/sanitizer/container CI, scheduled offline validation, Dependabot/pip cache and a consumer composite Action.
- [ ] Refresh baseline/mutation evidence, documentation and packaged-distribution checks.

## Finish

Local integration evidence: 350 Python tests pass with 9 explicit environment/platform
skips and 89% coverage. All 13 reference tasks pass 113 C cases on TCC, Clang
and MSVC; all 47 reviewed mutants are killed on TCC and Clang. ARM object
budgets, Ruff, Windows/Linux mypy, portable JSON Schema and published baseline
fingerprints pass. CI provides remaining GCC/macOS/AVR/container evidence.
Follow-up CI review fixes bind-mount file ownership by matching a non-root
host UID/GID, reaps a Darwin zombie group before retrying its termination,
and compares Unity object sections rather than unsupported linked Mach-O images.
Container workspace permission preparation also skips symlinks before inspecting
their targets, so candidate-created links cannot chmod host directories.
The 64 targeted runtime, evaluation and containment tests pass locally with
5 explicit tool/platform skips; four new regression tests bring the suite to 354.
Final coordinator review additionally corrected sampling output-root restoration,
completed-resume compatibility, collection checkpoints/statistics validation and
the existing csv-long column contract. Paid providers were mocked throughout.

- [ ] Run Ruff, both platform mypy checks, full coverage suite, schema/baseline/mutation checks and relevant real toolchain/containment tests.
- [ ] Commit scoped changes and push; run fresh whole-branch review and correct substantive findings.
- [ ] Verify GitHub CI; publish integration to main when validated, preserving a reviewable PR.
- [ ] Recheck newly opened issues; complete authorized actionable additions.
- [ ] Comment each issue with concrete changes, tests and commit/PR links, close only actually resolved issues, and verify final remote states.
