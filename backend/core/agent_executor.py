import logging
from backend.llm.universal_provider import UniversalProvider

logger = logging.getLogger(__name__)

def create_task(intent, query, task_id=None, **kwargs):
    """
    Task Creator logic wrapper. Links the intention to the real dispatcher.
    """
    from backend.core.task_router import dispatch_task
    import uuid
    import asyncio
    
    tid = task_id or str(uuid.uuid4())
    payload = {
        "task_id": tid,
        "query": query,
        "intent": intent,
        "file_ids": kwargs.get("file_ids", ""),
        "convo_id": kwargs.get("convo_id"),
        "provider": kwargs.get("provider", "auto"),
        "model": kwargs.get("model", "")
    }
    
    # We enqueue this via our intelligent multi-queue load balancer
    # Because we're in async, we schedule it or await it.
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(dispatch_task(payload))
    else:
        loop.run_until_complete(dispatch_task(payload))
        
    return tid


async def general_llm(query: str) -> str:
    llm = UniversalProvider()
    return await llm.complete(query)


async def news_agent(query: str) -> str:
    """Wrapper to call the News tool directly"""
    from backend.tools.news import NewsAnalystTool
    tool = NewsAnalystTool()
    return await tool.arun(query)


async def builder_agent(query: str) -> str:
    """Wrapper for builder logic (mock implementation for architecture)"""
    return "Building logic delegated to ultra agent or dedicated builder."


async def self_heal(intent: str, query: str, error: Exception) -> str:
    logger.warning(f"⚠️ Self-heal triggered for {intent}: {error}")
    
    if intent == "news":
        return await general_llm(f"Please provide recent news about: {query}")
        
    return f"Error executing task. {str(error)}"


async def execute_agent(intent: str, query: str) -> str:
    """
    Layer 3 — Tool Execution + Monitoring
    The production-level autonomous agent execution layer.
    """
    try:
        if intent == "news":
            return await news_agent(query)
            
        elif intent == "builder":
            return await builder_agent(query)
            
        else:
            return await general_llm(query)
            
    except Exception as e:
        return await self_heal(intent, query, e)
