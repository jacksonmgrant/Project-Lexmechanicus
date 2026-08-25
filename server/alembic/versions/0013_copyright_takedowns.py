"""add copyright takedowns

Revision ID: 0013_copyright_takedowns
Revises: 0012_bundles
Create Date: 2026-03-27 14:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_copyright_takedowns"
down_revision = "0012_bundles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("is_copyright_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "files",
        sa.Column("copyright_restricted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_files_is_copyright_restricted", "files", ["is_copyright_restricted"])

    op.create_table(
        "copyright_takedown_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("claimant_name", sa.String(length=120), nullable=False),
        sa.Column("claimant_email", sa.String(length=255), nullable=False),
        sa.Column("copyright_owner_name", sa.String(length=160), nullable=True),
        sa.Column("work_description", sa.Text(), nullable=False),
        sa.Column("infringement_explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_copyright_takedown_requests_file_id", "copyright_takedown_requests", ["file_id"])
    op.create_index("ix_copyright_takedown_requests_status", "copyright_takedown_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_copyright_takedown_requests_status", table_name="copyright_takedown_requests")
    op.drop_index("ix_copyright_takedown_requests_file_id", table_name="copyright_takedown_requests")
    op.drop_table("copyright_takedown_requests")

    op.drop_index("ix_files_is_copyright_restricted", table_name="files")
    op.drop_column("files", "copyright_restricted_at")
    op.drop_column("files", "is_copyright_restricted")
