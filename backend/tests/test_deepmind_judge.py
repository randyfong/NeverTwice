import pytest
from backend.app.schemas import BehavioralContract, JudgeVerdict
from backend.app.pipeline.deepmind_judge import deepmind_judge


@pytest.mark.asyncio
async def test_judge_blocked_on_failing_trace():
    contract = BehavioralContract(
        contract_id="CONTRACT-CHECKOUT-88",
        domain="code",
        target_function="process_cart_payment",
        required_invariants=["Single charge per customer checkout intent"],
        forbidden_side_effects=["Duplicate deduction on rapid multi-click"],
    )
    failed_trace = {
        "passed": False,
        "tests_run": 2,
        "tests_passed": 1,
        "tests_failed": 1,
        "failed": 1,
        "stdout": "FAILED test_suite.py::test_adversarial_rapid_retry - AssertionError: Duplicate charge detected!",
    }

    verdict = await deepmind_judge.evaluate_merge(
        contract=contract,
        candidate_patch="def process_cart_payment(): return {'charged': True}",
        sandbox_trace=failed_trace,
    )

    assert isinstance(verdict, JudgeVerdict)
    assert verdict.verdict_status in ["BLOCKED", "FAIL"]
    assert verdict.safety_score < 70.0
    assert verdict.critical_vulnerability is not None

    sig = deepmind_judge.generate_verdict_signature(verdict, contract.contract_id)
    assert sig.startswith("0x")
    assert len(sig) == 34  # 0x + 32 chars


@pytest.mark.asyncio
async def test_judge_verified_on_passing_trace():
    contract = BehavioralContract(
        contract_id="CONTRACT-CHECKOUT-88",
        domain="code",
        target_function="process_cart_payment",
        required_invariants=["Single charge per customer checkout intent"],
        forbidden_side_effects=["Duplicate deduction on rapid multi-click"],
    )
    passed_trace = {
        "passed": True,
        "tests_run": 2,
        "tests_passed": 2,
        "tests_failed": 0,
        "failed": 0,
        "stdout": "2 passed in 0.01s",
    }

    verdict = await deepmind_judge.evaluate_merge(
        contract=contract,
        candidate_patch="def process_cart_payment(idempotency_key): ... lock ...",
        sandbox_trace=passed_trace,
    )

    assert isinstance(verdict, JudgeVerdict)
    assert verdict.verdict_status in ["VERIFIED_MERGE_READY", "PASS"]
    assert verdict.safety_score >= 90.0
    assert verdict.critical_vulnerability is None

