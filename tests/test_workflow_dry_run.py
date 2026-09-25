"""Offline workflow tests using --dry-run style mock path."""

import json

import pytest

from hypothesis_engine import __version__
from hypothesis_engine.cli import main
from hypothesis_engine.llm import parse_json_object
from hypothesis_engine.models import REQUIRED_CHECK_IDS, CheckStatus, Confidence, Verdict
from hypothesis_engine.workflow import (
    TESTS_SCHEMA,
    VERIFICATION_SCHEMA,
    _normalize_background,
    _normalize_checks,
    _normalize_suggested_test,
    _normalize_verification,
    _parse_confidence,
    _parse_verdict,
    estimate_api_calls,
    run_workflow,
)


def test_dry_run_bundle_shape():
    bundle = run_workflow("quantum biology", n_hypotheses=2, dry_run=True)
    assert bundle.topic == "quantum biology"
    assert len(bundle.hypotheses) == 2
    assert len(bundle.verifications) == 2
    assert len(bundle.tests) == 2
    assert bundle.meta.get("dry_run") is True
    assert bundle.meta.get("verification") == VERIFICATION_SCHEMA
    assert bundle.meta.get("tests") == TESTS_SCHEMA
    assert bundle.meta.get("phase") == 2
    assert bundle.meta.get("engine_version") == __version__
    for ver in bundle.verifications:
        assert [c.id for c in ver.checks] == list(REQUIRED_CHECK_IDS)
        assert all(isinstance(c.status, CheckStatus) for c in ver.checks)
        assert all(c.summary for c in ver.checks)
    for t in bundle.tests:
        assert t.what_is_measured
        assert t.controls
        assert t.materials_or_data
        assert t.addresses_checks
        assert t.rough_duration
        assert set(t.addresses_checks) <= set(REQUIRED_CHECK_IDS)
    payload = json.loads(bundle.model_dump_json())
    assert "background" in payload
    assert payload["verifications"][0]["checks"][0]["id"] == "consistency"
    assert payload["tests"][0]["what_is_measured"]
    assert payload["meta"]["tests"] == "richer_tests_v1"


def test_normalize_checks_fills_missing_and_orders():
    raw = [
        {"id": "testability", "status": "pass", "summary": "ok test"},
        {"id": "unknown_extra", "status": "fail", "summary": "drop me"},
        {"id": "Consistency", "status": "warn", "summary": "case normalize"},
    ]
    checks = _normalize_checks(raw)
    assert [c.id for c in checks] == list(REQUIRED_CHECK_IDS)
    assert checks[0].status == CheckStatus.WARN
    assert checks[0].summary == "case normalize"
    assert checks[1].status == CheckStatus.PASS
    assert checks[2].status == CheckStatus.UNCLEAR  # confounds omitted
    assert checks[3].status == CheckStatus.UNCLEAR  # prior_knowledge omitted


def test_normalize_checks_empty_input():
    checks = _normalize_checks(None)
    assert len(checks) == 4
    assert all(c.status == CheckStatus.UNCLEAR for c in checks)


def test_estimate_api_calls_unchanged_by_multi_check():
    # Multi-check / richer tests are richer JSON in the same calls, not extra trips.
    assert estimate_api_calls(1) == 4
    assert estimate_api_calls(2) == 6
    assert estimate_api_calls(5) == 12


def test_normalize_suggested_test_coerces_partial_payload():
    t = _normalize_suggested_test(
        {
            "title": "Pilot",
            "method": "experiment",
            "description": "Do a small pilot",
            "what_would_falsify": "No signal",
            "controls": "single string control",
            "materials_or_data": ["kit A", "", "  kit B  "],
            "addresses_checks": ["Confounds", "unknown_check", "testability", "confounds"],
            "what_is_measured": None,
            "rough_difficulty": "not-a-real-level",
        },
        hyp_id="H1",
    )
    assert t.hypothesis_id == "H1"
    assert t.controls == ["single string control"]
    assert t.materials_or_data == ["kit A", "kit B"]
    assert t.addresses_checks == ["confounds", "testability"]
    assert t.what_is_measured == ""
    assert t.rough_duration == ""
    assert t.rough_difficulty == Confidence.MEDIUM


def test_normalize_suggested_test_unknown_method_and_missing_title():
    t = _normalize_suggested_test(
        {
            "method": "quantum-vibes",
            "description": "x",
            "what_would_falsify": "y",
        },
        hyp_id="H2",
    )
    assert t.method == "analysis"
    assert t.title.startswith("Suggested test")
    assert t.hypothesis_id == "H2"


def test_normalize_verification_soft_defaults_bad_enums():
    ver = _normalize_verification(
        {
            "verdict": "totally_wrong_label",
            "confidence": "super-high",
            "consistency_notes": "notes",
            "checks": [
                {"id": "consistency", "status": "maybe", "summary": "s"},
            ],
        },
        hyp_id="H1",
    )
    assert ver.verdict == Verdict.NEEDS_REVISION
    assert ver.confidence == Confidence.MEDIUM
    assert ver.checks[0].status.value == "unclear"
    assert ver.hypothesis_id == "H1"


def test_parse_helpers():
    assert _parse_confidence("HIGH") == Confidence.HIGH
    assert _parse_confidence("nope") == Confidence.MEDIUM
    assert _parse_verdict("not_testable") == Verdict.NOT_TESTABLE
    assert _parse_verdict("???") == Verdict.NEEDS_REVISION


def test_empty_topic_raises():
    with pytest.raises(ValueError):
        run_workflow("  ", dry_run=True)


def test_parse_json_with_fences():
    text = """Here you go:\n```json\n{\"a\": 1}\n```\n"""
    assert parse_json_object(text) == {"a": 1}


def test_parse_json_repairs_invalid_backslash_escape():
    # Models often emit \s or \path inside strings — invalid in JSON.
    text = r'{"hypothesis_id": "H1", "notes": "use \sigma and C:\temp\file"}'
    data = parse_json_object(text)
    assert data["hypothesis_id"] == "H1"
    assert "notes" in data


def test_parse_json_keeps_comma_brace_inside_string():
    text = '{"a": "hello, }", "b": 1,}'
    data = parse_json_object(text)
    assert data["a"] == "hello, }"
    assert data["b"] == 1


def test_background_fields_are_clipped():
    brief = _normalize_background(
        {"summary": "A" * 20_000, "key_concepts": ["x" * 2_000] * 40, "topic": "t"},
        topic="t",
        passages=[],
    )
    assert len(brief.summary) <= 4_000
    assert len(brief.key_concepts) <= 24
    assert all(len(item) <= 500 for item in brief.key_concepts)


def test_cli_dry_run_json(capsys):
    code = main(["--dry-run", "--json-only", "test topic", "-n", "1"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["topic"] == "test topic"
    assert len(data["hypotheses"]) == 1
    assert data["meta"]["verification"] == "multi_check_v1"
    assert data["meta"]["tests"] == "richer_tests_v1"
    assert len(data["verifications"][0]["checks"]) == 4
    assert data["tests"][0]["controls"]
    assert data["tests"][0]["addresses_checks"]
