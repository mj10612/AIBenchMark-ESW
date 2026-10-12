# Provider accounting and compile repair

Attempt latency measures the provider call alone; retry delays are separate.
Generation latency sums attempt latencies, while `elapsed_wall_seconds` records
wall time including waits. Reservations settle before backoff. Known pre-response
rate-limit, connection, HTTP 408, and server errors release their reserved charge.
Ambiguous timeouts retain the full reservation. This is a budget policy, not a
claim that unmeasured provider billing was zero: unknown usage and cost remain
unknown in reports. Exhausted transient errors remain pending even when subsequent
tasks succeed, and `--resume` retries those slots without repeating successes.

Dry runs and live runs construct the identical initial prompt and use the same
local LiteLLM pricing lookup: qualified model, bare model, then `get_model_info`.
Dry runs never call completion. Missing optional provider support or pricing is
reported as unknown. A spend guard with unknown pricing raises `PricingUnknownError`
with both custom-price flag names, independently of a budget overrun. Both custom
prices are required and replace the provider rates.

When the normalized `prompt_tokens_details.cached_tokens` count and cache-read
rate are available, fallback billing charges uncached and cached input separately.
Missing cache pricing conservatively uses the full input rate, explicitly labelled
`conservative-full-input-rate`; it does not invent a provider discount. Provider
response cost takes precedence. Cache-write or other provider-specific surcharges
require authoritative provider response cost; token-only fallback estimates cannot
reconstruct an unknown surcharge. See [LiteLLM cost documentation](https://docs.litellm.ai/docs/troubleshoot/cost_discrepancy).

Context prechecks use the model's local metadata and verified tokenizer count.
Byte bounds used for budget estimates are not treated as exact tokenizer counts.
When optional plan/review history causes overflow it is discarded while preserving
the original task and final instruction. An actual provider context error similarly
gets one retry with optional history removed. Irreducible oversized prompts fail
with an actionable error; unavailable metadata/tokenization leaves the provider
responsible for context validation. The context policy is recorded for comparison.

`--repair-turns N` (0..10, default 0) requests bounded additional generations only
after a compile failure. Each repair receives at most 2048 characters of scrubbed
compiler diagnostics. Functional test failures do not trigger compile repair.
Public transcripts distinguish `plan`, `implement`, `review`, and `repair` turns;
all attempts contribute usage/cost and share the spend guard. Repair counts are
restored on resume and must match for comparisons. Saved candidate files contain
the latest attempted implementation.

Provider exception diagnostics are scrubbed and capped before publication. Known
key, Bearer, key/value, URL credential, and credential-query patterns are removed.
`--api-key-env NAME` also scrubs that exact key and records only NAME in run options;
the value is passed to the provider without saving it in request transcripts.

The library exports provider classes, cost helpers, and `litellm_available()` for
optional support detection. CLI `--version` reports the evaluator package version;
invoking without a subcommand returns usage status 2. Mutation `--jobs` bounds
concurrent mutants within each task, and library/CLI minimum-score defaults are 1.
