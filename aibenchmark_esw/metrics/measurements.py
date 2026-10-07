"""Coverage-aware provider measurements and contributing model identity."""

import math


def generation_sequence(generation):
    turns = generation.get('turns')
    if turns:
        if not isinstance(turns, list) or any(not isinstance(turn, dict) for turn in turns):
            raise ValueError('Generation turns must be objects')
        sequence = tuple(turn.get('resolved_model') for turn in turns if turn.get('status') != 'failed')
    else:
        value = generation.get('resolved_model')
        sequence = (value,) if value is not None else ()
    if any(value is not None and (not isinstance(value, str) or not value.strip()) for value in sequence):
        raise ValueError('resolved_model must be a nonempty string or null')
    return sequence


def measurement_summary(results):
    tokens, costs, durations = [], [], []
    complete_tokens = complete_costs = partial_tokens = partial_costs = 0
    known_attempts = total_attempts = attempt_tasks = known_turns = total_turns = turn_tasks = 0
    for result in results:
        generation = result.generation or {}
        for key in ('usage', 'known_usage', 'usage_coverage'):
            if generation.get(key) is not None and not isinstance(generation[key], dict):
                raise ValueError('Generation ' + key + ' must be an object')
        for key in ('usage_complete', 'cost_complete'):
            if key in generation and not isinstance(generation[key], bool):
                raise ValueError('Generation ' + key + ' must be a boolean')
        for key in ('cost_usd', 'known_cost_usd', 'latency_seconds', 'budget_charge_usd'):
            value = generation.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value) or value < 0):
                raise ValueError('Invalid generation ' + key)
        for key in ('usage', 'known_usage'):
            for field in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                value = (generation.get(key) or {}).get(field)
                if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                    raise ValueError('Invalid generation token measurement')
        coverage = (generation.get('usage_coverage') or {}).get('total_tokens')
        if coverage is not None:
            if not isinstance(coverage, dict):
                raise ValueError('Usage coverage must be an object')
            known, count = coverage.get('known_attempts'), coverage.get('total_attempts')
            if (isinstance(known, bool) or not isinstance(known, int) or known < 0
                    or isinstance(count, bool) or not isinstance(count, int) or count < 0 or known > count):
                raise ValueError('Usage coverage request counts are invalid')
            known_attempts += known
            total_attempts += count
            attempt_tasks += 1
        turns = generation.get('turns')
        if turns is not None:
            if not isinstance(turns, list) or any(not isinstance(turn, dict) for turn in turns):
                raise ValueError('Generation turns must be objects')
            if any(turn.get('usage') is not None and not isinstance(turn['usage'], dict) for turn in turns):
                raise ValueError('Generation turn usage must be an object')
            total_turns += len(turns)
            known_turns += sum((turn.get('usage') or {}).get('total_tokens') is not None for turn in turns)
            turn_tasks += 1
        usage = generation.get('usage') or {}
        total = usage.get('total_tokens')
        if total is None:
            total = (generation.get('known_usage') or {}).get('total_tokens')
        cost = generation.get('cost_usd')
        known_cost = generation.get('known_cost_usd', cost)
        duration = generation.get('latency_seconds')
        if total is not None:
            if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                raise ValueError('Invalid token usage in report')
            tokens.append(total)
            if generation.get('usage_complete', True):
                complete_tokens += 1
            else:
                partial_tokens += 1
        if known_cost is not None:
            if isinstance(known_cost, bool) or not isinstance(known_cost, (int, float)) or not math.isfinite(known_cost) or known_cost < 0:
                raise ValueError('Invalid generation cost in report')
            costs.append(known_cost)
            if cost is not None and generation.get('cost_complete', True):
                complete_costs += 1
            else:
                partial_costs += 1
        if duration is not None:
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                raise ValueError('Invalid generation duration in report')
            durations.append(duration)
    passed = sum(result.test_result.passed for result in results)
    return {'task_attempts': len(results),
            'total_tokens': sum(tokens) if complete_tokens == len(results) and tokens else None,
            'known_total_tokens': sum(tokens) if tokens else None,
            'usage_tasks': complete_tokens, 'usage_partial_tasks': partial_tokens,
            'usage_known_attempts': known_attempts if attempt_tasks else None,
            'usage_total_attempts': total_attempts if attempt_tasks else None,
            'usage_attempt_coverage_tasks': attempt_tasks,
            'usage_known_turns': known_turns if turn_tasks else None,
            'usage_total_turns': total_turns if turn_tasks else None,
            'usage_turn_coverage_tasks': turn_tasks,
            'total_cost_usd': sum(costs) if complete_costs == len(results) and costs else None,
            'known_cost_usd': sum(costs) if costs else None,
            'cost_tasks': complete_costs, 'cost_partial_tasks': partial_costs,
            'cost_per_passed_task': sum(costs) / passed if complete_costs == len(results) and costs and passed else None,
            'generation_seconds': round(sum(durations), 6) if durations else None,
            'duration_tasks': len(durations)}


def render_measurements(results, summary=None):
    measurement = summary or measurement_summary(results)
    if summary is None and not any(result.generation for result in results):
        return []
    count = measurement.get('task_attempts', len(results))
    return [f"Tokens: {measurement['total_tokens'] if measurement['total_tokens'] is not None else 'Unknown'}; "
            f"known subtotal {measurement['known_total_tokens']}; complete {measurement['usage_tasks']}/{count} tasks; "
            f"partial {measurement['usage_partial_tasks']} tasks.",
            f"Cost USD: {measurement['total_cost_usd'] if measurement['total_cost_usd'] is not None else 'Unknown'}; "
            f"known subtotal {measurement['known_cost_usd']}; complete {measurement['cost_tasks']}/{count} tasks; "
            f"partial {measurement['cost_partial_tasks']} tasks.", coverage_text(measurement)]


def coverage_text(measurement):
    requests = (f"{measurement['usage_known_attempts']}/{measurement['usage_total_attempts']} measured requests"
                if measurement['usage_total_attempts'] is not None else 'Request coverage unknown (legacy report)')
    turns = (f"{measurement['usage_known_turns']}/{measurement['usage_total_turns']} measured turns"
             if measurement['usage_total_turns'] is not None else 'Turn coverage unknown (legacy report)')
    return requests + '; ' + turns + '.'


def portable_settings(value):
    """Discard machine-local executable locations and file timestamps only."""
    if isinstance(value, list):
        return [portable_settings(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in ('stamp', 'path', 'compiler_path'):
            continue
        if key == 'compiler' and isinstance(item, str):
            item = item.replace('\\', '/').rsplit('/', 1)[-1]
            if item.lower().endswith('.exe'):
                item = item[:-4]
        result[key] = portable_settings(item)
    return result
