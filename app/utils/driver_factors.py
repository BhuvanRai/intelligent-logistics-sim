import math
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.utils.traffic import get_traffic
from app.utils.weather import get_latest_weather
from app.utils.news import get_shipway_results

GRID_KM   = 5.0
GRID_DEG  = GRID_KM / 111.0
BASE_SPEED = 60.0

WEATHER_PENALTY = {
    "sunny": 0.00, "clear": 0.00, "partly cloudy": 0.03,
    "cloudy": 0.05, "overcast": 0.05, "mist": 0.10,
    "fog": 0.20, "freezing fog": 0.30,
    "light rain": 0.10, "moderate rain": 0.20,
    "heavy rain": 0.30, "torrential": 0.40,
    "light snow": 0.20, "moderate snow": 0.35,
    "heavy snow": 0.50, "blizzard": 0.65,
    "thunderstorm": 0.35, "sleet": 0.25,
    "haze": 0.08, "smoke": 0.10, "dust": 0.12, "sandstorm": 0.40,
}

SEVERITY_MAP     = {"low": 1, "medium": 2, "high": 3, "critical": 4}
NEWS_MAX_DELAY   = 0.50


def _snap(lat, lon):
    return (round(lat / GRID_DEG) * GRID_DEG,
            round(lon / GRID_DEG) * GRID_DEG)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _traffic_score(data):
    if not data or "error" in data:
        return 1.0
    if data.get("road_closure"):
        return 0.0
    cur = data.get("current_speed", 0)
    ff  = data.get("free_flow_speed", 1)
    if ff <= 0 or cur <= 0:
        return 1.0
    return min(1.0, cur / ff)


def _weather_score(data):
    if not data or "error" in data:
        return 1.0
    cond    = data.get("condition", {}).get("text", "").lower()
    penalty = max((v for k, v in WEATHER_PENALTY.items() if k in cond), default=0.0)
    wind    = data.get("wind_kph", 0)
    if wind > 60:
        penalty += ((wind - 60) / 10.0) * 0.02
    return max(0.0, 1.0 - penalty)


def _news_score(lat, lon, events):
    total = 0.0
    for ev in events:
        sev = SEVERITY_MAP.get(str(ev.get("severity", "low")).lower(), 0)
        if sev <= 1:
            continue
        radius = ev.get("radius_km", 0)
        if radius <= 0:
            continue
        dist = haversine(lat, lon, ev["center_lat"], ev["center_lon"])
        if dist >= radius:
            continue
        proximity = 1.0 - (dist / radius)
        sev_scale = (sev - 1) / 3.0
        total += proximity * sev_scale * NEWS_MAX_DELAY
    return 1.0 / (1.0 + min(total, NEWS_MAX_DELAY))


def get_driver_factors(drivers, src_lat, src_lon):
    news_events = get_shipway_results(1000)

    unique_cells = {}
    for d in drivers:
        key = _snap(d["lat"], d["lon"])
        if key not in unique_cells:
            unique_cells[key] = (d["lat"], d["lon"])

    src_key = _snap(src_lat, src_lon)
    if src_key not in unique_cells:
        unique_cells[src_key] = (src_lat, src_lon)

    traffic_cache = {}
    weather_cache = {}

    def fetch(key, lat, lon):
        return key, get_traffic(lat, lon), get_latest_weather(lat, lon)

    with ThreadPoolExecutor(max_workers=min(40, len(unique_cells))) as pool:
        futures = {
            pool.submit(fetch, k, lat, lon): k
            for k, (lat, lon) in unique_cells.items()
        }
        for fut in as_completed(futures):
            try:
                key, traffic, weather = fut.result(timeout=6)
                traffic_cache[key] = traffic
                weather_cache[key] = weather
            except Exception:
                pass

    result = []
    for d in drivers:
        key     = _snap(d["lat"], d["lon"])
        traffic = traffic_cache.get(key, {})
        weather = weather_cache.get(key, {})
        dist    = haversine(d["lat"], d["lon"], src_lat, src_lon)

        result.append({
            "driver_id":     d["id"],
            "lat":           d["lat"],
            "lon":           d["lon"],
            "capacity_kg":   d["capacity"],
            "distance_km":   round(dist, 3),
            "traffic_score": round(_traffic_score(traffic), 4),
            "weather_score": round(_weather_score(weather), 4),
            "news_score":    round(_news_score(d["lat"], d["lon"], news_events), 4),
            "effective_speed": BASE_SPEED * _traffic_score(traffic) * _weather_score(weather) * _news_score(d["lat"], d["lon"], news_events)
        })

    return result
