import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from backend.app.schemas import (
    BehavioralContract,
    SkillRuleCard,
    SandboxTestResult,
    JudgeVerdict,
    PipelineRunRequest,
    PipelineRunResponse,
)
from backend.app.config import Settings


def test_behavioral_contract_valid():
    contract = BehavioralContract(
        contract_id="contract_001",
        domain="defi",
        target_function="withdraw_liquidity",
        expected_inputs={"amount": 100, "user": "0xABC"},
        required_invariants=["user_balance >= amount", "pool_liquidity >= amount"],
        forbidden_side_effects=["reentrancy", "unauthorized_minting"],
        summary="Prevent reentrancy on withdrawal",
    )
    assert contract.contract_id == "contract_001"
    assert len(contract.required_invariants) == 2
    assert "reentrancy" in contract.forbidden_side_effects


def test_skill_rule_card_valid():
    card = SkillRuleCard(
        id="card_100",
        domain="defi",
        title="CEI Pattern Enforcement",
        flaw_pattern="External state call before balance deduction",
        invariant_rule="Always update internal ledger prior to invoking external transfer",
        win_rate_delta=0.15,
        embedding=[0.012] * 768,
    )
    assert card.id == "card_100"
    assert len(card.embedding) == 768
    assert isinstance(card.created_at, datetime)


def test_judge_verdict_bounds():
    verdict = JudgeVerdict(
        verdict_status="VERIFIED_MERGE_READY",
        safety_score=98.0,
        invariants_passed=3,
        invariants_total=3,
        critical_vulnerability=None,
        reasoning="All checks passed.",
    )
    assert verdict.safety_score == 98.0

    # Test safety_score validation bounds (0.0 to 100.0)
    with pytest.raises(ValidationError):
        JudgeVerdict(
            verdict_status="PASS",
            safety_score=150.0,
            invariants_passed=1,
            invariants_total=1,
            critical_vulnerability=None,
            reasoning="Invalid score",
        )


def test_settings_defaults():
    settings = Settings()
    assert settings.APP_ENV in ["development", "production", "testing"]
    assert settings.MONGODB_DATABASE_NAME == "nevertwice_memory"
    assert settings.SUBQ_TIMEOUT_SECONDS == 3.5
    assert settings.SANDBOX_TIMEOUT_SECONDS == 5.0
