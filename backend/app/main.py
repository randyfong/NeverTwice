import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.app.config import settings
from backend.app.schemas import (
    PipelineRunRequest,
    PipelineRunResponse,
)
from backend.app.pipeline.reconstructor import reconstruct_behavioral_contract
from backend.app.pipeline.memory_engine import (
    fetch_matching_rule_cards,
    create_and_store_skill_card,
    save_run_trajectory,
)
from backend.app.pipeline.builder_swarm import meta_worker_swarm
from backend.app.pipeline.sandbox_runner import run_in_sandbox
from backend.app.pipeline.deepmind_judge import deepmind_judge


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Optional non-blocking background startup for Fetch.ai uAgent node
    uagent_task = None
    try:
        from backend.app.protocol.uagent_node import nevertwice_agent
        uagent_task = asyncio.create_task(nevertwice_agent.run_async())
        print(f"🤖 NeverTwice Fetch.ai Agent Node running at {nevertwice_agent.address}")
    except Exception as e:
        print(f"⚠️ Fetch.ai Agent Node notice: {e}")

    yield

    if uagent_task:
        uagent_task.cancel()


app = FastAPI(
    title="NeverTwice Pipeline API",
    description="Deterministic anti-recurrence engine for LLM coding agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "database": settings.MONGODB_DATABASE_NAME,
        "models": {
            "judge": settings.GEMINI_JUDGE_MODEL,
            "embedding": settings.GEMINI_EMBEDDING_MODEL,
        },
    }


@app.post("/api/run-pipeline", response_model=PipelineRunResponse)
async def execute_nevertwice_pipeline(req: PipelineRunRequest):
    """
    Executes the 6-stage NeverTwice pre-merge pipeline:
    1. Subquadratic: Reconstruct BehavioralContract from raw crash telemetry.
    2. MongoDB Atlas: Recall past SkillRuleCards matching contract invariants.
    3. Meta Model API: Dispatch 3-worker swarm (Patch, Happy Tests, Red-team Tests).
    4. Pytest Sandbox: Run patch & tests in isolated ephemeral directory.
    5. DeepMind Judge: Impartial evaluation of test telemetry against invariants.
    6. Memory Consolidation: If blocked, learn and persist new SkillRuleCard to Atlas.
    """
    start_time = time.time()
    run_id = req.run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"

    # Stage 1: Subquadratic Context Reconstruction
    contract = await reconstruct_behavioral_contract(req.raw_crash_log, req.domain)

    # Stage 2: MongoDB Atlas Vector Retrieval (Memory Recall)
    active_rules = []
    if req.enable_memory:
        query_text = f"{contract.target_function} {' '.join(contract.required_invariants)}"
        active_rules = await fetch_matching_rule_cards(query_text, domain=req.domain)

    # Stage 3: Meta Model API Worker Swarm (Rules injected into prompt context)
    candidate_patch, test_suite = await meta_worker_swarm(contract, active_rules)

    # Stage 4: Isolated Pytest Sandbox Execution
    execution_trace = await run_in_sandbox(candidate_patch, test_suite)

    # Stage 5: Google DeepMind Independent Pre-Merge Judge
    verdict = await deepmind_judge.evaluate_merge(contract, candidate_patch, execution_trace)
    verdict_sig = deepmind_judge.generate_verdict_signature(verdict, contract.contract_id)

    # Stage 6: Episodic Memory Consolidation on Failure
    new_card_generated = None
    if verdict.verdict_status == "BLOCKED" and not req.dry_run:
        new_card_generated = await create_and_store_skill_card(contract, execution_trace, verdict)

    total_duration_ms = round((time.time() - start_time) * 1000, 2)

    response_payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contract": contract,
        "active_rules_used": active_rules,
        "candidate_patch": candidate_patch,
        "execution_trace": execution_trace,
        "verdict": verdict,
        "verdict_signature": verdict_sig,
        "new_rule_card": new_card_generated,
    }

    # Background persistence of execution trajectory for audit analytics
    if not req.dry_run:
        asyncio.create_task(save_run_trajectory(response_payload))

    return PipelineRunResponse(**response_payload)


