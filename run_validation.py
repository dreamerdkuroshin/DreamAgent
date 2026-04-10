import asyncio
import sys
import io

sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from backend.tools.news import NewsAnalystTool, get_cached
from backend.orchestrator.priority_router import detect_intent

async def main():
    print('--- Intent Detection ---')
    print('Query: "latest geopolitical war updates in japan perspective"')
    print('Intent:', detect_intent('latest geopolitical war updates in japan perspective'))

    print('\n--- Testing Scraper Cascade + Logic ---')
    tool = NewsAnalystTool()
    
    # Intentionally messy, un-normalized query to test the Zero Result Loop -> Simple Query pipeline
    query = 'latest geopolitical war updates in japan perspective'
    
    try:
        res = await asyncio.wait_for(tool.arun(query), timeout=60)
        
        print("\n--- CACHE VERIFICATION ---")
        cached = get_cached(query.lower()) or get_cached("geopolitical war japan")
        if cached:
            print("✅ Successfully cached result in memory!")
        else:
            print("⚠️ Not found in cache.")
        
        print("\n[Result Final Markdown Fragment]:\n")
        # Print the first 500 characters to verify warning flags or markdown payload
        if len(res) > 500:
            print(res[:500] + "\n\n...[truncated]")
        else:
            print(res)
    except Exception as e:
        print("\nCaught Error/Timeout:", type(e).__name__, str(e))
    
if __name__ == '__main__':
    asyncio.run(main())
