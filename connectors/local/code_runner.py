import subprocess

class CodeRunner:

    def run_python(self, code):
        """
        Runs Python code inside a Docker sandbox for safety.
        """
        try:
            result = subprocess.run(
                ["docker", "exec", "dreamagent_sandbox", "python3", "-c", code],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error executing code in sandbox: {e.stderr}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"