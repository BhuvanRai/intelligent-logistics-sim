"""
Grader — converts completed episode history into a final score [0.0, 1.0].

Each task has its own grading formula:

task_easy
    score = achieved_effective_speed / max_possible_effective_speed
    Reward per step is the same formula (single-step episode).

task_medium
    score = avg_effective_speed / BASE_SPEED
    Partial credit: each step rewards proportionally to effective speed.

task_hard
    score = 0.5 × delivery_completeness
          + 0.3 × speed_efficiency
          + 0.2 × utilisation_efficiency
    • delivery_completeness = total_delivered / total_goods
    • speed_efficiency      = avg_effective_speed / BASE_SPEED
    • utilisation_efficiency = steps_with_positive_capacity / total_steps
"""
from __future__ import annotations

from typing import Dict, List, Any

from app.models import GraderResult
from app.simulation.engine import BASE_SPEED

                                    
PASS_THRESHOLD = 0.40


                                                                                
                           
                                                                                

def compute_step_reward(
    task_id: str,
    chosen_factor: Dict,
    all_factors: List[Dict],
) -> float:
    """
    Returns a per-step reward in [0.0, 1.0].

    For all tasks the core signal is:
        reward = chosen_effective_speed / max_effective_speed_available

    This gives partial credit even for sub-optimal choices while strongly
    rewarding the optimal pick.
    """
    speeds = [f["effective_speed"] for f in all_factors]
    if not speeds:
        return 0.0
    max_speed = max(speeds)
    if max_speed <= 0:
        return 0.0
    raw = chosen_factor["effective_speed"] / max_speed
                                
    return round(min(1.0, max(0.0, raw)), 4)


                                                                                
                 
                                                                                

def grade_episode(
    task_id: str,
    history: List[Dict[str, Any]],
    total_goods_kg: float,
    total_delivered_kg: float,
    n_drivers_initial: int,
) -> GraderResult:
    """
    Compute final score from episode history.

    history items contain: {chosen_effective_speed, all_speeds, delivered_kg}
    """
    if not history:
        return GraderResult(
            task_id  = task_id,
            score    = 0.0,
            breakdown= {},
            passed   = False,
            message  = "No steps recorded.",
        )

    n_steps   = len(history)
    avg_speed = sum(h["chosen_effective_speed"] for h in history) / n_steps

                                                                                
    if task_id == "task_easy":
        max_speed_seen = max(
            max(h["all_speeds"]) for h in history if h["all_speeds"]
        ) if history else BASE_SPEED
        speed_eff = avg_speed / max(max_speed_seen, 1.0)
        score = round(min(1.0, speed_eff), 4)
        breakdown = {
            "avg_effective_speed": round(avg_speed, 2),
            "max_available_speed": round(max_speed_seen, 2),
            "speed_efficiency":    round(speed_eff, 4),
        }
        msg = f"Achieved {round(speed_eff*100, 1)}% of theoretical max speed."

                                                                                 
    elif task_id == "task_medium":
        speed_eff = avg_speed / BASE_SPEED
        score = round(min(1.0, speed_eff), 4)
        breakdown = {
            "avg_effective_speed": round(avg_speed, 2),
            "base_speed":          BASE_SPEED,
            "speed_efficiency":    round(speed_eff, 4),
        }
        msg = f"Avg effective speed {round(avg_speed, 1)} km/h ({round(speed_eff*100, 1)}% of {BASE_SPEED} km/h base)."

                                                                                 
    else:
        delivery_completeness = (
            total_delivered_kg / total_goods_kg if total_goods_kg > 0 else 0.0
        )
        speed_eff = avg_speed / BASE_SPEED

                                                                               
                                                                     
        positive_cap_steps = sum(
            1 for h in history if h.get("remaining_capacity_kg", 1) > 0
        )
        utilisation_eff = positive_cap_steps / n_steps if n_steps > 0 else 0.0

        score = round(
            min(1.0,
                0.5 * delivery_completeness
                + 0.3 * speed_eff
                + 0.2 * utilisation_eff
            ),
            4,
        )
        breakdown = {
            "delivery_completeness":  round(delivery_completeness, 4),
            "speed_efficiency":       round(speed_eff, 4),
            "utilisation_efficiency": round(utilisation_eff, 4),
            "avg_effective_speed":    round(avg_speed, 2),
            "total_delivered_kg":     round(total_delivered_kg, 1),
            "total_goods_kg":         round(total_goods_kg, 1),
        }
        msg = (
            f"Delivered {round(delivery_completeness*100, 1)}% of goods | "
            f"avg speed {round(avg_speed, 1)} km/h | "
            f"utilisation {round(utilisation_eff*100, 1)}%."
        )

    return GraderResult(
        task_id  = task_id,
        score    = score,
        breakdown= breakdown,
        passed   = score >= PASS_THRESHOLD,
        message  = msg,
    )
