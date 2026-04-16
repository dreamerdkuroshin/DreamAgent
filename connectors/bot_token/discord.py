import requests
from connectors.bot_token.base_bot import BaseBotConnector


class DiscordBot(BaseBotConnector):

    def send_message(self, channel_id, message):

        url = f"https://discord.com/api/v1.0/channels/{channel_id}/messages"

        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }

        data = {
            "content": message
        }

        r = requests.post(url, headers=headers, json=data)

        return r.json()