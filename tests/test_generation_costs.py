import unittest
from types import SimpleNamespace as N
from unittest.mock import Mock, patch

from aibenchmark_esw.llm.client import LLMClient
from aibenchmark_esw.llm.costs import BudgetExceededError, CostBudget


class TestGenerationCosts(unittest.TestCase):
    def test_shared_reservations_prevent_overspend(self):
        budget = CostBudget(0.02)
        first = budget.reserve(0.015)
        with self.assertRaises(BudgetExceededError):
            budget.reserve(0.015)
        budget.settle(first, 0.001)
        budget.reserve(0.015)

    def test_unknown_attempt_keeps_reserved_charge(self):
        budget = CostBudget(0.01)
        reservation = budget.reserve(0.01)
        budget.settle(reservation, None)
        with self.assertRaises(BudgetExceededError):
            budget.reserve(0.001)

    def test_client_measures_cost_and_retains_unknown_retry_coverage(self):
        provider = Mock()
        provider.completion.side_effect = [TimeoutError(), N(model="mock", usage=N(
            prompt_tokens=2, completion_tokens=3, total_tokens=5), choices=[N(
            finish_reason="stop", message=N(content="int f(void){return 1;}"))])]
        client = LLMClient("mock", max_retries=1, retry_backoff_seconds=0,
                           input_cost_per_million=1, output_cost_per_million=2)
        with patch.dict("sys.modules", {"litellm": provider}):
            client.generate_solution([{"role": "user", "content": "task"}])
        self.assertIsNone(client.last_generation["cost_usd"])
        self.assertAlmostEqual(client.last_generation["known_cost_usd"], 8e-6)
        self.assertIsNone(client.last_generation["usage"]["total_tokens"])

    def test_unknown_pricing_fails_before_provider_call(self):
        provider = Mock()
        client = LLMClient("mock", max_tokens=10, budget=CostBudget(1))
        with patch.dict("sys.modules", {"litellm": provider}), self.assertRaises(BudgetExceededError):
            client.generate_solution([{"role": "user", "content": "task"}])
        provider.completion.assert_not_called()
