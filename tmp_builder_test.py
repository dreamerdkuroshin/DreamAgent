import requests
import json

url = "http://127.0.0.1:8001/api/v1/builder/build"
data = {
    "name": "Untitled",
    "type": "landing",
    "features": ["auth"],
    "database": {"enabled": False, "type": "sqlite"},
    "purpose": "none",
    "products": [],
    "contact": {"address": "", "phone": "", "email": ""},
    "socials": [],
    "footer": "",
    "design": "modern",
    "audience": [],
    "pages": ["home"],
    "backend": False
}

try:
    response = requests.post(url, json=data)
    print("Status Code:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Exception:", str(e))
