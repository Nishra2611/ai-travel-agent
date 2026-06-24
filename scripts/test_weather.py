import os

import requests
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
r = requests.get(url, params=params)
data = r.json()
print(f"City: {data['city']['name']}")
print(f"Temp: {data['list'][0]['main']['temp']}C")
print(f"Weather: {data['list'][0]['weather'][0]['description']}")
print("OpenWeatherMap API working")
