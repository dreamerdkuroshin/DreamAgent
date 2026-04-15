import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

# Set up paths so we can import backend
import sys
import os
# Ensure root is in path
sys.path.append(os.getcwd())

from backend.agents.tool_agent import ToolAgent
from backend.agents.autonomous.autonomous_manager import AutonomousManager
from backend.agents.autonomous.events import AgentEvent
from backend.tools.notion_tool import create_learning_tracker

class TestOAuthResiliency(unittest.IsolatedAsyncioTestCase):

    @patch("backend.oauth.oauth_manager.get_active_token", new_callable=AsyncMock)
    async def test_tool_agent_reauth_json(self, mock_get_token):
        """Verify that ToolAgent returns a JSON reauth_required on missing token."""
        mock_get_token.return_value = None
        
        agent = ToolAgent()
        # Mocking the tool_registry entry for slack_message
        result = await agent.execute_tool(
            "slack_message", 
            user_id="test_user", 
            bot_id="test_bot", 
            channel="general", 
            text="hello"
        )
        
        data = json.loads(result)
        self.assertEqual(data["action"], "reauth_required")
        self.assertEqual(data["provider"], "slack")
        print("SUCCESS: ToolAgent reauth JSON verified.")

    @patch("backend.agents.autonomous.autonomous_manager.create_plan", new_callable=AsyncMock)
    async def test_autonomous_manager_reauth_event(self, mock_create_plan):
        """Verify that AutonomousManager yields an oauth_reconnect event on missing token."""
        # Mock a simple one-step plan
        mock_create_plan.return_value = [
            {"id": 1, "action": "Send slack message", "tool": "slack_message", "status": "pending"}
        ]
        
        provider = MagicMock()
        provider.get_chat_completion = AsyncMock(return_value="OK")
        manager = AutonomousManager(provider=provider)
        
        # Mock the executor to return a reauth_required action
        manager.executor.execute_step = AsyncMock(return_value={
            "action": "reauth_required",
            "provider": "slack",
            "message": "Auth needed"
        })
        
        events = []
        async for event in manager.stream("test_user", "test_bot", "Send a message"):
            events.append(event)
            
        # Check if any event has type 'oauth_reconnect'
        reconnect_events = [e for e in events if e["type"] == "oauth_reconnect"]
        self.assertTrue(len(reconnect_events) > 0)
        self.assertEqual(reconnect_events[0]["data"]["provider"], "slack")
        print("SUCCESS: AutonomousManager reauth event verified.")

    @patch("backend.oauth.oauth_manager.get_active_token", new_callable=AsyncMock)
    async def test_notion_tool_reauth_dict(self, mock_get_token):
        """Verify that Notion Tool returns a reauth_required dict on missing token."""
        mock_get_token.return_value = None
        
        result = create_learning_tracker(
            topic="Testing", 
            explanation="Test", 
            exercises=["Ex 1"],
            user_id="test_user",
            bot_id="test_bot"
        )
        
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "reauth_required")
        self.assertEqual(result["provider"], "notion")
        print("SUCCESS: Notion Tool reauth dict verified.")

if __name__ == "__main__":
    unittest.main()
