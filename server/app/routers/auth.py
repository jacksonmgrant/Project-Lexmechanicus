from __future__ import annotations

from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import authenticate_user, create_user, encode_jwt, get_current_user, get_optional_user, hash_password, verify_password
from ..db import SessionLocal
from ..models import User
from ..usage import AnonymousUsageGate, resolve_guest_key


router = APIRouter(prefix="/auth", tags=["auth"])
guest_usage = AnonymousUsageGate()


class AuthRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)

    @validator("email")
    def validate_email(cls, value: str):
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return normalized


class PasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


def serialize_user(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def _build_session_payload(request: Request, user: User | None):
    payload = {
        "authenticated": user is not None,
        "user": serialize_user(user) if user else None,
    }
    if user is None:
        guest_key = resolve_guest_key(request)
        payload["free_usage"] = await guest_usage.get_status(guest_key)
    return payload


@router.post("/signup")
async def signup(body: AuthRequest):
    async with SessionLocal() as db:
        user = await create_user(db, body.email, body.password)
    return {
        "access_token": encode_jwt(user.id),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.post("/login")
async def login(body: AuthRequest):
    async with SessionLocal() as db:
        user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    return {
        "access_token": encode_jwt(user.id),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.get("/me")
async def me(request: Request, user=Depends(get_optional_user)):
    return await _build_session_payload(request, user)


@router.post("/password")
async def update_password(body: PasswordUpdateRequest, user=Depends(get_current_user)):
    if body.current_password == body.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a new password.")
    async with SessionLocal() as db:
        db_user = await db.get(User, user.id)
        if not db_user or not verify_password(body.current_password, db_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your current password was incorrect.",
            )
        db_user.password_hash = hash_password(body.new_password)
        await db.commit()
    return {"status": "ok"}
