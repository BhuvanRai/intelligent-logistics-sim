"""Traffic mock module (placeholder for real API via TOMTOM_API_KEY)"""
import os
import random

def get_traffic(lat: float, lon: float, api_key: str = None) -> dict:
                                                                 
    if not api_key:
        api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key or api_key == "your_tomtom_key_here":
        return {
            "current_speed": random.uniform(20.0, 55.0),
            "free_flow_speed": 60.0,
            "confidence": 1.0,
            "road_closure": False
        }
                                                                             
    return {}
