"""add bundles

Revision ID: 0012_bundles
Revises: 0011_saved_files
Create Date: 2026-03-27 10:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_bundles"
down_revision = "0011_saved_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bundles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ruleset_id", sa.Integer(), sa.ForeignKey("rulesets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("owner_id", "ruleset_id", "title", name="uq_owner_ruleset_bundle_title"),
    )
    op.create_index("ix_bundles_owner_id", "bundles", ["owner_id"])
    op.create_index("ix_bundles_ruleset_id", "bundles", ["ruleset_id"])
    op.create_index("ix_bundles_is_public", "bundles", ["is_public"])

    op.create_table(
        "bundle_files",
        sa.Column("bundle_id", sa.Integer(), sa.ForeignKey("bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("bundle_id", "file_id"),
    )
    op.create_index("ix_bundle_files_file_id", "bundle_files", ["file_id"])

    op.create_table(
        "saved_bundles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bundle_id", sa.Integer(), sa.ForeignKey("bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "bundle_id", name="uq_user_saved_bundle_once"),
    )
    op.create_index("ix_saved_bundles_user_id", "saved_bundles", ["user_id"])
    op.create_index("ix_saved_bundles_bundle_id", "saved_bundles", ["bundle_id"])

    op.create_table(
        "user_ruleset_bundles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ruleset_id", sa.Integer(), sa.ForeignKey("rulesets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bundle_id", sa.Integer(), sa.ForeignKey("bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "ruleset_id", name="uq_user_ruleset_bundle_once"),
    )
    op.create_index("ix_user_ruleset_bundles_bundle_id", "user_ruleset_bundles", ["bundle_id"])


def downgrade() -> None:
    op.drop_index("ix_user_ruleset_bundles_bundle_id", table_name="user_ruleset_bundles")
    op.drop_table("user_ruleset_bundles")

    op.drop_index("ix_saved_bundles_bundle_id", table_name="saved_bundles")
    op.drop_index("ix_saved_bundles_user_id", table_name="saved_bundles")
    op.drop_table("saved_bundles")

    op.drop_index("ix_bundle_files_file_id", table_name="bundle_files")
    op.drop_table("bundle_files")

    op.drop_index("ix_bundles_is_public", table_name="bundles")
    op.drop_index("ix_bundles_ruleset_id", table_name="bundles")
    op.drop_index("ix_bundles_owner_id", table_name="bundles")
    op.drop_table("bundles")
