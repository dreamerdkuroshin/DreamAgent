"""Optimize prompts based on performance data."""

from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class PromptOptimizer:
    """Optimize prompts for better performance."""

    def __init__(self):
        """Initialize prompt optimizer."""
        self.prompt_history: Dict[str, List[str]] = {}
        self.performance_metrics: Dict[str, float] = {}

    def optimize_prompt(self, prompt: str, task: str) -> str:
        """Optimize a prompt for a specific task.
        
        Args:
            prompt: Original prompt
            task: Task type
            
        Returns:
            Optimized prompt
        """
        optimized = prompt.strip()
        
        # Pass 1: Role priming by task type
        if task == "creative":
            optimized = f"Act as a professional creative writer. {optimized}"
        elif task in ["analytical", "code", "logic"]:
            optimized = f"Act as an expert systems engineer and logical thinker. {optimized}"
        
        # Pass 2: Chain-of-thought injection for analytical tasks
        if task in ["analytical", "logic", "reasoning"]:
            if "step by step" not in optimized.lower():
                optimized += "\nLet's think step by step to ensure accuracy."
        
        # Pass 3: Structured output nudge
        if "format" not in optimized.lower() and "structure" not in optimized.lower():
            optimized += "\nPlease provide the response in a clear, structured format using markdown."
        
        # Pass 4: Whitespace cleanup
        import re
        optimized = re.sub(r'\n{3,}', '\n\n', optimized)
        
        self.prompt_history.setdefault(task, []).append(optimized)
        return optimized

    def evaluate_prompt_performance(self, prompt: str, results: List[Any]) -> float:
        """Evaluate how well a prompt performed.
        
        Args:
            prompt: Prompt to evaluate
            results: Results from using the prompt
            
        Returns:
            Performance score
        """
        score = 0.0
        
        # Score on length (avoid too short or too long - assuming some heuristic)
        if 50 < len(prompt) < 500:
            score += 20.0
        
        # Structure markers
        if any(x in prompt.lower() for x in ["markdown", "table", "bullet", "list"]):
            score += 30.0
        
        # Negative phrase detection
        negative_phrases = ["as an ai", "i cannot", "i don't have", "sorry, but"]
        results_text = " ".join([str(r) for r in results]).lower()
        penalty = sum(10.0 for p in negative_phrases if p in results_text)
        score -= penalty
        
        # Normalize/Base score
        score = max(0.0, score + 50.0) 
        
        self.performance_metrics[prompt] = score
        return score

    def get_best_prompt(self, task: str) -> str:
        """Get the best performing prompt for a task."""
        prompts = self.prompt_history.get(task, [])
        if not prompts:
            return ""
        
        return max(prompts, key=lambda p: self.performance_metrics.get(p, 0.0))

