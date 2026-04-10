from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/webhook/slack")
async def slack_webhook(request: Request):
    import hmac
    import hashlib
    import os
    import time

    payload = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")
    secret = os.getenv("SLACK_SIGNING_SECRET")

    # Prevent replay attacks
    if timestamp and abs(time.time() - int(timestamp)) > 60 * 5:
        return {"status": "request too old"}, 401

    if secret and signature and timestamp:
        sig_base = f"v0:{timestamp}:".encode() + payload
        hash_object = hmac.new(secret.encode(), sig_base, hashlib.sha256)
        expected_signature = "v0=" + hash_object.hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return {"status": "invalid signature"}, 401

    payload_json = await request.json()

    # Slack URL verification
    if payload_json.get("type") == "url_verification":
        return {"challenge": payload_json["challenge"]}

    event = payload.get("event", {})

    if event.get("type") == "message":

        user = event.get("user")
        text = event.get("text")

        print("Slack message from", user)
        print("Message:", text)

    return {"status": "ok"}

async def slack_handler(payload):

    event = payload.get("event", {})

    if event.get("type") == "message":

        print("Slack message:", event.get("text"))

    return {"status": "slack processed"}