"""add user display name

Revision ID: 0003_user_display_name
Revises: 0002_openai_vector_store_sync
Create Date: 2026-03-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_user_display_name"
down_revision = "0002_openai_vector_store_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
