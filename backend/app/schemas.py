from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


class BehavioralContract(BaseModel):
    """Structured contract generated from raw crash logs / stack traces."""
    contract_id: str = Field(..., description="Unique UUID or identifier for the contract")
    domain: str = Field(default="code", description="Application domain (e.g., code, sql, cloud)")
    target_function: str = Field(..., description="Function or module name where flaw originated")
    expected_inputs: dict[str, Any] = Field(default_factory=dict, description="Typical input signature / arguments")
    required_invariants: list[str] = Field(
        default_factory=list,
        description="Conditions that must strictly hold true across all executions",
    )
    forbidden_side_effects: list[str] = Field(
        default_factory=list,
        description="Forbidden behaviors or side effects that must never recur",
    )
    summary: str = Field(default="", description="High-level description of failure mode and contract intent")


class SkillRuleCard(BaseModel):
    """Episodic memory rule unit stored in and retrieved from MongoDB Atlas."""
    id: str = Field(..., description="Unique card ID or MongoDB ObjectID string")
    domain: str = Field(default="code", description="Application domain tag")
    title: str = Field(..., description="Short descriptive title of rule")
    flaw_pattern: str = Field(..., description="Pattern description of the anti-pattern or vulnerability")
    invariant_rule: str = Field(..., description="Hard rule to prevent recurrence of this flaw pattern")
    win_rate_delta: float = Field(default=0.0, description="Observed success/prevention delta score")
    embedding: list[float] | None = Field(default=None, description="768-dim vector embedding")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SandboxTestResult(BaseModel):
    """Test telemetry captured from isolated pytest execution."""
    passed: bool
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    failed: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time_seconds: float = 0.0


class JudgeVerdict(BaseModel):
    """Evaluation verdict produced by Google DeepMind Judge."""
    verdict_status: Literal["BLOCKED", "VERIFIED_MERGE_READY", "PASS", "FAIL", "NEEDS_REVISION"]
    safety_score: float = Field(..., ge=0.0, le=100.0, description="Calculated safety confidence score (0-100)")
    invariants_passed: int = Field(default=0, ge=0)
    invariants_total: int = Field(default=0, ge=0)
    critical_vulnerability: str | None = Field(
        default=None,
        description="Identified vulnerability or failure description if blocked",
    )
    reasoning: str = Field(..., description="Detailed explanation supporting verdict")
    recommended_rule_patch: str | None = Field(
        default=None,
        description="Proposed SkillRuleCard invariant rule if novel flaw detected",
    )


class PipelineRunRequest(BaseModel):
    """Input payload to trigger the full NeverTwice pipeline."""
    run_id: str | None = None
    raw_crash_log: str = Field(..., description="Raw stack trace or runtime crash log")
    domain: str = Field(default="code", description="Target application domain")
    enable_memory: bool = Field(default=True, description="Enable MongoDB episodic memory recall")
    dry_run: bool = Field(default=False, description="Run without updating persistent memory")


class PipelineRunResponse(BaseModel):
    """End-to-end telemetry and artifacts produced by the pipeline."""
    run_id: str
    timestamp: str
    contract: BehavioralContract
    active_rules_used: list[Any] = Field(default_factory=list)
    candidate_patch: str
    execution_trace: dict[str, Any]
    verdict: JudgeVerdict
    verdict_signature: str | None = None
    new_rule_card: dict[str, Any] | None = None
