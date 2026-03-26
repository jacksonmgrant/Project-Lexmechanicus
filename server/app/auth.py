from __future__ import annotations
import base64
import hashlib
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .config import settings


security = HTTPBearer(auto_error=False)
PASSWORD_HASH_PREFIX = "bcrypt_sha256$"


async def create_user(db, email: str, password: str, display_name: str | None = None):
    normalized_email = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.")
    normalized_display_name = display_name.strip() if display_name else None
    u = User(email=normalized_email, display_name=normalized_display_name or None, password_hash=hash_password(password))
    db.add(u)
    await db.commit()
    await db.refresh(u)
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
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(password, user.password_hash):
        return None
    if not user.password_hash.startswith(PASSWORD_HASH_PREFIX):
        user.password_hash = hash_password(password)
        await db.commit()
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid or has expired.",
        )
    async with SessionLocal() as db:
        u = await db.get(User, int(payload["sub"]))
        if not u:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found.")
        return u


async def get_current_user(user=Depends(get_optional_user)):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Create an account or sign in to use this feature.",
        )
    return user
