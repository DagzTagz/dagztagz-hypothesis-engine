"""Topic hashing / optional encryption for audit logs."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hypothesis_engine.audit import (
    AuditEncryptionUnavailable,
    decrypt_topic,
    topic_audit_fields,
    topic_sha256,
)
from hypothesis_engine.cli import main


def test_topic_sha256_stable():
    assert topic_sha256("hello") == topic_sha256("hello")
    assert topic_sha256("hello") != topic_sha256("Hello")


def test_default_fields_are_hash_only():
    fields = topic_audit_fields("secret topic", encryption_secret="")
    assert "topic" not in fields
    assert "topic_encrypted" not in fields
    assert fields["topic_storage"] == "hash_only"
    assert fields["topic_sha256"] == topic_sha256("secret topic")


def test_encrypt_and_decrypt_roundtrip():
    fields = topic_audit_fields(
        "secret topic",
        encryption_secret="unit-test-passphrase-not-for-prod",
    )
    assert "topic" not in fields
    assert "topic_encrypted" in fields
    assert fields["topic_storage"] == "encrypted"
    plain = decrypt_topic(fields["topic_encrypted"], "unit-test-passphrase-not-for-prod")
    assert plain == "secret topic"


def test_plaintext_opt_in():
    fields = topic_audit_fields("visible", include_plaintext=True, encryption_secret="")
    assert fields["topic"] == "visible"
    assert fields["topic_storage"] == "plaintext+hash"


def test_missing_crypto_fails_closed_when_key_set():
    with patch.dict("sys.modules", {"cryptography": None, "cryptography.fernet": None}):
        # Force import failure inside audit_crypto path
        with patch(
            "hypothesis_engine.audit._load_crypto",
            side_effect=AuditEncryptionUnavailable("install hint"),
        ):
            with pytest.raises(AuditEncryptionUnavailable):
                topic_audit_fields("x", encryption_secret="some-key")


def test_cli_fails_when_key_set_but_crypto_missing(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("AUDIT_LOG_KEY", "configured-but-maybe-missing-extra")
    log = tmp_path / "a.jsonl"

    def _boom():
        raise AuditEncryptionUnavailable(
            "AUDIT_LOG_KEY is set, but encryption support is not installed. "
            "Install it with:  pip install 'dagztagz-hypothesis-engine[audit]'"
        )

    monkeypatch.setattr(
        "hypothesis_engine.audit._load_crypto",
        lambda: (_ for _ in ()).throw(
            AuditEncryptionUnavailable(
                "AUDIT_LOG_KEY is set, but encryption support is not installed. "
                "Install it with:  pip install 'dagztagz-hypothesis-engine[audit]'"
            )
        ),
    )
    code = main(
        ["--dry-run", "--json-only", "-n", "1", "--audit-log", str(log), "private topic"]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "dagztagz-hypothesis-engine[audit]" in err
    assert not log.exists() or log.read_text(encoding="utf-8").strip() == ""


def test_cli_audit_log_has_no_plaintext_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AUDIT_LOG_KEY", raising=False)
    log = tmp_path / "a.jsonl"
    code = main(
        ["--dry-run", "--json-only", "-n", "1", "--audit-log", str(log), "private topic xyz"]
    )
    assert code == 0
    for line in log.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert "topic" not in row
        assert row.get("topic_sha256")
        assert "private topic xyz" not in line


def test_cli_loads_audit_key_from_dotenv_file(tmp_path: Path, monkeypatch):
    """AUDIT_LOG_KEY in a local .env should enable encryption without export."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUDIT_LOG_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "AUDIT_LOG_KEY=dotenv-passphrase-for-unit-test\n",
        encoding="utf-8",
    )
    log = tmp_path / "a.jsonl"
    code = main(
        ["--dry-run", "--json-only", "-n", "1", "--audit-log", str(log), "dotenv topic"]
    )
    assert code == 0
    start = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert start["topic_storage"] == "encrypted"
    assert "topic_encrypted" in start
    assert "dotenv topic" not in log.read_text(encoding="utf-8")
