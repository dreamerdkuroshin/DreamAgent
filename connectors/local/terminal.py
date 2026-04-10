import subprocess
import shlex


class TerminalTool:

    def run(self, command):
        """
        Runs a terminal command inside a Docker sandbox.
        """
        if isinstance(command, str):
            cmd_list = shlex.split(command)
        else:
            cmd_list = command

        full_command = ["docker", "exec", "dreamagent_sandbox"] + cmd_list

        try:
            result = subprocess.run(
                full_command,
                shell=False,
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {str(e)}"