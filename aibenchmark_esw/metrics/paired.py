"""Paired task-level evidence; deterministic, dependency-free statistics."""
import math
import random
import statistics


def paired_statistics(deltas):
    n = len(deltas)
    if not n:
        return {'matched_tasks': 0, 'median_delta': None, 'median_delta_ci95': None,
                'p_value': None, 'test': 'unavailable', 'cohens_dz': None}
    nonzero = sorted(abs(value) for value in deltas if value != 0)
    ranks = {}
    position = 0
    while position < len(nonzero):
        end = position + 1
        while end < len(nonzero) and nonzero[end] == nonzero[position]:
            end += 1
        ranks[nonzero[position]] = position + 1 + end  # Twice the mean rank.
        position = end
    weights = [ranks[abs(value)] for value in deltas if value != 0]
    positive = sum(ranks[abs(value)] for value in deltas if value > 0)
    total = sum(weights)
    if len(weights) <= 50:
        counts = {0: 1}
        for weight in weights:
            updated = dict(counts)
            for rank, count in counts.items():
                updated[rank + weight] = updated.get(rank + weight, 0) + count
            counts = updated
        distance = abs(2 * positive - total)
        p = sum(count for rank, count in counts.items() if abs(2 * rank - total) >= distance) / (2 ** len(weights))
        method = 'Wilcoxon signed-rank, exact sign enumeration with ties; zeros excluded'
    else:
        deviation = max(0, abs(positive - total / 2) - 1)
        sigma = math.sqrt(sum(weight * weight for weight in weights) / 4)
        p = math.erfc(deviation / (sigma * math.sqrt(2)))
        method = 'Wilcoxon signed-rank, tie-aware normal approximation with continuity correction; zeros excluded'
    interval = None
    if n >= 2:
        rng = random.Random(2026)
        boot = sorted(statistics.median(rng.choices(deltas, k=n)) for _ in range(2000))
        interval = [boot[49], boot[1949]]
    sd = statistics.stdev(deltas) if n >= 2 else None
    effect = statistics.mean(deltas) / sd if sd else 0.0 if all(value == 0 for value in deltas) else None
    return {'matched_tasks': n, 'median_delta': statistics.median(deltas), 'median_delta_ci95': interval,
            'bootstrap_resamples': 2000 if interval else 0, 'bootstrap_seed': 2026,
            'p_value': p, 'test': method, 'cohens_dz': effect,
            'effect_note': 'Undefined with fewer than two pairs or constant nonzero deltas' if effect is None else None}


def paired_comparisons(comparison, baseline_model=None):
    baseline_model = baseline_model or comparison['models'][0]['model']
    baseline = {row['task_id']: row for row in comparison['task_rows'] if row['model'] == baseline_model}
    if not baseline:
        raise ValueError('Baseline model is absent from comparison')
    comparisons = []
    for model in (row['model'] for row in comparison['models'] if row['model'] != baseline_model):
        tasks = {row['task_id']: row for row in comparison['task_rows'] if row['model'] == model}
        matched = sorted(set(tasks) & set(baseline))
        deltas = {task: tasks[task]['total'] - baseline[task]['total'] for task in matched}
        row = {'model': model, 'baseline': baseline_model, 'task_deltas': deltas,
               'unmatched_tasks': len(set(tasks) ^ set(baseline)), **paired_statistics(list(deltas.values()))}
        comparisons.append(row)
    for row in comparisons:
        row['p_value_bonferroni'] = min(1.0, row['p_value'] * len(comparisons)) if row['p_value'] is not None else None
    return {'baseline': baseline_model, 'unit': 'paired task mean across completed samples',
            'interpretation': 'Exploratory differences across selected tasks; no proof of superiority or model generation noise. Bootstrap assumes exchangeable task pairs.',
            'comparisons': comparisons}
