"""Offline workflow tests using --dry-run style mock path."""

import json

import pytest

from hypothesis_engine.cli import main
from hypothesis_engine.llm import parse_json_object
from hypothesis_engine.models import REQUIRED_CHECK_IDS, CheckStatus
from hypothesis_engine.workflow import (
    VERIFICATION_SCHEMA,
    _normalize_checks,
    estimate_api_calls,
    run_workflow,
)


def test_dry_run_bundle_shape():
    bundle = run_workflow("quantum biology", n_hypotheses=2, dry_run=True)
    assert bundle.topic == "quantum biology"
    assert len(bundle.hypotheses) == 2
    assert len(bundle.verifications) == 2
    assert bundle.meta.get("dry_run") is True
    assert bundle.meta.get("verification") == VERIFICATION_SCHEMA
    assert bundle.meta.get("phase") == 2
    for ver in bundle.verifications:
        assert [c.id for c in ver.checks] == list(REQUIRED_CHECK_IDS)
        assert all(isinstance(c.status, CheckStatus) for c in ver.checks)
        assert all(c.summary for c in ver.checks)
    payload = json.loads(bundle.model_dump_json())
    assert "background" in payload
    assert payload["verifications"][0]["checks"][0]["id"] == "consistency"


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
    # Multi-check is richer JSON in the same verify call, not extra round-trips.
    assert estimate_api_calls(1) == 4
    assert estimate_api_calls(2) == 6
    assert estimate_api_calls(5) == 12


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


def test_cli_dry_run_json(capsys):
    code = main(["--dry-run", "--json-only", "test topic", "-n", "1"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["topic"] == "test topic"
    assert len(data["hypotheses"]) == 1
    assert data["meta"]["verification"] == "multi_check_v1"
    assert len(data["verifications"][0]["checks"]) == 4
