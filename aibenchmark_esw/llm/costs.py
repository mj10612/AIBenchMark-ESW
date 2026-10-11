"""Measured costs and conservative, shared request reservations (USD)."""
import math
import threading


class BudgetExceededError(RuntimeError):
    """A request cannot be reserved within the configured run budget."""


class PricingUnknownError(ValueError):
    """Pricing configuration is missing, independently of available spend."""


def _model_entries(provider, model):
    table = getattr(provider, 'model_cost', {}) if provider is not None else {}
    if isinstance(table, dict):
        for key in (model, model.split('/', 1)[-1]):
            entry = table.get(key)
            if isinstance(entry, dict) and entry:
                yield entry
    lookup = getattr(provider, 'get_model_info', None)
    if callable(lookup):
        try:
            entry = lookup(model=model)
            if isinstance(entry, dict):
                yield entry
        except Exception:
            pass


def model_info(provider, model):
    fallback: dict = {}
    for entry in _model_entries(provider, model):
        fallback = fallback or entry
        if entry.get('max_input_tokens') or entry.get('max_tokens'):
            return entry
    return fallback


def valid_cost(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def token_upper_bound(messages):
    # UTF-8 bytes bound ordinary byte-pair tokens; include message framing.
    return sum(len(str(message.get("content", "")).encode("utf-8")) + 64 for message in messages) + 64


def pricing(provider, model, input_price=None, output_price=None):
    if input_price is not None or output_price is not None:
        if not valid_cost(input_price) or not valid_cost(output_price):
            raise ValueError("Provide both --input-cost-per-million and --output-cost-per-million as finite nonnegative numbers")
        return {"input_per_token": input_price / 1_000_000,
                "output_per_token": output_price / 1_000_000, "source": "user"}
    for entry in _model_entries(provider, model):
        first, second = entry.get("input_cost_per_token"), entry.get("output_cost_per_token")
        if valid_cost(first) and valid_cost(second):
            cached = entry.get('cache_read_input_token_cost')
            return {"input_per_token": first, "output_per_token": second, "source": "litellm-model-cost",
                    'cached_input_per_token': cached if valid_cost(cached) else first,
                    'cache_pricing_source': 'model-table' if valid_cost(cached) else 'conservative-full-input-rate'}
    return None


def usage_cost(usage, prices):
    if not isinstance(usage, dict) or prices is None:
        return None
    first, second = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (first, second)):
        return None
    assert isinstance(first, int) and isinstance(second, int)
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)
    if isinstance(cached, bool) or not isinstance(cached, int) or not 0 <= cached <= first:
        return None
    return ((first - cached) * prices["input_per_token"]
            + cached * prices.get('cached_input_per_token', prices['input_per_token'])
            + second * prices["output_per_token"])


class CostBudget:
    def __init__(self, limit, spent=0.0):
        if not valid_cost(limit) or not valid_cost(spent):
            raise ValueError("Cost budget and initial spend must be finite nonnegative USD")
        self.limit, self.spent = float(limit), float(spent)
        self.reserved = 0.0
        self._lock = threading.Lock()

    def reserve(self, estimate):
        if not valid_cost(estimate):
            raise PricingUnknownError("Unknown model pricing; provide --input-cost-per-million and --output-cost-per-million")
        with self._lock:
            if self.spent + self.reserved + estimate > self.limit + 1e-12:
                raise BudgetExceededError("Maximum run cost reached; pending tasks can be resumed")
            self.reserved += estimate
        return estimate

    def settle(self, reservation, measured):
        with self._lock:
            self.reserved -= reservation
            # An unmeasured attempted request keeps its full reservation charged.
            self.spent += measured if valid_cost(measured) else reservation

    def snapshot(self):
        with self._lock:
            return {"limit_usd": self.limit, "charged_usd": self.spent, "reserved_usd": self.reserved}
