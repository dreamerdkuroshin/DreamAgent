class BaseBotConnector:

    def __init__(self, token):
        self.token = token

    def start(self):
        raise NotImplementedError

    def send_message(self, message):
        raise NotImplementedError