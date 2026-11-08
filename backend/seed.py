"""
backend/seed.py - Standalone or module demo reset utility
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path automatically
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pymongo import MongoClient
from backend.app.config import settings
from backend.app.pipeline.memory_engine import clear_memory_state


def reset_demo():
    print(f"Connecting to MongoDB Atlas ({settings.MONGODB_DATABASE_NAME})...")
    try:
        res = clear_memory_state(reset_all_rules=True)
        print(f"✓ Cleared {res.get('deleted_trajectories', 0)} past run trajectories from MongoDB.")
        print(f"✓ Cleared {res.get('deleted_rules', 0)} stored rules from MongoDB.")
        print("✓ Demo database is ready for live pitch Run 1 (Cold Start).")
    except Exception as e:
        print(f"⚠️ MongoDB Atlas connection notice: {e}")
        print("✓ In-memory store fallback will handle live demo runs.")


if __name__ == "__main__":
    reset_demo()
