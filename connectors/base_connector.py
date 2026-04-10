"""Base connector class for all DreamAgent connectors."""


class BaseConnector:
    """Base class for all service connectors."""

    name = "base"

    def __init__(self, token=None):
        self.token = token

    def is_available(self) -> bool:
        """Check if the connector is properly configured and available."""
        return self.token is not None

    def connect(self) -> None:
        """Establish connection to the service."""
        pass

    def authenticate(self) -> None:
        """Authenticate with the service."""
        pass

    def execute(self, action: str, params: dict = None):
        """Execute an action on the service.

        Args:
            action: Action name to execute.
            params: Optional parameters for the action.

        Raises:
            NotImplementedError: Subclasses must implement this.
        """
        raise NotImplementedError(f"Connector '{self.name}' must implement execute()")

    def disconnect(self) -> None:
        """Disconnect from the service."""
        pass