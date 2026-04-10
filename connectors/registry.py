import pkgutil
import importlib

CONNECTORS = {
    "gmail":       "connectors.oauth.google.gmail.GmailConnector",
    "notion":      "connectors.oauth.notion.NotionConnector",
    "slack":       "connectors.oauth.slack.SlackConnector",
    "stripe":      "connectors.api_key.stripe.StripeConnector",
    "telegram":    "connectors.bot_token.telegram.TelegramBot",
    "teams":       "connectors.oauth.microsoft.teams.TeamsConnector",
    "excel":       "connectors.oauth.microsoft.excel.ExcelConnector",
    "word":        "connectors.oauth.microsoft.word.WordConnector",
    "powerpoint":  "connectors.oauth.microsoft.powerpoint.PowerPointConnector",
}


class ConnectorRegistry:

    def __init__(self):
        self.connectors = {}

    def load_connectors(self):
        """Import each connector by its dotted path and store it."""
        for name, dotted_path in CONNECTORS.items():
            try:
                module_path, class_name = dotted_path.rsplit(".", 1)
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                self.connectors[name] = cls
            except Exception as e:
                print(f"[ConnectorRegistry] Could not load '{name}': {e}")

    def get(self, name):
        return self.connectors.get(name)