@app.post("/api/stream-pipeline")
async def stream_nevertwice_pipeline(req: PipelineRunRequest):
    """
    Server-Sent Events (SSE) streaming endpoint:
    Streams live stage transitions and intermediate telemetry to the frontend.
    """
    async def event_generator():
        run_id = req.run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"

        # Event 1: Pipeline Init
        yield f"data: {json.dumps({'event': 'PIPELINE_START', 'stage': 0, 'message': 'Initializing NeverTwice pre-merge pipeline...', 'run_id': run_id})}\n\n"
        await asyncio.sleep(0.1)

        # Event 2: Stage 1 Subquadratic Reconstruct
        yield f"data: {json.dumps({'event': 'STAGE_1_START', 'stage': 1, 'message': 'Subquadratic sparse prefill: Reconstructing behavioral contract...'})}\n\n"
        contract = await reconstruct_behavioral_contract(req.raw_crash_log, req.domain)
        yield f"data: {json.dumps({'event': 'STAGE_1_DONE', 'stage': 1, 'data': contract.model_dump()})}\n\n"

        # Event 3: Stage 2 MongoDB Memory Recall
        yield f"data: {json.dumps({'event': 'STAGE_2_START', 'stage': 2, 'message': 'MongoDB Atlas: Performing $vectorSearch for past episodic rule cards...'})}\n\n"
        active_rules = []
        if req.enable_memory:
            query_text = f"{contract.target_function} {' '.join(contract.required_invariants)}"
            active_rules = await fetch_matching_rule_cards(query_text, domain=req.domain)
        yield f"data: {json.dumps({'event': 'STAGE_2_DONE', 'stage': 2, 'rules_count': len(active_rules), 'data': active_rules})}\n\n"

        # Event 4: Stage 3 Meta Swarm Synthesis
        yield f"data: {json.dumps({'event': 'STAGE_3_START', 'stage': 3, 'message': 'Meta Model API: Worker Swarm synthesizing candidate patch & pytest suite...'})}\n\n"
        candidate_patch, test_suite = await meta_worker_swarm(contract, active_rules)
        yield f"data: {json.dumps({'event': 'STAGE_3_DONE', 'stage': 3, 'patch_length': len(candidate_patch)})}\n\n"

        # Event 5: Stage 4 Ephemeral Pytest Sandbox
        yield f"data: {json.dumps({'event': 'STAGE_4_START', 'stage': 4, 'message': 'Pytest Sandbox: Running isolated test suite in temporary directory...'})}\n\n"
        execution_trace = await run_in_sandbox(candidate_patch, test_suite)
        yield f"data: {json.dumps({'event': 'STAGE_4_DONE', 'stage': 4, 'data': execution_trace})}\n\n"

        # Event 6: Stage 5 Google DeepMind Judge
        yield f"data: {json.dumps({'event': 'STAGE_5_START', 'stage': 5, 'message': 'Google DeepMind Judge: Assessing execution trace against behavioral invariants...'})}\n\n"
        verdict = await deepmind_judge.evaluate_merge(contract, candidate_patch, execution_trace)
        verdict_sig = deepmind_judge.generate_verdict_signature(verdict, contract.contract_id)
        yield f"data: {json.dumps({'event': 'STAGE_5_DONE', 'stage': 5, 'data': verdict.model_dump(), 'signature': verdict_sig})}\n\n"

        # Event 7: Stage 6 Episodic Memory Consolidation
        new_card = None
        if verdict.verdict_status == "BLOCKED" and not req.dry_run:
            yield f"data: {json.dumps({'event': 'STAGE_6_START', 'stage': 6, 'message': 'Atlas Memory Consolidation: Synthesizing novel SkillRuleCard from failure...'})}\n\n"
            new_card = await create_and_store_skill_card(contract, execution_trace, verdict)
            yield f"data: {json.dumps({'event': 'STAGE_6_DONE', 'stage': 6, 'data': new_card})}\n\n"

        # Final Event: Complete Payload
        final_payload = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contract": contract.model_dump(),
            "active_rules_used": active_rules,
            "candidate_patch": candidate_patch,
            "execution_trace": execution_trace,
            "verdict": verdict.model_dump(),
            "verdict_signature": verdict_sig,
            "new_rule_card": new_card,
        }
        if not req.dry_run:
            asyncio.create_task(save_run_trajectory(final_payload))

        yield f"data: {json.dumps({'event': 'PIPELINE_COMPLETE', 'result': final_payload})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Static Frontend Serving for Unified Container Deployment
STATIC_DIST_PATH = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if STATIC_DIST_PATH.exists() and (STATIC_DIST_PATH / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIST_PATH / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Don't intercept API or docs routes
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")

        file_candidate = STATIC_DIST_PATH / full_path
        if full_path and file_candidate.exists() and file_candidate.is_file():
            return FileResponse(file_candidate)

        return FileResponse(STATIC_DIST_PATH / "index.html")

