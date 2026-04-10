"""
backend/api/webhook_handlers.py

Unified Response Dispatcher for all Webhook Platforms.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

# ── PLATFORM SENDERS ────────────────────────────────────────────────────────

async def _discord_send(application_id: str, token: str, text: str):
    url = f"https://discord.com/api/v10/webhooks/{application_id}/{token}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"content": text[:2000]})
    except Exception as exc:
        logger.warning(f"[Webhook] Discord followup failed: {exc}")

async def _slack_send(bot_token: str, channel: str, text: str):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json; charset=utf-8"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, headers=headers, json={"channel": channel, "text": text})
    except Exception as exc:
        logger.warning(f"[Webhook] Slack send failed: {exc}")

async def _wa_send(access_token: str, phone_number_id: str, recipient: str, text: str):
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, headers=headers, json=payload)
    except Exception as exc:
        logger.warning(f"[Webhook] WhatsApp send failed: {exc}")

async def _tg_send(token: str, chat_id: str, text: str, parse_mode: str = "Markdown"):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 400 and "parse_mode" in resp.text:
                payload["parse_mode"] = ""
                await client.post(url, json=payload)
    except Exception as exc:
        logger.warning(f"[Webhook] Telegram send failed: {exc}")

async def _tg_typing(token: str, chat_id: str):
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={"chat_id": chat_id, "action": "typing"})
    except Exception:
        pass


# ── UNIFIED DISPATCHER ───────────────────────────────────────────────────────

async def send_response(platform: str, user_id: str, text: str, **kwargs):
    """Route outgoing reply to the correct platform API."""
    if platform == "telegram":
        await _tg_send(kwargs.get("token"), user_id, text)
    elif platform == "slack":
        await _slack_send(kwargs.get("token"), user_id, text)
    elif platform == "discord":
        await _discord_send(kwargs.get("application_id"), kwargs.get("interaction_token"), text)
    elif platform == "whatsapp":
        await _wa_send(kwargs.get("token"), kwargs.get("phone_id"), user_id, text)
    else:
        logger.error(f"[Dispatcher] Unknown platform '{platform}'")
