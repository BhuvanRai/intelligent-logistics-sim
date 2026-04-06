"""
FastAPI application — OpenEnv-compliant server.

Endpoints
─────────
POST /reset          → Start new episode, return first observation
POST /step           → Send action, receive reward + next observation
GET  /state/{sid}    → Full internal state snapshot
GET  /tasks          → List all task definitions
GET  /health         → Health-check for deployment ping
GET  /               → Landing page / environment summary
"""
from __future__ import annotations

import os
import traceback
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.environment import get_state, reset, step
from .models import (
    Action,
    EnvironmentState,
    ResetRequest,
    ResetResponse,
    StepResult,
    TaskListResponse,
)
from .tasks.registry import get_all_tasks

                                                                                
              
                                                                                

app = FastAPI(
    title       = "Intelligent Logistics Orchestration — OpenEnv",
    description = (
        "An OpenEnv-compliant environment that simulates real-world logistics "
        "driver assignment. Supports three tasks (easy / medium / hard) with "
        "scored rewards in [0, 1]."
    ),
    version = "1.0.0",
    docs_url= "/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


                                                                                
                    
                                                                                

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": tb},
    )


                                                                                
         
                                                                                

@app.get("/health", tags=["meta"])
async def health() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


                                                                                
       
                                                                                

@app.get("/", tags=["meta"])
async def root() -> Dict[str, Any]:
    return {
        "name":        "Intelligent Logistics Orchestration",
        "version":     "1.0.0",
        "description": "OpenEnv environment for AI-driven driver assignment.",
        "tasks":       [t.id for t in get_all_tasks()],
        "docs":        "/docs",
        "endpoints": {
            "reset":  "POST /reset",
            "step":   "POST /step",
            "state":  "GET  /state/{session_id}",
            "tasks":  "GET  /tasks",
            "health": "GET  /health",
        },
    }


                                                                                
                         
                                                                                

@app.post("/reset", response_model=ResetResponse, tags=["openenv"])
async def api_reset(request: ResetRequest) -> ResetResponse:
    """
    Start a new episode.

    - **task_id**: `task_easy` | `task_medium` | `task_hard`
    - **seed**: optional integer for reproducibility
    """
    return reset(request)


@app.post("/step", response_model=StepResult, tags=["openenv"])
async def api_step(action: Action) -> StepResult:
    """
    Execute one driver-assignment action.

    Send the `session_id` returned by `/reset` and the `driver_id` of the
    chosen driver.  Returns per-step reward and the next observation.
    When `done=true`, also returns the episode `score`.
    """
    return step(action)


@app.get("/state/{session_id}", response_model=EnvironmentState, tags=["openenv"])
async def api_state(session_id: str) -> EnvironmentState:
    """Return the full internal state snapshot for a session."""
    return get_state(session_id)


@app.get("/tasks", response_model=TaskListResponse, tags=["openenv"])
async def api_tasks() -> TaskListResponse:
    """List all available tasks with metadata."""
    return TaskListResponse(tasks=get_all_tasks())


                                                                                
              
                                                                                

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(
        "app.main:app",
        host    = "0.0.0.0",
        port    = port,
        reload  = False,
        workers = 1,
        log_level = os.getenv("LOG_LEVEL", "info"),
    )
