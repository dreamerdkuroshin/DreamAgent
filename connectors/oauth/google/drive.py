import requests

class GoogleDriveConnector:

    BASE_URL = "https://www.googleapis.com/drive/v3"

    def __init__(self, token):
        self.token = token

    def list_files(self):

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        r = requests.get(
            f"{self.BASE_URL}/files",
            headers=headers
        )

        return r.json()