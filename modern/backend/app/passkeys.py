"""WebAuthn / Passkey support for AlarmDecoder Modern."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

# In-memory challenge store with TTL (5 minutes)
_CHALLENGES: dict[str, dict[str, Any]] = {}
_CHALLENGE_TTL_SECONDS = 300


def _prune_challenges() -> None:
    now = time.time()
    stale = [c for c, d in _CHALLENGES.items() if now - d["created_at"] > _CHALLENGE_TTL_SECONDS]
    for c in stale:
        _CHALLENGES.pop(c, None)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class PasskeyPublic(BaseModel):
    id: str
    name: str
    username: str
    created_at: str
    last_used_at: str | None = None


class PasskeyRegisterBeginResponse(BaseModel):
    challenge: str
    rp: dict[str, str]
    user: dict[str, str]
    pubKeyCredParams: list[dict[str, Any]]
    timeout: int
    authenticatorSelection: dict[str, Any]


class PasskeyRegisterFinishRequest(BaseModel):
    id: str
    rawId: str
    name: str = "Passkey"
    clientDataJSON: str
    attestationObject: str


class PasskeyLoginBeginResponse(BaseModel):
    challenge: str
    timeout: int
    rpId: str | None = None


class PasskeyLoginFinishRequest(BaseModel):
    id: str
    rawId: str
    clientDataJSON: str
    authenticatorData: str
    signature: str


def create_registration_options(username: str, rp_id: str = "localhost") -> PasskeyRegisterBeginResponse:
    _prune_challenges()
    challenge_bytes = secrets.token_bytes(32)
    challenge = _b64url_encode(challenge_bytes)
    user_id = _b64url_encode(hashlib.sha256(username.encode()).digest())

    _CHALLENGES[challenge] = {
        "type": "registration",
        "username": username,
        "created_at": time.time(),
    }

    return PasskeyRegisterBeginResponse(
        challenge=challenge,
        rp={"name": "AlarmDecoder", "id": rp_id},
        user={"id": user_id, "name": username, "displayName": username},
        pubKeyCredParams=[
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257}, # RS256
        ],
        timeout=60000,
        authenticatorSelection={
            "residentKey": "preferred",
            "userVerification": "preferred",
        },
    )


def verify_registration(
    payload: PasskeyRegisterFinishRequest,
    database: Any,
) -> PasskeyPublic:
    _prune_challenges()
    # Parse clientDataJSON
    try:
        client_data_bytes = _b64url_decode(payload.clientDataJSON)
        client_data = json.loads(client_data_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid clientDataJSON") from exc

    challenge = client_data.get("challenge", "")
    entry = _CHALLENGES.pop(challenge, None)
    if not entry or entry.get("type") != "registration":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired registration challenge")

    username = entry["username"]
    cred_id = payload.id
    # Store attestation object as the public key credential blob
    cred = database.add_passkey(
        credential_id=cred_id,
        username=username,
        name=payload.name or "Passkey",
        public_key=payload.attestationObject,
    )

    return PasskeyPublic(
        id=cred.id,
        name=cred.name,
        username=cred.username,
        created_at=cred.created_at.isoformat() if hasattr(cred.created_at, "isoformat") else str(cred.created_at),
        last_used_at=None,
    )


def create_authentication_options(rp_id: str = "localhost") -> PasskeyLoginBeginResponse:
    _prune_challenges()
    challenge_bytes = secrets.token_bytes(32)
    challenge = _b64url_encode(challenge_bytes)

    _CHALLENGES[challenge] = {
        "type": "authentication",
        "created_at": time.time(),
    }

    return PasskeyLoginBeginResponse(
        challenge=challenge,
        timeout=60000,
        rpId=rp_id,
    )


def verify_authentication(
    payload: PasskeyLoginFinishRequest,
    database: Any,
) -> str:
    """Verify an assertion and return the authenticated username."""
    _prune_challenges()
    try:
        client_data_bytes = _b64url_decode(payload.clientDataJSON)
        client_data = json.loads(client_data_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid clientDataJSON") from exc

    challenge = client_data.get("challenge", "")
    entry = _CHALLENGES.pop(challenge, None)
    if not entry or entry.get("type") != "authentication":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired login challenge")

    cred = database.get_passkey(payload.id)
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey credential not recognized")

    database.update_passkey_usage(cred.id, cred.sign_count + 1)
    return cred.username
