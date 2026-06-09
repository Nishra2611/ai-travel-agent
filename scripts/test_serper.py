import requests
import os
from dotenv import load_dotenv

load_dotenv()

url = "https://google.serper.dev/search"

headers = {
    "X-API-KEY": os.getenv("SERPER_API_KEY"),
    "Content-Type": "application/json"
}

payload = {
    "q": "top tourist attractions Paris",
    "num": 5
}

response = requests.post(url, json=payload, headers=headers)
data = response.json()

print("Status Code:", response.status_code)

if response.status_code != 200:
    print("Error:")
    print(data)
    exit()

print("\nTop Results:")
for item in data.get("organic", [])[:3]:
    print("-", item["title"])

print("\n✓ Serper working")