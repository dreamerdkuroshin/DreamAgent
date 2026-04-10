from abc import ABC, abstractmethod

class Tool(ABC):

    @abstractmethod
    def run(self, input: str):
        pass
