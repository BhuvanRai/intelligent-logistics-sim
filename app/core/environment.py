"""
LogisticsEnvironment — core RL environment logic.

Implements the OpenEnv contract:
    reset(task_id, seed)  →  ResetResponse
    step(session_id, driver_id)  →  StepResult
    state(session_id)  →  EnvironmentState

Design principles
─────────────────
• Stateless from the server's perspective — all mutable state lives in the
  session store, which is passed in/out via plain dicts.
• Zero external API calls when USE_REAL_API=false (default).
• When USE_REAL_API=true, driver factors are fetched from the real TomTom +
  WeatherAPI stack defined in app/utils/ (reusing your existing code).
• The grader is called internally at the end of each episode and the final
  score is returned in the last StepResult.
"""
from __future__ import annotations

import copy
import os
from typing import Any, Dict, List, Optional

from app.core.session_store import new_session, get_session, set_session
from app.graders.grader import compute_step_reward, grade_episode
from app.models import (
    Action, Assignment, DriverFactor, EpisodeStats, EnvironmentState,
    Location, Observation, ResetRequest, ResetResponse, StepResult,
    TaskStatus,
)
from app.simulation.engine import BASE_SPEED, get_mock_driver_factors
from app.tasks.registry import build_episode, get_task_info

USE_REAL_API = os.getenv("USE_REAL_API", "false").lower() == "true"


                                                                                
          
                                                                                

def _build_observation(state: Dict, session_id: str) -> Observation:
    """Convert the raw session state dict into a typed Observation."""
    asgn_raw = state["current_assignment"]
    drivers  = state["driver_pool"]

                                         
    if USE_REAL_API:
        try:
            from app.utils.driver_factors import get_driver_factors
            factors = get_driver_factors(
                drivers,
                asgn_raw["src_lat"],
                asgn_raw["src_lon"],
            )
        except Exception:
            factors = get_mock_driver_factors(
                drivers, asgn_raw["src_lat"], asgn_raw["src_lon"]
            )
    else:
        factors = get_mock_driver_factors(
            drivers, asgn_raw["src_lat"], asgn_raw["src_lon"]
        )

                                                  
    state["latest_factors"] = factors

    driver_models = [
        DriverFactor(
            driver_id     = f["driver_id"],
            distance_km   = f["distance_km"],
            capacity_kg   = f["capacity_kg"],
            traffic_score = f["traffic_score"],
            weather_score = f["weather_score"],
            news_score    = f["news_score"],
            effective_speed = f["effective_speed"],
        )
        for f in factors
    ]

    assignment = Assignment(
        id                  = asgn_raw["id"],
        src                 = Location(lat=asgn_raw["src_lat"], lon=asgn_raw["src_lon"]),
        dest                = Location(lat=asgn_raw["dest_lat"], lon=asgn_raw["dest_lon"]),
        total_goods_kg      = asgn_raw["total_goods_kg"],
        remaining_goods_kg  = asgn_raw["remaining_goods_kg"],
    )

    stats = state["episode_stats"]
    ep_stats = EpisodeStats(
        total_delivered_kg  = stats["total_delivered_kg"],
        avg_effective_speed = (
            stats["speed_sum"] / stats["steps"] if stats["steps"] > 0 else 0.0
        ),
        steps_taken         = stats["steps"],
        drivers_remaining   = len(drivers),
    )

    return Observation(
        step          = state["step"],
        assignment    = assignment,
        drivers       = driver_models,
        episode_stats = ep_stats,
        task_id       = state["task_id"],
        session_id    = session_id,
        done          = state["done"],
    )


def _advance_assignment(state: Dict) -> bool:
    """
    Move to the next assignment in the queue.
    Returns True if there is a next assignment, False if the queue is exhausted.
    """
    state["assignment_queue_index"] += 1
    idx = state["assignment_queue_index"]
    queue = state["assignment_queue"]
    if idx < len(queue):
        state["current_assignment"] = copy.deepcopy(queue[idx])
        return True
    return False


                                                                                
                   
                                                                                

def reset(request: ResetRequest) -> ResetResponse:
    """
    Initialise a new episode for the requested task and return the first
    observation without requiring any agent action.
    """
    task_id = request.task_id
    if get_task_info(task_id) is None:
        raise ValueError(f"Unknown task_id '{task_id}'. "
                         "Use GET /tasks to see available tasks.")

    episode = build_episode(task_id, request.seed)

    sid = new_session()
    state: Dict[str, Any] = {
        "task_id":               task_id,
        "step":                  0,
        "done":                  False,
        "driver_pool":           episode["driver_pool"],
        "assignment_queue":      episode["assignment_queue"],
        "assignment_queue_index": 0,
        "current_assignment":    copy.deepcopy(episode["assignment_queue"][0]),
        "max_steps":             episode["max_steps"],
        "total_goods_kg":        sum(a["total_goods_kg"] for a in episode["assignment_queue"]),
        "n_drivers_initial":     len(episode["driver_pool"]),
        "latest_factors":        [],
        "history":               [],
        "episode_stats": {
            "total_delivered_kg": 0.0,
            "speed_sum":          0.0,
            "steps":              0,
        },
    }

                                                                          
    obs = _build_observation(state, sid)
    set_session(sid, state)

    return ResetResponse(
        session_id  = sid,
        task_id     = task_id,
        observation = obs,
    )


