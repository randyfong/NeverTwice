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


def reset_demo():
    print(f"Connecting to MongoDB Atlas ({settings.MONGODB_DATABASE_NAME})...")
    try:
        client = MongoClient(
            settings.MONGODB_ATLAS_URI,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
        )
        client.admin.command("ping")
        db = client[settings.MONGODB_DATABASE_NAME]

        # 1. Clear run trajectories
        traj_res = db["run_trajectories"].delete_many({})
        print(f"✓ Cleared {traj_res.deleted_count} past run trajectories.")

        # 2. Remove learned payments rule to reset to cold state
        rule_res = db["skill_cards"].delete_one({"id": "RULE-PAY-042"})
        print(f"✓ Removed RULE-PAY-042 (Cold start reset: {rule_res.deleted_count} removed).")

        total_rules = db["skill_cards"].count_documents({})
        print(f"✓ Active skill rules remaining in episodic memory: {total_rules}")
        print("✓ Demo database is ready for live pitch Run 1 (Cold Start).")
    except Exception as e:
        print(f"⚠️ MongoDB Atlas connection notice: {e}")
        print("✓ In-memory store fallback will handle live demo runs.")


if __name__ == "__main__":
    reset_demo()
