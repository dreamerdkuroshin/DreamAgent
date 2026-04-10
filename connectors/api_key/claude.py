import requests
from connectors.api_key.base_api import BaseAPIConnector


class ClaudeClient(BaseAPIConnector):

    BASE_URL = "https://api.anthropic.com/v1/messages"

    def chat(self, prompt):

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        data = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 500,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        r = requests.post(self.BASE_URL, headers=headers, json=data)

        return r.json()