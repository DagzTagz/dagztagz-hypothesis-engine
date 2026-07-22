"""Unit tests for structured models (no API calls)."""

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


def test_bundle_roundtrip_json():
    checks = [
        CheckResult(id=cid, status=CheckStatus.PASS, summary=f"ok {cid}")
        for cid in REQUIRED_CHECK_IDS
    ]
    bundle = HypothesisBundle(
        topic="photosynthesis efficiency",
        background=BackgroundBrief(
            topic="photosynthesis efficiency",
            summary="Mock summary",
            key_concepts=["chlorophyll"],
            known_limitations=["not literature"],
        ),
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="X increases Y under Z",
                rationale="Because…",
                assumptions=["lab conditions"],
            )
        ],
        verifications=[
            VerificationResult(
                hypothesis_id="H1",
                verdict=Verdict.PLAUSIBLE,
                confidence=Confidence.MEDIUM,
                consistency_notes="Seems consistent at high level",
                checks=checks,
            )
        ],
        tests=[
            SuggestedTest(
                hypothesis_id="H1",
                title="Measure Y while varying X",
                method="experiment",
                description="Controlled lab assay",
                what_would_falsify="Y does not change with X",
            )
        ],
        overall_notes="ok",
        meta={"phase": 2, "verification": "multi_check_v1"},
    )
    data = bundle.to_pretty_dict()
    again = HypothesisBundle.model_validate(data)
    assert again.hypotheses[0].id == "H1"
    assert again.verifications[0].verdict == Verdict.PLAUSIBLE
    assert len(again.verifications[0].checks) == 4
    assert again.verifications[0].checks[0].id == "consistency"


def test_verification_checks_default_empty():
    """Older payloads without checks still validate (empty list)."""
    ver = VerificationResult(
        hypothesis_id="H1",
        verdict=Verdict.NEEDS_REVISION,
        consistency_notes="legacy shape",
    )
    assert ver.checks == []
