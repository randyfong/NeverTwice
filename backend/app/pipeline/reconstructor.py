import json
import logging
import httpx
from backend.app.schemas import BehavioralContract
from backend.app.config import settings

logger = logging.getLogger("nevertwice.reconstructor")

SUBQ_SYSTEM_PROMPT = """
You are the Subquadratic Behavioral Specification Reconstructor for NeverTwice.
Your job is to ingest noisy, messy, truncated system crash traces, console logs, and multi-file code contexts,
and reconstruct the underlying Behavioral Contract specifying what the code was SUPPOSED to do.

You must return ONLY a valid JSON object matching this schema:
{
  "contract_id": "CONTRACT-<DOMAIN>-<HASH>",
  "target_function": "<function_name_or_endpoint>",
  "expected_inputs": { "<arg_name>": "<expected_type_or_format>" },
  "required_invariants": [
    "<Explicit condition that must remain true during and after execution>"
  ],
  "forbidden_side_effects": [
    "<State corruption, duplicate charge, unhandled leakage that must never happen>"
  ]
}
Do not include markdown fences, preambles, or commentary. Output raw valid JSON only.
"""

DETERMINISTIC_RECONSTRUCTION_FALLBACK: dict[str, BehavioralContract] = {
    "code": BehavioralContract(
        contract_id="CONTRACT-CHECKOUT-88",
        domain="code",
        target_function="process_cart_payment",
        expected_inputs={"cart_id": "str", "amount": "float", "idempotency_key": "str"},
        required_invariants=[
            "Single charge per customer checkout intent",
            "Zero balance decrement if payment gateway times out",
        ],
        forbidden_side_effects=[
            "Duplicate deduction on rapid multi-click",
            "Unbounded non-idempotent transaction dispatch",
        ],
        summary="Prevent duplicate charges on payment retries",
    ),
    "sql": BehavioralContract(
        contract_id="CONTRACT-MIGRATION-12",
        domain="sql",
        target_function="migrate_user_tenants",
        expected_inputs={"batch_size": "int", "lock_timeout_ms": "int"},
        required_invariants=[
            "Zero data loss on transactional rollback",
            "Non-exclusive read locks preserved",
        ],
        forbidden_side_effects=[
            "Table deadlocks on concurrent worker write",
        ],
        summary="Ensure zero data loss and lock concurrency during schema migration",
    ),
    "cloud": BehavioralContract(
        contract_id="CONTRACT-TERRAFORM-04",
        domain="cloud",
        target_function="provision_vpc_peering",
        expected_inputs={"cidr_block": "str", "region": "str"},
        required_invariants=[
            "No public exposure of internal subnet CIDR",
            "Encrypted peering route tables enforced",
        ],
        forbidden_side_effects=[
            "Overlapping route collisions leading to route drops",
        ],
        summary="Enforce CIDR isolation and encryption on VPC peering",
    ),
}


async def reconstruct_behavioral_contract(raw_crash_log: str, domain: str = "code") -> BehavioralContract:
    """
    Submits raw crash telemetry to Subquadratic API to synthesize a BehavioralContract.
    Applies a strict timeout budget with instant fallback to guarantee demo resilience.
    """
    if not settings.SUBQUADRATIC_API_KEY:
        logger.info("[SubQ] Missing API Key: using deterministic contract fallback.")
        return DETERMINISTIC_RECONSTRUCTION_FALLBACK.get(domain, DETERMINISTIC_RECONSTRUCTION_FALLBACK["code"])

    headers = {
        "Authorization": f"Bearer {settings.SUBQUADRATIC_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "subq-context-v1",
        "messages": [
            {"role": "system", "content": SUBQ_SYSTEM_PROMPT},
            {"role": "user", "content": f"Domain: {domain}\n\nCrash Log & Telemetry:\n{raw_crash_log}"},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=settings.SUBQ_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{settings.SUBQUADRATIC_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            return BehavioralContract(
                contract_id=parsed.get("contract_id", f"CONTRACT-{domain.upper()}-AUTO"),
                domain=domain,
                target_function=parsed.get("target_function", "unknown_handler"),
                expected_inputs=parsed.get("expected_inputs", {}),
                required_invariants=parsed.get("required_invariants", []),
                forbidden_side_effects=parsed.get("forbidden_side_effects", []),
                summary=parsed.get("summary", ""),
            )

    except Exception as e:
        logger.warning(f"[SubQ] Call failed or timed out ({type(e).__name__}: {str(e)}). Engaging fallback contract.")
        return DETERMINISTIC_RECONSTRUCTION_FALLBACK.get(domain, DETERMINISTIC_RECONSTRUCTION_FALLBACK["code"])

