"""add file titles and descriptions

Revision ID: 0004_file_meta
Revises: 0003_user_display_name
Create Date: 2026-03-25 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_file_meta"
down_revision = "0003_user_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("files", sa.Column("title", sa.String(length=120), nullable=True))
    op.add_column("files", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE files SET title = filename WHERE title IS NULL")
    op.alter_column("files", "title", existing_type=sa.String(length=120), nullable=False)


def downgrade() -> None:
    op.drop_column("files", "description")
    op.drop_column("files", "title")
