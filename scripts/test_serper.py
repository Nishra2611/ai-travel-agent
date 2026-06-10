import requests
import os
from dotenv import load_dotenv

load_dotenv()
url = "https://google.serper.dev/search"
headers = {
    "X-API-KEY": os.getenv("SERPER_API_KEY"),
    "Content-Type": "application/json"
}
payload = {"q": "top tourist attractions Paris 2024", "num": 5}
r = requests.post(url, json=payload, headers=headers)
results = r.json()

for item in results.get('organic', [])[:3]:
    print(f"- {item['title']}")
print("Serper API working")
