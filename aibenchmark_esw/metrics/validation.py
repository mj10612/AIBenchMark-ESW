"""Validate saved result data before it participates in scoring summaries."""

import math


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _number(value, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError(f"{name} must be a finite nonnegative number")


def _name(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def validate_task_result(item, default_model):
    _name(item.get("task_id"), "task_id")
    _name(item.get("model_name", default_model), "model_name")
    if isinstance(item.get("tier"), bool) or not isinstance(item.get("tier"), int) or item["tier"] not in (1, 2, 3, 4):
        raise ValueError("tier must be an integer from 1 to 4")
    compiled = _bool(item.get("compiled"), "compiled")
    tests = _object(item.get("test_result"), "test_result")
    total = _count(tests.get("total"), "test_result.total")
    passed = _count(tests.get("passed"), "test_result.passed")
    failed = _count(tests.get("failed"), "test_result.failed")
    ignored = _count(tests.get("ignored", 0), "test_result.ignored")
    completed = _bool(tests.get("completed", total > 0), "test_result.completed")
    all_passed = _bool(tests.get("all_passed"), "test_result.all_passed")
    returncode = tests.get("returncode")
    if returncode is not None and (isinstance(returncode, bool) or not isinstance(returncode, int)):
        raise ValueError("test_result.returncode must be an integer or null")
    if completed:
        if not compiled or total == 0 or passed + failed + ignored != total:
            raise ValueError("Completed tests require compilation and consistent nonempty test counts")
        if returncode is not None and returncode != failed:
            raise ValueError("Completed test returncode must match the failure count")
    # Incomplete output can contain contradictory diagnostic counts, but must
    # never claim success or contribute points.
    expected_pass = compiled and completed and total > 0 and passed == total and failed == ignored == 0
    if all_passed != expected_pass:
        raise ValueError("all_passed contradicts compilation, completion or test counts")

    size = _object(item.get("size_metrics"), "size_metrics")
    for name in ("flash_bytes", "ram_bytes", "ref_flash_bytes", "ref_ram_bytes"):
        _count(size.get(name, 0), f"size_metrics.{name}")
    measured = _bool(size.get("measured", True), "size_metrics.measured")
    safety = _object(item.get("safety_metrics"), "safety_metrics")
    for name in ("error_count", "warning_count"):
        _count(safety.get(name, 0), f"safety_metrics.{name}")
    violations = safety.get("violations", [])
    if not isinstance(violations, list) or any(not isinstance(value, str) for value in violations):
        raise ValueError("safety_metrics.violations must be an array of strings")
    _number(item.get("execution_time_sec"), "execution_time_sec")
    for name in ("target_standard", "effective_standard"):
        if item.get(name) is not None and item[name] not in ("c99", "c11", "c17"):
            raise ValueError(f"{name} must be c99, c11, c17 or null")
    if item.get("error_log") is not None and not isinstance(item["error_log"], str):
        raise ValueError("error_log must be a string or null")

    scores = _object(item.get("scores"), "scores")
    for name in ("functional", "memory", "safety", "total"):
        _number(scores.get(name), f"scores.{name}")
        if scores[name] > 100:
            raise ValueError(f"scores.{name} must be at most 100")
    if not compiled or not completed:
        if any(scores[name] for name in ("functional", "memory", "safety", "total")):
            raise ValueError("Uncompiled or incomplete tasks must have zero scores")
    else:
        functional = round(passed / total * 100, 2)
        if not math.isclose(scores["functional"], functional, abs_tol=0.01):
            raise ValueError("Functional score contradicts the test counts")
    if not measured and scores["memory"] != 0:
        raise ValueError("Unmeasured memory must have zero memory score")


def validate_composite_score(result):
    if result.weights is None:
        return  # Older reports did not preserve the weights.
    scores, weights = result.scores, result.weights
    expected = (weights.functional * scores.functional_score + scores.functional_score / 100 *
                (weights.memory * scores.memory_score + weights.safety * scores.safety_score))
    # Stored dimensions and the composite have already been rounded separately.
    if not math.isclose(scores.total_score, expected, abs_tol=0.02):
        raise ValueError("Composite score contradicts the dimensions and task weights")
