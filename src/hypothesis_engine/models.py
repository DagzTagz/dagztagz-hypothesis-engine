"""Structured data models for the Phase 1 hypothesis workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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


class BackgroundBrief(BaseModel):
    """Phase 1 stand-in for literature retrieval (model knowledge only)."""

    topic: str
    summary: str = Field(description="Short background briefing")
    key_concepts: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(
        default_factory=list,
        description="What this brief is NOT (e.g. not a literature search)",
    )
    caveats: list[str] = Field(default_factory=list)


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


class VerificationResult(BaseModel):
    """Adversarial check of one hypothesis."""

    hypothesis_id: str
    verdict: Verdict
    confidence: Confidence = Confidence.MEDIUM
    consistency_notes: str
    critiques: list[CritiquePoint] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)


class SuggestedTest(BaseModel):
    """A concrete way to test a hypothesis."""

    hypothesis_id: str
    title: str
    method: str = Field(description="experiment | simulation | analysis | observation")
    description: str
    what_would_falsify: str
    rough_difficulty: Confidence = Confidence.MEDIUM
    notes: list[str] = Field(default_factory=list)


class HypothesisBundle(BaseModel):
    """Full structured output for one run of the Phase 1 workflow."""

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
