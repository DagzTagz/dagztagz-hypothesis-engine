"""CLI safety: live confirmation, audit log, friendly errors."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis_engine.cli import _friendly_error, main
from hypothesis_engine.workflow import estimate_api_calls


def test_estimate_api_calls():
    assert estimate_api_calls(1) == 4  # bg + gen + 1 verify + 1 tests
    assert estimate_api_calls(2) == 6
    assert estimate_api_calls(5) == 12


def test_dry_run_skips_live_confirm(capsys):
    code = main(["--dry-run", "--json-only", "-n", "1", "safety topic"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["meta"]["dry_run"] is True


def test_live_refuses_noninteractive_without_yes(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main(["live topic please", "-n", "1"])
    assert code == 2
    err = capsys.readouterr().err
    assert "LIVE MODE" in err or "non-interactive" in err or "Refusing" in err
    assert "tokens" in err.lower() or "pricing" in err.lower() or "Not a price quote" in err


def test_live_yes_reaches_missing_key(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    # Avoid loading a real .env key during unit tests
    monkeypatch.setenv("XAI_API_KEY", "")
    code = main(["live topic please", "-n", "1", "--yes"])
    assert code == 1
    err = capsys.readouterr().err
    assert "XAI_API_KEY" in err or "Missing" in err


def test_audit_log_dry_run(tmp_path: Path, capsys):
    log = tmp_path / "audit.jsonl"
    code = main(
        [
            "--dry-run",
            "--json-only",
            "-n",
            "1",
            "--audit-log",
            str(log),
            "audit topic",
        ]
    )
    assert code == 0
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    events = [json.loads(line)["event"] for line in lines]
    assert "start" in events
    assert "complete" in events


def test_friendly_error_missing_key():
    msg = _friendly_error(RuntimeError("Missing XAI_API_KEY. Copy .env.example"))
    assert "XAI_API_KEY" in msg
    assert "getting-started" in msg.lower() or ".env" in msg
