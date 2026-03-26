from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
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
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int]
    s3_key: Mapped[str] = mapped_column(String(512))
    is_public: Mapped[bool]
    openai_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    openai_vector_store_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    openai_vector_store_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    openai_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class FileChunk(Base):
    __tablename__ = "file_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    start_byte: Mapped[int]
    end_byte: Mapped[int]
    title: Mapped[str | None]
    section: Mapped[str | None]
    snippet: Mapped[str]
    # embedding column created via migration
