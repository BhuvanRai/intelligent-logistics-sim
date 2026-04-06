                      
"""
pre_validation.py

A validation script to ensure the FastAPI server starts, the endpoints
are compliant with OpenEnv, and the three required tasks function properly.
This runs automatically during the Docker build.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

import requests

PORT = 7860
BASE_URL = f"http://127.0.0.1:{PORT}"

def wait_for_server(timeout: int = 15) -> bool:
    print(f"Waiting for server at {BASE_URL}...")
    for i in range(timeout):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=1)
            if r.status_code == 200:
                print("Server is up!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
        print(f"Waiting... ({i+1}/{timeout})")
    return False

def test_reset(task_id: str) -> str:
    print(f"  Testing /reset for {task_id}...")
    r = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id, "seed": 42}, timeout=5)
    r.raise_for_status()
    data = r.json()
    assert "session_id" in data
    assert "observation" in data
    assert "assignment" in data["observation"]
    assert "drivers" in data["observation"]
    return data["session_id"]

def test_step_and_state(session_id: str, task_id: str) -> None:
    print(f"  Testing /state and /step for {session_id}...")
               
    r = requests.get(f"{BASE_URL}/state/{session_id}", timeout=5)
    r.raise_for_status()
    state_data = r.json()
    driver_pool = state_data["driver_pool"]
    if not driver_pool:
        print("    No drivers in pool, skipping step test.")
        return
        
    first_driver_id = driver_pool[0]["id"]

               
    r = requests.post(
        f"{BASE_URL}/step",
        json={"session_id": session_id, "driver_id": first_driver_id},
        timeout=5
    )
    r.raise_for_status()
    step_data = r.json()
    assert "reward" in step_data
    assert "observation" in step_data
    assert "done" in step_data

def run_validations():
    print("Fetching tasks...")
    r = requests.get(f"{BASE_URL}/tasks", timeout=5)
    r.raise_for_status()
    tasks = r.json().get("tasks", [])
    
    task_ids = [t["id"] for t in tasks]
    print(f"Found tasks: {task_ids}")
    
    assert "task_easy" in task_ids
    assert "task_medium" in task_ids
    assert "task_hard" in task_ids

    for t_id in task_ids:
        print(f"\nValidating {t_id}")
        session_id = test_reset(t_id)
        test_step_and_state(session_id, t_id)
        
    print("\nAll OpenEnv endpoints validated successfully.")

if __name__ == "__main__":
    print("Starting FastAPI server in the background...")
    os.environ["PORT"] = str(PORT)
    os.environ["LOG_LEVEL"] = "error"
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)]
    )

    try:
        if not wait_for_server():
            print("Failed to start server in time.")
            sys.exit(1)
            
        run_validations()
    except Exception as e:
        print(f"Validation failed: {e}")
        sys.exit(1)
    finally:
        print("Stopping server...")
        server_process.terminate()
        server_process.wait()
