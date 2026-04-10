import requests
from connectors.api_key.base_api import BaseAPIConnector


class HuggingFaceClient(BaseAPIConnector):

    BASE_URL = "https://api-inference.huggingface.co/models"

    def run_model(self, model, text):

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        r = requests.post(
            f"{self.BASE_URL}/{model}",
            headers=headers,
            json={"inputs": text}
        )

        return r.json()