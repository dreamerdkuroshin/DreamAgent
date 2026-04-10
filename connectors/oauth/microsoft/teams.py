import requests

class TeamsConnector:

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, token):
        self.token = token

    def list_teams(self):

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        r = requests.get(
            f"{self.BASE_URL}/me/joinedTeams",
            headers=headers
        )

        return r.json()
        
    def get_teams(self):
        """Deprecated: Use list_teams instead."""
        return self.list_teams()