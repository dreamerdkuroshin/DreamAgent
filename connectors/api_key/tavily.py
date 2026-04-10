import requests
from connectors.api_key.base_api import BaseAPIConnector


class TavilyClient(BaseAPIConnector):

    BASE_URL = "https://api.tavily.com/search"

    def search(self, query):

        data = {
            "api_key": self.api_key,
            "query": query
        }

        r = requests.post(self.BASE_URL, json=data)

        return r.json()