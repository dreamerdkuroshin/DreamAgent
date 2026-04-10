"""Manage and track costs across services."""

from typing import Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CostData:
    """Cost tracking information."""
    service: str
    amount: float
    currency: str = "USD"


class CostManager:
    """Track and manage costs across services."""

    def __init__(self):
        """Initialize cost manager."""
        self.costs: Dict[str, float] = {}
        self.total_cost = 0.0

    def record_cost(self, service: str, amount: float) -> None:
        """Record a cost for a service.
        
        Args:
            service: Service name
            amount: Cost amount
        """
        if amount < 0:
            logger.warning(f"Invalid cost amount {amount} for service {service}.")
            return
            
        self.costs[service] = self.costs.get(service, 0.0) + amount
        self.total_cost += amount

    def get_cost_report(self) -> Dict[str, Any]:
        """Get a cost report."""
        breakdown = sorted(self.costs.items(), key=lambda x: x[1], reverse=True)
        top_service = breakdown[0][0] if breakdown else None
        avg_cost = self.total_cost / len(self.costs) if self.costs else 0.0
        
        return {
            "total": self.total_cost,
            "breakdown": dict(breakdown),
            "top_service": top_service,
            "average_per_service": avg_cost
        }

    def get_cost_by_service(self, service: str) -> float:
        """Get total cost for a specific service."""
        return self.costs.get(service, 0.0)
