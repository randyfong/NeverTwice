import asyncio
import logging
from typing import Any
from pymongo import MongoClient
from google import genai
from backend.app.config import settings
from backend.app.schemas import SkillRuleCard

logger = logging.getLogger("nevertwice.memory_engine")

# ---------------------------------------------------------------------------
# MongoDB Client & Collection Handles
# ---------------------------------------------------------------------------
_mongo_client: MongoClient | None = None
_db = None
_cards_collection = None
_trajectories_collection = None

# In-memory storage fallback for local/offline testing
_in_memory_cards: dict[str, dict[str, Any]] = {}
_in_memory_trajectories: list[dict[str, Any]] = {} if False else []


def clear_memory_state(reset_all_rules: bool = True) -> dict[str, Any]:
    """
    Clears recorded trajectories and stored rules in MongoDB (and in-memory fallback)
    so the demo can restart completely cleanly.
    """
    global _in_memory_cards, _in_memory_trajectories
    _in_memory_cards.clear()
    _in_memory_trajectories.clear()

    db = get_mongo_db()
    deleted_trajectories = 0
    deleted_rules = 0

    if db is not None:
        try:
            res_traj = db["run_trajectories"].delete_many({})
            deleted_trajectories = res_traj.deleted_count
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Clear trajectories failed: {e}")

        try:
            # Delete all stored skill rules in MongoDB to reset episodic memory completely
            res_rule = db["skill_cards"].delete_many({}) if reset_all_rules else db["skill_cards"].delete_one({"id": "RULE-PAY-042"})
            deleted_rules = res_rule.deleted_count
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Clear rules failed: {e}")

    return {
        "status": "reset_complete",
        "cleared_mongo": db is not None,
        "deleted_trajectories": deleted_trajectories,
        "deleted_rules": deleted_rules,
    }


def get_demo_state() -> dict[str, Any]:
    """Retrieves current recorded trajectories and active rules from MongoDB or in-memory fallback."""
    db = get_mongo_db()
    trajectories = []
    rules = []

    if db is not None:
        try:
            trajectories = list(db["run_trajectories"].find({}, {"_id": 0}).sort("timestamp", -1).limit(20))
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Fetch trajectories failed: {e}")
        try:
            rules = list(db["skill_cards"].find({}, {"_id": 0, "embedding": 0}).limit(20))
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Fetch rules failed: {e}")
    else:
        trajectories = list(reversed(_in_memory_trajectories))[:20]
        rules = [{k: v for k, v in card.items() if k != "embedding"} for card in _in_memory_cards.values()][:20]

    return {
        "trajectories": trajectories,
        "rules": rules,
        "total_trajectories": len(trajectories),
        "total_rules": len(rules),
    }


def get_mongo_db():
    global _mongo_client, _db, _cards_collection, _trajectories_collection
    if _db is None:
        try:
            _mongo_client = MongoClient(
                settings.MONGODB_ATLAS_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
            )
            # Ping to verify reachability
            _mongo_client.admin.command("ping")
            _db = _mongo_client[settings.MONGODB_DATABASE_NAME]
            _cards_collection = _db["skill_cards"]
            _trajectories_collection = _db["run_trajectories"]
            logger.info("[Mongo Atlas] Connected successfully to Atlas cluster.")
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Connection unready/offline ({type(e).__name__}: {e}). Using in-memory store.")
            _db = None
    return _db


# ---------------------------------------------------------------------------
# Gemini Embedding Helper (768 Dimensions)
# ---------------------------------------------------------------------------
def get_embedding(text: str) -> list[float]:
    """Generates a 768-dimensional vector embedding using Google Gemini text-embedding-004."""
    if not settings.GOOGLE_API_KEY:
        return [0.0] * 768

    try:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        response = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=text,
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.warning(f"[Embedding Warning] Failed to compute embedding via Gemini: {e}")
        return [0.0] * 768


