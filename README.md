---
title: Intelligent Logistics Orchestration (OpenEnv)
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
app_file: app/main.py
pinned: false
license: mit
---

# openenv logistics sim

this is a complete, containerized environment for simulating real-world logistics and dispatch scenarios. i built it specifically to evaluate LLMs and RL agents by testing how well they can route under varying conditions like traffic, bad weather, low driver capacity, and local news events. 

## features

### 1. openenv compliant api
it acts as a stateless backend for agent evaluation, strictly typed with pydantic limits. it exposes standard openenv endpoints:
* `/health`: readiness probe
* `/tasks`: fetches difficulties
* `/reset`: init a sim with a random seed (guarantees deterministic environment gen for benchmarks). returns initial drivers, current shipment, and session_id.
* `/step`: takes agent actions (session_id, driver_id), runs physics engine, updates capacity pools, and returns rewards/state.
* `/state`: dumps the full state loop for debugging

### 2. sim physics
agents need to optimize the effective speed of drivers (`BASE_SPEED * traffic * weather * news`). 
* **traffic**: factors in free-flow vs current speed, drops to 0 if a road closure is detected.
* **weather**: 22 different condition types. e.g. light rain is a 10% penalty, heavy snow is 50%. it handles excess wind speeds over 60 kph too.
* **news**: monitors local supply chain disruptions (accidents, strikes etc), calculating impact radius using the haversine formula. closer to epicenter = higher penalty.

### 3. dual mode operation
* **live mode uses APIs** (`USE_REAL_API=true`): async fetches to tomtom, weatherapi, and local pgsql using concurrent.futures thread pooling
* **offline mode** (`USE_REAL_API=false`): the default. recreating complexities using deterministic geohashing. good for generating million step offline training epochs instantly without burning api credits.

### 4. grader
there are 3 tasks w/ partial step rewards:
* `task_easy`: 1 assignment, 5 drivers, 10 steps. basically test if the agent can pick the most obvious efficient choice
* `task_medium`: 3 assignments, 8-12 drivers, 30 steps. focuses on speeds over degrading shipments
* `task_hard`: 5 assignments, 5-20 drivers, 80 steps. full capacity management - agents get penalized hard if all drivers are exhausted while cargo is left.

## setup

requirements: python 3.10+, ~8gb ram.

1. clone repo
2. copy `.env.example` -> `.env`. (add tomtom/weatherapi keys if using real api mode)
   note: you need `API_BASE_URL` and `MODEL_NAME` in your env too otherwise the inference script will crash.
3. `pip install -r requirements.txt`
4. start the server:
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 7860`
5. test run the ai inference script:
   `python inference.py --task all`

outputs use `[START]`, `[STEP]`, and `[END]` tags so log parsers can grab the reasoning easily.

### docker
its docker ready too.
`docker build -t logistics-env .`
`docker run -p 7860:7860 logistics-env`
(the build will run `pre_validation.py` to assert the endpoints work properly before finishing)

enjoy, sorry if the code is a bit messy i took out the comments lol.
