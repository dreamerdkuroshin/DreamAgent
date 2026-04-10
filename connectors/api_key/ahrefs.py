import requests
from connectors.api_key.base_api import BaseAPIConnector


class AhrefsClient(BaseAPIConnector):

    BASE_URL = "https://apiv2.ahrefs.com"

    def backlinks(self, domain):

        params = {
            "token": self.api_key,
            "target": domain,
            "from": "backlinks",
            "mode": "domain"
        }

        r = requests.get(self.BASE_URL, params=params)

        return r.json()