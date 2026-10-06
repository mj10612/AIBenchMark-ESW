"""Public, dependency-free access to the portable report structure contract."""

import json
from importlib.resources import files


def report_schema():
    """Return an independent draft 2020-12 JSON Schema document."""
    return json.loads(files("aibenchmark_esw").joinpath("schemas/report-v2.schema.json").read_text(encoding="utf-8"))


def validate_report_structure(report):
    """Validate structure using the optional schema extra; no compiler/provider."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise ValueError("Install aibenchmark-esw[schema] to run structural validation") from error
    errors = sorted(Draft202012Validator(report_schema()).iter_errors(report), key=lambda item: str(list(item.path)))
    if errors:
        raise ValueError("Report schema violation: " + "; ".join(
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors[:10]))
