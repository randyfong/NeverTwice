"""Preview registration; pass --register to submit to Agentverse.

Run from the repository root: backend/.venv/bin/python -m backend.register_agentverse
Secrets are read from the environment / root .env and never printed.
"""
import argparse
import ipaddress
import json
from urllib.parse import urlparse

from backend.app.config import settings
from uagents_core.identity import Identity
from uagents_core.utils.registration import (
    AgentverseRequestError,
    RegistrationRequestCredentials,
    register_chat_agent,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true", help="Submit registration to Agentverse")
    args = parser.parse_args()
    endpoint = settings.FETCHAI_AGENT_ENDPOINT
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path != "/submit" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("Set FETCHAI_AGENT_ENDPOINT to a public https://hostname/submit URL.")
    if parsed.hostname == "localhost" or parsed.hostname.endswith((".localhost", ".local")):
        parser.error("The endpoint must be public, not localhost.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        if not address.is_global:
            parser.error("The endpoint must use a public address.")
    seed = settings.FETCHAI_AGENT_SEED
    if not seed or seed in {"nevertwice_default_seed_phrase", "nevertwice_super_secret_recovery_seed_phrase", "nevertwice_verifying_referee_seed_phrase_2026"}:
        parser.error("Set FETCHAI_AGENT_SEED to a private, stable seed before registering.")
    print(json.dumps({
        "name": settings.FETCHAI_AGENT_NAME,
        "address": Identity.from_seed(seed, 0).address,
        "endpoint": endpoint,
        "submit": args.register,
    }, indent=2))
    if not args.register:
        return
    if not settings.AGENTVERSE_API_KEY:
        parser.error("Set AGENTVERSE_API_KEY locally; do not paste it into chat.")
    try:
        register_chat_agent(
            name=settings.FETCHAI_AGENT_NAME,
            endpoint=endpoint,
            active=True,
            credentials=RegistrationRequestCredentials(
                agentverse_api_key=settings.AGENTVERSE_API_KEY,
                agent_seed_phrase=seed,
            ),
            description="Pre-merge crash-log analysis, candidate patch testing, and failure-pattern memory for coding agents.",
            readme=("# NeverTwice\n\nSend a JSON object containing `raw_crash_log`, "
                    "optional `enable_memory` (boolean), and `domain` (code). "
                    "NeverTwice returns a pre-merge verdict from its analysis pipeline. "
                    "Model/database services must be configured for live results; "
                    "unconfigured services can use demo fallbacks. "
                    "Results are not a production safety certification."),
            starter_prompts=["What does NeverTwice do?"],
        )
    except AgentverseRequestError as exc:
        raise SystemExit(f"Agentverse registration failed: {exc}") from None
    print("Registered successfully. Keep the agent and its public endpoint running.")


if __name__ == "__main__":
    main()
