import pytest
from backend.app.schemas import BehavioralContract, JudgeVerdict
from backend.app.pipeline.memory_engine import (
    get_embedding,
    fetch_matching_rule_cards,
    create_and_store_skill_card,
    save_run_trajectory,
    _in_memory_cards,
)


def test_get_embedding_format():
    # Embedding generation must produce 768 dimensions
    emb = get_embedding("idempotency key transaction lock")
    assert isinstance(emb, list)
    assert len(emb) == 768


@pytest.mark.asyncio
async def test_memory_engine_lifecycle():
    # 1. Clean in-memory state
    _in_memory_cards.clear()

    # 2. Verify empty recall (Cold start)
    cold_rules = await fetch_matching_rule_cards("process_cart_payment idempotency lock", domain="code")
    assert len(cold_rules) == 0

    # 3. Consolidate a newly blocked lesson
    contract = BehavioralContract(
        contract_id="CONTRACT-CHECKOUT-88",
        domain="code",
        target_function="process_cart_payment",
        expected_inputs={"amount": 100},
        required_invariants=["Single charge per customer checkout intent"],
        forbidden_side_effects=["Duplicate deduction on rapid multi-click"],
    )
    verdict = JudgeVerdict(
        verdict_status="BLOCKED",
        safety_score=58.0,
        invariants_passed=1,
        invariants_total=2,
        critical_vulnerability="Double-Click Race Condition: Charged customer twice ($100 instead of $50)",
        reasoning="Payment endpoint permitted double charge on rapid retry.",
        recommended_rule_patch="Enforce atomic lock on idempotency token prior to payment dispatch.",
    )

    stored_card = await create_and_store_skill_card(contract, {}, verdict)
    assert stored_card["id"] == "RULE-PAY-042"
    assert "idempotency" in stored_card["invariant_rule"].lower()

    # 4. Verify warm memory recall (Run 2)
    warm_rules = await fetch_matching_rule_cards("process_cart_payment idempotency", domain="code")
    assert len(warm_rules) >= 1
    assert warm_rules[0]["id"] == "RULE-PAY-042"

    # 5. Save trajectory audit trace
    traj_id = await save_run_trajectory({
        "run_id": "test_run_001",
        "verdict": verdict.model_dump(),
        "contract": contract.model_dump(),
        "active_rules_used": warm_rules,
        "execution_trace": {"passed": False, "tests_run": 2},
    })
    assert traj_id is not None
