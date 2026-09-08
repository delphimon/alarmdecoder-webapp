from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

import logging

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ApiTokenRecord, UserRecord
from .models import AuthStatus, UserPublic


logger = logging.getLogger("alarmdecoder.auth")
_SESSION_SECRET_MIN_LENGTH = 32

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
COOKIE_NAME = "ad2_session"
CSRF_COOKIE_NAME = "ad2_csrf"
CSRF_HEADER_NAME = "x-csrf-token"


def warn_weak_secret(secret: str) -> None:
    """Log a warning if SESSION_SECRET is shorter than the minimum required length."""
    if len(secret) < _SESSION_SECRET_MIN_LENGTH:
        logger.warning(
            "SESSION_SECRET is only %d characters; at least %d are required for adequate security. "
            "Set ALARMDECODER_SESSION_SECRET to a strong random value in production.",
            len(secret),
            _SESSION_SECRET_MIN_LENGTH,
        )



def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(username: str, role: str, secret: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": username, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)},
        secret,
        algorithm="HS256",
    )


def decode_access_token(token: str, secret: str) -> dict[str, object] | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def hash_api_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def user_public(user: UserRecord) -> UserPublic:
    return UserPublic(id=user.id, username=user.username, role=user.role, disabled=user.disabled)  # type: ignore[arg-type]


def get_user(session: Session, username: str) -> UserRecord | None:
    return session.scalar(select(UserRecord).where(UserRecord.username == username))


def create_user(session: Session, username: str, password: str, role: str) -> UserRecord:
    existing = get_user(session, username)
    if existing is not None:
        raise ValueError("User already exists")
    user = UserRecord(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, username: str, password: str) -> UserRecord | None:
    user = get_user(session, username)
    if user is None or user.disabled:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=60 * 60 * 8,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def set_csrf_cookie(response: Response) -> str:
    token = token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=False,
        secure=False,
        samesite="strict",
        max_age=60 * 60 * 8,
        path="/",
    )
    return token


def csrf_token_from_request(request: Request) -> str | None:
    return request.cookies.get(CSRF_COOKIE_NAME)


def token_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]
    return request.cookies.get(COOKIE_NAME)


def bearer_token_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]
    return None


def current_user_from_request(request: Request) -> UserRecord | None:
    runtime = request.app.state.runtime
    token = token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token, runtime.config.session_secret)
    username = str(payload.get("sub", "")) if payload else ""
    with runtime.database.session_factory() as session:
        if username:
            return get_user(session, username)

        bearer = bearer_token_from_request(request)
        if not bearer:
            return None
        token_hash = hash_api_token(bearer)
        api_token = session.scalar(select(ApiTokenRecord).where(ApiTokenRecord.token_hash == token_hash))
        if api_token is None or api_token.disabled:
            return None
        user = session.get(UserRecord, api_token.user_id)
        if user is None or user.disabled:
            return None
        api_token.last_used_at = datetime.now(timezone.utc)
        session.commit()
        user.role = api_token.role
        return user


def optional_current_user(request: Request) -> UserRecord | None:
    return current_user_from_request(request)


def require_csrf(request: Request) -> None:
    if bearer_token_from_request(request):
        return
    if COOKIE_NAME in request.cookies or CSRF_COOKIE_NAME in request.cookies:
        cookie = request.cookies.get(CSRF_COOKIE_NAME)
        header = request.headers.get(CSRF_HEADER_NAME)
        if not cookie or not header or cookie != header:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid.")



def require_current_user(user: UserRecord | None = Depends(optional_current_user)) -> UserRecord:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def require_role(*roles: str):
    def dependency(user: UserRecord = Depends(require_current_user)) -> UserRecord:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role.")
        return user

    return dependency


def auth_status(request: Request) -> AuthStatus:
    runtime = request.app.state.runtime
    user = current_user_from_request(request)
    return AuthStatus(
        authenticated=user is not None,
        auth_required=runtime.config.auth_required or runtime.database.users_exist(),
        csrf_token=csrf_token_from_request(request),
        user=user_public(user) if user else None,
    )
