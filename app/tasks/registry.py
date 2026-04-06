"""
Task registry — defines all three tasks and exposes helpers used by the
environment and grader.
"""
from __future__ import annotations

import random
from typing import Dict, Optional

from app.models import TaskInfo, TaskDifficulty
from app.simulation.engine import init_drivers, init_assignment


                                                                                
                 
                                                                                

TASK_CATALOGUE: Dict[str, TaskInfo] = {
    "task_easy": TaskInfo(
        id          = "task_easy",
        name        = "Optimal Driver Selection",
        difficulty  = TaskDifficulty.easy,
        description = (
            "Choose the single best driver from a pool of 5 for one delivery. "
            "Reward = achieved effective speed / theoretical max effective speed."
        ),
        max_steps   = 10,
    ),
    "task_medium": TaskInfo(
        id          = "task_medium",
        name        = "Multi-Step Delivery",
        difficulty  = TaskDifficulty.medium,
        description = (
            "Manage 3 consecutive deliveries with 8–12 drivers. Driver capacities "
            "degrade with each step. Score = normalised avg effective speed."
        ),
        max_steps   = 30,
    ),
    "task_hard": TaskInfo(
        id          = "task_hard",
        name        = "Full Logistics Episode",
        difficulty  = TaskDifficulty.hard,
        description = (
            "Complete 5 assignments with 5–20 drivers. Drivers leave the pool "
            "when exhausted. Score = composite of delivery completeness, "
            "avg effective speed, and driver utilisation efficiency."
        ),
        max_steps   = 80,
    ),
}


def get_all_tasks() -> list[TaskInfo]:
    return list(TASK_CATALOGUE.values())


def get_task_info(task_id: str) -> Optional[TaskInfo]:
    return TASK_CATALOGUE.get(task_id)


                                                                                
                      
 
                                                                     
                                                                                

def build_episode(task_id: str, seed: Optional[int] = None) -> Dict:
    """
    Build a fresh episode dict for the given task.

    Returns a dict with:
        driver_pool           : list of driver dicts
        assignment_queue      : list of assignment dicts (ordered)
        max_steps             : episode step limit
        num_assignments_total : used for grader completeness score
    """
    rng = random.Random(seed)

    if task_id == "task_easy":
        n_drivers     = 5
        n_assignments = 1
    elif task_id == "task_medium":
        n_drivers     = rng.randint(8, 12)
        n_assignments = 3
    else:             
        n_drivers     = rng.randint(5, 20)
        n_assignments = 5

    drivers     = init_drivers(n_drivers, rng)
    assignments = [init_assignment(i + 1, rng) for i in range(n_assignments)]

    info = get_task_info(task_id)
    return {
        "driver_pool":            drivers,
        "assignment_queue":       assignments,
        "max_steps":              info.max_steps if info else 80,
        "num_assignments_total":  n_assignments,
    }
