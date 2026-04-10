import asyncio
import sys
import io

import os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from backend.orchestrator.priority_router import detect_intent
from backend.tools.news import NewsAnalystTool
from backend.api.chat_worker import split_tasks

async def main():
    print('--- Intent Debug ---')
    print('war:', detect_intent('give me news about war'))
    print('japanese hindi:', detect_intent('मुझे जापान की खबर हिंदी में बताओ'))
    print('pizza:', detect_intent('build website for pizza shop'))
    
    print('\n--- Split Tasks ---')
    tasks = split_tasks('1. latest tech news\n2. summarize it\nThen do something else')
    for i, t in enumerate(tasks):
        print(f'{i+1}. {t}')
        
    print('\n--- News Tool Language parsing --')
    tool = NewsAnalystTool()
    try:
        res = await tool.arun('मुझे जापान की खबर हिंदी में बताओ')
        print(res[:200] + '...' if len(res)>200 else res)
    except Exception as e:
        print(f"Error in tool.arun: {e}")
    
if __name__ == '__main__':
    asyncio.run(main())
