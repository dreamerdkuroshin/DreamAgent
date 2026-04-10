from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, messages: list):
        pass

    @abstractmethod
    def stream(self, messages: list):
        pass
