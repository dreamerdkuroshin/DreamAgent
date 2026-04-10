import requests
from connectors.oauth.oauth_base import OAuthBase

class SlackConnector(OAuthBase):

    AUTH_URL = "https://slack.com/oauth/v2/authorize"
    TOKEN_URL = "https://slack.com/api/oauth.v2.access"

    def __init__(self, token=None, client_id=None, client_secret=None, redirect_uri=None):
        self.token = token
        if client_id and client_secret and redirect_uri:
            super().__init__(client_id, client_secret, redirect_uri)

    def get_auth_url(self):
        scopes = [
            "chat:write",
            "channels:read",
            "users:read",
            "team:read",
            "files:read",
            "reactions:read"
        ]
        scope_str = " ".join(scopes)
        return f"{self.AUTH_URL}?client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope={scope_str}&response_type=code"

    def get_token(self, code):
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        response = requests.post(self.TOKEN_URL, data=data)
        return response.json()

    def list_channels(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get("https://slack.com/api/conversations.list", headers=headers)
        return response.json()

    def list_users(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get("https://slack.com/api/users.list", headers=headers)
        return response.json()

    def send_message(self, channel, text):
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "channel": channel,
            "text": text
        }
        response = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=data)
        return response.json()

    def execute(self, action, params=None):
        params = params or {}
        if action == "list_channels":
            return self.list_channels()
        elif action == "list_users":
            return self.list_users()
        elif action == "send_message":
            return self.send_message(params.get("channel"), params.get("text"))
        return {"error": "Unknown action"}
