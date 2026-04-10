import requests

class ExcelConnector:

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, token):
        self.token = token

    def list_files(self):

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        r = requests.get(
            f"{self.BASE_URL}/me/drive/root/children",
            headers=headers
        )

        return r.json()