from __future__ import annotations
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active_game_system_tag_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id", ondelete="SET NULL"), nullable=True)
    active_ruleset_id: Mapped[int | None] = mapped_column(ForeignKey("rulesets.id", ondelete="SET NULL"), nullable=True)
    dmca_strike_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    dmca_suspended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dmca_suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GameSystem(Base):
    __tablename__ = "game_systems"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    game_system_id: Mapped[int] = mapped_column(ForeignKey("game_systems.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))


class File(Base):
    __tablename__ = "files"
    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"))
    game_system_tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"))
    ruleset_id: Mapped[int | None] = mapped_column(ForeignKey("rulesets.id", ondelete="RESTRICT"), nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int]
    s3_key: Mapped[str] = mapped_column(String(512))
    is_public: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_copyright_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    copyright_restricted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    openai_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    openai_vector_store_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    openai_vector_store_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    openai_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Ruleset(Base):
    __tablename__ = "rulesets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("rulesets.id", ondelete="SET NULL"), nullable=True)
    edition_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RulesetAlias(Base):
    __tablename__ = "ruleset_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    ruleset_id: Mapped[int] = mapped_column(ForeignKey("rulesets.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FileTag(Base):
    __tablename__ = "file_tags"
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FileChunk(Base):
    __tablename__ = "file_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    start_byte: Mapped[int]
    end_byte: Mapped[int]
    title: Mapped[str | None]
    section: Mapped[str | None]
    snippet: Mapped[str]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)


class MarketplacePack(Base):
    __tablename__ = "marketplace_packs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    game_system_id: Mapped[int] = mapped_column(ForeignKey("game_systems.id", ondelete="CASCADE"))
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavedPack(Base):
    __tablename__ = "saved_packs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    marketplace_pack_id: Mapped[int] = mapped_column(ForeignKey("marketplace_packs.id", ondelete="CASCADE"))


class SavedFile(Base):
    __tablename__ = "saved_files"
    __table_args__ = (
        UniqueConstraint("user_id", "file_id", name="uq_user_saved_file_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Bundle(Base):
    __tablename__ = "bundles"
    __table_args__ = (
        UniqueConstraint("owner_id", "ruleset_id", "title", name="uq_owner_ruleset_bundle_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ruleset_id: Mapped[int] = mapped_column(ForeignKey("rulesets.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BundleFile(Base):
    __tablename__ = "bundle_files"
    bundle_id: Mapped[int] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SavedBundle(Base):
    __tablename__ = "saved_bundles"
    __table_args__ = (
        UniqueConstraint("user_id", "bundle_id", name="uq_user_saved_bundle_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    bundle_id: Mapped[int] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserRulesetBundle(Base):
    __tablename__ = "user_ruleset_bundles"
    __table_args__ = (
        UniqueConstraint("user_id", "ruleset_id", name="uq_user_ruleset_bundle_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ruleset_id: Mapped[int] = mapped_column(ForeignKey("rulesets.id", ondelete="CASCADE"))
    bundle_id: Mapped[int] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CopyrightTakedownRequest(Base):
    __tablename__ = "copyright_takedown_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    claimant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    claimant_email: Mapped[str] = mapped_column(String(255), nullable=False)
    claimant_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    claimant_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    copyright_owner_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    work_description: Mapped[str] = mapped_column(Text, nullable=False)
    material_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    infringement_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    claimant_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    good_faith_statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    accuracy_statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    authority_statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploader_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    strike_applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    counter_claimant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    counter_claimant_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counter_claimant_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    counter_claimant_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    counter_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    counter_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counter_mistake_statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    counter_perjury_statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    counter_jurisdiction_statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    counter_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    counter_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    counter_reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counter_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimant_notified_of_counter_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    restore_after_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    restore_deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lawsuit_notice_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
