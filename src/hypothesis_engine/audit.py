"""Audit-log helpers: protect topic strings (hash + optional encryption)."""

from __future__ import annotations

import hashlib
import os
from typing import Any


class AuditEncryptionUnavailable(RuntimeError):
    """AUDIT_LOG_KEY is set but the optional cryptography extra is not installed."""


_INSTALL_HINT = (
    "AUDIT_LOG_KEY is set, but encryption support is not installed. "
    "Install it with:  pip install 'dagztagz-hypothesis-engine[audit]'  "
    "(or for a local checkout:  pip install -e '.[audit]'  /  pip install -e '.[dev]'). "
    "Alternatively, unset AUDIT_LOG_KEY to use hash-only audit topics, "
    "or pass --audit-include-topic for explicit plaintext (less private)."
)


def topic_sha256(topic: str) -> str:
    return hashlib.sha256(topic.encode("utf-8")).hexdigest()


def _load_crypto():
    try:
        from hypothesis_engine import audit_crypto

        return audit_crypto
    except ImportError as exc:
        # Missing cryptography (or broken install of the optional extra)
        raise AuditEncryptionUnavailable(_INSTALL_HINT) from exc


def encrypt_topic(topic: str, secret: str) -> str:
    return _load_crypto().encrypt_topic(topic, secret)


def decrypt_topic(token: str, secret: str) -> str:
    return _load_crypto().decrypt_topic(token, secret)


def topic_audit_fields(
    topic: str,
    *,
    include_plaintext: bool = False,
    encryption_secret: str | None = None,
) -> dict[str, Any]:
    """Fields to store for a topic in the audit log.

    Default: only ``topic_sha256`` (one-way; cannot recover the text).
    If ``encryption_secret`` / ``AUDIT_LOG_KEY`` is set: also ``topic_encrypted``
    (requires optional ``[audit]`` extra; fails hard if missing — does not silently
    fall back to hash-only while a key is configured).
    If ``include_plaintext``: also ``topic`` (explicit opt-in; least private).
    """
    fields: dict[str, Any] = {
        "topic_sha256": topic_sha256(topic),
        "topic_storage": "hash_only",
    }

    if encryption_secret is not None:
        secret = encryption_secret.strip()
    else:
        secret = os.environ.get("AUDIT_LOG_KEY", "").strip()

    if secret:
        # Fail closed if user asked for encryption but crypto extra is missing.
        fields["topic_encrypted"] = encrypt_topic(topic, secret)
        fields["topic_storage"] = "encrypted"

    if include_plaintext:
        fields["topic"] = topic
        fields["topic_storage"] = "plaintext+encrypted" if secret else "plaintext+hash"

    return fields
