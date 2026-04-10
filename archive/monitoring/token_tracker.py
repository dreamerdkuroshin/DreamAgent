"""Track token usage across models and API calls."""

from typing import Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage statistics."""
    input_tokens: int
    output_tokens: int
    total_tokens: int


class TokenTracker:
    """Track and report token usage."""

    def __init__(self):
        """Initialize token tracker."""
        self.usage_by_model: Dict[str, TokenUsage] = {}
        self.total_usage = TokenUsage(0, 0, 0)

    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for a model.
        
        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        total = input_tokens + output_tokens
        
        if model not in self.usage_by_model:
            self.usage_by_model[model] = TokenUsage(0, 0, 0)
            
        self.usage_by_model[model].input_tokens += input_tokens
        self.usage_by_model[model].output_tokens += output_tokens
        self.usage_by_model[model].total_tokens += total
        
        self.total_usage.input_tokens += input_tokens
        self.total_usage.output_tokens += output_tokens
        self.total_usage.total_tokens += total

    def get_usage_report(self) -> Dict[str, Any]:
        """Get a detailed usage report."""
        report = {
            "total": {
                "input_tokens": self.total_usage.input_tokens,
                "output_tokens": self.total_usage.output_tokens,
                "total_tokens": self.total_usage.total_tokens
            },
            "by_model": {}
        }
        
        for model, usage in self.usage_by_model.items():
            report["by_model"][model] = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens
            }
            
        return report
