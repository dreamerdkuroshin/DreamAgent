from fastapi import APIRouter, Request, Header
import stripe
import os

router = APIRouter()

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET
        )

    except stripe.error.SignatureVerificationError:
        return {"status": "invalid signature"}

    event_type = event["type"]

    if event_type == "payment_intent.succeeded":
        payment = event["data"]["object"]

        print("Payment successful:", payment["amount"])

    elif event_type == "customer.created":
        customer = event["data"]["object"]

        print("New customer:", customer["email"])

    return {"status": "success"}

async def stripe_handler(payload):

    event_type = payload.get("type")

    if event_type == "payment_intent.succeeded":

        payment = payload["data"]["object"]

        print("Payment success:", payment["amount"])

    return {"status": "stripe processed"}