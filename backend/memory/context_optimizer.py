"""
backend/memory/context_optimizer.py

Context Window Optimizer.
Manages token budget, synthesizes old Dragonfly turns, limits context size.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

MAX_CONTEXT_TOKENS = 3000

class ContextOptimizer:
    def __init__(self, llm_provider=None):
        self.llm = llm_provider
    
    async def optimize(self, context: Dict[str, Any], user_id: str, bot_id: str) -> Dict[str, Any]:
        """
        Optimizes memory payload to fit roughly within MAX_CONTEXT_TOKENS.
        For now, does a simplistic character-based estimation (4 chars = 1 token).
        """
        # Count roughly
        def estimate_tokens(text: str) -> int:
            return len(text) // 4
            
        session_str = "\n".join(context.get("session", []))
        core_str = "\n".join(context.get("core_memory", []))
        long_term_str = "\n".join(context.get("long_term", []))
        
        session_toks = estimate_tokens(session_str)
        core_toks = estimate_tokens(core_str)
        lt_toks = estimate_tokens(long_term_str)
        
        total = session_toks + core_toks + lt_toks
        
        if total <= MAX_CONTEXT_TOKENS:
            return context
            
        logger.info(f"[ContextOptimizer] Context size ({total} tokens) exceeds {MAX_CONTEXT_TOKENS}. Trimming.")
        
        # 1. Core memory is NEVER pruned.
        available_budget = MAX_CONTEXT_TOKENS - core_toks
        if available_budget < 0:
            logger.warning("[ContextOptimizer] Core memory ALONE exceeds budget!")
            available_budget = 0
            
        # 2. Allocate 60% of remaining to session, 40% to LT
        sess_budget = int(available_budget * 0.6)
        lt_budget = available_budget - sess_budget
        
        optimized_context = {
            "core_memory": context.get("core_memory", []),
            "preferences": context.get("preferences", {})
        }
        
        # Trim Long Term
        if lt_toks > lt_budget:
            logger.info("[ContextOptimizer] Trimming long_term memory to fit budget.")
            # Simple heuristic: keep the top N that fit
            kept_lt = []
            current_lt_toks = 0
            for item in context.get("long_term", []):
                t = estimate_tokens(item)
                if current_lt_toks + t > lt_budget:
                    break
                kept_lt.append(item)
                current_lt_toks += t
            optimized_context["long_term"] = kept_lt
        else:
            optimized_context["long_term"] = context.get("long_term", [])
            sess_budget += (lt_budget - lt_toks) # Give back unused
            
        # Trim Session: In a real environment, we'd asynchronously summarize here.
        # For inline speed, we just drop oldest for the prompt.
        if session_toks > sess_budget:
            logger.info("[ContextOptimizer] Trimming session memory to fit budget.")
            kept_session = []
            curr_sess_toks = 0
            # Keep most recent (end of list)
            for item in reversed(context.get("session", [])):
                t = estimate_tokens(item)
                if curr_sess_toks + t > sess_budget:
                    break
                kept_session.insert(0, item)
                curr_sess_toks += t
            optimized_context["session"] = kept_session
        else:
            optimized_context["session"] = context.get("session", [])
            
        return optimized_context

context_optimizer = ContextOptimizer()
