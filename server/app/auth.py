from __future__ import annotations
import base64
import hashlib
import time

import bcrypt
import jwt
from fastapi import Depends, status
from fastapi.security import HTTPBearer
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select
from .db import SessionLocal
from .errors import raise_api_error
from .models import User
from .config import settings


security = HTTPBearer(auto_error=False)
PASSWORD_HASH_PREFIX = "bcrypt_sha256$"


async def create_user(db, email: str, password: str, display_name: str | None = None):
    normalized_email = email.strip().lower()
    try:
        existing = await db.scalar(select(User).where(User.email == normalized_email))
    except SQLAlchemyError:
        await db.rollback()
        raise_api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "The account service is temporarily unavailable.", "ACCOUNT_LOOKUP_FAILED")
    if existing:
        raise_api_error(status.HTTP_409_CONFLICT, "An account with that email already exists.", "EMAIL_ALREADY_REGISTERED")
    normalized_display_name = display_name.strip() if display_name else None
    u = User(email=normalized_email, display_name=normalized_display_name or None, password_hash=hash_password(password))
    try:
        db.add(u)
        await db.commit()
        await db.refresh(u)
    except IntegrityError:
        await db.rollback()
        raise_api_error(status.HTTP_409_CONFLICT, "An account with that email already exists.", "EMAIL_ALREADY_REGISTERED")
    except SQLAlchemyError:
        await db.rollback()
        raise_api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "The account could not be created right now.", "ACCOUNT_CREATE_FAILED")
    return u


def verify_password(password: str, password_hash: str):
    password_bytes = password.encode("utf-8")
    try:
        if password_hash.startswith(PASSWORD_HASH_PREFIX):
            return bcrypt.checkpw(_prehash_password(password_bytes), password_hash.removeprefix(PASSWORD_HASH_PREFIX).encode("utf-8"))
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_password(password: str):
    hashed = bcrypt.hashpw(_prehash_password(password.encode("utf-8")), bcrypt.gensalt())
    return f"{PASSWORD_HASH_PREFIX}{hashed.decode('utf-8')}"


async def authenticate_user(db, email: str, password: str):
    normalized_email = email.strip().lower()
    try:
        user = await db.scalar(select(User).where(User.email == normalized_email))
    except SQLAlchemyError:
        await db.rollback()
        raise_api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "The sign-in service is temporarily unavailable.", "AUTH_LOOKUP_FAILED")
    if not user or not verify_password(password, user.password_hash):
        return None
    if not user.password_hash.startswith(PASSWORD_HASH_PREFIX):
        user.password_hash = hash_password(password)
        try:
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
    return user


def _prehash_password(password: bytes) -> bytes:
    digest = hashlib.sha256(password).digest()
    return base64.b64encode(digest)


def encode_jwt(user_id: int):
    payload = {"sub": str(user_id), "exp": int(time.time()) + settings.ACCESS_TOKEN_TTL_HOURS * 3600}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


async def get_optional_user(token=Depends(security)):
    if token is None or not token.credentials:
        return None
    try:
        payload = jwt.decode(token.credentials, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            "Your session is invalid or has expired.",
            "SESSION_INVALID",
        )
    async with SessionLocal() as db:
        try:
            u = await db.get(User, user_id)
        except SQLAlchemyError:
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The authentication service is temporarily unavailable.",
                "AUTH_SERVICE_UNAVAILABLE",
            )
        if not u:
            raise_api_error(status.HTTP_401_UNAUTHORIZED, "User account not found.", "USER_NOT_FOUND")
        return u


async def get_current_user(user=Depends(get_optional_user)):
    if user is None:
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            "Create an account or sign in to use this feature.",
            "AUTH_REQUIRED",
        )
    return user
