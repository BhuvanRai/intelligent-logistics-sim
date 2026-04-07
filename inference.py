import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import aiohttp
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN")
ENV_URL      = os.environ.get("ENV_URL",      "http://localhost:7860")

TASKS        = ["task_easy", "task_medium", "task_hard"]
MAX_RETRIES  = 3

def log_start(task: str, env: str, model: str):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str] = None):
    done_val = str(done).lower()
    err_val = error.replace('\n', ' ') if error else "null"
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={err_val}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    succ_val = str(success).lower()
    rew_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={succ_val} steps={steps} score={score:.3f} rewards={rew_str}", flush=True)


class LogisticsAction:
    def __init__(self, action_str: str, driver_id: int):
        self.action_str = action_str
        self.driver_id = driver_id

class LogisticsObservation:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

class StepResult:
    def __init__(self, observation: LogisticsObservation, reward: float, done: bool, score: float, error: Optional[str] = None):
        self.observation = observation
        self.reward = reward
        self.done = done
        self.score = score
        self.error = error

class ResetResult:
    def __init__(self, observation: LogisticsObservation, session_id: str):
        self.observation = observation
        self.session_id = session_id


class LogisticsEnv:
    """Async environment wrapper compatible with standard OpenEnv structural patterns."""
    def __init__(self, base_url: str, task_id: str, seed: Optional[int] = None):
        self.base_url = base_url
        self.task_id = task_id
        self.seed = seed
        self.session_id = None
        self.session = aiohttp.ClientSession()

    async def reset(self) -> ResetResult:
        payload = {"task_id": self.task_id}
        if self.seed is not None:
            payload["seed"] = self.seed
        async with self.session.post(f"{self.base_url}/reset", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            self.session_id = data["session_id"]
            return ResetResult(LogisticsObservation(data["observation"]), self.session_id)

    async def step(self, action: LogisticsAction) -> StepResult:
        payload = {"session_id": self.session_id, "driver_id": action.driver_id}
        try:
            async with self.session.post(f"{self.base_url}/step", json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return StepResult(
                    observation=LogisticsObservation(data["observation"]),
                    reward=float(data["reward"]),
                    done=data["done"],
                    score=float(data.get("score") or 0.0),
                    error=None
                )
        except Exception as e:
            return StepResult(
                observation=LogisticsObservation({}),
                reward=0.0,
                done=True,
                score=0.0,
                error=str(e)
            )

    async def close(self):
        await self.session.close()


def get_model_message(client: OpenAI, obs: LogisticsObservation, history: List[str]) -> LogisticsAction:
    """Invokes OpenAI LLM to parse current state, respecting the requested history pattern."""
    obs_data = obs.data
    drivers = obs_data.get("drivers", [])
    if not drivers:
        return LogisticsAction(action_str="assign_driver(0)", driver_id=0)

    assignment = obs_data["assignment"]
    stats      = obs_data["episode_stats"]

    driver_lines = "\n".join(
        f"  • Driver {d['driver_id']:>2d} | dist={d['distance_km']:>7.1f} km | cap={d['capacity_kg']:>7.1f} kg | eff_speed={d['effective_speed']:.1f} km/h"
        for d in drivers
    )
    history_str = "\n".join(history[-5:])

    prompt = f"""You are an intelligent logistics dispatch system.
Assign the OPTIMAL driver for the current delivery.

=== CURRENT ASSIGNMENT ===
Goods remaining: {assignment['remaining_goods_kg']:.1f} kg

=== AVAILABLE DRIVERS ===
{driver_lines}

=== EPISODE STATS ===
Steps taken: {stats['steps_taken']}

=== HISTORY LOG ===
{history_str}

Reply with ONLY a JSON object:
{{ "driver_id": <integer> }}"""

    valid_ids = {d["driver_id"] for d in drivers}

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a standalone logistics dispatch JSON agent."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            chosen = int(data["driver_id"])
            if chosen in valid_ids:
                return LogisticsAction(action_str=f"assign_driver({chosen})", driver_id=chosen)
        except Exception as exc:
            pass
        time.sleep(0.5)

    best = max(drivers, key=lambda d: d["effective_speed"])
    return LogisticsAction(action_str=f"assign_driver({best['driver_id']})", driver_id=best['driver_id'])


async def run_task(client: OpenAI, task_name: str, seed: Optional[int]) -> float:
    """Averaged representation of the OpenEnv containerized asyncio execution block."""
    env = LogisticsEnv(base_url=ENV_URL, task_id=task_name, seed=seed)
    
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env="logistics_sim", model=MODEL_NAME)

    try:
        result = await env.reset()
        obs = result.observation
        
        while True:
            steps_taken += 1
            
            action = get_model_message(client, obs, history)
            
            result = await env.step(action)
            obs = result.observation
            
            reward = result.reward
            done = result.done
            error = result.error
            
            rewards.append(reward)
            
            log_step(step=steps_taken, action=action.action_str, reward=reward, done=done, error=error)
            
            history.append(f"Step {steps_taken}: {action.action_str!r} -> reward {reward:+.2f}")
            
            if done:
                score = result.score
                success = score >= 0.40
                break
                
            if not obs.data.get("drivers"):
                break

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
            
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
        
    return score


async def main() -> None:
    parser = argparse.ArgumentParser(description="Async OpenEnv SDK-Style Inference Script")
    parser.add_argument("--task", choices=TASKS + ["all"], default="all")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN or "no-key")

    tasks_to_run = TASKS if args.task == "all" else [args.task]
    results = {}

    for task_name in tasks_to_run:
        score = await run_task(client, task_name, args.seed)
        results[task_name] = score

    print(file=sys.stderr)
    print("Final Async Results:", file=sys.stderr)
    for tid, sc in results.items():
        print(f"  {tid}: {sc:.4f}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
