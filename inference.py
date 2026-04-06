                      
"""
inference.py — OpenEnv Round 1 inference script.

Uses an LLM (via OpenAI client) to act as a driver-assignment agent.
Emits structured stdout logs in the required [START] / [STEP] / [END] format.

Required environment variables
───────────────────────────────
  API_BASE_URL   Base URL of the OpenAI-compatible LLM API
  MODEL_NAME     Model identifier  (e.g. gpt-4o-mini)
  HF_TOKEN       API key / Hugging Face token

Usage
─────
  python inference.py                          # runs all 3 tasks
  python inference.py --task task_easy         # single task
  python inference.py --task task_hard --seed 42
  python inference.py --env-url http://localhost:7860  # custom env URL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

                                                                                
                
                                                                                

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN",     "")
ENV_URL      = os.environ.get("ENV_URL",      "http://localhost:7860")

TASKS        = ["task_easy", "task_medium", "task_hard"]
MAX_RETRIES  = 3                                      
REQUEST_TIMEOUT = 30                                 


                                                                                
             
                                                                                

def make_llm_client() -> OpenAI:
    return OpenAI(
        base_url = API_BASE_URL,
        api_key  = HF_TOKEN or "no-key",
    )


                                                                                
                  
                                                                                

def env_reset(task_id: str, seed: Optional[int] = None) -> Dict:
    payload: Dict[str, Any] = {"task_id": task_id}
    if seed is not None:
        payload["seed"] = seed
    r = requests.post(f"{ENV_URL}/reset", json=payload, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()


def env_step(session_id: str, driver_id: int) -> Dict:
    r = requests.post(
        f"{ENV_URL}/step",
        json={"session_id": session_id, "driver_id": driver_id},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def env_tasks() -> List[Dict]:
    r = requests.get(f"{ENV_URL}/tasks", timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json().get("tasks", [])


                                                                                
                 
                                                                                

def build_prompt(observation: Dict) -> str:
    assignment = observation["assignment"]
    drivers    = observation["drivers"]
    stats      = observation["episode_stats"]

    driver_lines = "\n".join(
        f"  • Driver {d['driver_id']:>2d} | dist={d['distance_km']:>7.1f} km"
        f" | cap={d['capacity_kg']:>7.1f} kg"
        f" | traffic={d['traffic_score']:.3f}"
        f" | weather={d['weather_score']:.3f}"
        f" | news={d['news_score']:.3f}"
        f" | eff_speed={d['effective_speed']:.1f} km/h"
        for d in drivers
    )

    return f"""You are an intelligent logistics dispatch system.
Your job is to assign the OPTIMAL driver for the current delivery.

=== CURRENT ASSIGNMENT ===
  Assignment #{assignment['id']}
  Source     : lat={assignment['src']['lat']}, lon={assignment['src']['lon']}
  Destination: lat={assignment['dest']['lat']}, lon={assignment['dest']['lon']}
  Goods remaining: {assignment['remaining_goods_kg']:.1f} kg (of {assignment['total_goods_kg']:.1f} kg total)

=== AVAILABLE DRIVERS ===
{driver_lines}

=== EPISODE STATS ===
  Steps taken          : {stats['steps_taken']}
  Total delivered (kg) : {stats['total_delivered_kg']:.1f}
  Avg effective speed  : {stats['avg_effective_speed']:.1f} km/h
  Drivers remaining    : {stats['drivers_remaining']}

=== YOUR TASK ===
Select the driver that maximises EFFECTIVE SPEED while penalising large
distances. Consider:
  1. Higher effective_speed is better  (traffic × weather × news × BASE_SPEED)
  2. Closer drivers reach the source faster (lower distance_km is better)
  3. Drivers with enough capacity to cover the remaining goods are preferred
     (capacity_kg >= remaining_goods_kg)

