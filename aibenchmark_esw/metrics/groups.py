"""Additive tier-weighted and task-category views; flat scores remain available."""
from collections import defaultdict


def grouped_scores(results, metadata=None):
    def passing(result):
        tests = result.test_result
        return result.compiled and tests.completed and tests.passed and tests.total_tests > 0 and tests.passed_tests == tests.total_tests and tests.failed_tests == tests.ignored_tests == 0

    def summarize(items):
        return {'count': len({item.task_id for item in items}), 'task_attempts': len(items),
                'mean_score': round(sum(item.scores.total_score for item in items) / len(items), 6),
                'pass_at_1_pct': round(sum(passing(item) for item in items) / len(items) * 100, 6)}

    categories = (metadata or {}).get('task_categories') or {}
    tiers, groups = defaultdict(list), defaultdict(list)
    for result in results:
        tiers[str(result.tier)].append(result)
        groups[categories.get(result.task_id, 'Unknown (legacy report)')].append(result)
    weight = sum(result.tier for result in results)
    return {'tier_weighted_score': round(sum(result.scores.total_score * result.tier for result in results) / weight, 6) if weight else 0.0,
            'tier_weight_policy': 'proportional-to-tier-v1',
            'by_tier': {key: summarize(items) for key, items in sorted(tiers.items())},
            'by_category': {key: summarize(items) for key, items in sorted(groups.items())}}


def breakdown_rows(models):
    return [dict(model=model['model'], scope=scope, group=group, **values)
            for model in models for scope in ('by_tier', 'by_category')
            for group, values in model.get(scope, {}).items()]


def breakdown_markdown(models):
    from aibenchmark_esw.metrics.text import markdown_text
    lines = ['', '### Tier and category breakdown', '',
             '| Model | Group type | Group | Tasks | Attempts | Mean | Pass@1 (%) | Delta vs baseline |',
             '| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |']
    for row in breakdown_rows(models):
        delta = row.get('delta_vs_baseline')
        lines.append('| ' + ' | '.join(markdown_text(value) for value in (
            row['model'], row['scope'], row['group'], row['count'], row['task_attempts'],
            row['mean_score'], row['pass_at_1_pct'], delta if delta is not None else 'Unavailable')) + ' |')
    return lines
