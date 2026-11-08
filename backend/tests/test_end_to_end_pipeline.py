import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.pipeline.memory_engine import _in_memory_cards


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "database" in data


@pytest.mark.asyncio
async def test_reset_demo_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/reset-demo")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "reset_complete"

        res_state = await client.get("/api/demo-state")
        assert res_state.status_code == 200
        state = res_state.json()
        assert state["total_trajectories"] == 0
        assert state["total_rules"] == 0


@pytest.mark.asyncio
async def test_end_to_end_pipeline_transition():
    """
    Validates the Golden Path:
    - Run 1 (Cold Start): No prior memory -> Naive patch fails red team -> Judge BLOCKS -> Consolidates RULE-PAY-042.
    - Run 2 (Warm Memory): Recalls RULE-PAY-042 -> Resilient patch passes -> Judge VERIFIED_MERGE_READY.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Reset memory state
        _in_memory_cards.clear()

        raw_crash = """
        Traceback (most recent call last):
          File "/app/services/checkout.py", line 42, in process_cart_payment
            raise DuplicateChargeException("Cart charge already in flight")
        """

        # -----------------
        # RUN 1: Cold Start
        # -----------------
        run1_payload = {
            "run_id": "RUN-DEMO-001",
            "raw_crash_log": raw_crash,
            "domain": "code",
            "enable_memory": True,
            "dry_run": False,
        }
        res1 = await client.post("/api/run-pipeline", json=run1_payload)
        assert res1.status_code == 200
        data1 = res1.json()

        assert data1["run_id"] == "RUN-DEMO-001"
        assert data1["contract"]["target_function"] == "process_cart_payment"
        # Cold start must have 0 prior active rules
        assert len(data1["active_rules_used"]) == 0
        # Execution trace must have failed
        assert data1["execution_trace"]["passed"] is False
        # DeepMind Judge must have BLOCKED
        assert data1["verdict"]["verdict_status"] == "BLOCKED"
        assert data1["verdict"]["safety_score"] < 70.0
        assert data1["verdict"]["critical_vulnerability"] is not None
        # Must have consolidated a new rule card
        assert data1["new_rule_card"] is not None
        assert data1["new_rule_card"]["id"] == "RULE-PAY-042"

        # ------------------
        # RUN 2: Warm Memory
        # ------------------
        run2_payload = {
            "run_id": "RUN-DEMO-002",
            "raw_crash_log": raw_crash,
            "domain": "code",
            "enable_memory": True,
            "dry_run": False,
        }
        res2 = await client.post("/api/run-pipeline", json=run2_payload)
        assert res2.status_code == 200
        data2 = res2.json()

        assert data2["run_id"] == "RUN-DEMO-002"
        # Warm run must have recalled RULE-PAY-042 from episodic memory
        assert len(data2["active_rules_used"]) >= 1
        assert data2["active_rules_used"][0]["id"] == "RULE-PAY-042"
        # Patch must now pass all tests in the sandbox
        assert data2["execution_trace"]["passed"] is True
        # DeepMind Judge must now verify merge readiness
        assert data2["verdict"]["verdict_status"] == "VERIFIED_MERGE_READY"
        assert data2["verdict"]["safety_score"] >= 90.0
        assert data2["verdict"]["critical_vulnerability"] is None
        # Cryptographic signature present for Fetch.ai verification
        assert data2["verdict_signature"].startswith("0x")

