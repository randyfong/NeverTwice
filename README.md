# NeverTwice: Autonomous Pre-Merge Referee & Anti-Recurrence Engine

> **NeverTwice** is a deterministic pre-merge referee and episodic memory layer for autonomous coding agents (Devin, AutoPR, OpenHands). It guarantees that code-level flaws, race conditions, and catastrophic production failures are **never repeated twice**.

---

## 🏆 Key Architecture & Platform Integrations

1. **Subquadratic Sparse Prefill (Stage 1)**: Ingests noisy, multi-megabyte log files and truncated stack traces in milliseconds to synthesize structured `BehavioralContract` models under a strict 3.5s timeout budget.
2. **MongoDB Atlas Episodic Memory (Stage 2 & 6)**: Stores past failure patterns as `SkillRuleCard` units with **768-dimensional vector embeddings** (via Google Gemini `text-embedding-004`) and performs `$vectorSearch` memory recall.
3. **Meta Model API Swarm (Stage 3)**: Dispatches a 3-worker concurrent swarm (`asyncio.gather`):
   - **Worker A**: Candidate patch synthesizer with retrieved memory injection.
   - **Worker B**: Nominal happy-path test generator.
   - **Worker C**: Adversarial red-team stress tester crafting concurrency & boundary attacks.
4. **Isolated Ephemeral Sandbox (Stage 4)**: Executes code and pytest suites inside a temporary subprocess directory with a strict 5.0s budget to capture deterministic test telemetry.
5. **Google DeepMind Pre-Merge Judge (Stage 5)**: Impartial referee powered by Gemini 2.5 (`temperature=0.0`, `response_schema=JudgeVerdict`) that checks runtime traces against behavioral invariants and generates cryptographic attestation signatures.
6. **Fetch.ai uAgents Protocol**: Exposes NeverTwice to the network so autonomous coding agents can query the referee node (`uagent_node.py`) and verify pull requests before merging.

---

## 🚀 Quick Start (One Command)

To run the backend, Fetch.ai referee agent, and frontend dashboard simultaneously:

```bash
./start.sh
```

- **Dashboard**: [http://localhost:5173](http://localhost:5173)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Fetch.ai Agent Endpoint**: `http://127.0.0.1:8001/submit`

---

## 🧪 Testing

Run the full automated test suite (16 tests across all modules):

```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/
```

Reset database memory state to Cold Start:
```bash
python3 backend/seed.py
```

Simulate an external coding bot querying the referee:
```bash
python3 backend/simulate_pr_agent.py
```

