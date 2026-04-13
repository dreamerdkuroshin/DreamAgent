import httpx
import asyncio
import json

async def main():
    try:
        async with httpx.AsyncClient() as c:
            async with c.stream('GET', 'http://127.0.0.1:8001/api/v1/chat/stream?query=Should%20I%20build%20in%20public%20or%20stay%20private%3F&taskId=test&provider=auto', timeout=120.0) as r:
                async for line in r.aiter_lines():
                    print(line)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    asyncio.run(main())
