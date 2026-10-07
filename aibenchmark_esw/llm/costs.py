"""Measured costs and conservative, shared request reservations (USD)."""
import math
import threading


class BudgetExceededError(RuntimeError):
    """A request cannot be reserved within the configured run budget."""


def valid_cost(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def token_upper_bound(messages):
    # UTF-8 bytes bound ordinary byte-pair tokens; include message framing.
    return sum(len(str(message.get("content", "")).encode("utf-8")) + 64 for message in messages) + 64


def pricing(provider, model, input_price=None, output_price=None):
    if input_price is not None or output_price is not None:
        if not valid_cost(input_price) or not valid_cost(output_price):
            raise ValueError("Both input/output costs per million must be finite nonnegative numbers")
        return {"input_per_token": input_price / 1_000_000,
                "output_per_token": output_price / 1_000_000, "source": "user"}
    table = getattr(provider, "model_cost", {}) if provider is not None else {}
    entry = table.get(model, {}) if isinstance(table, dict) else {}
    first, second = entry.get("input_cost_per_token"), entry.get("output_cost_per_token")
    if valid_cost(first) and valid_cost(second):
        return {"input_per_token": first, "output_per_token": second, "source": "litellm-model-cost"}
    return None


def usage_cost(usage, prices):
    if not isinstance(usage, dict) or prices is None:
        return None
    first, second = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (first, second)):
        return None
    return first * prices["input_per_token"] + second * prices["output_per_token"]


class CostBudget:
    def __init__(self, limit, spent=0.0):
        if not valid_cost(limit) or not valid_cost(spent):
            raise ValueError("Cost budget and initial spend must be finite nonnegative USD")
        self.limit, self.spent = float(limit), float(spent)
        self.reserved = 0.0
        self._lock = threading.Lock()

    def reserve(self, estimate):
        if not valid_cost(estimate):
            raise BudgetExceededError("Cannot reserve a request with unknown pricing; supply both custom token prices")
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
