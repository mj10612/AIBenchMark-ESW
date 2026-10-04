# Reproducing and comparing benchmark results

Install `pip install -e ".[dev,llm]"` and make a C compiler available. Run the
dataset asset check and reference baseline before spending provider credits:

```bash
aibenchmark-esw validate
aibenchmark-esw run --model baseline --output results/baseline.json
python -m unittest discover -s tests -v
```

Use exact, preferably snapshot, provider model IDs available to your account.
The README shows OpenAI/Anthropic runs with matching token limits and timeouts.
Credentials belong in environment variables, never in committed reports.

On PowerShell, set `$env:OPENAI_API_KEY` or `$env:ANTHROPIC_API_KEY`, then pass
the model directly, for example `--model "openai/<available-model-id>"`.
Temperature is omitted unless explicitly supplied. Provider defaults and model
sampling can still vary; recording settings does not guarantee identical outputs.

## What a report records

Schema version 2 includes UTC time, package/Python/host versions, compiler
identity/version and optimization, source revision when available, task
selection, and generation settings. Task fingerprints cover effective task
configuration, task text/sources/tests, and the Unity harness; candidate and
prompt hashes identify the generated implementation and submitted messages.
An evaluator hash identifies the Python implementation used for grading.
Checkout paths and CRLF/LF differences do not alter these hashes.

`validate` checks required files without compilation or API access. During a
run, missing, empty, or unreadable task assets fail that task before generation;
the failure stays in the report and denominator while other valid tasks continue.
Passing this file check does not establish reference correctness or budget fit.

Reports also record the selected static-analysis backend and cppcheck version.
Per-task safety results distinguish disabled, completed, failed, and unrun
cppcheck checks. A failed invocation retains its diagnostic and uses the built-in
rules; reports and comparisons explicitly warn about that reduced coverage.
Comparisons reject differing recorded analyzer configurations/versions and warn
when older reports lack analyzer information. CSV includes cppcheck completed
and failed task counts.

For repeatable analyzer selection, set `AIBENCHMARK_ESW_CPPCHECK=off` to use only
the built-in rules, or set it to a cppcheck executable path. When unset, PATH
discovery remains the default. A programmatic `StaticAnalyzer` executable
argument takes precedence. Compiler-matrix CI jobs explicitly use built-in
analysis; a separate Linux job installs cppcheck and requires real analysis of
a reference implementation and a deliberate out-of-bounds defect. To run those
integration checks locally, set `AIBENCHMARK_ESW_TEST_CPPCHECK` to your working
cppcheck executable and run `python -m unittest discover -s tests -p test_cppcheck_integration.py -v`.

Per-task generation metadata includes the requested and resolved model,
provider-reported token usage, elapsed generation time, and finish reason.
Missing usage stays unknown. API failures and token-limit truncations stay in
the report and denominator, receiving zero points. A failed or oversized
reference prevents memory normalization and produces an explicit error.

Use `--save-solutions results/model_sources` to save extracted implementation
files, then replay one with:

```bash
aibenchmark-esw eval --task tier1_crc16 --solution results/model_sources/tier1_crc16.c
```

To retain a local evaluation as JSON, add `--output results/local_crc16.json`.
It includes the same toolchain, analyzer, task, and candidate fingerprints as
`run`; local evaluations have no provider prompt or usage. Compilation and test
failures are still saved. `--reference` and `--solution` select alternative inputs
and cannot be combined.

## Checkpoints and interruption

`run --output` writes a checkpoint before any provider requests and after each
task, replacing the destination only after a complete JSON file is flushed.
An output-path failure therefore stops the initial run before generation. A
later write failure preserves the previous valid checkpoint.

Ctrl+C during generation/evaluation saves available completed results, usage,
and an `interrupted` run status, then exits with code 130. Unfinished tasks stay
in the report and denominator with zero scores and explicit diagnostics.
`metadata.pending_tasks` identifies them. An abrupt process termination leaves
the last checkpoint marked `running`. Report commands display unfinished state;
comparisons require finished runs. Each new invocation starts fresh and replaces
its requested output file, so use distinct filenames to retain prior runs.

## Fair comparisons

```bash
aibenchmark-esw compare --results results/openai.json results/claude.json --format cli
aibenchmark-esw compare --results results/openai.json results/claude.json \
  --format markdown --output results/comparison.md
aibenchmark-esw compare --results results/openai.json results/claude.json \
  --format csv --output results/comparison.csv
```

Runs must contain distinct model names and identical task sets, including
failures. Available weights, C standards, task/dataset and evaluator fingerprints, compilers,
host architecture, temperatures, token limits, and request timeouts must agree. Legacy reports
without provenance carry explicit warnings, rather than a claim of comparability.
CSV includes usage/duration task counts so partial totals can be identified.

Report readers validate booleans, counts, finite nonnegative measurements,
supported schema versions, and score consistency before rendering or comparing.
Uncompiled or incomplete tasks cannot carry positive scores. Valid legacy files
remain readable; metadata and weights they never recorded remain unknown.

Pass@1 here means one generated candidate passes all tests for a task. It is not
a multi-sample Pass@k estimate. Memory is the host implementation object's
allocated-section footprint, excluding stack/heap and the harness; it is not
the final MCU image. The safety scanner is heuristic. Host tests do not prove
portable ISR/thread synchronization or certification for safety-critical use.

GitHub Actions publishes baseline JSON and Markdown for each compiler job.
Those artifacts validate reference implementations and packaging, not paid
provider model performance. Real provider evaluations are opt-in and require
your own authorized API access.
