import requests
from connectors.api_key.base_api import BaseAPIConnector


class SupabaseClient(BaseAPIConnector):

    def __init__(self, url, api_key):
        super().__init__(api_key)
        self.url = url

    def get_tables(self):

        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}"
        }

        r = requests.get(
            f"{self.url}/rest/v1/",
            headers=headers
        )

        return r.json()