"""
backend/agents/specialized/shell_agent.py

ShellAgent — An agent that can run terminal/shell commands locally.
Used by the autonomous loop for tasks like "run this script", "install a package", etc.
"""
import asyncio
import logging
from ..executor import ExecutorAgent

logger = logging.getLogger(__name__)

SHELL_SYSTEM = """You are a Shell Agent with the ability to run terminal commands on the local machine.
When given a task:
1. Determine the appropriate shell command to accomplish it.
2. Output ONLY the shell command to run, nothing else (no markdown, no explanation).
3. If the task requires multiple commands, chain them with && (Unix) or ; (Windows).
4. Only output commands safe for local execution. Never use rm -rf / or similar destructive commands.

Example task: "Check Python version"
Example output: python --version
"""


class ShellAgent(ExecutorAgent):
    """Executor that can run local shell commands."""

    def __init__(self, llm, memory=None, tools=None):
        super().__init__(llm, memory, tools)
        self.role = "shell_agent"

    async def execute(self, step: str, context: str = "") -> str:
        """
        1. Ask LLM to derive the shell command for this step.
        2. Run it and return the combined stdout/stderr.
        """
        # Step 1: Ask the LLM what command to run
        cmd_prompt = f"Task: {step}\n\nWhat shell command(s) should I run to accomplish this? Output ONLY the command, nothing else."
        command = await self.think(cmd_prompt, system=SHELL_SYSTEM)
        command = command.strip().strip("`").strip()

        # Strip markdown fences if the LLM wrapped it
        if command.startswith("```"):
            lines = command.splitlines()
            command = "\n".join(lines[1:-1]).strip()

        logger.info("[ShellAgent] Running command: %s", command[:120])

        # Step 2: Actually execute it safely
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                proc.kill()
                output = "[TIMEOUT] Command exceeded 30s limit."
                exit_code = -1

            result = f"$ {command}\n\n{output.strip()}\n\n[Exit code: {exit_code}]"
            logger.info("[ShellAgent] Done. Exit=%d, output=%d chars", exit_code, len(output))
            return result
        except Exception as e:
            logger.error("[ShellAgent] Error: %s", e)
            return f"$ {command}\n\n[ERROR] {e}"

    def _get_system_prompt(self) -> str:
        return SHELL_SYSTEM
