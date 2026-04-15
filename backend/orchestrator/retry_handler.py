"""
backend/orchestrator/retry_handler.py

Provides HTTP 429 handling, explicitly returning structured RETRY signals 
to ensure background workers defer execution without blocking threads.
"""
from typing import Dict, Any, Callable
import time
import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

# Global rate limit tracker [provider -> next_available_timestamp]
# In a highly distributed environment, this would be a Redis keyspace.
# For now, memory dictionary if single process or backed by Redis logic if available.
_PROVIDER_RATELIMITS: Dict[str, float] = {}

def get_provider_available_at(provider: str) -> float:
    return _PROVIDER_RATELIMITS.get(provider, 0.0)

def set_provider_rate_limit(provider: str, retry_after_sec: int):
    _PROVIDER_RATELIMITS[provider] = time.time() + retry_after_sec

async def with_retry(
    provider_name: str, 
    func: Callable, 
    *args, 
    **kwargs
) -> Dict[str, Any]:
    """
    Wraps an async function to gracefully handle 429 errors.
    Returns standard 'success' map or an explicit dict instructing a backoff.
    """
    now = time.time()
    next_avail = get_provider_available_at(provider_name)
    
    if now < next_avail:
        wait_time = int(next_avail - now)
        logger.warning(f"[RateLimit] Pre-emptively deferring {provider_name} request for {wait_time}s.")
        return {
            "action": "retry_later",
            "retry_after": wait_time,
            "max_retries": 3,
            "backoff": "linear"
        }

    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            retry_after_str = e.response.headers.get("Retry-After", "10")
            try:
                retry_after = int(retry_after_str)
            except ValueError:
                retry_after = 10
                
            set_provider_rate_limit(provider_name, retry_after)
            
            logger.warning(f"[RateLimit] Hit 429 on {provider_name}. Backing off for {retry_after}s.")
            return {
                "action": "retry_later",
                "retry_after": retry_after,
                "max_retries": 3,
                "backoff": "exponential"
            }
        raise e
