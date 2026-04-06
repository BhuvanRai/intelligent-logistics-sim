"""Weather API mock module (placeholder for WeatherAPI)"""
import os
import random

def get_latest_weather(lat: float, lon: float) -> dict:
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key or api_key == "your_weatherapi_key_here":
        return {
            "condition": {"text": random.choice(["clear", "partly cloudy", "light rain"])},
            "wind_kph": random.uniform(5.0, 25.0)
        }
    return {}
