import os


BASE_ROOT = os.getenv("LIVE_SMOKE_ROOT_URL", "http://localhost:8000").rstrip("/")
BASE = f"{BASE_ROOT}/api/v1"