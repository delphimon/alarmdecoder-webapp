"""Symmetric encryption utilities for sensitive settings (panel PIN, secrets)."""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO = b"alarmdecoder-modern-settings-key"
_HKDF_SALT = b"alarmdecoder-modern-v1"


def derive_fernet_key(session_secret: str) -> bytes:
    """Derive a 32-byte Fernet-compatible key from SESSION_SECRET using HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    raw = hkdf.derive(session_secret.encode())
    return base64.urlsafe_b64encode(raw)


def encrypt_value(plaintext: str, session_secret: str) -> str:
    """Encrypt a string value. Returns a Fernet token (URL-safe base64 string)."""
    key = derive_fernet_key(session_secret)
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(token: str, session_secret: str) -> str:
    """Decrypt a value encrypted with encrypt_value. Raises ValueError on failure."""
    try:
        key = derive_fernet_key(session_secret)
        f = Fernet(key)
        return f.decrypt(token.encode()).decode()
    except Exception as exc:
        raise ValueError("Failed to decrypt value — SESSION_SECRET may have changed") from exc
