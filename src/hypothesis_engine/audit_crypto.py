"""Optional Fernet helpers for audit-log topic encryption.

Requires the optional dependency::

    pip install 'dagztagz-hypothesis-engine[audit]'
"""

from __future__ import annotations

import base64
import hashlib


def fernet_from_secret(secret: str):
    """Build a Fernet instance from a passphrase or raw Fernet key string."""
    from cryptography.fernet import Fernet

    secret = secret.strip()
    if not secret:
        raise ValueError("empty audit encryption secret")

    # Prefer treating the value as a ready-made Fernet key when it decodes to 32 bytes.
    try:
        raw = base64.urlsafe_b64decode(secret)
        if len(raw) == 32:
            return Fernet(secret.encode("ascii") if isinstance(secret, str) else secret)
    except Exception:  # noqa: BLE001 — derive from passphrase instead
        pass

    try:
        return Fernet(secret.encode("ascii"))
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        return Fernet(derived)


def encrypt_topic(topic: str, secret: str) -> str:
    token = fernet_from_secret(secret).encrypt(topic.encode("utf-8"))
    return token.decode("ascii")


def decrypt_topic(token: str, secret: str) -> str:
    plain = fernet_from_secret(secret).decrypt(token.encode("ascii"))
    return plain.decode("utf-8")
