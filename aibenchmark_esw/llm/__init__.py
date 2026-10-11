"""Optional language-model provider support."""

import importlib.util
import sys

from .client import LLMClient
from .costs import BudgetExceededError, CostBudget, PricingUnknownError, pricing, token_upper_bound, usage_cost

__all__ = ['LLMClient', 'CostBudget', 'BudgetExceededError', 'PricingUnknownError',
           'pricing', 'usage_cost', 'token_upper_bound', 'litellm_available']


def litellm_available() -> bool:
    """Detect optional provider support without importing it or making a request."""
    if 'litellm' in sys.modules:
        return sys.modules['litellm'] is not None
    return importlib.util.find_spec('litellm') is not None
