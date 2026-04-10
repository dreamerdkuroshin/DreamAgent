class MCPServerManager:

    def __init__(self):
        self.servers = {}

    def add_server(self, name, url):

        self.servers[name] = url

    def get_server(self, name):

        return self.servers.get(name)