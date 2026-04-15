import urllib.request
import urllib.parse
import json

prompt = "Conduct research on Gen Z UI trends. Assert that Gen Z hates simple UI and only wants complex, highly animated interfaces."
q = urllib.parse.quote(prompt)
# Testing with trust_mode=truth
url = f"http://127.0.0.1:8001/api/v1/chat/stream?query={q}&taskId=truth_test_1&provider=auto&trust_mode=truth"

print("Triggering Truth Engine Test:", url)
try:
    with urllib.request.urlopen(url, timeout=300) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    etype = data.get("type")
                    if etype == "status":
                        print(f"STATUS: {data.get('content')}")
                    elif etype == "truth_metrics":
                        print(f"TRUTH METRICS: Score={data.get('score')} | Status={data.get('status')} | Contradictions={data.get('contradictions')}")
                    elif etype == "step":
                        print(f"STEP: {data.get('content')[:100]}...")
                    elif etype == "final":
                        print("\nFINAL RESULT RECEIVED.")
                        # Check for the Scorecard
                        if "System Intelligence Scorecard" in data.get("content", ""):
                            print("Scorecard Detected in Output.")
                        if "[⚠️ Source does not support claim]" in data.get("content", ""):
                            print("Semantic Judge Corrected a claim!")
                except:
                    pass
except Exception as e:
    print("Test Failed:", e)
