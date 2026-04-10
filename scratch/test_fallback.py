import asyncio
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm.universal_provider import UniversalProvider

async def test_fallback():
    print("Testing UniversalProvider Fallback...")
    # Initialize with 'auto' provider
    provider = UniversalProvider(provider="auto", mode="AUTO")
    
    prompt = "Reply with exactly 'FIX_VERIFIED' if you can hear me."
    print(f"Prompt: {prompt}")
    
    try:
        response = await provider.complete(prompt)
        print(f"Response: {response}")
        print(f"Final Provider: {provider.final_provider}")
        print(f"Final Model: {provider.final_model}")
    except Exception as e:
        print(f"Caught Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_fallback())
