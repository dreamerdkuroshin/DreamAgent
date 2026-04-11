"""
integrations/stripe_client.py

Stripe payment integration for DreamAgent Builder.
Powers checkout sessions, subscriptions, webhooks, and customer management.

Setup:
    pip install stripe

Usage:
    from integrations.stripe_client import get_stripe
    st = get_stripe()
    session = st.create_checkout_session(price_id="price_xxx", success_url="...", cancel_url="...")
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class StripeClient:
    """
    Wrapper around the Stripe Python SDK.
    Falls back gracefully if stripe package not installed.
    """

    def __init__(self, api_key: str, webhook_secret: str = ""):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self._stripe = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            import stripe as _stripe  # type: ignore
            _stripe.api_key = self.api_key
            self._stripe = _stripe
            self._available = bool(self.api_key)
            if self._available:
                logger.info("[Stripe] ✅ Stripe client initialized.")
            else:
                logger.warning("[Stripe] ⚠️  STRIPE_API_KEY not set.")
        except ImportError:
            logger.warning(
                "[Stripe] ⚠️  'stripe' package not installed. "
                "Run: pip install stripe"
            )
        except Exception as e:
            logger.error(f"[Stripe] ❌ Initialization failed: {e}")

    @property
    def available(self) -> bool:
        return self._available

    # ── Checkout ──────────────────────────────────────────────────────

    def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        mode: str = "subscription",
        customer_email: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session.

        Args:
            price_id: Stripe Price ID (e.g. 'price_1abc...')
            success_url: Redirect URL on payment success
            cancel_url: Redirect URL on payment cancel
            mode: 'subscription', 'payment', or 'setup'
            customer_email: Pre-fill customer email
            metadata: Extra metadata to attach to session

        Returns:
            Dict with 'session_id' and 'url' keys
        """
        if not self._available:
            return {"error": "Stripe not available"}
        try:
            params: Dict[str, Any] = {
                "mode": mode,
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
            if customer_email:
                params["customer_email"] = customer_email
            if metadata:
                params["metadata"] = metadata
            session = self._stripe.checkout.Session.create(**params)
            return {"session_id": session.id, "url": session.url}
        except Exception as e:
            logger.error(f"[Stripe] create_checkout_session error: {e}")
            return {"error": str(e)}

    # ── Customer management ────────────────────────────────────────────

    def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a Stripe Customer record."""
        if not self._available:
            return {"error": "Stripe not available"}
        try:
            params: Dict[str, Any] = {"email": email}
            if name:
                params["name"] = name
            if metadata:
                params["metadata"] = metadata
            customer = self._stripe.Customer.create(**params)
            return {"customer_id": customer.id, "email": customer.email}
        except Exception as e:
            logger.error(f"[Stripe] create_customer error: {e}")
            return {"error": str(e)}

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve a Stripe Customer by ID."""
        if not self._available:
            return {"error": "Stripe not available"}
        try:
            customer = self._stripe.Customer.retrieve(customer_id)
            return {"customer_id": customer.id, "email": customer.email, "name": customer.name}
        except Exception as e:
            return {"error": str(e)}

    # ── Subscriptions ─────────────────────────────────────────────────

    def get_subscriptions(self, customer_id: str) -> Dict[str, Any]:
        """List active subscriptions for a customer."""
        if not self._available:
            return {"error": "Stripe not available", "subscriptions": []}
        try:
            subs = self._stripe.Subscription.list(customer=customer_id, status="active")
            return {
                "subscriptions": [
                    {
                        "id": s.id,
                        "status": s.status,
                        "current_period_end": s.current_period_end,
                        "plan": s.plan.id if hasattr(s, "plan") else None,
                    }
                    for s in subs.data
                ]
            }
        except Exception as e:
            return {"error": str(e), "subscriptions": []}

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a Stripe subscription immediately."""
        if not self._available:
            return {"error": "Stripe not available"}
        try:
            sub = self._stripe.Subscription.cancel(subscription_id)
            return {"status": sub.status, "canceled_at": sub.canceled_at}
        except Exception as e:
            return {"error": str(e)}

    # ── Webhook verification ───────────────────────────────────────────

    def verify_webhook(self, payload: bytes, sig_header: str) -> Optional[Dict[str, Any]]:
        """
        Verify and parse a Stripe webhook event.

        Args:
            payload: Raw request body bytes
            sig_header: Stripe-Signature header value

        Returns:
            Parsed event dict, or None on failure
        """
        if not self._available or not self.webhook_secret:
            return None
        try:
            event = self._stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return dict(event)
        except self._stripe.error.SignatureVerificationError as e:
            logger.warning(f"[Stripe] Webhook signature invalid: {e}")
            return None
        except Exception as e:
            logger.error(f"[Stripe] Webhook parsing error: {e}")
            return None

    # ── Payment Intents ───────────────────────────────────────────────

    def create_payment_intent(self, amount_cents: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a PaymentIntent for direct payment flows."""
        if not self._available:
            return {"error": "Stripe not available"}
        try:
            params: Dict[str, Any] = {
                "amount": amount_cents,
                "currency": currency,
                "automatic_payment_methods": {"enabled": True},
            }
            if metadata:
                params["metadata"] = metadata
            intent = self._stripe.PaymentIntent.create(**params)
            return {"client_secret": intent.client_secret, "intent_id": intent.id}
        except Exception as e:
            return {"error": str(e)}

    # ── Health check ──────────────────────────────────────────────────

    def ping(self) -> Dict[str, Any]:
        """Quick connectivity test."""
        if not self._available:
            return {"status": "unavailable", "reason": "Stripe not installed or STRIPE_API_KEY missing"}
        try:
            # List 1 customer as a lightweight API call
            self._stripe.Customer.list(limit=1)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}


@lru_cache(maxsize=1)
def get_stripe() -> StripeClient:
    """Get a singleton StripeClient from environment config."""
    api_key = os.getenv("STRIPE_API_KEY", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_BUILDER", "") or os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not api_key:
        logger.warning("[Stripe] STRIPE_API_KEY not set in .env")
    return StripeClient(api_key=api_key, webhook_secret=webhook_secret)