def step(action: Action) -> StepResult:
    """
    Execute one agent action (driver assignment) and return the next
    observation, per-step reward, and done flag.
    """
    sid     = action.session_id
    state   = get_session(sid)
    if state is None:
        raise ValueError(f"Session '{sid}' not found. Call POST /reset first.")
    if state["done"]:
        raise ValueError("Episode is already finished. Call POST /reset to start a new one.")

                                                                                
    pool = state["driver_pool"]
    pool_ids = [d["id"] for d in pool]
    if action.driver_id not in pool_ids:
        raise ValueError(
            f"driver_id {action.driver_id} is not in the available pool {pool_ids}."
        )

    factors = state["latest_factors"]
    chosen_factor = next((f for f in factors if f["driver_id"] == action.driver_id), None)
    if chosen_factor is None:
        raise ValueError(f"No factor entry found for driver {action.driver_id}.")

                                                                                
    asgn       = state["current_assignment"]
    delivered  = min(chosen_factor["capacity_kg"], asgn["remaining_goods_kg"])
    asgn["remaining_goods_kg"] = round(asgn["remaining_goods_kg"] - delivered, 2)

                                    
    driver_obj = next(d for d in pool if d["id"] == action.driver_id)
    driver_obj["capacity"] = round(driver_obj["capacity"] - delivered, 2)

                                                                                
    reward = compute_step_reward(state["task_id"], chosen_factor, factors)

                                                                                
    state["step"] += 1
    stats = state["episode_stats"]
    stats["total_delivered_kg"] += delivered
    stats["speed_sum"]          += chosen_factor["effective_speed"]
    stats["steps"]              += 1

    history_entry = {
        "step":                    state["step"],
        "driver_id":               action.driver_id,
        "delivered_kg":            delivered,
        "chosen_effective_speed":  chosen_factor["effective_speed"],
        "all_speeds":              [f["effective_speed"] for f in factors],
        "remaining_capacity_kg":   driver_obj["capacity"],
        "reward":                  reward,
    }
    state["history"].append(history_entry)

                                                                                
    if driver_obj["capacity"] <= 0:
        pool.remove(driver_obj)
                                                                               

                                                                                
    episode_done = False
    if asgn["remaining_goods_kg"] <= 0:
        has_next = _advance_assignment(state)
        if not has_next:
            episode_done = True

                                                                                
    if not pool:
        episode_done = True
    if state["step"] >= state["max_steps"]:
        episode_done = True

    state["done"] = episode_done

                                                                                
    final_score: Optional[float] = None
    info: Dict[str, Any] = {
        "delivered_this_step": delivered,
        "driver_removed": driver_obj["capacity"] <= 0 if not episode_done else False,
    }
    if episode_done:
        grader_result = grade_episode(
            task_id            = state["task_id"],
            history            = state["history"],
            total_goods_kg     = state["total_goods_kg"],
            total_delivered_kg = stats["total_delivered_kg"],
            n_drivers_initial  = state["n_drivers_initial"],
        )
        final_score = grader_result.score
        info["grader"] = grader_result.model_dump()

                                                                                
    if not episode_done:
        obs = _build_observation(state, sid)
    else:
                                                      
                                                       
        obs = Observation(
            step          = state["step"],
            assignment    = Assignment(
                id                 = asgn["id"],
                src                = Location(lat=asgn["src_lat"], lon=asgn["src_lon"]),
                dest               = Location(lat=asgn["dest_lat"], lon=asgn["dest_lon"]),
                total_goods_kg     = asgn["total_goods_kg"],
                remaining_goods_kg = asgn["remaining_goods_kg"],
            ),
            drivers       = [],
            episode_stats = EpisodeStats(
                total_delivered_kg  = stats["total_delivered_kg"],
                avg_effective_speed = (
                    stats["speed_sum"] / stats["steps"] if stats["steps"] > 0 else 0.0
                ),
                steps_taken         = stats["steps"],
                drivers_remaining   = len(pool),
            ),
            task_id    = state["task_id"],
            session_id = sid,
            done       = True,
            info       = info,
        )

    set_session(sid, state)

    return StepResult(
        observation = obs,
        reward      = reward,
        done        = episode_done,
        score       = final_score,
        info        = info,
    )


def get_state(session_id: str) -> EnvironmentState:
    """Return a full snapshot of the session's internal state."""
    state = get_session(session_id)
    if state is None:
        raise ValueError(f"Session '{session_id}' not found.")

    asgn = state["current_assignment"]
    stats = state["episode_stats"]

    return EnvironmentState(
        session_id               = session_id,
        task_id                  = state["task_id"],
        status                   = TaskStatus.completed if state["done"] else TaskStatus.active,
        current_step             = state["step"],
        assignment_queue         = [
            Assignment(
                id                  = a["id"],
                src                 = Location(lat=a["src_lat"], lon=a["src_lon"]),
                dest                = Location(lat=a["dest_lat"], lon=a["dest_lon"]),
                total_goods_kg      = a["total_goods_kg"],
                remaining_goods_kg  = a["remaining_goods_kg"],
            )
            for a in state["assignment_queue"]
        ],
        current_assignment_index = state["assignment_queue_index"],
        driver_pool              = state["driver_pool"],
        episode_stats            = EpisodeStats(
            total_delivered_kg  = stats["total_delivered_kg"],
            avg_effective_speed = (
                stats["speed_sum"] / stats["steps"] if stats["steps"] > 0 else 0.0
            ),
            steps_taken         = stats["steps"],
            drivers_remaining   = len(state["driver_pool"]),
        ),
        history                  = state["history"],
    )
