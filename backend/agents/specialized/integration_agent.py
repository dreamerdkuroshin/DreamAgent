"""
backend/agents/specialized/integration_agent.py

IntegrationAgent — An agent that detects bot tokens in the user's prompt,
extracts them, and automatically starts the requested bot locally.
"""
import logging
import json
import requests
from ..executor import ExecutorAgent

logger = logging.getLogger(__name__)

INTEGRATION_SYSTEM = """You are an Integration Agent.
Your job is to identify if the user is providing an API token, authentication key, or a bot token (like Telegram, Discord, Tavily, OpenAI, etc).
Extract the platform/service name and the exact token perfectly without any markdown, and output a JSON array of objects.
Do not output anything other than valid JSON. Do not wrap in ```json.

Determine the 'type' field:
- Use 'bot' if it belongs to a chat platform (telegram, discord, slack, whatsapp).
- Use 'api' for generic tool/model keys (openai, tavily, anthropic, ahrefs, supabase, stripe, mistral, groq).

Example input: "this is my telegram bot token now 1234:AAHg... start it"
Example output:
[
  {"platform": "telegram", "token": "1234:AAHg...", "type": "bot"}
]

Example input: "Here is my Tavily API key: tvly-12345"
Example output:
[
  {"platform": "tavily", "token": "tvly-12345", "type": "api"}
]
"""

class IntegrationAgent(ExecutorAgent):
    """Executor that saves tokens, starts bots, and configures API keys."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools)
        self.role = "integration_agent"

    async def execute(self, step: str, context: str = "") -> str:
        prompt = f"Extract the platform and token from this text:\n\n{step}\n\nOutput only a JSON array."
        response = await self.think(prompt, system=INTEGRATION_SYSTEM)
        response = str(response).strip().strip("`").strip("json").strip()
        
        logger.info("[IntegrationAgent] Parsed: %s", response)
        try:
            items = json.loads(response)
        except Exception as e:
            return f"❌ Failed to parse tokens from user prompt. LLM output: {response}"

        results = []
        for item in items:
            platform = item.get("platform", "").lower()
            token = item.get("token", "")
            itype = item.get("type", "bot")
            
            if not platform or not token:
                continue

            if itype == "bot":
                try:
                    from backend.api.integrations import _start_bot, _load_tokens, _save_tokens, _ts
                    import os
                    from pathlib import Path

                    env_key = f"{platform.upper()}_BOT_TOKEN"
                    os.environ[env_key] = token

                    # Save to .env
                    env_path = Path(__file__).parent.parent.parent.parent / ".env"
                    if env_path.exists():
                        current = env_path.read_text()
                        if env_key in current:
                            lines = [line if not line.startswith(f"{env_key}=") else f"{env_key}={token}" for line in current.splitlines()]
                            env_path.write_text("\n".join(lines) + "\n")
                        else:
                            with env_path.open("a") as f:
                                f.write(f"\n{env_key}={token}\n")
                    else:
                        env_path.write_text(f"{env_key}={token}\n")

                    # Use native _start_bot
                    tokens = _load_tokens()
                    tokens[platform] = {"token": token, "saved_at": _ts()}
                    _save_tokens(tokens)

                    data = _start_bot(platform, token)
                    if data.get("started"):
                        results.append(f"✅ Successfully started {platform.capitalize()} bot (PID: {data.get('pid')}).")
                    elif data.get("already_running"):
                        results.append(f"ℹ️ {platform.capitalize()} bot is already running.")
                    else:
                        results.append(f"❌ Failed to start {platform.capitalize()} bot: {data.get('error', 'Unknown Error')}")
                except Exception as e:
                    results.append(f"❌ Error communicating with backend for {platform}: {e}")
            else:
                # Generic API key logic (Tavily, OpenAI, etc)
                import os
                from pathlib import Path
                
                env_key = f"{platform.upper()}_API_KEY"
                os.environ[env_key] = token
                
                # Append to .env file
                env_path = Path(__file__).parent.parent.parent.parent / ".env"
                if env_path.exists():
                    current = env_path.read_text()
                    if env_key in current:
                        # naive replace
                        lines = [line if not line.startswith(f"{env_key}=") else f"{env_key}={token}" for line in current.splitlines()]
                        env_path.write_text("\n".join(lines) + "\n")
                    else:
                        with env_path.open("a") as f:
                            f.write(f"\n{env_key}={token}\n")
                else:
                    env_path.write_text(f"{env_key}={token}\n")
                    
                results.append(f"✅ Successfully saved {platform.capitalize()} API key and configured the environment.")

        if not results:
            return "No valid API keys or Bot tokens found."
        return "\n".join(results)

    def _get_system_prompt(self) -> str:
        return INTEGRATION_SYSTEM
