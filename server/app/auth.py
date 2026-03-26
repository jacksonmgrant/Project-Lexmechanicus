from __future__ import annotations
import time

import jwt
from passlib.hash import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .config import settings


security = HTTPBearer(auto_error=False)


async def create_user(db, email: str, password: str):
    normalized_email = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.")
    u = User(email=normalized_email, password_hash=bcrypt.hash(password))
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def verify_password(password: str, password_hash: str):
    return bcrypt.verify(password, password_hash)


def hash_password(password: str):
    return bcrypt.hash(password)


async def authenticate_user(db, email: str, password: str):
    normalized_email = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


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
