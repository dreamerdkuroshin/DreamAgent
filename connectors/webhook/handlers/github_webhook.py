from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/webhook/github")
async def github_webhook(request: Request):
    import hmac
    import hashlib
    import os

    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    if secret and signature:
        hash_object = hmac.new(secret.encode(), payload, hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return {"status": "invalid signature"}, 401

    payload_json = await request.json()
    event = request.headers.get("X-GitHub-Event")

    if event == "push":

        repo = payload["repository"]["name"]
        commits = payload["commits"]

        print("Push to repo:", repo)

        for commit in commits:
            print("Commit:", commit["message"])

    elif event == "pull_request":

        pr = payload["pull_request"]["title"]

        print("New PR:", pr)

    return {"status": "received"}

async def github_handler(payload):

    repo = payload["repository"]["name"]

    print("Repository:", repo)

    for commit in payload.get("commits", []):

        print("Commit:", commit["message"])

    return {"status": "github processed"}