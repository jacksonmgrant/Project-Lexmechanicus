"""expand dmca workflows and repeat infringer policy

Revision ID: 0015_dmca_hardening
Revises: 0014_file_created_at
Create Date: 2026-03-27 23:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_dmca_hardening"
down_revision = "0014_file_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("dmca_strike_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("dmca_suspended_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("dmca_suspension_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_users_dmca_suspended_at", "users", ["dmca_suspended_at"])

    op.add_column(
        "copyright_takedown_requests",
        sa.Column("claimant_phone", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("claimant_address", sa.Text(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("material_location", sa.Text(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("claimant_signature", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("good_faith_statement_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("accuracy_statement_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("authority_statement_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("uploader_notified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("strike_applied_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_claimant_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_claimant_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_claimant_phone", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_claimant_address", sa.Text(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_signature", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_mistake_statement_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_perjury_statement_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_jurisdiction_statement_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_submitted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_reviewed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_reviewed_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("counter_review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("claimant_notified_of_counter_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("restore_after_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("restore_deadline_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("restored_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "copyright_takedown_requests",
        sa.Column("lawsuit_notice_received_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_copyright_takedown_requests_restore_after_at",
        "copyright_takedown_requests",
        ["restore_after_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_copyright_takedown_requests_restore_after_at", table_name="copyright_takedown_requests")
    op.drop_column("copyright_takedown_requests", "lawsuit_notice_received_at")
    op.drop_column("copyright_takedown_requests", "restored_at")
    op.drop_column("copyright_takedown_requests", "restore_deadline_at")
    op.drop_column("copyright_takedown_requests", "restore_after_at")
    op.drop_column("copyright_takedown_requests", "claimant_notified_of_counter_at")
    op.drop_column("copyright_takedown_requests", "counter_review_notes")
    op.drop_column("copyright_takedown_requests", "counter_reviewed_by")
    op.drop_column("copyright_takedown_requests", "counter_reviewed_at")
    op.drop_column("copyright_takedown_requests", "counter_submitted_at")
    op.drop_column("copyright_takedown_requests", "counter_jurisdiction_statement_confirmed")
    op.drop_column("copyright_takedown_requests", "counter_perjury_statement_confirmed")
    op.drop_column("copyright_takedown_requests", "counter_mistake_statement_confirmed")
    op.drop_column("copyright_takedown_requests", "counter_signature")
    op.drop_column("copyright_takedown_requests", "counter_explanation")
    op.drop_column("copyright_takedown_requests", "counter_claimant_address")
    op.drop_column("copyright_takedown_requests", "counter_claimant_phone")
    op.drop_column("copyright_takedown_requests", "counter_claimant_email")
    op.drop_column("copyright_takedown_requests", "counter_claimant_name")
    op.drop_column("copyright_takedown_requests", "strike_applied_at")
    op.drop_column("copyright_takedown_requests", "uploader_notified_at")
    op.drop_column("copyright_takedown_requests", "disabled_at")
    op.drop_column("copyright_takedown_requests", "authority_statement_confirmed")
    op.drop_column("copyright_takedown_requests", "accuracy_statement_confirmed")
    op.drop_column("copyright_takedown_requests", "good_faith_statement_confirmed")
    op.drop_column("copyright_takedown_requests", "claimant_signature")
    op.drop_column("copyright_takedown_requests", "material_location")
    op.drop_column("copyright_takedown_requests", "claimant_address")
    op.drop_column("copyright_takedown_requests", "claimant_phone")

    op.drop_index("ix_users_dmca_suspended_at", table_name="users")
    op.drop_column("users", "dmca_suspension_reason")
    op.drop_column("users", "dmca_suspended_at")
    op.drop_column("users", "dmca_strike_count")
