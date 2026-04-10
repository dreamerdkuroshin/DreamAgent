"""
backend/agents/manager_agent.py

The Bot Factory Manager:
- Analyses user intent
- Generates personality, name, and constraints
- Creates the bot in the DB
"""
import json
import logging
from typing import Optional, Dict
from backend.llm.universal_provider import UniversalProvider
from backend.services.bot_service import create_bot, get_bot_by_token
from backend.core.database import SessionLocal

logger = logging.getLogger(__name__)

class ManagerAgent:
    def __init__(self):
        self.llm = UniversalProvider(provider="auto")

    async def analyze_and_create(self, user_prompt: str, token: str, platform: str) -> Dict:
        """
        Parses a request like 'Make me a math teacher bot' and sets it up.
        """
        system_prompt = (
            "You are the DreamAgent Bot Factory Manager. "
            "Your job is to analyze a user request for a new AI bot and generate a JSON configuration. "
            "Output ONLY valid JSON with keys: 'name', 'personality', 'description'. "
            "The 'personality' should be a detailed set of rules (system prompt) for the specific bot. "
            "Be creative but strict about the user's constraints."
        )
        
        try:
            raw_response = await self.llm.complete(
                f"{system_prompt}\n\nUser Request: {user_prompt}"
            )
            # Find the JSON block
            if "```json" in raw_response:
                raw_response = raw_response.split("```json")[1].split("```")[0].strip()
            elif "{" in raw_response:
                raw_response = raw_response[raw_response.find("{"):raw_response.rfind("}")+1]

            config = json.loads(raw_response)
            
            db = SessionLocal()
            bot = create_bot(
                db, 
                name=config.get("name", "Custom Bot"),
                platform=platform,
                token=token,
                personality=config.get("personality", "You are a helpful AI.")
            )
            db.close()
            
            return {
                "success": True,
                "bot_id": bot.id,
                "name": bot.name,
                "personality": bot.personality,
                "integration_url": f"/api/v1/integrations/webhook/{platform}/{bot.id}"
            }

        except Exception as e:
            logger.error(f"[ManagerAgent] Error: {e}")
            return {"success": False, "error": str(e)}

manager_agent = ManagerAgent()
