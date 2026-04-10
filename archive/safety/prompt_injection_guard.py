"""
safety/prompt_injection_guard.py
Hardened prompt injection detector.

Improvements over previous version:
  - Unicode NFKC normalisation before pattern matching
    (defeats homoglyph substitution: ｉｇｎｏｒｅ → ignore)
  - Bidirectional text override stripping (U+202A–U+202E, U+2066–U+2069)
  - Base64 payload heuristic detection
  - sanitize() now applies all the same normalisations, not just delimiter removal
  - sanitize() is clearly documented as defence-in-depth, not a sole gate
"""

import base64
import logging
import re
import unicodedata
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bidirectional control characters (common in text-direction attacks)
# ---------------------------------------------------------------------------
_BIDI_CHARS = re.compile(
    r"[\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]"
)

# ---------------------------------------------------------------------------
# Injection patterns
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: List[Tuple[str, str]] = [
    # Instruction override
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?", "instruction_override"),
    (r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?", "instruction_override"),
    (r"forget\s+(everything|all|your\s+previous)", "instruction_override"),
    (r"new\s+(task|instruction|directive)\s*:", "instruction_override"),

    # Role injection / jailbreaks
    (r"\byou\s+are\s+(now\s+)?(a\s+|an\s+)?(DAN|evil|unrestricted|jailbroken)", "role_injection"),
    (r"\bact\s+as\s+(a\s+|an\s+)?(DAN|evil|unrestricted)", "role_injection"),
    (r"pretend\s+(you\s+)?(have\s+no|without)\s+restrictions?", "role_injection"),
    (r"you\s+have\s+no\s+restrictions?", "role_injection"),
    (r"developer\s+mode\s+(enabled|on|activated)", "role_injection"),

    # System prompt exfiltration
    (r"repeat\s+(your\s+)?(system\s+prompt|instructions)", "exfiltration_attempt"),
    (r"print\s+(your\s+)?(system\s+prompt|instructions)", "exfiltration_attempt"),
    (r"reveal\s+(your\s+)?(system\s+prompt|instructions|secrets?)", "exfiltration_attempt"),
    (r"output\s+(your\s+)?(full\s+)?(system\s+prompt|instructions)", "exfiltration_attempt"),

    # Prompt delimiter injection
    (r"<\|system\|>|<\|user\|>|<\|assistant\|>", "delimiter_injection"),
    (r"\[INST\]|\[/INST\]", "delimiter_injection"),
    (r"###\s*(System|Instruction|Prompt)\s*:", "delimiter_injection"),

    # Data exfiltration via URLs
    (r"https?://\S+\?(.*&)?(token|key|secret|password)=", "url_exfiltration"),
]

_COMPILED_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), label)
    for pat, label in _INJECTION_PATTERNS
]

# Base64 heuristic — strings ≥ 40 chars that are valid base64 and decode to
# something containing injection keywords.
_B64_MIN_LEN = 40
_B64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_B64_INJECTION_KEYWORDS = re.compile(
    r"ignore|disregard|forget|system\s*prompt|jailbreak|DAN",
    re.IGNORECASE,
)


def _normalise(text: str) -> str:
    """
    Normalise Unicode and strip bidirectional control characters.

    NFKC collapses full-width/ligature variants to their ASCII equivalents,
    defeating homoglyph substitution.  Bidi strip removes invisible direction
    overrides that can visually conceal injection text.
    """
    text = _BIDI_CHARS.sub("", text)
    return unicodedata.normalize("NFKC", text)


def _check_base64_payloads(text: str) -> List[str]:
    """Return detected labels for any base64-encoded injection payloads."""
    labels = []
    for match in _B64_RE.finditer(text):
        candidate = match.group()
        try:
            decoded = base64.b64decode(candidate + "==").decode("utf-8", errors="replace")
            if _B64_INJECTION_KEYWORDS.search(decoded):
                labels.append("base64_encoded_injection")
                logger.warning(
                    "PromptInjectionGuard: base64 payload contains injection keywords."
                )
        except Exception:
            pass
    return labels


class PromptInjectionGuard:
    """Detect and mitigate prompt injection attacks."""

    def __init__(self):
        self.patterns = _COMPILED_PATTERNS

    def detect_injection(self, text: str) -> Tuple[bool, List[str]]:
        """
        Detect potential prompt injection attempts.

        Normalises the text before pattern matching so that homoglyph and
        bidi-override evasions are caught.

        Returns:
            (is_injection, detected_labels)
        """
        if not text or not isinstance(text, str):
            return False, []

        normalised = _normalise(text)
        detected: List[str] = []

        for pattern, label in self.patterns:
            if pattern.search(normalised):
                detected.append(label)
                logger.warning(
                    "PromptInjectionGuard: detected '%s' in input.", label
                )

        detected.extend(_check_base64_payloads(normalised))

        return bool(detected), list(dict.fromkeys(detected))  # dedupe, preserve order

    def sanitize(self, text: str) -> str:
        """
        Best-effort sanitisation.

        IMPORTANT: This is defence-in-depth only.  Always run detect_injection()
        first and REJECT inputs that return is_injection=True.  Never rely on
        sanitize() as the sole line of defence.

        Steps applied:
          1. Strip bidi override characters.
          2. NFKC unicode normalisation.
          3. Remove known delimiter tokens.
          4. Collapse excess whitespace.
        """
        if not text or not isinstance(text, str):
            return text or ""

        # Step 1 + 2: normalise
        sanitized = _normalise(text)

        # Step 3: strip known delimiter tokens
        sanitized = re.sub(
            r"<\|system\|>|<\|user\|>|<\|assistant\|>",
            "", sanitized, flags=re.IGNORECASE,
        )
        sanitized = re.sub(r"\[INST\]|\[/INST\]", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(
            r"###\s*(System|Instruction|Prompt)\s*:", "[removed]", sanitized, flags=re.IGNORECASE
        )

        # Step 4: collapse whitespace
        sanitized = re.sub(r"\s{3,}", "  ", sanitized).strip()

        return sanitized
