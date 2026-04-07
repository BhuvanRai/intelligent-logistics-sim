---
title: Intelligent Logistics Orchestration (OpenEnv)
emoji: 🐨
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
app_file: app/main.py
pinned: false
license: mit
short_description: OpenEnv reinforcement learning environment for logistics assignment.
---

# Intelligent Logistics Orchestration (OpenEnv)

Welcome to the **Intelligent Logistics Orchestration** environment! This is a complete, containerized environment fully compliant with the [OpenEnv specification](https://github.com/openenv). It is built specifically to benchmark and evaluate large language models (LLMs) and advanced Reinforcement Learning (RL) agents in complex, multi-variable real-world scenarios.

Traditional toy environments often simplify state to simple grids or perfect-information graphs. In contrast, this environment places agents in the role of a fleet dispatcher who must route drivers across varying conditions, managing unexpected disruptions such as live traffic gridlocks, severe hazardous weather formations, fluctuating driver capacity, and breaking local news events that cause supply chain bottlenecks. 

By modeling these distinct real-world factors into a unified metric of "effective delivery speed", this environment isolates the agent's ability to plan, prioritize, and manage exhaustible logistics resources across multiple chained delivery phases.

---

## 1. Environment Description & Core Mechanics

The core goal of the agent is to successfully deliver an assigned cargo payload (measured in kilograms) from a source geolocation to a destination geolocation. To achieve this, the agent must recursively assign available drivers from a pool to chip away at the total remaining cargo capacity. 

However, real-world routing is not as simple as picking the closest driver. Agents must optimize a dynamic equation: **The Effective Speed**.

### The Physics Engine: Effective Speed Calculation

Every driver in the pool possesses a base theoretical routing speed (`BASE_SPEED`). In an ideal mathematical vacuum, routing decisions would rely solely on geographic proximity (`distance_km`). However, our built-in physics engine degrades this base speed using three continuous multiplier factors:

1. **Live Traffic Multiplier (`traffic_score`):**
   A continuous float `[0.0, 1.0]`. It compares current free-flow highway speeds against real-time congestion metrics. A score of `1.0` means empty roads, whereas a score of `0.0` represents an absolute road closure or gridlock. An agent assigning a driver to a heavily congested route will see their effective speed plummet, regardless of physical proximity.

2. **Meteorological / Weather Penalty (`weather_score`):**
   We model over 20 unique atmospheric and meteorological condition types. 
   - Mild constraints (e.g., Light Rain, Overcast) may only introduce a minor 5-15% velocity penalty.
   - Severe weather constraints (e.g., Heavy Snow, Torrential Flooding, Freezing Fog) drastically throttle the routing capacity by up to 60%.
   - The engine also dynamically handles wind shear, applying aggressive non-linear penalties if wind vectors exceed 60 kilometers per hour.

3. **Geospatial News/Disruption Engine (`news_score`):**
   The environment monitors a mock local news event stream to calculate localized supply chain shocks (e.g., transit strikes, critical infrastructure failure, accidents). The disruption impact is aggressively calculated using the **Haversine formula** to measure the exact blast radius of the disruption against the driver's current coordinates. The closer a driver is to an epicenter, the worse their penalty.

**Mathematical Routine:**
`Effective Speed = BASE_SPEED * traffic_score * weather_score * news_score`

Agents are scored internally by how close they get their assigned driver's `Effective Speed` to the absolute maximum mathematical potential speed available across the fleet on any given turn.

---

## 2. Action and Observation Spaces

This environment communicates entirely via structured parameter types and strictly parsed JSON validation, conforming natively to the OpenEnv API spec.

### The Observation Space

The state of the environment is represented cleanly via a single comprehensive dictionary object on every turn. Instead of "hidden" states, the agent is provided all necessary real-time metrics to calculate the mathematical optimum. 

**Structure:** `Dict`
```json
{
  "step": 1,
  "task_id": "task_medium",
  "session_id": "a1b2c3d4-xxxx",
  "done": false,
  "episode_stats": {
    "total_delivered_kg": 150.0,
    "avg_effective_speed": 45.2,
    "steps_taken": 3,
    "drivers_remaining": 8
  },
  "assignment": {
    "id": 101,
    "src": {"lat": 40.7128, "lon": -74.0060},
    "dest": {"lat": 42.3601, "lon": -71.0589},
    "total_goods_kg": 5000.0,
    "remaining_goods_kg": 4850.0
  },
  "drivers": [
    {
      "driver_id": 12,
      "distance_km": 15.4,
      "capacity_kg": 250.0,
      "traffic_score": 0.85,
      "weather_score": 0.90,
      "news_score": 1.0,
      "effective_speed": 61.2
    },
    ...
  ]
}
```
**Key Components:**
- `assignment`: The current logistics objective. Note that `remaining_goods_kg` degrades on every successful step until the assignment is finalized.
- `drivers`: The dynamic pool of allocatable vehicles. `capacity_kg` decreases persistently across steps. If a driver drops to `<= 0` capacity, they are forcibly removed from the array permanently. 
- `episode_stats`: Crucial tracking metrics that summarize the success of the agent across the full episode.

### The Action Space

**Structure:** `Discrete`
The agent simply replies with the targeted `driver_id` from the currently valid integer pool. The ID must match an active driver in the `drivers` array observation field.

```json
{
  "driver_id": 12
}
```
*Note: Any submission of an invalid, non-existent, or exhausted driver ID will result in a penalized failure state and exception block.*

---

## 3. The 3-Tier Grader Benchmark

We split evaluation into three progressive difficulties to test model scale and reasoning fidelity.

### `task_easy` (Optimal Driver Selection)
- **Scope:** 1 Assignment, 5 Drivers, 10 Steps.
- **Challenge:** A pure classification test. Can the agent properly digest the weather/traffic math and select the obvious heuristic winner? 

### `task_medium` (Multi-Step Delivery)
- **Scope:** 3 Consecutive Assignments, 8-12 Drivers, 30 Steps.
- **Challenge:** As assignments progress, driver cargo capacity is rapidly eaten away. An agent cannot simply pick the "fastest" driver blindly; they must allocate properly sized drivers to properly sized shipments to preserve fleet endurance over mid-length timeframes.

### `task_hard` (Full Logistics Episode / Knapsack Test)
- **Scope:** 5 Full Assignments, 5-20 Drivers, up to 80 Steps.
- **Challenge:** A grueling resource-management pipeline. The agent will rapidly run out of drivers if they assign large capacity vehicles to small lingering payloads. Exhausting the entire fleet before finishing the remaining assignments forces an aggressive failure and a `0.0` score cap. Success here requires verifiable multi-hop reasoning.

---

## 4. Setup Instructions

The physical server operates over FastAPI as a stateless backend engine. It can be run fully locally, compiled into Docker, or deployed via Hugging Face Spaces.

### System Requirements
- Python 3.10+
- ~8GB RAM
- Optional: Configured API Keys for TomTom & WeatherAPI if running in `live` mode.

### 4.1. Local API Installation

1. **Clone the repository and install dependencies:**
   ```bash
   git clone <repository_url>
   cd intelligent-logistics-sim
   pip install -r requirements.txt
   ```

2. **Configure your Environment Tracking:**
   ```bash
   cp .env.example .env
   ```
   *Required Environment Variables (especially for the baseline inference script):*
   - `OPENAI_API_KEY` (or `HF_TOKEN` if using HF models via endpoint integrations)
   - `API_BASE_URL` (Defaults to `https://api.openai.com/v1`)
   - `MODEL_NAME` (e.g., `gpt-4o-mini`)
   - `USE_REAL_API` (Set to `false` for offline hashing metrics; set to `true` to fire live concurrent async network requests to real-world TomTom maps).

3. **Start the Uvicorn Back-End Engine:**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 7860
   ```

### 4.2. Docker Native Build & Hugging Face Workflow

We have provided a compliant `Dockerfile`. The build system enforces test-driven deployments; it will explicitly run `pre_validation.py` inside the container build loop to execute tests against `/health`, `/tasks`, `/reset`, and `/step` over all three tasks internally. If a test fails, the build halts.

```bash
docker build -t logistics-env .
docker run -p 7860:7860 logistics-env
```
Once deployed to a HF Space, the OpenEnv evaluator can inherently connect via the standard `http://<your-space-url>/` network bindings.

---

## 5. Sample Usage & Inference

Want to test an LLM against the environment right now? We've bundled an OpenEnv Evaluation compatible `inference.py` asynchronous script!

```bash
python inference.py --task all --seed 42
```
This script cleanly initializes your model against the local API, loops through observations natively, and prints correctly formatted, rigid validation signals:

```
[START] task=task_hard env=logistics_sim model=gpt-4o-mini
[STEP] step=1 action=assign_driver(2) reward=0.89 done=false error=null
[STEP] step=2 action=assign_driver(1) reward=0.91 done=false error=null
[STEP] ...
[END] success=true steps=14 score=0.884 rewards=0.89,0.91...
```

*Note: You can pass custom seeds (`--seed 42`) specifically when generating offline validation subsets to guarantee identical driver arrays and coordinate spans across differing tests algorithms.*

Enjoy dissecting your dispatch logic!
