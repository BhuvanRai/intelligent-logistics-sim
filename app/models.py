"""
Pydantic models — typed contracts for all OpenEnv API surfaces.

All request/response models are defined here so that FastAPI can auto-generate
OpenAPI docs and validate payloads at the boundary.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


                                                                                
               
                                                                                

class TaskDifficulty(str, Enum):
    easy   = "easy"
    medium = "medium"
    hard   = "hard"


class TaskStatus(str, Enum):
    active    = "active"
    completed = "completed"
    failed    = "failed"


                                                                                
                                             
                                                                                

class Location(BaseModel):
    lat: float = Field(..., description="Latitude in decimal degrees")
    lon: float = Field(..., description="Longitude in decimal degrees")


class DriverFactor(BaseModel):
    driver_id:     int   = Field(..., description="Unique driver identifier")
    distance_km:   float = Field(..., description="Haversine distance from driver to assignment source (km)")
    capacity_kg:   float = Field(..., description="Remaining cargo capacity (kg)")
    traffic_score: float = Field(..., ge=0.0, le=1.0, description="0=gridlock → 1=free-flow")
    weather_score: float = Field(..., ge=0.0, le=1.0, description="0=severe → 1=clear")
    news_score:    float = Field(..., ge=0.0, le=1.0, description="0=high disruption → 1=none")
    effective_speed: float = Field(..., description="BASE_SPEED × traffic × weather × news (km/h)")


class Assignment(BaseModel):
    id:                int   = Field(..., description="Assignment sequence number")
    src:               Location
    dest:              Location
    total_goods_kg:    float = Field(..., description="Original goods weight (kg)")
    remaining_goods_kg: float = Field(..., description="Goods yet to be delivered (kg)")


class EpisodeStats(BaseModel):
    total_delivered_kg: float = Field(default=0.0)
    avg_effective_speed: float = Field(default=0.0)
    steps_taken:         int   = Field(default=0)
    drivers_remaining:   int   = Field(default=0)


                                                                                
                                     
                                                                                

class Observation(BaseModel):
    step:           int
    assignment:     Assignment
    drivers:        List[DriverFactor]
    episode_stats:  EpisodeStats
    task_id:        str
    session_id:     str
    done:           bool = False
    info:           Dict[str, Any] = Field(default_factory=dict)


                                                                                
                                 
                                                                                

class Action(BaseModel):
    session_id: str = Field(..., description="Session token returned by /reset")
    driver_id:  int = Field(..., description="ID of the driver to assign")


                                                                                
                
                                                                                

class StepResult(BaseModel):
    observation:  Observation
    reward:       float = Field(..., ge=0.0, le=1.0, description="Per-step reward in [0, 1]")
    done:         bool
    score:        Optional[float] = Field(None, ge=0.0, le=1.0, description="Final episode score (only set when done=True)")
    info:         Dict[str, Any] = Field(default_factory=dict)


                                                                                
                                        
                                                                                

class EnvironmentState(BaseModel):
    session_id:       str
    task_id:          str
    status:           TaskStatus
    current_step:     int
    assignment_queue: List[Assignment]
    current_assignment_index: int
    driver_pool:      List[Dict[str, Any]]
    episode_stats:    EpisodeStats
    history:          List[Dict[str, Any]] = Field(default_factory=list)


                                                                                
                           
                                                                                

class ResetRequest(BaseModel):
    task_id: str = Field(
        default="task_easy",
        description="One of: task_easy | task_medium | task_hard",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional random seed for reproducibility",
    )
    use_real_api: Optional[bool] = Field(
        default=None,
        description="Override the default environment variable for using real external APIs.",
    )


class ResetResponse(BaseModel):
    session_id:  str
    task_id:     str
    observation: Observation


                                                                                
            
                                                                                

class TaskInfo(BaseModel):
    id:          str
    name:        str
    difficulty:  TaskDifficulty
    description: str
    max_steps:   int
    score_range: str = "0.0 – 1.0"


class TaskListResponse(BaseModel):
    tasks: List[TaskInfo]


                                                                                
                  
                                                                                

class GraderResult(BaseModel):
    task_id:    str
    score:      float = Field(..., ge=0.0, le=1.0)
    breakdown:  Dict[str, float] = Field(default_factory=dict)
    passed:     bool
    message:    str
