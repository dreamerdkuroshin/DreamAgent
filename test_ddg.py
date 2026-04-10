from duckduckgo_search import DDGS
import traceback

try:
    with DDGS() as ddgs:
        results = list(ddgs.text("today news", max_results=5))
        with open("test_ddg.txt", "w", encoding="utf-8") as f:
            f.write(str(results))
except Exception as e:
    with open("test_ddg.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
