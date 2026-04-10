import sys
import os
import asyncio
import logging

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure the backend module can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable debug logging so we can see LLM failures
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from backend.tools.news import NewsAnalystTool

def test():
    tool = NewsAnalystTool()
    print("\n=== Running NewsAnalystTool with query: 'give me news about lebanon' ===\n")
    try:
        result = tool.run("give me news about lebanon")
        print("\n=== RESULT ===")
        print(result[:3000] if len(result) > 3000 else result)
    except Exception as e:
        import traceback
        print(f"\n=== ERROR ===")
        traceback.print_exc()

if __name__ == "__main__":
    test()
