import pytest
from backend.app.schemas import BehavioralContract
from backend.app.pipeline.reconstructor import (
    reconstruct_behavioral_contract,
    DETERMINISTIC_RECONSTRUCTION_FALLBACK,
)


@pytest.mark.asyncio
async def test_reconstructor_fallback_when_offline(monkeypatch):
    # Ensure offline / fallback path works cleanly
    from backend.app.config import settings

    monkeypatch.setattr(settings, "SUBQUADRATIC_API_KEY", "")

    sample_log = """
    Traceback (most recent call last):
      File "/app/services/checkout.py", line 42, in process_cart_payment
        raise DuplicateChargeException("Cart charge already in flight")
    """

    contract = await reconstruct_behavioral_contract(sample_log, domain="code")

    assert isinstance(contract, BehavioralContract)
    assert contract.contract_id == "CONTRACT-CHECKOUT-88"
    assert contract.target_function == "process_cart_payment"
    assert len(contract.required_invariants) >= 2
    assert "Single charge per customer checkout intent" in contract.required_invariants
    assert "Duplicate deduction on rapid multi-click" in contract.forbidden_side_effects


@pytest.mark.asyncio
async def test_reconstructor_domain_fallbacks():
    sql_contract = await reconstruct_behavioral_contract("Deadlock error in SQL transaction", domain="sql")
    assert sql_contract.target_function == "migrate_user_tenants"
    assert "Zero data loss on transactional rollback" in sql_contract.required_invariants

    cloud_contract = await reconstruct_behavioral_contract("Overlapping CIDR detected", domain="cloud")
    assert cloud_contract.target_function == "provision_vpc_peering"
    assert "No public exposure of internal subnet CIDR" in cloud_contract.required_invariants


@pytest.mark.asyncio
async def test_reconstructor_network_resilience(monkeypatch):
    from backend.app.config import settings

    # Simulate configured key pointing to an unreachable endpoint to verify timeout/graceful degradation
    monkeypatch.setattr(settings, "SUBQUADRATIC_API_KEY", "test_key_dummy")
    monkeypatch.setattr(settings, "SUBQUADRATIC_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setattr(settings, "SUBQ_TIMEOUT_SECONDS", 0.2)

    contract = await reconstruct_behavioral_contract("Error 500: Server timeout in checkout", domain="code")
    assert isinstance(contract, BehavioralContract)
    assert contract.target_function == "process_cart_payment"

