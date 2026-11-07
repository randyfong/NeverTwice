import pytest
from backend.app.schemas import BehavioralContract, SkillRuleCard
from backend.app.pipeline.extractor import extract_code_block
from backend.app.pipeline.builder_swarm import meta_worker_swarm
from backend.app.pipeline.sandbox_runner import run_in_sandbox


def test_extract_code_block():
    markdown_wrapped = """
    Here is the patch:
    ```python
    def add(a, b):
        return a + b
    ```
    Enjoy!
    """
    assert extract_code_block(markdown_wrapped) == "def add(a, b):\n        return a + b"

    plain = "def hello(): return 'world'"
    assert extract_code_block(plain) == plain


@pytest.mark.asyncio
async def test_meta_swarm_cold_start():
    contract = BehavioralContract(
        contract_id="CONTRACT-CHECKOUT-88",
        domain="code",
        target_function="process_cart_payment",
        expected_inputs={"amount": 100},
        required_invariants=["Single charge per customer checkout intent"],
        forbidden_side_effects=["Duplicate deduction on rapid multi-click"],
    )

    # 1. Cold start: empty rules
    patch, test_suite = await meta_worker_swarm(contract, rules=[])
    assert "def process_cart_payment" in patch
    assert "test_happy_path" in test_suite

    # 2. Execute in sandbox (Cold start should fail adversarial duplicate charge test)
    telemetry = await run_in_sandbox(patch, test_suite)
    assert telemetry["tests_run"] >= 1
    # Cold start naive patch fails the duplicate charge check
    assert telemetry["passed"] is False
    assert telemetry["failed"] >= 1


@pytest.mark.asyncio
async def test_meta_swarm_warm_start_with_rules():
    contract = BehavioralContract(
        contract_id="CONTRACT-CHECKOUT-88",
        domain="code",
        target_function="process_cart_payment",
        expected_inputs={"amount": 100},
        required_invariants=["Single charge per customer checkout intent"],
        forbidden_side_effects=["Duplicate deduction on rapid multi-click"],
    )
    rule = SkillRuleCard(
        id="RULE-PAY-042",
        domain="code",
        title="Always Enforce Idempotency Key Lock",
        flaw_pattern="Duplicate transaction execution",
        invariant_rule="Acquire lock on idempotency token",
        win_rate_delta=41.4,
    )

    # 1. Warm start: rule injected
    patch, test_suite = await meta_worker_swarm(contract, rules=[rule])
    assert "idempotency_key" in patch

    # 2. Execute in sandbox (Warm start should pass all tests including adversarial check)
    telemetry = await run_in_sandbox(patch, test_suite)
    assert telemetry["passed"] is True
    assert telemetry["tests_failed"] == 0
    assert telemetry["tests_passed"] >= 2

