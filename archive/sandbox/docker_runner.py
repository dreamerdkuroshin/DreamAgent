"""
sandbox/docker_runner.py
Docker container execution with guaranteed temp file cleanup.

Previous version: on TimeoutExpired, the exception handler returned early
without entering a finally block, leaving temp files on disk and potentially
leaving containers running.

This version wraps everything in a single try/finally to guarantee cleanup
regardless of how the subprocess exits.
"""

import logging
import os
import subprocess
import tempfile
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DockerRunner:
    """Execute Python code in an isolated Docker container."""

    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image

    def run(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run code in a Docker container with resource limits.

        Returns a dict with keys: success, output, error_output, return_code.
        Guarantees that the host temp file is always removed, even on timeout.
        """
        temp_path = None
        try:
            # Write code to a temp file; will be bind-mounted read-only.
            with tempfile.NamedTemporaryFile(
                suffix=".py", delete=False, mode="w", encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = os.path.abspath(f.name)

            cmd = [
                "docker", "run", "--rm",
                "--network", "none",          # no internet access
                "--memory", "128m",
                "--memory-swap", "128m",      # no swap either
                "--cpus", "0.5",
                "--read-only",
                "--tmpfs", "/tmp:size=16m",   # writable /tmp for stdlib tempfiles
                "--label", "dreamagent_sandbox=true",
                "-v", f"{temp_path}:/tmp/code.py:ro",
                self.image,
                "python", "/tmp/code.py",
            ]

            result_data: Dict[str, Any] = {}
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                result_data = {
                    "success": proc.returncode == 0,
                    "output": proc.stdout,
                    "error_output": proc.stderr,
                    "return_code": proc.returncode,
                }
            except subprocess.TimeoutExpired as exc:
                logger.warning("DockerRunner: execution timed out after %ds.", timeout)
                # Kill lingering containers spawned by this runner.
                self._kill_sandbox_containers()
                result_data = {
                    "success": False,
                    "output": (getattr(exc, "stdout", None) or b"").decode("utf-8", errors="replace"),
                    "error_output": f"Execution timed out after {timeout} seconds.",
                    "return_code": -1,
                }
            except Exception as exc:
                logger.error("DockerRunner: unexpected error: %s", exc)
                result_data = {
                    "success": False,
                    "output": "",
                    "error_output": str(exc),
                    "return_code": -1,
                }

            return result_data

        finally:
            # Always clean up the host temp file.
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as e:
                    logger.warning("DockerRunner: could not remove temp file '%s': %s", temp_path, e)

    def _kill_sandbox_containers(self) -> None:
        """Force-remove any running containers labelled as sandbox containers."""
        try:
            ps_result = subprocess.run(
                ["docker", "ps", "-q", "-f", "label=dreamagent_sandbox=true"],
                capture_output=True, text=True, timeout=5,
            )
            for cid in ps_result.stdout.strip().splitlines():
                if cid:
                    subprocess.run(["docker", "kill", cid], capture_output=True, timeout=5)
        except Exception as e:
            logger.warning("DockerRunner: error killing sandbox containers: %s", e)

    def cleanup(self) -> None:
        """Remove ALL stopped sandbox containers (call at shutdown)."""
        try:
            ps_result = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", "label=dreamagent_sandbox=true"],
                capture_output=True, text=True,
            )
            for cid in ps_result.stdout.strip().splitlines():
                if cid:
                    subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
        except Exception as e:
            logger.warning("DockerRunner: cleanup error: %s", e)
