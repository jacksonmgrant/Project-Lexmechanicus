"""add created_at to files

Revision ID: 0014_file_created_at
Revises: 0013_copyright_takedowns
Create Date: 2026-03-27 21:25:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_file_created_at"
down_revision = "0013_copyright_takedowns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("files")}
    if "created_at" not in existing_columns:
        op.add_column(
            "files",
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("files")}
    if "created_at" in existing_columns:
        op.drop_column("files", "created_at")
