"""
backend/api/security.py

Centralized Security Layer for Webhook Validations.
"""
import time
import hmac
import hashlib
import logging
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

logger = logging.getLogger(__name__)

def verify_discord(public_key_hex: str, signature: str, timestamp: str, body: bytes) -> bool:
    """Verifies ed25519 interactions signature sent by Discord."""
    if not public_key_hex or not signature or not timestamp:
        return False
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False
    except Exception as e:
        logger.error(f"[Security] Discord signature verification failed: {e}")
        return False

def verify_slack(signing_secret: str, signature: str, timestamp: str, body: bytes) -> bool:
    """Verifies the x-slack-signature."""
    if not signing_secret or not signature or not timestamp:
        return False
    
    # Check for replay attacks (> 5 mins)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except ValueError:
        return False
        
    sig_basestring = f"v0:{timestamp}:" + body.decode('utf-8')
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

def verify_whatsapp(mode: str, verify_token: str, expected_token: str) -> bool:
    """Verifies WhatsApp Cloud API GET Handshake."""
    return mode == "subscribe" and verify_token == expected_token
