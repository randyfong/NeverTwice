"""
backend/simulate_pr_agent.py - Standalone or module external agent simulator
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path automatically
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from uagents import Agent, Context
from backend.app.protocol.uagent_node import VerifyCodeRequest, VerifyCodeResponse, nevertwice_agent

EXTERNAL_AGENT_SEED = "external_devin_agent_mock_seed_2026"
external_agent = Agent(
    name="devin_autonomous_bot",
    port=8002,
    seed=EXTERNAL_AGENT_SEED,
    endpoint=["http://127.0.0.1:8002/submit"],
)


@external_agent.on_event("startup")
async def send_verification(ctx: Context):
    ctx.logger.info("🤖 Devin Bot online. Submitting candidate PR to NeverTwice Referee...")
    req = VerifyCodeRequest(
        task_id="PR-CHECKOUT-001",
        repo_url="https://github.com/acme/shop",
        pr_number=42,
        raw_crash_log="DuplicateChargeException: Cart charge already in flight",
        enable_memory=True,
        domain="code",
    )
    await ctx.send(nevertwice_agent.address, req)


@external_agent.on_message(model=VerifyCodeResponse)
async def handle_verdict(ctx: Context, sender: str, msg: VerifyCodeResponse):
    ctx.logger.info(f"✅ Received NeverTwice Verdict: {msg.verdict_status} ({msg.safety_score}%)")
    ctx.logger.info(f"🔑 Cryptographic Assertion: {msg.agent_signature}")
    if msg.applied_rule_card_id:
        ctx.logger.info(f"🧠 Applied Episodic Rule: {msg.applied_rule_card_id} (+{msg.delta_improvement}% Win Rate)")


if __name__ == "__main__":
    external_agent.run()
