"""add saved files

Revision ID: 0011_saved_files
Revises: 0010_seed_popular_wargames
Create Date: 2026-03-26 22:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_saved_files"
down_revision = "0010_seed_popular_wargames"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "file_id", name="uq_user_saved_file_once"),
    )
    op.create_index("ix_saved_files_user_id", "saved_files", ["user_id"])
    op.create_index("ix_saved_files_file_id", "saved_files", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_files_file_id", table_name="saved_files")
    op.drop_index("ix_saved_files_user_id", table_name="saved_files")
    op.drop_table("saved_files")
