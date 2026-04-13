"""
backend/agents/debate_agent.py

DebateAgent — Synthesizes two opposing viewpoints to arrive at a nuanced conclusion.
"""
import logging
from typing import Optional
from .base_agent import BaseAgent
import asyncio

logger = logging.getLogger(__name__)

DEBATE_SYSTEM = """You are a Strict Logic Validator Agent.
Your job is to read two opposing arguments.
DO NOT randomly summarize. You MUST:
1. Identify exactly where the two personas contradict each other fundamentally.
2. Evaluate which side's logic is stronger based on realism vs. assumption.
3. Deliver a specific Final Verdict that declares why one structural argument defeats the other (or what hyper-specific hybrid approach is needed).
"""

PERSONA_SYSTEM = """You are participating in a debate. 
Given a question and a specific persona, you must argue passionately and logically from that persona's perspective.
Provide 2-3 strong points. Be concise but persuasive.
"""

class DebateAgent(BaseAgent):
    """
    Spawns multiple personas to debate a topic, then synthesizes a conclusion.
    """

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools, role="debate")

    async def debate(self, question: str, publish=None) -> str:
        """
        Orchestrates an internal debate between two personas and synthesizes the result.
        """
        logger.info(f"[DebateAgent] Triggering debate for: {question[:50]}...")
        
        # 1. Ask Planner/LLM to generate 2 opposing personas
        persona_prompt = f"Given this question to debate: '{question}', name two opposing expert personas that should argue it. Format: 'Persona 1: [Name] - [Stance]\\nPersona 2: [Name] - [Stance]'"
        personas_text = await self.think(persona_prompt)
        
        try:
            lines = [line.strip() for line in personas_text.strip().split("\\n") if "Persona" in line]
            persona1 = lines[0] if len(lines) > 0 else "Persona 1: Aggressive Growth Hacker"
            persona2 = lines[1] if len(lines) > 1 else "Persona 2: Cautious Foundation Builder"
        except:
            persona1 = "Persona 1: Aggressive Growth Hacker"
            persona2 = "Persona 2: Cautious Foundation Builder"

        if publish:
            publish({
                "type": "agent", "agent": "debate", "role": "system",
                "status": "running", "content": f"🔀 Spawning Debate:\\n{persona1}\\n{persona2}"
            })

        # 2. Get arguments from both personas concurrently
        async def _get_argument(persona: str):
            p = f"QUESTION: {question}\\nYOUR PERSONA: {persona}\\nArgue your stance."
            return await self.think(p, system=PERSONA_SYSTEM)

        arg1, arg2 = await asyncio.gather(
            _get_argument(persona1),
            _get_argument(persona2)
        )

        if publish:
            publish({
                "type": "agent", "agent": "debate", "role": "system",
                "status": "running", "content": f"🛡️ Arguments generated. Validator synthesizing..."
            })

        # 3. Synthesize
        synth_prompt = (
            f"QUESTION: {question}\n\n"
            f"ARGUMENT 1 ({persona1}):\n{arg1}\n\n"
            f"ARGUMENT 2 ({persona2}):\n{arg2}\n\n"
            f"Synthesize the strongest points from both into a nuanced final verdict."
        )
        
        synthesis = await self.think(synth_prompt, system=DEBATE_SYSTEM)
        
        final_output = (
            f"## Debate Analysis\n\n"
            f"**{persona1}**\n{arg1}\n\n"
            f"**{persona2}**\n{arg2}\n\n"
            f"### ⚖️ Validator Final Verdict\n{synthesis}"
        )
        
        return final_output
