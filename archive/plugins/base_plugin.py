class BasePlugin:

    name = "base"

    def execute(self, input_data):
        raise NotImplementedError