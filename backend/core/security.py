"""
backend/core/security.py
Handles strict AES-256 Fernet encryption for API keys and tokens to prevent
raw credentials from ever touching the database or logs.
"""
import os
import logging
from cryptography.fernet import Fernet
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load env in case it wasn't loaded
load_dotenv()

def _get_or_create_key() -> bytes:
    """
    Retrieves the ENCRYPTION_KEY.
    If run in PROD, missing key strictly fails to prevent unrecoverable DB scenarios.
    If run in DEV, auto-generates and appends to .env to protect against restart data-loss.
    """
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    if key:
        return key.encode()

    # Fail fast if PROD
    env = os.getenv("ENV", "development").lower()
    if env in ["production", "prod"]:
        raise RuntimeError("CRITICAL ERROR: 'ENCRYPTION_KEY' not found in environment. Refusing to start in PROD.")

    # Auto-generate for Dev
    new_key = Fernet.generate_key()
    
    # Try to persist it to .env
    env_path = Path(".env")
    try:
        if not env_path.exists():
            env_path.write_text(f"ENCRYPTION_KEY={new_key.decode()}\n")
        else:
            with env_path.open("a") as f:
                f.write(f"\nENCRYPTION_KEY={new_key.decode()}\n")
        
        # Inject to live env
        os.environ["ENCRYPTION_KEY"] = new_key.decode()
        logger.warning("Auto-generated ENCRYPTION_KEY for development and saved to .env.")
    except Exception as e:
        logger.error(f"Failed to persist auto-generated ENCRYPTION_KEY: {e}. Keys will be lost on restart!")
    
    return new_key


_FERNET = None
try:
    _FERNET = Fernet(_get_or_create_key())
except Exception as e:
    logger.error(f"Security Configuration Failed: {e}")
    raise


def encrypt_token(token: str) -> str:
    """Encrypts a string strictly with Fernet."""
    if not token:
        return ""
    return _FERNET.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypts a Fernet string. Returns empty string on failure (e.g. rotated key)."""
    if not encrypted_token:
        return ""
    try:
        return _FERNET.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.warning(
            "Failed to decrypt API key — key may have been rotated or regenerated. "
            "Re-save your API keys in Settings to re-encrypt them with the current key."
        )
        return ""  # Return empty so callers fall back to env-var lookup
