# Report integrity and CI gates

The report reader rejects a present `samples: null` field, inconsistent derived
generation summaries, and collection children produced under different grading
conditions. Completed collections require at least one completed sample. Empty
interrupted collections remain readable and resumable, but cannot be compared or
aggregated as completed evidence.

New interrupted collections embed `sampling.active_report`, preserving active
sample spending so its summary can be checked. Older interrupted collections
without that report retain recorded spending as an explicitly unverified subtotal.
Run IDs, timestamps, compiler installation paths, and resolved model differences
between independent samples remain informational.

Standalone memory and safety dimensions are unavailable if any contributing
attempt was unmeasured. Reports include the measured-attempt counts. Composite
scores still include every failed or pending task under the recorded scoring policy.
Provider coverage uses task attempts, including every contributing sample.

Independent sample intervals use two-sided 95% Student-t critical values with
sample standard deviation, clipped to [0, 100]. One sample has no interval; above
30 degrees of freedom the df=30 critical value is used conservatively. These
intervals assume independent samples; repeating deterministic generations does
not establish independence.

`compare` and `trend` remain report-only by default. `--fail-on-regression` saves
all requested evidence atomically before returning status 3 for a measured score
drop exceeding `--regression-threshold`. Compare uses `--baseline-model` (default:
the leading model in the comparison). Trend compares only compatible predecessor
identities within each grading group. An exact-threshold drop does not fail.

Exit statuses: 0 for a clean/report-only result, 1 for invalid input or evaluation
failure, 2 for command usage errors, 3 for an opt-in measured regression, and 130
for interruption. Incompatible reports are invalid input, not a measured regression.
CSV exporters prefix formula-like text cells with an apostrophe. Markdown escapes
untrusted label content. Comparison JUnit removes XML-forbidden control characters.

Offline GitHub Actions gate example (with two previously saved compatible reports):

```yaml
- name: Compare saved evidence
  run: >-
    aibenchmark-esw compare --results baseline.json candidate.json
    --baseline-model baseline --fail-on-regression --regression-threshold 1
    --format junit --output artifacts/comparison.xml
- name: Upload comparison evidence
  if: always()
  uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
  with:
    name: comparison-evidence
    path: artifacts/comparison.xml
```
