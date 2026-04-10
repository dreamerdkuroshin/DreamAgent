from base_plugin import BasePlugin

class WebSearchPlugin(BasePlugin):

    name = "web_search"

    def execute(self, query):
        return f"Searching web for {query}"