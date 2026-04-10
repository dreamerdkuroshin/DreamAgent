import asyncio
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

class Sandbox:
    """Isolates agent code execution. Defaults to subprocess if docker is not enabled in ENV."""
    def __init__(self):
        self.mode = os.getenv("SANDBOX_MODE", "subprocess").lower()

    async def run(self, code: str) -> str:
        if self.mode == "docker":
            return await self._run_docker(code)
        else:
            return await self._run_subprocess(code)

    async def _run_docker(self, code: str) -> str:
        logger.info("Running code in Docker sandbox...")
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "run", "--rm",
                "--memory=100m",
                "--cpus=0.5",
                "python:3.11",
                "python", "-c", code,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return stdout.decode() or stderr.decode()
        except Exception as e:
            logger.error(f"Docker sandbox failed: {e}")
            return f"Sandbox execution error: {e}"

    async def _run_subprocess(self, code: str) -> str:
        logger.info("Running code in Subprocess sandbox...")
        try:
            process = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            try:
                # 10 second timeout
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
                return stdout.decode() + "\n" + stderr.decode()
            except asyncio.TimeoutError:
                process.kill()
                return "Execution timed out (10s) ❌"
        except Exception as e:
            logger.error(f"Subprocess sandbox failed: {e}")
            return f"Sandbox execution error: {e}"
