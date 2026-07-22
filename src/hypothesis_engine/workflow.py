"""Single workflow: background → generate → multi-check verify → suggest tests."""

from __future__ import annotations

import json
from collections.abc import Callable

from openai import OpenAI

from hypothesis_engine import prompts
from hypothesis_engine.config import Settings, get_settings
from hypothesis_engine.llm import build_client, chat_json
from hypothesis_engine.models import (
    REQUIRED_CHECK_IDS,
    BackgroundBrief,
    CheckResult,
    CheckStatus,
    Confidence,
    Hypothesis,
    HypothesisBundle,
    SuggestedTest,
    Verdict,
    VerificationResult,
)

# Bumped when verification schema gains multi-check dimensions (still one API call).
VERIFICATION_SCHEMA = "multi_check_v1"


def estimate_api_calls(n_hypotheses: int) -> int:
    """Rough live-mode call count: background + generate + verify×N + tests×N.

    Multi-check verification still uses one verify call per hypothesis (richer
    JSON, not extra round-trips).
    """
    n = max(1, min(5, int(n_hypotheses)))
    return 2 + 2 * n


def run_workflow(
    topic: str,
    *,
    n_hypotheses: int = 2,
    settings: Settings | None = None,
    client: OpenAI | None = None,
    dry_run: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> HypothesisBundle:
    """Run the full pipeline for a topic (background → generate → verify → tests).

    Parameters
    ----------
    topic:
        Scientific topic or short research question.
    n_hypotheses:
        How many hypotheses to propose (kept small for cost/clarity).
    dry_run:
        If True, return deterministic mock output without calling the API.
    on_progress:
        Optional callback for human-readable step updates (e.g. CLI spinner text).
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")
    if n_hypotheses < 1 or n_hypotheses > 5:
        raise ValueError("n_hypotheses must be between 1 and 5")

    def _progress(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    settings = settings or get_settings()

    if dry_run:
        _progress("Dry-run: building mock results (no network)…")
        return _mock_bundle(topic, n_hypotheses)

    client = client or build_client(settings)
    model = settings.xai_model
    total = estimate_api_calls(n_hypotheses)
    step = 0

    def _tick(label: str) -> None:
        nonlocal step
        step += 1
        _progress(f"[{step}/{total}] {label}")

    _tick("Calling xAI for background brief (this can take a while)…")
    background = _step_background(client, model, topic)
    _progress("Background brief received.")

    _tick("Generating hypotheses (please wait; do not type)…")
    hypotheses = _step_generate(client, model, topic, background, n_hypotheses)
    _progress(f"Generated {len(hypotheses)} hypothesis(es).")

    verifications: list[VerificationResult] = []
    tests: list[SuggestedTest] = []
    for hyp in hypotheses:
        _tick(f"Multi-check verifying {hyp.id} (one API call)…")
        ver = _step_verify(client, model, topic, background, hyp)
        verifications.append(ver)
        check_bits = ", ".join(f"{c.id}={c.status.value}" for c in ver.checks)
        _progress(f"{hyp.id} verification done ({ver.verdict.value}; {check_bits}).")

        _tick(f"Suggesting tests for {hyp.id}…")
        tests.extend(_step_tests(client, model, topic, hyp, ver))
        _progress(f"{hyp.id} test suggestions done.")

    _progress("All API steps finished. Assembling report…")
    overall = _overall_notes(hypotheses, verifications)
    return HypothesisBundle(
        topic=topic,
        background=background,
        hypotheses=hypotheses,
        verifications=verifications,
        tests=tests,
        overall_notes=overall,
        meta={
            "phase": 2,
            "model": model,
            "n_hypotheses": n_hypotheses,
            "background_mode": "model_knowledge_only",
            "verification": VERIFICATION_SCHEMA,
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
    data["checks"] = [
        c.model_dump(mode="json") for c in _normalize_checks(data.get("checks"))
    ]
    return VerificationResult.model_validate(data)


def _normalize_checks(raw: object) -> list[CheckResult]:
    """Ensure the four fixed multi-check slots are present and ordered.

    Unknown ids from the model are dropped; missing required ids become unclear.
    """
    by_id: dict[str, CheckResult] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id", "")).strip().lower().replace(" ", "_").replace("-", "_")
            if cid not in REQUIRED_CHECK_IDS or cid in by_id:
                continue
            try:
                by_id[cid] = CheckResult.model_validate({**item, "id": cid})
            except Exception:  # noqa: BLE001 — bad model row → placeholder
                by_id[cid] = CheckResult(
                    id=cid,
                    status=CheckStatus.UNCLEAR,
                    summary="Model returned an invalid check object for this id.",
                )

    ordered: list[CheckResult] = []
    for cid in REQUIRED_CHECK_IDS:
        if cid in by_id:
            ordered.append(by_id[cid])
        else:
            ordered.append(
                CheckResult(
                    id=cid,
                    status=CheckStatus.UNCLEAR,
                    summary="Model omitted this check; treat as not assessed.",
                )
            )
    return ordered


def _mock_checks(*, plausible: bool) -> list[CheckResult]:
    """Deterministic multi-check rows for dry-run."""
    if plausible:
        return [
            CheckResult(
                id="consistency",
                status=CheckStatus.PASS,
                summary="Mock: statement coheres with its listed assumptions.",
            ),
            CheckResult(
                id="testability",
                status=CheckStatus.PASS,
                summary="Mock: claim is framed as measurable and falsifiable.",
            ),
            CheckResult(
                id="confounds",
                status=CheckStatus.WARN,
                summary="Mock: alternative explanations not fully ruled out.",
            ),
            CheckResult(
                id="prior_knowledge",
                status=CheckStatus.PASS,
                summary="Mock: no obvious conflict with well-established knowledge.",
            ),
        ]
    return [
        CheckResult(
            id="consistency",
            status=CheckStatus.WARN,
            summary="Mock: some tension between claim and assumptions.",
        ),
        CheckResult(
            id="testability",
            status=CheckStatus.PASS,
            summary="Mock: still testable in principle.",
        ),
        CheckResult(
            id="confounds",
            status=CheckStatus.FAIL,
            summary="Mock: major confounds missing; needs clearer controls.",
        ),
        CheckResult(
            id="prior_knowledge",
            status=CheckStatus.WARN,
            summary="Mock: partial tension with established patterns (synthetic).",
        ),
    ]


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
        "Run complete (multi-check verification). "
        "Treat outputs as research aids, not established science. "
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
        plausible = i % 2 == 1
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
                verdict=Verdict.PLAUSIBLE if plausible else Verdict.NEEDS_REVISION,
                confidence=Confidence.LOW,
                consistency_notes="Dry-run multi-check verification placeholder.",
                checks=_mock_checks(plausible=plausible),
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
        meta={
            "phase": 2,
            "dry_run": True,
            "n_hypotheses": n,
            "verification": VERIFICATION_SCHEMA,
        },
    )


def bundle_to_json(bundle: HypothesisBundle, *, indent: int = 2) -> str:
    return json.dumps(bundle.to_pretty_dict(), indent=indent, ensure_ascii=False)
