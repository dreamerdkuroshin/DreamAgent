import urllib.request
import urllib.parse
prompt = "Build and launch a simple AI product in 3 steps. Constraints: - You must use real-time research for market data. - You must generate code for a landing page. - You must validate your own output. Now simulate a failure in the research step and continue execution."
q = urllib.parse.quote(prompt)
url = f"http://127.0.0.1:8001/api/v1/chat/stream?query={q}&taskId=chaos1&provider=auto"
print("Triggering:", url)
try:
    with urllib.request.urlopen(url, timeout=300) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if line:
                print(line)
except Exception as e:
    print("Failed", e)
