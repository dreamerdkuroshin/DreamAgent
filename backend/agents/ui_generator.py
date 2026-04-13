"""
backend/agents/ui_generator.py

Responsible for taking a project plan and writing the frontend UI files.
"""
import logging
import json
from typing import Dict, Any, Callable, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class UIGeneratorAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm, role="ui_generator")

    async def run(self, plan: Dict[str, Any], publish_event: Optional[Callable] = None) -> Dict[str, str]:
        files_to_gen = plan.get("files_to_generate", ["index.html"])
        ui_files = [
            f for f in files_to_gen
            if any(e in f.lower() for e in [".html", ".css", ".jsx", ".tsx", ".js"])
            and "server" not in f.lower()
            and "main.py" not in f.lower()
        ]
        
        generated = {}
        for i, fname in enumerate(ui_files):
            if publish_event:
                publish_event({
                    "type": "builder_step",
                    "step": "ui_coding",
                    "progress": int(20 + (i / len(ui_files)) * 15),
                    "message": f"🎨 UI Generator writing {fname}..."
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

        prompt = f"""You are an Expert UI Frontend Developer.
Generate the file: {filename}

Project spec:
- Name: {spec.get('project_name')}
- Sections: {", ".join(spec.get('sections', []))}
- Color palette: {spec.get('color_palette')}
- Font: {spec.get('font', 'Inter')}
- Key features: {spec.get('key_features', [])}
{context}

RULES:
1. Output ONLY the raw file content — no explanation, no markdown fences.
2. Make it incredibly beautiful, responsive, and production-quality.
3. Use the specified colors and font.
4. Ensure the file is standalone if needed.
"""
        try:
            result = await self.think(prompt)
            result = result.strip()
            
            # strip markdown fences safely
            fences = [f"```{ext}", "```html", "```css", "```js", "```jsx", "```tsx", "```"]
            for fence in fences:
                if result.startswith(fence):
                    result = result[len(fence):]
                    break
            if result.endswith("```"):
                result = result[:-3]
            return result.strip()
        except Exception as e:
            logger.error(f"[UIGenerator] Failed for {filename}: {e}")
            return ""
