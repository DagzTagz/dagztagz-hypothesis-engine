"""Structured data models for the hypothesis workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# Fixed multi-check ids (Phase 2 verification). One API call still returns all.
REQUIRED_CHECK_IDS: tuple[str, ...] = (
    "consistency",
    "testability",
    "confounds",
    "prior_knowledge",
)


class Confidence(StrEnum):
    """Coarse confidence labels — not calibrated probabilities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Verdict(StrEnum):
    """Adversarial verification outcome for a single hypothesis."""

    PLAUSIBLE = "plausible"
    NEEDS_REVISION = "needs_revision"
    CONTRADICTED = "contradicted"
    NOT_TESTABLE = "not_testable"


class CheckStatus(StrEnum):
    """Per-check outcome within multi-check verification."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNCLEAR = "unclear"


class RetrievedPassage(BaseModel):
    """One chunk from local (or mock) retrieval for RAG v0."""

    id: str = Field(description="Stable id in this run, e.g. S1")
    title: str
    identifier: str = Field(description="Local path or mock:// identifier")
    snippet: str = Field(description="Short excerpt used for grounding")
    year: str | None = None
    backend: str = Field(
        default="local",
        description="local | mock (v0 has no remote backends)",
    )
    score: float | None = None


class BackgroundBrief(BaseModel):
    """Background briefing; optional local-file grounding (RAG v0)."""

    topic: str
    summary: str = Field(description="Short background briefing")
    key_concepts: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(
        default_factory=list,
        description="What this brief is NOT (e.g. not a full literature search)",
    )
    caveats: list[str] = Field(default_factory=list)
    sources: list[RetrievedPassage] = Field(
        default_factory=list,
        description="Retrieved local passages when --retrieve is used",
    )
    grounding: str = Field(
        default="model_only",
        description="model_only | retrieved | mixed",
    )


class Hypothesis(BaseModel):
    """A single testable scientific hypothesis plus rationale."""

    id: str = Field(description="Stable id within this run, e.g. H1")
    statement: str = Field(description="Clear, falsifiable hypothesis statement")
    rationale: str = Field(description="Why this might be true / interesting")
    assumptions: list[str] = Field(default_factory=list)
    domain: str | None = None


class CritiquePoint(BaseModel):
    """One adversarial critique against a hypothesis."""

    claim: str
    severity: Confidence = Confidence.MEDIUM
    evidence_or_reasoning: str


class CheckResult(BaseModel):
    """One dimension of multi-check adversarial verification."""

    id: str = Field(
        description="Check id: consistency | testability | confounds | prior_knowledge"
    )
    status: CheckStatus = CheckStatus.UNCLEAR
    summary: str = Field(description="One-sentence finding for this check")


class VerificationResult(BaseModel):
    """Adversarial check of one hypothesis (overall + per-check dimensions)."""

    hypothesis_id: str
    verdict: Verdict
    confidence: Confidence = Confidence.MEDIUM
    consistency_notes: str
    checks: list[CheckResult] = Field(
        default_factory=list,
        description=(
            "Fixed multi-check results "
            "(consistency, testability, confounds, prior_knowledge)"
        ),
    )
    critiques: list[CritiquePoint] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)


class SuggestedTest(BaseModel):
    """A concrete way to test a hypothesis (richer Phase 2 experiment design)."""

    hypothesis_id: str
    title: str
    method: str = Field(description="experiment | simulation | analysis | observation")
    description: str
    what_would_falsify: str
    what_is_measured: str = Field(
        default="",
        description="What observable / quantity this design actually records",
    )
    controls: list[str] = Field(
        default_factory=list,
        description="Controls, baselines, or comparison conditions",
    )
    materials_or_data: list[str] = Field(
        default_factory=list,
        description="Key materials, instruments, datasets, or compute needed",
    )
    addresses_checks: list[str] = Field(
        default_factory=list,
        description=(
            "Multi-check ids this design responds to "
            "(e.g. confounds, testability) when known"
        ),
    )
    rough_difficulty: Confidence = Confidence.MEDIUM
    rough_duration: str = Field(
        default="",
        description="Coarse time scale, e.g. hours | days | weeks | months",
    )
    notes: list[str] = Field(default_factory=list)


class HypothesisBundle(BaseModel):
    """Full structured output for one run of the workflow."""

    topic: str
    background: BackgroundBrief
    hypotheses: list[Hypothesis]
    verifications: list[VerificationResult]
    tests: list[SuggestedTest]
    overall_notes: str = Field(
        default="",
        description="Honest summary of uncertainty and next steps",
    )
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_pretty_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
