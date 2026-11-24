"""Run lifecycle (audit F6): one terminal audit event per start, honest progress."""

import json
from pathlib import Path

import pytest

from hypothesis_engine import cli, workflow
from hypothesis_engine.cli import main


def _events(log: Path) -> list[str]:
    return [json.loads(line)["event"] for line in log.read_text().splitlines()]


def test_output_failure_still_ends_the_run_in_the_audit_log(tmp_path: Path, capsys):
    log = tmp_path / "audit.jsonl"
    out = tmp_path / "out.json"
    out.symlink_to(tmp_path / "elsewhere.json")
    code = main(
        ["--dry-run", "--audit-log", str(log), "-o", str(out), "probe topic"]
    )
    assert code == 1
    assert _events(log) == ["start", "output_failed"]


def test_interrupt_still_ends_the_run_in_the_audit_log(
    tmp_path: Path, monkeypatch, capsys
):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_workflow", interrupted)
    log = tmp_path / "audit.jsonl"
    with pytest.raises(KeyboardInterrupt):
        main(["--dry-run", "--audit-log", str(log), "probe topic"])
    assert _events(log) == ["start", "interrupted"]


def test_error_and_complete_are_the_only_other_endings(
    tmp_path: Path, monkeypatch, capsys
):
    log = tmp_path / "audit.jsonl"
    assert main(["--dry-run", "--json-only", "--audit-log", str(log), "ok topic"]) == 0

    def broken(*args, **kwargs):
        raise ValueError("Model returned no hypotheses")

    monkeypatch.setattr(cli, "run_workflow", broken)
    assert main(["--dry-run", "--audit-log", str(log), "bad topic"]) == 1
    assert _events(log) == ["start", "complete", "start", "error"]


def test_progress_total_counts_the_hypotheses_that_survived(monkeypatch):
    """n=2 with one unusable row runs 4 steps, and progress must end at 4/4."""
    replies = iter(
        [
            {"summary": "brief", "key_concepts": [], "known_limitations": ["x"]},
            {
                "hypotheses": [
                    {"id": "H1", "statement": "X raises Y.", "rationale": "r"},
                    {"id": "H2"},  # no statement: dropped by _step_generate
                ]
            },
            {"verdict": "plausible", "confidence": "low", "checks": []},
            {"tests": []},
        ]
    )
    monkeypatch.setattr(workflow, "chat_json", lambda *a, **k: next(replies))
    monkeypatch.setenv("XAI_API_KEY", "xai-test-not-a-real-key")
    lines: list[str] = []
    bundle = workflow.run_workflow(
        "probe topic", n_hypotheses=2, client=object(), on_progress=lines.append
    )
    assert len(bundle.hypotheses) == 1
    steps = [line.split("]")[0] + "]" for line in lines if line.startswith("[")]
    assert steps == ["[1/6]", "[2/6]", "[3/4]", "[4/4]"]
