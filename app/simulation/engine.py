"""
Simulation utilities — mock driver factors, scoring helpers, geometry.
No external API calls are made here; everything is deterministic given a seed.
When USE_REAL_API=true, the real driver_factors module is used instead.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

                                                                                
            
                                                                                

LAT_MIN    = 6.5
LAT_MAX    = 35.5
LON_MIN    = 68.0
LON_MAX    = 97.5
BASE_SPEED = 60.0             
MAX_DIST   = 3500.0                                    


                                                                                
           
                                                                                

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two lat/lon points."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def rand_loc(rng: random.Random) -> Tuple[float, float]:
    """Sample a random lat/lon within India's bounding box."""
    return (
        round(rng.uniform(LAT_MIN, LAT_MAX), 4),
        round(rng.uniform(LON_MIN, LON_MAX), 4),
    )


                                                                                
                         
 
                                                                               
                                                                      
                                                       
                                                                                

def _geo_hash(lat: float, lon: float) -> int:
    """Stable integer hash from a lat/lon grid cell (5 km cells)."""
    cell_lat = round(lat * 20) / 20          
    cell_lon = round(lon * 20) / 20
    return hash((round(cell_lat, 2), round(cell_lon, 2))) & 0xFFFFFF


def mock_traffic_score(lat: float, lon: float) -> float:
    """
    Returns a plausible traffic score 0.4 → 1.0.
    Urban centres (higher population density proxies) get lower scores.
    """
    seed = _geo_hash(lat, lon) ^ 0xABCD12
    rng  = random.Random(seed)
                                                                                
    urban_proximity = max(0.0, 1.0 - abs(lat - 19.0) / 13.0) * max(0.0, 1.0 - abs(lon - 78.0) / 10.0)
    base = rng.uniform(0.55, 1.0)
    return round(max(0.35, base - urban_proximity * 0.35), 4)


def mock_weather_score(lat: float, lon: float) -> float:
    """
    Returns a plausible weather score 0.5 → 1.0.
    Coastal and north-eastern regions get slightly harsher weather.
    """
    seed = _geo_hash(lat, lon) ^ 0xF00D42
    rng  = random.Random(seed)
    coastal = max(0.0, 1.0 - min(abs(lon - 72.0), abs(lon - 80.0), abs(lon - 88.0)) / 5.0)
    base = rng.uniform(0.65, 1.0)
    return round(max(0.50, base - coastal * 0.25), 4)


def mock_news_score(lat: float, lon: float) -> float:
    """
    Returns a plausible news disruption score 0.6 → 1.0.
    Randomly seeded per cell so some regions appear more disrupted.
    """
    seed = _geo_hash(lat, lon) ^ 0x1337BE
    rng  = random.Random(seed)
    return round(rng.uniform(0.60, 1.0), 4)


                                                                                
                        
                                                                                

def get_mock_driver_factors(
    drivers: List[Dict],
    src_lat: float,
    src_lon: float,
) -> List[Dict]:
    """
    Return a list of factor dicts for each driver using mock signals.
    This mirrors the interface of the real get_driver_factors() in
    app/utils/driver_factors.py but requires no external API calls.
    """
    result = []
    for d in drivers:
        dist = haversine(d["lat"], d["lon"], src_lat, src_lon)
        ts   = mock_traffic_score(d["lat"], d["lon"])
        ws   = mock_weather_score(d["lat"], d["lon"])
        ns   = mock_news_score(d["lat"], d["lon"])
        eff  = round(BASE_SPEED * ts * ws * ns, 2)
        result.append({
            "driver_id":     d["id"],
            "distance_km":   round(dist, 3),
            "capacity_kg":   d["capacity"],
            "traffic_score": ts,
            "weather_score": ws,
            "news_score":    ns,
            "effective_speed": eff,
        })
    return result


                                                                                
                  
                                                                                

def compute_driver_score(factor: Dict) -> float:
    """
    Composite score used to rank drivers:
        effective_speed − distance_penalty

    Lower distance → higher score (prefer nearby drivers).
    """
    distance_penalty = (factor["distance_km"] / MAX_DIST) * 5.0
    return factor["effective_speed"] - distance_penalty


def pick_best_driver_index(factors: List[Dict]) -> int:
    """Return the index of the highest-scoring driver."""
    return max(range(len(factors)), key=lambda i: compute_driver_score(factors[i]))


                                                                                
                                     
                                                                                

def init_drivers(n: int, rng: random.Random) -> List[Dict]:
    """Initialise a pool of n drivers with random locations and capacities."""
    return [
        {
            "id":       i,
            "lat":      round(rng.uniform(LAT_MIN, LAT_MAX), 4),
            "lon":      round(rng.uniform(LON_MIN, LON_MAX), 4),
            "capacity": round(rng.uniform(100.0, 1000.0), 1),
        }
        for i in range(n)
    ]


def init_assignment(idx: int, rng: random.Random) -> Dict:
    """Create a single delivery assignment with random src/dest/goods."""
    sl, slo = rand_loc(rng)
    dl, dlo = rand_loc(rng)
    goods   = round(rng.uniform(200.0, 5000.0), 1)
    return {
        "id":                 idx,
        "src_lat":            sl,
        "src_lon":            slo,
        "dest_lat":           dl,
        "dest_lon":           dlo,
        "total_goods_kg":     goods,
        "remaining_goods_kg": goods,
    }
