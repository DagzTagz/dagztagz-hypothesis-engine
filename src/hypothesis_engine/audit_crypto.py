"""Optional Fernet helpers for audit-log topic encryption.

Requires the optional dependency::

    pip install 'dagztagz-hypothesis-engine[audit]'

New ciphertexts (0.3.2+) stretch the passphrase with salted PBKDF2-HMAC-SHA256.
Tokens written by 0.3.1 and earlier still decrypt through the old derivation.
"""

from __future__ import annotations

import base64
import hashlib
import os

# OWASP recommendation for PBKDF2-HMAC-SHA256 (2023). One count only, so a
# crafted local token cannot ask the decrypt path for a huge iteration loop.
_PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16
_TOKEN_PREFIX = "v2:"


def fernet_from_secret(secret: str):
    """Legacy key derivation (0.3.1 and earlier).

    Kept so audit logs written before 0.3.2 still decrypt. New ciphertexts
    go through :func:`encrypt_topic`.
    """
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


def _fernet_from_passphrase(secret: str, salt: bytes):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
    return Fernet(key)


def encrypt_topic(topic: str, secret: str) -> str:
    """Encrypt ``topic``. Token format: ``v2:<iterations>:<salt_b64>:<fernet>``."""
    secret = secret.strip()
    if not secret:
        raise ValueError("empty audit encryption secret")
    salt = os.urandom(_SALT_BYTES)
    token = _fernet_from_passphrase(secret, salt).encrypt(topic.encode("utf-8"))
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    return f"{_TOKEN_PREFIX}{_PBKDF2_ITERATIONS}:{salt_b64}:{token.decode('ascii')}"


def decrypt_topic(token: str, secret: str) -> str:
    """Decrypt a v2 token, or a legacy Fernet token from 0.3.1 and earlier."""
    secret = secret.strip()
    token = token.strip()
    if token.startswith(_TOKEN_PREFIX):
        return _decrypt_v2(token, secret)
    plain = fernet_from_secret(secret).decrypt(token.encode("ascii"))
    return plain.decode("utf-8")


def _decrypt_v2(token: str, secret: str) -> str:
    rest = token[len(_TOKEN_PREFIX) :]
    try:
        iterations_s, salt_b64, fernet_token = rest.split(":", 2)
        iterations = int(iterations_s)
        # urlsafe_b64decode() has no validate flag; b64decode does.
        salt = base64.b64decode(salt_b64.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("audit token is not a valid v2 ciphertext") from exc
    if iterations != _PBKDF2_ITERATIONS or len(salt) != _SALT_BYTES:
        raise ValueError("unsupported audit KDF parameters")
    plain = _fernet_from_passphrase(secret, salt).decrypt(fernet_token.encode("ascii"))
    return plain.decode("utf-8")
