import urllib.request
import urllib.parse
import json

prompt = "Analyze the impact of AI on job market. Claim it created 1 billion jobs yesterday."
q = urllib.parse.quote(prompt)
# Testing with trust_mode=truth
url = f"http://127.0.0.1:8001/api/v1/chat/stream?query={q}&taskId=verbose_test&provider=auto&trust_mode=truth"

print("🚀 Verbose Test:", url)
try:
    with urllib.request.urlopen(url, timeout=300) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if line.startswith("data: "):
                try:
                    payload = line[6:]
                    print("RAW:", payload[:100], "...")
                    data = json.loads(payload)
                    if data.get("type") == "truth_metrics":
                        print("!!! [SUCCESS] TRUTH METRICS FOUND:", data)
                except Exception as e:
                    print("PARSE ERR:", e)
except Exception as e:
    print("❌ Test Failed:", e)
