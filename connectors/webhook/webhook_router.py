from fastapi import APIRouter, Request
from connectors.webhook.webhook_registry import WebhookRegistry

router = APIRouter()
registry = WebhookRegistry()


@router.post("/webhook/{service}")
async def universal_webhook(service: str, request: Request):
    payload = await request.json()
    handler = registry.get_handler(service)
    if not handler:
        return {"error": "no handler registered"}
    return await handler(payload)