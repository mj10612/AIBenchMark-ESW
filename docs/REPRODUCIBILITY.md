# Reproducing and comparing benchmark results

Install `pip install -e ".[dev,llm]"` and make a C compiler available. Run the
reference baseline before spending provider credits:

```bash
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

Pass@1 here means one generated candidate passes all tests for a task. It is not
a multi-sample Pass@k estimate. Memory is the host implementation object's
allocated-section footprint, excluding stack/heap and the harness; it is not
the final MCU image. The safety scanner is heuristic. Host tests do not prove
portable ISR/thread synchronization or certification for safety-critical use.

GitHub Actions publishes baseline JSON and Markdown for each compiler job.
Those artifacts validate reference implementations and packaging, not paid
provider model performance. Real provider evaluations are opt-in and require
your own authorized API access.
