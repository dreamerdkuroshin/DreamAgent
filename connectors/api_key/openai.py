import requests
from connectors.api_key.base_api import BaseAPIConnector


class OpenAIClient(BaseAPIConnector):

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def chat(self, prompt):

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        r = requests.post(self.BASE_URL, headers=headers, json=data)

        return r.json()