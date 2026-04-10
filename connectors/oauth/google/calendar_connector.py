import requests

class GoogleCalendarConnector:

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    def __init__(self, token):
        self.token = token

    def list_events(self):

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        r = requests.get(
            f"{self.BASE_URL}/calendars/primary/events",
            headers=headers
        )

        return r.json()