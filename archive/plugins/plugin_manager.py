class PluginManager:

    def __init__(self):
        self.plugins = {}

    def register(self, plugin):
        self.plugins[plugin.name] = plugin

    def execute(self, name, data):
        if name not in self.plugins:
            raise Exception("Plugin not found")

        return self.plugins[name].execute(data)
        