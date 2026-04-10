"""Policy engine for defining and enforcing safety policies."""

from typing import Dict, List, Any, Callable, Tuple
import logging

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Define and enforce safety policies."""

    def __init__(self):
        """Initialize policy engine."""
        self.policies: Dict[str, Callable] = {}

    def register_policy(self, name: str, policy_func: Callable) -> None:
        """Register a new policy.
        
        Args:
            name: Policy name
            policy_func: Function that evaluates the policy
        """
        self.policies[name] = policy_func

    def evaluate_policies(self, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Evaluate all policies against a context.
        
        Args:
            context: Context to evaluate
            
        Returns:
            Tuple of (all_passed, failed_policies)
        """
        all_passed = True
        failed_policies = []
        
        for name, policy_func in self.policies.items():
            try:
                passed = policy_func(context)
                if not passed:
                    all_passed = False
                    failed_policies.append(name)
            except Exception as e:
                logger.error(f"Error evaluating policy {name}: {e}")
                all_passed = False
                failed_policies.append(name)
                
        return all_passed, failed_policies
