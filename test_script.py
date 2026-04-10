import asyncio
from backend.agents.specialized.web_agent import WebAgent
import traceback

async def main():
    try:
        wa = WebAgent()
        res = await wa.search("today news")
        with open("test_out.txt", "w", encoding="utf-8") as f:
            f.write(res)
    except Exception as e:
        with open("test_out.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())

asyncio.run(main())
