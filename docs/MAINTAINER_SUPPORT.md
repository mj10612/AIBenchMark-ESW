# Maintainer support: evidence and intended use

## Verifiable project value

The project studies embedded C failures that ordinary pass/fail coding tasks
can overlook: constrained object footprints, peripheral/register behavior,
fixed-width arithmetic, and selected allocation/safety rules. Users can run the
reference dataset locally without API access, inspect every C test and golden
implementation, and compare saved provider runs with recorded inputs.

Evidence is available in [CI runs](https://github.com/sentimentalmija-lgtm/AIBenchMark-ESW/actions),
[resolved issues](https://github.com/sentimentalmija-lgtm/AIBenchMark-ESW/issues?q=is%3Aissue%20is%3Aclosed),
the [reference baseline](../results/baseline.md) ([JSON](../results/baseline.json)), and
[reproducibility instructions](REPRODUCIBILITY.md). Reference scores are not
claims about any provider model. Mocked integration tests do not establish
live API compatibility or model quality.

## Intended support outcomes

Maintainer access to coding assistants would help review regression fixes,
triage reproducible issues, improve tests, and maintain package/release workflows.
If API credits are separately awarded, proposed uses are reproducible provider
evaluations and investigation of concrete benchmark failures, with explicit
token limits, recorded usage, and public methodology. Planned deliverables are
reviewed task additions, CI evidence, and shareable comparison reports.

## Program criteria and project maturity

The official [OpenAI program](https://openai.com/form/codex-for-oss/) considers
project usage, ecosystem importance, and continuing maintainer work. Its API
credits can support maintainer automation and other core open-source workflows.
The official [Claude program](https://claude.com/contact-sales/claude-for-oss)
lists downstream usage, substantial outside contributions, community participation,
and infrastructure criticality as qualifying routes; it also invites maintainers
to explain ecosystem value when they do not fit those routes. The described
Claude benefit is a subscription, not an assumed API credit grant.

This is an early-stage project. Repository features and maintenance evidence do
not demonstrate the programs' adoption thresholds. Application materials should
include only independently verifiable downloads, dependents, external contributions,
and maintainer roles. Do not infer eligibility or publish adoption/model-performance
figures that have not been measured. Official criteria and benefits may change;
verify the linked application pages when updating an application.
