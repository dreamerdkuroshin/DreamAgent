import requests
from connectors.oauth.oauth_base import OAuthBase

class NotionConnector(OAuthBase):

    AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.notion.com/v1/oauth/token"

    def __init__(self, token=None, client_id=None, client_secret=None, redirect_uri=None):
        self.token = token
        if client_id and client_secret and redirect_uri:
            super().__init__(client_id, client_secret, redirect_uri)

    def get_auth_url(self):
        return f"{self.AUTH_URL}?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&owner=user"

    def get_token(self, code):
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        auth = (self.client_id, self.client_secret)
        response = requests.post(self.TOKEN_URL, data=data, auth=auth)
        return response.json()

    def list_databases(self):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28"
        }
        response = requests.get("https://api.notion.com/v1/databases", headers=headers)
        return response.json()

    def search(self, query):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28"
        }
        data = {"query": query}
        response = requests.post("https://api.notion.com/v1/search", headers=headers, json=data)
        return response.json()

    def get_page(self, page_id):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28"
        }
        response = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers)
        return response.json()

    def create_page(self, parent_id, properties):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28"
        }
        data = {
            "parent": {"database_id": parent_id},
            "properties": properties
        }
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
        return response.json()

    def execute(self, action, params=None):
        params = params or {}
        if action == "list_databases":
            return self.list_databases()
        elif action == "search":
            return self.search(params.get("query"))
        elif action == "get_page":
            return self.get_page(params.get("page_id"))
        elif action == "create_page":
            return self.create_page(params.get("parent_id"), params.get("properties"))
        return {"error": "Unknown action"}
