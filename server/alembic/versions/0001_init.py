from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0001_init"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "game_systems",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
    )

    op.create_table(
        "folders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_system_id", sa.Integer, sa.ForeignKey("game_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "game_system_id", "name", name="uq_folder_name"),
    )

    op.create_table(
        "files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("folder_id", sa.Integer, sa.ForeignKey("folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("is_public", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "file_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("file_id", sa.Integer, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_byte", sa.Integer, nullable=False),
        sa.Column("end_byte", sa.Integer, nullable=False),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("section", sa.String(300), nullable=True),
        sa.Column("snippet", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1024)),
        sa.Index("ix_file_chunks_file_id", "file_id"),
    )

    op.create_table(
        "marketplace_packs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_system_id", sa.Integer, sa.ForeignKey("game_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("folder_id", sa.Integer, sa.ForeignKey("folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("saves", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("folder_id", name="uq_market_folder_once"),
    )

    op.create_table(
        "saved_packs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("marketplace_pack_id", sa.Integer, sa.ForeignKey("marketplace_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "marketplace_pack_id", name="uq_user_saved_once"),
    )

    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_chunk_id", sa.Integer, sa.ForeignKey("file_chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "file_chunk_id", name="uq_fav_once"),
    )

    op.create_table(
        "queries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("game_system_id", sa.Integer, sa.ForeignKey("game_systems.id", ondelete="SET NULL")),
        sa.Column("q", sa.Text, nullable=False),
        sa.Column("used_tokens_in", sa.Integer, server_default="0"),
        sa.Column("used_tokens_out", sa.Integer, server_default="0"),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("auto_escalated", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade():
    for t in ("queries", "favorites", "saved_packs", "marketplace_packs", "file_chunks", "files", "folders", "game_systems", "users"):
        op.drop_table(t)
