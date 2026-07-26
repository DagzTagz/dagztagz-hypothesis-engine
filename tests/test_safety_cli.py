"""CLI safety: live confirmation, audit log, friendly errors."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis_engine import __version__
from hypothesis_engine.cli import _display_topic, _friendly_error, main
from hypothesis_engine.config import Settings
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
    assert log.stat().st_mode & 0o777 == 0o600


def test_output_and_audit_files_are_owner_only(tmp_path: Path, capsys):
    """-o and --audit-log must not be group/world-readable by default."""
    out = tmp_path / "out.json"
    log = tmp_path / "audit.jsonl"
    # Pre-create loose perms; CLI should tighten on write/append.
    out.write_text("old\n", encoding="utf-8")
    out.chmod(0o664)
    log.write_text("", encoding="utf-8")
    log.chmod(0o664)

    code = main(
        [
            "--dry-run",
            "--json-only",
            "-n",
            "1",
            "-o",
            str(out),
            "--audit-log",
            str(log),
            "private topic",
        ]
    )
    assert code == 0
    assert out.stat().st_mode & 0o777 == 0o600
    assert log.stat().st_mode & 0o777 == 0o600
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["topic"] == "private topic"


def test_friendly_error_missing_key():
    msg = _friendly_error(RuntimeError("Missing XAI_API_KEY. Copy .env.example"))
    assert "XAI_API_KEY" in msg
    assert "getting-started" in msg.lower() or ".env" in msg


def test_friendly_error_redacts_key_shaped_text():
    msg = _friendly_error(RuntimeError("upstream said sk-abc123secret in body"))
    assert "sk-abc" not in msg
    assert "redacted" in msg.lower() or "secret-like" in msg.lower()


def test_display_topic_truncates():
    long = "a" * 200
    shown = _display_topic(long, limit=50)
    assert len(shown) == 50
    assert shown.endswith("…")


def test_settings_trusted_xai_host():
    s = Settings(XAI_BASE_URL="https://api.x.ai/v1")
    assert s.uses_trusted_xai_host() is True
    s2 = Settings(XAI_BASE_URL="https://evil.example/v1")
    assert s2.uses_trusted_xai_host() is False


def test_cli_version_and_engine_meta(capsys):
    code = main(["--dry-run", "--json-only", "-n", "1", "version topic"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["meta"]["engine_version"] == __version__
    assert __version__ == "0.3.0"


def test_cli_rejects_n_out_of_range():
    # argparse choices should reject before workflow (exits process)
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--json-only", "-n", "9", "bad n"])
    assert exc.value.code == 2
