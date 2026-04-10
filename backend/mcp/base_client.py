"""
backend/mcp/base_client.py
Abstract Client enforcing the MCP tool protocol.
"""
from abc import ABC, abstractmethod

class BaseMCPClient(ABC):
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def list_tools(self):
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict):
        pass

    @abstractmethod
    async def close(self):
        pass
