import urllib.request, json

data = json.dumps({
    "name": "Ollama Worker",
    "type": "Worker",
    "model": "gemma3:4b",
    "provider": "ollama",
    "description": "Local Ollama agent for testing"
}).encode()

req = urllib.request.Request("http://localhost:8000/api/agents", data=data, headers={"Content-Type": "application/json"}, method="POST")
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
print("Agent created:", json.dumps(result, indent=2))

agents_req = urllib.request.Request("http://localhost:8000/api/agents")
agents_resp = urllib.request.urlopen(agents_req)
agents = json.loads(agents_resp.read())
print(f"\nTotal agents in DB: {len(agents)}")
for a in agents:
    print(f"  - {a.get('id','?')}: {a.get('name','?')} ({a.get('provider','?')} / {a.get('model','?') or a.get('model_name','?')})")
