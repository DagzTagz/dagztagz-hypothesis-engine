"""Phase 1 single workflow: background → generate → verify → suggest tests."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from hypothesis_engine import prompts
from hypothesis_engine.config import Settings, get_settings
from hypothesis_engine.llm import build_client, chat_json
from hypothesis_engine.models import (
    BackgroundBrief,
    Confidence,
    Hypothesis,
    HypothesisBundle,
    SuggestedTest,
    VerificationResult,
    Verdict,
)


def estimate_api_calls(n_hypotheses: int) -> int:
    """Rough live-mode call count: background + generate + verify×N + tests×N."""
    n = max(1, min(5, int(n_hypotheses)))
    return 2 + 2 * n


def run_workflow(
    topic: str,
    *,
    n_hypotheses: int = 2,
    settings: Settings | None = None,
    client: OpenAI | None = None,
    dry_run: bool = False,
) -> HypothesisBundle:
    """Run the full Phase 1 pipeline for a topic.

    Parameters
    ----------
    topic:
        Scientific topic or short research question.
    n_hypotheses:
        How many hypotheses to propose (kept small for cost/clarity).
    dry_run:
        If True, return deterministic mock output without calling the API.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")
    if n_hypotheses < 1 or n_hypotheses > 5:
        raise ValueError("n_hypotheses must be between 1 and 5")

    settings = settings or get_settings()

    if dry_run:
        return _mock_bundle(topic, n_hypotheses)

    client = client or build_client(settings)
    model = settings.xai_model

    background = _step_background(client, model, topic)
    hypotheses = _step_generate(client, model, topic, background, n_hypotheses)

    verifications: list[VerificationResult] = []
    tests: list[SuggestedTest] = []
    for hyp in hypotheses:
        ver = _step_verify(client, model, topic, background, hyp)
        verifications.append(ver)
        tests.extend(_step_tests(client, model, topic, hyp, ver))

    overall = _overall_notes(hypotheses, verifications)
    return HypothesisBundle(
        topic=topic,
        background=background,
        hypotheses=hypotheses,
        verifications=verifications,
        tests=tests,
        overall_notes=overall,
        meta={
            "phase": 1,
            "model": model,
            "n_hypotheses": n_hypotheses,
            "background_mode": "model_knowledge_only",
        },
    )


def _step_background(client: OpenAI, model: str, topic: str) -> BackgroundBrief:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.BACKGROUND_USER.format(topic=topic),
        temperature=0.3,
    )
    if "known_limitations" not in data:
        data["known_limitations"] = [
            "Phase 1 brief uses model knowledge only; not a literature search."
        ]
    return BackgroundBrief.model_validate(data)


def _step_generate(
    client: OpenAI,
    model: str,
    topic: str,
    background: BackgroundBrief,
    n: int,
) -> list[Hypothesis]:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.GENERATE_USER.format(
            topic=topic,
            background_json=background.model_dump_json(),
            n=n,
        ),
        temperature=0.6,
    )
    raw = data.get("hypotheses", data if isinstance(data, list) else [])
    if not isinstance(raw, list) or not raw:
        raise ValueError("Model returned no hypotheses")
    hyps = [Hypothesis.model_validate(item) for item in raw[:n]]
    # Normalize ids if model forgot them
    for i, h in enumerate(hyps, start=1):
        if not h.id:
            h.id = f"H{i}"
    return hyps


def _step_verify(
    client: OpenAI,
    model: str,
    topic: str,
    background: BackgroundBrief,
    hyp: Hypothesis,
) -> VerificationResult:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.VERIFY_USER.format(
            topic=topic,
            background_json=background.model_dump_json(),
            hypothesis_json=hyp.model_dump_json(),
        ),
        temperature=0.3,
    )
    if "hypothesis_id" not in data:
        data["hypothesis_id"] = hyp.id
    return VerificationResult.model_validate(data)


def _step_tests(
    client: OpenAI,
    model: str,
    topic: str,
    hyp: Hypothesis,
    ver: VerificationResult,
) -> list[SuggestedTest]:
    data = chat_json(
        client,
        model=model,
        system=prompts.SYSTEM_SCIENTIST,
        user=prompts.TESTS_USER.format(
            topic=topic,
            hypothesis_json=hyp.model_dump_json(),
            verification_json=ver.model_dump_json(),
        ),
        temperature=0.5,
    )
    raw = data.get("tests", [])
    if not isinstance(raw, list):
        return []
    tests: list[SuggestedTest] = []
    for item in raw:
        if isinstance(item, dict) and "hypothesis_id" not in item:
            item = {**item, "hypothesis_id": hyp.id}
        tests.append(SuggestedTest.model_validate(item))
    return tests


def _overall_notes(
    hypotheses: list[Hypothesis],
    verifications: list[VerificationResult],
) -> str:
    by_id = {v.hypothesis_id: v for v in verifications}
    parts: list[str] = []
    for h in hypotheses:
        v = by_id.get(h.id)
        if not v:
            parts.append(f"{h.id}: no verification")
            continue
        parts.append(f"{h.id}: verdict={v.verdict.value}, confidence={v.confidence.value}")
    return (
        "Phase 1 run complete. Treat outputs as research aids, not established science. "
        + " | ".join(parts)
    )


def _mock_bundle(topic: str, n: int) -> HypothesisBundle:
    """Deterministic offline output for demos and tests (no network)."""
    background = BackgroundBrief(
        topic=topic,
        summary=(
            f"Mock background for '{topic}'. In live mode this would be a short "
            "model-knowledge briefing, not a literature review."
        ),
        key_concepts=["mock-concept"],
        known_limitations=["dry-run mode; no LLM call"],
        caveats=["For local testing only"],
    )
    hypotheses: list[Hypothesis] = []
    verifications: list[VerificationResult] = []
    tests: list[SuggestedTest] = []
    for i in range(1, n + 1):
        hid = f"H{i}"
        hypotheses.append(
            Hypothesis(
                id=hid,
                statement=f"Mock hypothesis {i} about {topic}: measurable effect X depends on Y.",
                rationale="Generated in dry-run mode for scaffolding tests.",
                assumptions=["This is synthetic data"],
                domain="mock",
            )
        )
        verifications.append(
            VerificationResult(
                hypothesis_id=hid,
                verdict=Verdict.PLAUSIBLE if i % 2 else Verdict.NEEDS_REVISION,
                confidence=Confidence.LOW,
                consistency_notes="Dry-run verification placeholder.",
                critiques=[],
                contradictions=[],
                revision_suggestions=["Replace with live run for real critique"],
            )
        )
        tests.append(
            SuggestedTest(
                hypothesis_id=hid,
                title=f"Mock test for {hid}",
                method="simulation",
                description="Run a toy simulation that varies Y and measures X.",
                what_would_falsify="No dependence of X on Y under the stated conditions.",
                rough_difficulty=Confidence.LOW,
                notes=["dry-run"],
            )
        )
    return HypothesisBundle(
        topic=topic,
        background=background,
        hypotheses=hypotheses,
        verifications=verifications,
        tests=tests,
        overall_notes="Dry-run mock output; no API calls were made.",
        meta={"phase": 1, "dry_run": True, "n_hypotheses": n},
    )


def bundle_to_json(bundle: HypothesisBundle, *, indent: int = 2) -> str:
    return json.dumps(bundle.to_pretty_dict(), indent=indent, ensure_ascii=False)
