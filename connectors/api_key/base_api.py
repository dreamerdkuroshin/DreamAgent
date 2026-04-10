"""Base class for API-key authenticated connectors."""


class BaseAPIConnector:
    """Connector base for services that use a static API key."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def request(self, method: str = "GET", endpoint: str = "", **kwargs):
        """Make an authenticated request to the service.

        Subclasses should override this with the appropriate HTTP call.

        Raises:
            NotImplementedError: Subclasses must implement this.
        """
        raise NotImplementedError("Subclasses must implement request()")