"""Registry for webhook handlers."""


class WebhookRegistry:
    """Registry that maps webhook names to their handler functions."""

    def __init__(self):
        self.handlers: dict = {}

    def register(self, name: str, handler) -> None:
        """Register a webhook handler.

        Args:
            name: Webhook identifier.
            handler: Callable to invoke when the webhook fires.
        """
        self.handlers[name] = handler

    def get(self, name: str):
        """Get a handler by name (short alias)."""
        return self.handlers.get(name)

    def get_handler(self, name: str):
        """Get a handler by name (explicit alias kept for backward compatibility)."""
        return self.handlers.get(name)

    def list_handlers(self):
        """Return all registered webhook names."""
        return list(self.handlers.keys())