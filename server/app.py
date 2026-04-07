import os
import sys
import uvicorn

# Ensure the root project directory is on the path so `app/...` can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

def main():
    """
    Entry point for the OpenEnv multi-mode deployment server.
    """
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
