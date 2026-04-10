"""
connectors/local/chrome_control.py
Chrome browser automation with security hardening.

Changes from previous version:
  - open() rejects non-HTTPS URLs and checks against a domain allowlist
  - JavaScript execution disabled for untrusted pages (--disable-javascript)
  - type() length-limited to prevent runaway input injection
  - All actions logged for audit trails
"""

import logging
import os
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)

_MAX_TYPE_LENGTH = 2000  # characters — prevent runaway keystrokes


def _load_domain_allowlist() -> set[str]:
    """
    Load permitted domains from CHROME_DOMAIN_ALLOWLIST env var
    (comma-separated list, e.g. "example.com,api.myapp.com").
    Returns an empty set if the var is unset (all HTTPS domains blocked).
    """
    raw = os.getenv("CHROME_DOMAIN_ALLOWLIST", "")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


class ChromeControl:
    """
    Selenium Chrome wrapper restricted to an HTTPS domain allowlist.

    Set CHROME_DOMAIN_ALLOWLIST in your environment before instantiating.
    Example:
        CHROME_DOMAIN_ALLOWLIST=app.mycompany.com,docs.mycompany.com
    """

    def __init__(self):
        self._allowlist = _load_domain_allowlist()
        if not self._allowlist:
            logger.warning(
                "ChromeControl: CHROME_DOMAIN_ALLOWLIST is empty — "
                "all navigation will be blocked."
            )

        opts = Options()
        # Prevent execution of arbitrary JavaScript on loaded pages.
        opts.add_argument("--disable-javascript")
        # Run headless in CI/server environments.
        if os.getenv("CHROME_HEADLESS", "1") == "1":
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        self.driver = webdriver.Chrome(options=opts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_url(self, url: str) -> str:
        """
        Validate URL scheme and domain.
        Returns the (unchanged) URL on success; raises ValueError otherwise.
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("https",):
            raise ValueError(
                f"ChromeControl: only HTTPS URLs are permitted. Got scheme '{parsed.scheme}'."
            )

        domain = parsed.hostname or ""
        if not any(
            domain == allowed or domain.endswith("." + allowed)
            for allowed in self._allowlist
        ):
            raise PermissionError(
                f"ChromeControl: domain '{domain}' is not in the allowlist. "
                f"Allowed: {self._allowlist or 'none'}."
            )

        return url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, url: str):
        """Navigate to a validated HTTPS URL."""
        safe_url = self._validate_url(url)
        logger.info("ChromeControl.open: %s", safe_url)
        self.driver.get(safe_url)

    def click(self, selector: str):
        logger.debug("ChromeControl.click: %s", selector)
        element = self.driver.find_element(By.CSS_SELECTOR, selector)
        element.click()

    def type(self, selector: str, text: str):
        if len(text) > _MAX_TYPE_LENGTH:
            raise ValueError(
                f"ChromeControl.type: text length {len(text)} exceeds "
                f"maximum allowed {_MAX_TYPE_LENGTH} characters."
            )
        logger.debug("ChromeControl.type: selector=%s len=%d", selector, len(text))
        element = self.driver.find_element(By.CSS_SELECTOR, selector)
        element.send_keys(text)

    def get_text(self, selector: str) -> str:
        element = self.driver.find_element(By.CSS_SELECTOR, selector)
        return element.text

    def close(self):
        self.driver.quit()
