"""
backend/agents/backend_generator.py

Responsible for taking a project plan and writing the backend logic files.
"""
import logging
import json
from typing import Dict, Any, Callable, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class BackendGeneratorAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm, role="backend_generator")

    async def run(self, plan: Dict[str, Any], publish_event: Optional[Callable] = None) -> Dict[str, str]:
        files_to_gen = plan.get("files_to_generate", [])
        
        # Determine backend files (exclude distinct UI files)
        backend_files = [f for f in files_to_gen if f.endswith(".py") or f.endswith(".java") or "server" in f.lower() or "api" in f.lower()]
        
        generated = {}
        for i, fname in enumerate(backend_files):
            if publish_event:
                publish_event({
                    "type": "builder_step",
                    "step": "backend_coding",
                    "progress": int(35 + (i / len(backend_files)) * 15),
                    "message": f"⚙️ Backend Generator writing {fname}..."
                })
            content = await self._generate_file(fname, plan, generated)
            if content:
                generated[fname] = content
                
        return generated

    async def _generate_file(self, filename: str, spec: Dict[str, Any], already_generated: Dict[str, str]) -> str:
        ext = filename.split(".")[-1]
        context = ""
        if already_generated:
            for k, v in list(already_generated.items())[:2]:
                context += f"\n--- Already generated: {k} ---\n{v[:2000]}\n"

        prompt = f"""You are an Expert Backend Engineer.
Generate the file: {filename}

Project spec:
- Name: {spec.get('project_name')}
- Key features: {spec.get('key_features', [])}
{context}

RULES:
1. Output ONLY the raw file content — no explanation, no markdown fences.
2. Focus on robust error handling, scalability, and security.
3. Provide valid logic that fits the project spec.
"""
        try:
            result = await self.think(prompt)
            result = result.strip()
            
            # strip markdown fences safely
            fences = [f"```{ext}", "```python", "```javascript", "```js", "```ts", "```"]
            for fence in fences:
                if result.startswith(fence):
                    result = result[len(fence):]
                    break
            if result.endswith("```"):
                result = result[:-3]
            return result.strip()
        except Exception as e:
            logger.error(f"[BackendGenerator] Failed for {filename}: {e}")
            return ""
