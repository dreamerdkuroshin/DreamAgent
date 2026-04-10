from connectors.base_connector import BaseConnector
import requests

class GmailConnector(BaseConnector):

    name = "gmail"
    BASE_URL = "https://gmail.googleapis.com/gmail/v1"

    def __init__(self, token=None):
        super().__init__(token)

    def list_messages(self, limit: int = 10, q: str = ""):
        """List Gmail messages.
        
        Args:
            limit: Maximum number of messages to return.
            q: Optional query string format specific to Gmail.
        """
        if not self.token:
            return {"error": "Gmail connector requires an OAuth token."}

        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        
        params = {"maxResults": limit}
        if q:
            params["q"] = q

        try:
            r = requests.get(
                f"{self.BASE_URL}/users/me/messages",
                headers=headers,
                params=params
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": f"Failed to list messages: {e}"}

    def execute(self, action, params=None):
        params = params or {}
        if action == "list_messages":
            return self.list_messages(
                limit=params.get("limit", 10),
                q=params.get("q", "")
            )
        return {"error": f"Unknown action: {action}"}