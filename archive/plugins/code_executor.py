from plugins.base_plugin import BasePlugin
import subprocess
import tempfile

class CodeExecutorPlugin(BasePlugin):

    name = "code_executor"

    def execute(self, code):

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".py"
        ) as f:

            f.write(code.encode())
            file_path = f.name

        result = subprocess.run(
            ["python", file_path],
            capture_output=True,
            text=True
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr
        }