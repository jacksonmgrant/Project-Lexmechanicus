from __future__ import annotations

from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError

from ..auth import authenticate_user, create_user, encode_jwt, get_current_user, get_optional_user, hash_password, verify_password
from ..db import SessionLocal
from ..errors import raise_api_error
from ..models import User
from ..services.bundles import get_active_bundle_for_ruleset, get_bundle_file_count, get_saved_bundle_ids, serialize_bundle
from ..services.rulesets import get_active_ruleset, serialize_ruleset
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


class SignupRequest(AuthRequest):
    display_name: str = Field(min_length=1, max_length=120)

    @validator("display_name")
    def validate_display_name(cls, value: str):
        normalized = value.strip()
        if not normalized:
            raise ValueError("Enter a display name.")
        return normalized


class PasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)

    @validator("display_name", pre=True, always=True)
    def validate_display_name(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(str(value).strip().split())
        return normalized or None


def serialize_user(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def _build_session_payload(request: Request, user: User | None):
    try:
        async with SessionLocal() as db:
            active_game_system, available_game_systems = await get_active_ruleset(db, user_id=user.id if user else None)
            active_bundle = await get_active_bundle_for_ruleset(
                db,
                user_id=user.id if user else None,
                ruleset_id=active_game_system.id if active_game_system else None,
            )
            if user is not None:
                await db.commit()
            serialized_game_systems = [serialize_ruleset(tag) for tag in available_game_systems]

            serialized_active_bundle = None
            if active_bundle is not None:
                saved_bundle_ids = await get_saved_bundle_ids(
                    db,
                    user_id=user.id if user else None,
                    bundle_ids=[active_bundle.id],
                )
                file_count = await get_bundle_file_count(db, bundle_id=active_bundle.id)
                serialized_active_bundle = serialize_bundle(
                    active_bundle,
                    ruleset=active_game_system,
                    owner=user if user and active_bundle.owner_id == user.id else await db.get(User, active_bundle.owner_id),
                    file_count=file_count,
                    is_saved=active_bundle.id in saved_bundle_ids,
                    is_default=True,
                )

            payload = {
                "authenticated": user is not None,
                "user": serialize_user(user) if user else None,
                "active_game_system": serialize_ruleset(active_game_system),
                "available_game_systems": [tag for tag in serialized_game_systems if tag is not None],
                "active_bundle": serialized_active_bundle,
            }
    except SQLAlchemyError:
        raise_api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Your session could not be loaded right now.",
            "SESSION_LOAD_FAILED",
        )

    if user is None:
        guest_key = resolve_guest_key(request)
        payload["free_usage"] = await guest_usage.get_status(guest_key)
    return payload


@router.post("/signup")
async def signup(body: SignupRequest):
    async with SessionLocal() as db:
        user = await create_user(db, body.email, body.password, body.display_name)
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
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password.",
            "INVALID_CREDENTIALS",
        )
    return {
        "access_token": encode_jwt(user.id),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.get("/me")
async def me(request: Request, user=Depends(get_optional_user)):
    return await _build_session_payload(request, user)


@router.put("/profile")
async def update_profile(body: ProfileUpdateRequest, user=Depends(get_current_user)):
    async with SessionLocal() as db:
        try:
            db_user = await db.get(User, user.id)
            if db_user is None:
                raise_api_error(
                    status.HTTP_404_NOT_FOUND,
                    "User account not found.",
                    "USER_NOT_FOUND",
                )
            db_user.display_name = body.display_name
            await db.commit()
            await db.refresh(db_user)
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Your profile could not be updated right now.",
                "PROFILE_UPDATE_FAILED",
            )
    return {"user": serialize_user(db_user)}


@router.post("/password")
async def update_password(body: PasswordUpdateRequest, user=Depends(get_current_user)):
    if body.current_password == body.new_password:
        raise_api_error(status.HTTP_400_BAD_REQUEST, "Choose a new password.", "PASSWORD_REUSE")
    async with SessionLocal() as db:
        try:
            db_user = await db.get(User, user.id)
            if not db_user or not verify_password(body.current_password, db_user.password_hash):
                raise_api_error(
                    status.HTTP_401_UNAUTHORIZED,
                    "Your current password was incorrect.",
                    "CURRENT_PASSWORD_INCORRECT",
                )
            db_user.password_hash = hash_password(body.new_password)
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise_api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Your password could not be updated right now.",
                "PASSWORD_UPDATE_FAILED",
            )
    return {"status": "ok"}