# ---------------------------------------------------------------------------
# 1. Retrieval: Vector Search with Exact Match Fallback
# ---------------------------------------------------------------------------
async def fetch_matching_rule_cards(query_context: str, domain: str = "code", limit: int = 3) -> list[dict[str, Any]]:
    """
    Retrieves matching SkillRuleCards using MongoDB Atlas $vectorSearch.
    Falls back gracefully to domain queries or in-memory cache if offline.
    """
    db = get_mongo_db()
    if db is not None:
        try:
            query_vector = await asyncio.to_thread(get_embedding, query_context)
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": settings.MONGODB_VECTOR_INDEX,
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": limit * 10,
                        "limit": limit,
                        "filter": {
                            "domain": {"$eq": domain}
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "id": 1,
                        "domain": 1,
                        "title": 1,
                        "flaw_pattern": 1,
                        "invariant_rule": 1,
                        "win_rate_delta": 1,
                        "tags": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]
            results = list(db["skill_cards"].aggregate(pipeline))
            if results:
                return results
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Vector search warning: {e}. Falling back to standard query...")

        try:
            fallback_cursor = db["skill_cards"].find(
                {"domain": domain},
                {"_id": 0, "embedding": 0},
            ).limit(limit)
            results = list(fallback_cursor)
            if results:
                return results
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Domain query fallback failed: {e}")

    # In-memory store fallback
    matched = [
        {k: v for k, v in card.items() if k != "embedding"}
        for card in _in_memory_cards.values()
        if card.get("domain") == domain
    ]
    return matched[:limit]


# ---------------------------------------------------------------------------
# 2. Memory Consolidation: Storing Lessons from Blocked Runs
# ---------------------------------------------------------------------------
async def create_and_store_skill_card(contract: Any, trace: dict[str, Any], verdict: Any) -> dict[str, Any]:
    """
    Transforms a judge-blocked failure into a persistent SkillRuleCard in Atlas.
    """
    rule_id = "RULE-PAY-042"
    title = "Always Enforce Idempotency Key Lock on Financial Endpoints"
    crit = getattr(verdict, "critical_vulnerability", "Duplicate transaction execution")
    flaw_pattern = f"Rapid multi-click failure: {crit}"
    invariant_rule = (
        getattr(verdict, "recommended_rule_patch", None)
        or "Assert and acquire an atomic distributed lock on the idempotency token before calling charge APIs."
    )

    text_to_embed = f"{title}. {flaw_pattern}. {invariant_rule}"
    embedding = await asyncio.to_thread(get_embedding, text_to_embed)

    card_doc = {
        "id": rule_id,
        "domain": getattr(contract, "domain", "code"),
        "title": title,
        "flaw_pattern": flaw_pattern,
        "invariant_rule": invariant_rule,
        "win_rate_delta": 41.4,
        "tags": ["payments", "race-condition", "idempotency", "redis"],
        "embedding": embedding,
    }

    db = get_mongo_db()
    if db is not None:
        try:
            await asyncio.to_thread(
                db["skill_cards"].update_one,
                {"id": rule_id},
                {"$set": card_doc},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Save card failed ({e}), writing to in-memory fallback.")
            _in_memory_cards[rule_id] = card_doc
    else:
        _in_memory_cards[rule_id] = card_doc

    return {k: v for k, v in card_doc.items() if k != "embedding"}


# ---------------------------------------------------------------------------
# 3. Trajectory Logging: Run History for Analytics & Audit
# ---------------------------------------------------------------------------
async def save_run_trajectory(run_data: dict[str, Any]) -> str:
    """
    Saves complete pre-merge pipeline execution trajectories.
    """
    trajectory = {
        "run_id": run_data.get("run_id"),
        "task_name": run_data.get("task_name", "Shopping Cart Checkout"),
        "status": run_data.get("verdict", {}).get("verdict_status") if isinstance(run_data.get("verdict"), dict) else getattr(run_data.get("verdict"), "verdict_status", "UNKNOWN"),
        "safety_score": run_data.get("verdict", {}).get("safety_score") if isinstance(run_data.get("verdict"), dict) else getattr(run_data.get("verdict"), "safety_score", 0.0),
        "contract": run_data.get("contract"),
        "rules_applied": run_data.get("active_rules_used", []),
        "tests_passed": run_data.get("execution_trace", {}).get("passed", False),
        "total_tests": run_data.get("execution_trace", {}).get("tests_run", 0),
        "timestamp": run_data.get("timestamp"),
    }

    db = get_mongo_db()
    if db is not None:
        try:
            result = await asyncio.to_thread(db["run_trajectories"].insert_one, trajectory)
            return str(result.inserted_id)
        except Exception as e:
            logger.warning(f"[Mongo Atlas] Trajectory logging failed ({e}), saving to in-memory fallback.")

    _in_memory_trajectories.append(trajectory)
    return f"mem_{len(_in_memory_trajectories)}"

