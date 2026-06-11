from amadeus import Client, ResponseError
import os
from dotenv import load_dotenv

load_dotenv()
amadeus = Client(
    client_id=os.getenv("AMADEUS_CLIENT_ID"),
    client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
    hostname='test'
)

try:
    response = amadeus.shopping.flight_offers_search.get(
        originLocationCode='BOM',
        destinationLocationCode='CDG',
        departureDate='2025-12-01',
        adults=1,
        max=3
    )
    print(f"Found {len(response.data)} flights")
    print(response.data[0]['price'])
    print("Amadeus API working")
except ResponseError as e:
    print(f"Error: {e.response.body}")
