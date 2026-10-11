# Paired comparisons, tier weighting, and persistent SARIF sources

The flat `overall_score` remains available. New reports additionally record a
`tier_weighted_score` using weights proportional to task tier (1, 2, 3, 4).
Comparisons rank by this additive score and show both values. Tier and category
breakdowns publish distinct task counts, attempt counts, mean scores, Pass@1 and
delta against the selected baseline. Failed attempts remain in every denominator.
Legacy categories appear as unknown. Markdown, HTML and csv-long include group
tables/rows; csv-long's `scope` distinguishes task, by_tier and by_category rows.
Collection comparisons average all completed samples; standalone collection
report dimensions and weighted groups retain their explicit first-sample scope.

Paired comparisons use each matched task's mean across completed samples. They
publish per-task deltas, median delta, a deterministic 2,000-resample percentile
bootstrap interval (seed 2026), Wilcoxon signed-rank p-value and Cohen dz. Exact
sign enumeration handles ties for up to 50 nonzero pairs; larger sets use a
tie-aware normal approximation. Zero differences are excluded from signed ranks.
One pair has no bootstrap interval; constant nonzero differences have undefined
dz. Bonferroni-adjusted p-values cover comparisons against the baseline. Default
baseline is the leading weighted model; `compare --baseline-model NAME` overrides
it. JUnit adds informational statistics cases; regression failures retain their
existing per-task score threshold policy and do not depend on significance.

These are exploratory task-level differences. Tasks are a fixed, heterogeneous
benchmark; bootstrap intervals assume exchangeable task pairs. They do not
estimate stochastic generation noise or prove that a model is superior.

`eval --solution` and `run --save-solutions` record persistent candidate paths and
content hashes. Export from a repository root:

```sh
aibenchmark-esw report --results results/run.json --format sarif --source-root . --output results/findings.sarif
```

For relocated sources or independently saved samples, use `--source-mapping`
with a JSON object mapping task IDs, or `task_id:sample_run_id`, to relative paths.
Only readable files inside the source root whose normalized content hash matches
the recorded candidate receive repository-relative, URI-escaped locations and
stable fingerprints. Identical source/rule/location findings merge their sample
IDs; separately mapped files remain distinct. Missing or mismatched mappings are
diagnostic-only results without guessed locations or code-scanning fingerprints.
Commit candidate sources if publishing findings to code scanning. Exports never
upload sources or SARIF automatically.
