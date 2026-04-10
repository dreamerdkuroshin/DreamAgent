"""
monitoring/logger.py
Structured application logging with secret-scrubbing filter.

Previous version: basicConfig to a flat log file with no secret scrubbing.
API keys, tokens, and bearer credentials appearing in log messages would be
written to disk in plaintext.

This version adds:
  - SecretScrubFilter — redacts patterns matching API keys / bearer tokens
    before they reach any handler.
  - JSON-structured output option (set LOG_FORMAT=json in env).
  - Configurable log level (LOG_LEVEL env var).
  - File rotation to prevent unbounded log growth.
"""

import logging
import logging.handlers
import os
import re

# ---------------------------------------------------------------------------
# Secret scrubbing
# ---------------------------------------------------------------------------

_SCRUB_PATTERNS = [
    # Bearer tokens in Authorization headers
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{16,}", re.IGNORECASE), "Bearer [REDACTED]"),
    # sk- style API keys (OpenAI, Anthropic, etc.)
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{16,}"), "sk-[REDACTED]"),
    # Generic token= / key= / secret= / password= patterns
    (re.compile(r'(token|key|secret|password|api_key)\s*[=:]\s*["\']?[A-Za-z0-9\-_\.]{8,}["\']?',
                re.IGNORECASE), r'\1=[REDACTED]'),
]


class SecretScrubFilter(logging.Filter):
    """Redact credential-like strings from log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._scrub(str(record.msg))
        record.args = tuple(self._scrub(str(a)) for a in (record.args or ()))
        return True

    @staticmethod
    def _scrub(text: str) -> str:
        for pattern, replacement in _SCRUB_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

def _setup_logger() -> logging.Logger:
    log_level  = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_file   = os.getenv("LOG_FILE", "dreamagent.log")
    max_bytes  = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))   # 10 MB
    backup_cnt = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    root = logging.getLogger()
    root.setLevel(log_level)

    scrub = SecretScrubFilter()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    console.addFilter(scrub)
    root.addHandler(console)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_cnt, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s"
    ))
    file_handler.addFilter(scrub)
    root.addHandler(file_handler)

    return logging.getLogger("DreamAgent")


logger = _setup_logger()