Reply with ONLY a JSON object on a single line, no other text:
{ "driver_id": <integer>} """


                                                                                
                                                            
                                                                                

def llm_pick_driver(
    client: OpenAI,
    observation: Dict,
) -> int:
    """
    Ask the LLM to pick a driver_id.  Falls back to the highest effective-speed
    driver if parsing fails after MAX_RETRIES attempts.
    """
    drivers    = observation["drivers"]
    valid_ids  = {d["driver_id"] for d in drivers}
    prompt     = build_prompt(observation)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model    = MODEL_NAME,
                messages = [
                    {
                        "role":    "system",
                        "content": (
                            "You are a logistics dispatch AI. "
                            "Always respond with exactly one JSON object "
                            'containing a single key "driver_id" with an integer value.'
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature    = 0.0,
                max_tokens     = 32,
                response_format= {"type": "json_object"},
            )
            raw  = response.choices[0].message.content.strip()
            data = json.loads(raw)
            chosen = int(data["driver_id"])
            if chosen in valid_ids:
                return chosen
                                                                  
            print(
                f"  [WARN] LLM returned invalid driver_id={chosen}, "
                f"valid={sorted(valid_ids)}. Retrying ({attempt+1}/{MAX_RETRIES}).",
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"  [WARN] LLM call failed: {exc}. Retrying ({attempt+1}/{MAX_RETRIES}).", file=sys.stderr)
        time.sleep(0.5 * (attempt + 1))

                                                                  
    best = max(drivers, key=lambda d: d["effective_speed"])
    print(
        f"  [FALLBACK] Heuristic selected driver {best['driver_id']} "
        f"(eff={best['effective_speed']:.1f} km/h).",
        file=sys.stderr,
    )
    return best["driver_id"]


                                                                                
                     
                                                                                

def run_task(client: OpenAI, task_id: str, seed: Optional[int] = None) -> float:
    """
    Run one complete episode for task_id.
    Emits [START] … [STEP]* … [END] to stdout.
    Returns final score.
    """
    print(f"[START] task={task_id} env=logistics_sim model={MODEL_NAME}", flush=True)

    reset_resp = env_reset(task_id, seed)
    session_id = reset_resp["session_id"]
    obs        = reset_resp["observation"]

    step_num        = 0
    total_reward    = 0.0
    final_score     = 0.0
    rewards_list    = []

    done = obs.get("done", False)

    while not done:
        step_num += 1

        driver_id = llm_pick_driver(client, obs)

        error_val = "null"
        try:
            step_resp = env_step(session_id, driver_id)
            reward    = float(step_resp["reward"])
            done      = step_resp["done"]
            obs       = step_resp["observation"]
        except Exception as e:
            reward    = 0.0
            done      = True
            error_val = str(e).replace("\n", " ")
            step_resp = {}

        total_reward += reward
        rewards_list.append(reward)

        done_val = str(done).lower()
        action_str = f"assign_driver({driver_id})"

        print(
            f"[STEP] step={step_num} action={action_str} reward={reward:.2f} done={done_val} error={error_val}",
            flush=True,
        )

        if done:
            final_score = float(step_resp.get("score") or 0.0)
            break

        if not obs.get("drivers"):
            break

    success_val = str(final_score >= 0.40).lower()
    rewards_str = ",".join(f"{r:.2f}" for r in rewards_list)

    print(f"[END] success={success_val} steps={step_num} score={final_score:.3f} rewards={rewards_str}", flush=True)

    return final_score


                                                                                
       
                                                                                

def main() -> None:
    parser = argparse.ArgumentParser(description="OpenEnv inference script for Intelligent Logistics Orchestration")
    parser.add_argument("--task",    choices=TASKS + ["all"], default="all",
                        help="Task to run (default: all)")
    parser.add_argument("--seed",    type=int, default=None,
                        help="Random seed for reproducibility")
    parser.add_argument("--env-url", default=ENV_URL,
                        help=f"Environment base URL (default: {ENV_URL})")
    args = parser.parse_args()

    global ENV_URL
    ENV_URL = args.env_url

                                       
    try:
        r = requests.get(f"{ENV_URL}/health", timeout=10)
        r.raise_for_status()
    except Exception as exc:
        print(f"[ERROR] Cannot reach environment at {ENV_URL}: {exc}", file=sys.stderr)
        sys.exit(1)

    client = make_llm_client()

    tasks_to_run = TASKS if args.task == "all" else [args.task]
    results: Dict[str, float] = {}

    for task_id in tasks_to_run:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"  Running {task_id}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        try:
            score = run_task(client, task_id, args.seed)
            results[task_id] = score
            print(f"  ✓ {task_id} score = {score:.4f}", file=sys.stderr)
        except Exception as exc:
            print(f"  ✗ {task_id} FAILED: {exc}", file=sys.stderr)
            results[task_id] = 0.0

    avg_score = sum(results.values()) / len(results) if results else 0.0

    print(file=sys.stderr)
    print("Final Results:", file=sys.stderr)
    for tid, sc in results.items():
        print(f"  {tid}: {sc:.4f}", file=sys.stderr)
    print(f"  Average  : {avg_score:.4f}", file=sys.stderr)


if __name__ == "__main__":
    main()
