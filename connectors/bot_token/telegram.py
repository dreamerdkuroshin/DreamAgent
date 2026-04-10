import requests
from connectors.bot_token.base_bot import BaseBotConnector


class TelegramBot(BaseBotConnector):

    def send_message(self, chat_id, text):

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        data = {
            "chat_id": chat_id,
            "text": text
        }

        r = requests.post(url, json=data)

        return r.json()