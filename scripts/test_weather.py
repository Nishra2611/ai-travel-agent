import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

url = "https://api.openweathermap.org/data/2.5/forecast"

params = {
    "q": "Paris,FR",
    "appid": API_KEY,
    "units": "metric",
    "cnt": 7
}

response = requests.get(url, params=params)
data = response.json()

if response.status_code != 200:
    print("API Error:")
    print(data)
    exit()

print(f"City: {data['city']['name']}")
print(f"Temp: {data['list'][0]['main']['temp']}°C")
print(f"Weather: {data['list'][0]['weather'][0]['description']}")
print("✓ OpenWeatherMap working")